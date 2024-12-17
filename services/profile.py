from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4
from supabase import create_client, Client
import os
import logging
import json
from models.profile import Profile, ProfileCreate
from models.memory import MemoryCreate, Category, Memory, Location
from services.memory import MemoryService
import openai
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Service Class
class ProfileService:
    table_name = "profiles"

    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.openai_client = openai.Client(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    async def parse_backstory(self, profile_id: UUID, backstory: str, profile_data: Dict[str, Any], language: str = "de") -> None:
        """Parse memories from backstory and create initial memories in the specified language"""
        try:
            logger.info(f"Parsing backstory for profile {profile_id} in language {language}")

            # Create single session for all initial memories
            session_data = {
                "id": str(uuid4()),
                "profile_id": str(profile_id),
                "category": "initial",
                "started_at": datetime.utcnow().isoformat(),
                "emotional_state": {"initial": "neutral"},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Create session
            try:
                session_result = self.supabase.table("interview_sessions").insert(session_data).execute()
                if not session_result.data:
                    raise Exception("Failed to create interview session")
                session_id = session_result.data[0]['id']
                logger.info(f"Created interview session: {session_id}")
            except Exception as e:
                logger.error(f"Failed to create interview session: {str(e)}")
                raise

            # Use the same session_id for all memories

            # Create birth memory
            try:
                city = profile_data['place_of_birth'].split(',')[0].strip()
                country = profile_data['place_of_birth'].split(',')[-1].strip()

                birth_description = {
                    "de": f"{profile_data['first_name']} {profile_data['last_name']} wurde in {profile_data['place_of_birth']} geboren",
                    "en": f"{profile_data['first_name']} {profile_data['last_name']} was born in {profile_data['place_of_birth']}"
                }.get(language, f"{profile_data['first_name']} {profile_data['last_name']} was born in {profile_data['place_of_birth']}")

                birth_memory = MemoryCreate(
                    category=Category.CHILDHOOD,
                    description=birth_description,
                    time_period=datetime.strptime(profile_data['date_of_birth'], "%Y-%m-%d"),
                    location=Location(
                        name=profile_data['place_of_birth'],
                        city=city,
                        country=country,
                        description="Geburtsort" if language == "de" else "Place of birth"
                    )
                )

                await MemoryService.create_memory(birth_memory, profile_id, session_id)
                logger.info("Birth memory created successfully")

            except Exception as e:
                logger.error(f"Error creating birth memory: {str(e)}")

            # Parse and create additional memories using the SAME session_id
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""Extract distinct memories from the backstory and format them as a JSON object.
                            The date is a single string in the format "YYYY-MM-DD". If it is a timespan always use the start date.
                            Write all text content in {language} language.
                            For each memory in the "memories" array, provide:
                            {{
                                "description": "Full description of the memory in {language}",
                                "category": "One of: childhood/career/relationships/travel/hobbies/pets",
                                "date": "YYYY-MM-DD (approximate if not specified)",
                                "location": {{
                                    "name": "Location name",
                                    "city": "City if mentioned",
                                    "country": "Country if mentioned",
                                    "description": "Brief description of the location in {language}"
                                }}
                            }}"""
                        },
                        {
                            "role": "user",
                            "content": f"Please analyze this text and return the memories as JSON: {backstory}"
                        }
                    ],
                    response_format={ "type": "json_object" }
                )

                try:
                    parsed_memories = json.loads(response.choices[0].message.content)
                    logger.info(f"Parsed memories: {parsed_memories}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    logger.error(f"Raw response: {response.choices[0].message.content}")
                    raise Exception("Failed to parse OpenAI response")

                # Create all memories using the same session_id
                for memory_data in parsed_memories.get('memories', []):
                    try:
                        category_str = memory_data.get('category', 'childhood').upper()
                        category = getattr(Category, category_str, Category.CHILDHOOD)

                        logger.info("------------------- parsed memory -----------")
                        logger.info(category)
                        logger.info(memory_data.get('description'))
                        logger.info(memory_data.get('date'))

                        memory = MemoryCreate(
                            category=category,
                            description=memory_data['description'],
                            time_period=memory_data.get('date'),
                            location=Location(**memory_data['location']) if memory_data.get('location') else None
                        )

                        # Use the same session_id for all memories
                        await MemoryService.create_memory(memory, profile_id, session_id)
                        logger.debug(f"Created memory: {memory.description}")

                    except Exception as e:
                        logger.error(f"Error creating individual memory: {str(e)}")
                        continue

            except Exception as e:
                logger.error(f"Error parsing memories from backstory: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Error in parse_backstory: {str(e)}")
            raise Exception(f"Failed to parse backstory: {str(e)}")
            
    @classmethod
    async def get_all_profiles(cls) -> List[Profile]:
        """Get all profiles"""
        try:
            service = cls()
            
            # Direct SQL query to get profiles with their session counts
            query = """
                SELECT p.*,
                       (SELECT COUNT(*) 
                        FROM interview_sessions 
                        WHERE profile_id = p.id) as session_count
                FROM profiles p
                ORDER BY p.updated_at DESC
            """

            result = service.supabase.table('profiles').select("*").execute()
            
            profiles = []
            for profile_data in result.data:
                try:
                    # Convert date strings
                    if isinstance(profile_data['date_of_birth'], str):
                        profile_data['date_of_birth'] = datetime.fromisoformat(
                            profile_data['date_of_birth']
                        ).date()

                    if isinstance(profile_data['created_at'], str):
                        profile_data['created_at'] = datetime.fromisoformat(
                            profile_data['created_at']
                        )

                    if isinstance(profile_data['updated_at'], str):
                        profile_data['updated_at'] = datetime.fromisoformat(
                            profile_data['updated_at']
                        )
                    
                    # Initialize metadata if it doesn't exist
                    if not profile_data.get('metadata'):
                        profile_data['metadata'] = {}

                    # Add session count to metadata
                    session_count_result = service.supabase.table('interview_sessions')\
                        .select('id', count='exact')\
                        .eq('profile_id', profile_data['id'])\
                        .execute()

                    profile_data['metadata']['session_count'] = session_count_result.count
                    
                    profiles.append(Profile(**profile_data))
                except Exception as e:
                    logger.error(f"Error converting profile data: {str(e)}")
                    logger.error(f"Problematic profile data: {profile_data}")
                    continue

            return profiles

        except Exception as e:
            logger.error(f"Error fetching all profiles: {str(e)}")
            raise

    @classmethod
    async def create_profile(cls, profile_data: ProfileCreate, language: str = "en") -> Profile:
        """Creates a new profile and initializes memories from backstory"""
        try:
            service = cls()  # Create instance

            # Extract backstory from metadata if present
            backstory = None
            metadata = profile_data.metadata if hasattr(profile_data, 'metadata') else {}
            if isinstance(metadata, dict):
                backstory = metadata.get('backstory')

            # Prepare profile data for database
            data = {
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "date_of_birth": profile_data.date_of_birth.isoformat(),
                "place_of_birth": profile_data.place_of_birth,
                "gender": profile_data.gender,
                "children": profile_data.children,
                "spoken_languages": profile_data.spoken_languages,
                "profile_image_url": profile_data.profile_image_url,
                "metadata": metadata,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            # Insert profile into database
            result = service.supabase.table(service.table_name).insert(data).execute()

            if not result.data:
                raise Exception("No data returned from profile creation")

            profile_id = result.data[0]['id']
            created_profile = Profile(**result.data[0])

            # Parse backstory and create initial memories if backstory exists
            if backstory:
                await service.parse_backstory(
                    profile_id=profile_id,
                    backstory=backstory,
                    profile_data=data,
                    language=language  # Pass the language parameter
                )

            return created_profile

        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")
        raise Exception(f"Failed to create profile: {str(e)}")

    async def get_profile(self, profile_id: UUID4) -> Optional[Profile]:
        """Retrieves a profile by ID"""
        try:
            logger.debug(f"Fetching profile with ID: {profile_id}")

            # Fetch the profile from Supabase
            result = self.supabase.table(self.table_name)\
                .select("*")\
                .eq("id", str(profile_id))\
                .execute()

            if not result.data:
                return None

            profile_data = result.data[0]

            # Convert date strings to proper date objects
            if isinstance(profile_data['date_of_birth'], str):
                profile_data['date_of_birth'] = datetime.fromisoformat(
                    profile_data['date_of_birth']
                ).date()

            if isinstance(profile_data['created_at'], str):
                profile_data['created_at'] = datetime.fromisoformat(
                    profile_data['created_at']
                )

            if isinstance(profile_data['updated_at'], str):
                profile_data['updated_at'] = datetime.fromisoformat(
                    profile_data['updated_at']
                )

            return Profile(**profile_data)

        except Exception as e:
            logger.error(f"Error in get_profile: {str(e)}")
            logger.error(f"Profile ID: {profile_id}")
            logger.error(f"Profile data: {profile_data if 'profile_data' in locals() else 'No data fetched'}")
            raise


    @staticmethod
    async def update_profile(profile_id: UUID4, profile_data: ProfileCreate) -> Profile:
        """
        Updates an existing profile by ID.
        """
        try:
            # Update data in Supabase
            response = supabase.table(ProfileService.table_name).update(profile_data.dict()).eq("id", str(profile_id)).execute()

            # Check for errors
            if response.get("error"):
                raise Exception(f"Supabase error: {response['error']['message']}")

            if response["data"]:
                profile = Profile(**response["data"][0])
                return profile
            raise Exception("Profile not found")
        except Exception as e:
            raise Exception(f"Failed to update profile: {str(e)}")

    @staticmethod
    async def delete_profile(profile_id: UUID4) -> bool:
        """
        Deletes a profile and all associated data by ID.
        """
        try:
            service = ProfileService()

            # First get the profile to check if it exists and get image URL
            result = service.supabase.table("profiles").select("*").eq("id", str(profile_id)).execute()

            if not result.data:
                return False

            profile = result.data[0]

            # Delete profile image from storage if it exists
            if profile.get('profile_image_url'):
                try:
                    # Extract filename from URL
                    filename = profile['profile_image_url'].split('/')[-1]
                    service.supabase.storage.from_("profile-images").remove([filename])
                    logger.debug(f"Deleted profile image: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete profile image: {str(e)}")

            # Delete all related data
            # Note: Due to cascade delete in Supabase, we only need to delete the profile
            result = service.supabase.table("profiles").delete().eq("id", str(profile_id)).execute()

            if result.data:
                logger.info(f"Successfully deleted profile {profile_id} and all associated data")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete profile {profile_id}: {str(e)}")
            raise Exception(f"Failed to delete profile: {str(e)}")