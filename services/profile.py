from datetime import date, datetime, timezone
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
from services.usermanagement import UserManagementService
from services.knowledgemanagement import KnowledgeManagement

logger = logging.getLogger(__name__)

class ProfileRating(BaseModel):
    completeness: float
    memories_count: int
    memories_with_images: int
    rating: str
    
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
        self.user_management_service = UserManagementService()

    async def parse_backstory(self, profile_id: UUID, backstory: str, profile_data: Dict[str, Any], language: str = "de") -> None:
        """Parse memories from backstory and create initial memories in the specified language"""
        try:
            logger.info(f"Parsing backstory for profile {profile_id} in language {language}")

            # Create initial session
            session_data = {
                "id": str(uuid4()),
                "profile_id": str(profile_id),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",  # Mark as completed since this is initialization
                "completed_at": datetime.now(timezone.utc).isoformat()
            }

            result = self.supabase.table("interview_sessions").insert(session_data).execute()
            session_id = result.data[0]['id']
            
            # Create profile context string
            pronoun = "him" if profile_data["gender"].lower() == "male" else "her"
            profile_context = f"The main character of our memories is {profile_data['first_name']} {profile_data['last_name']} which is of {profile_data['gender']} gender. When rewriting memories reference to {pronoun} as {profile_data['first_name']}."

            # Get narrator settings directly from profile metadata
            metadata = profile_data.get('metadata', {})
            narrator_perspective = metadata.get('narrator_perspective', 'ego')
            narrator_style = metadata.get('narrator_style', 'neutral')
            narrator_verbosity = metadata.get('narrator_verbosity', 'normal')
            
            # Create birth memory
            try:
                # Handle place of birth parsing with better validation
                place_parts = profile_data['place_of_birth'].split(',')
                if len(place_parts) >= 2:
                    city = place_parts[0].strip()
                    country = place_parts[-1].strip()
                else:
                    city = profile_data['place_of_birth'].strip()
                    country = "Deutschland" if language == "de" else "Germany"

                logger.info(f"Parsed location - city: {city}, country: {country}")

                first_name = profile_data['first_name']
                last_name = profile_data['last_name']
                place = profile_data['place_of_birth']

                # Create birth description based on narrator perspective
                if narrator_perspective == 'ego':
                    birth_description = {
                        "de": f"Ich wurde in {place} geboren",
                        "en": f"I was born in {place}"
                    }.get(language, f"I was born in {place}")
                else:  # third person
                    birth_description = {
                        "de": f"{first_name} {last_name} wurde in {place} geboren",
                        "en": f"{first_name} {last_name} was born in {place}"
                    }.get(language, f"{first_name} {last_name} was born in {place}")

                logger.info(f"Created birth description: {birth_description}")
                
                birth_memory = MemoryCreate(
                    category=Category.CHILDHOOD,
                    description=birth_description,
                    time_period=datetime.strptime(profile_data['date_of_birth'], "%Y-%m-%d"),
                    location=Location(
                        name=place,
                        city=city,
                        country=country,
                        description="Geburtsort" if language == "de" else "Place of birth"
                    )
                )
                logger.info(f"Created birth memory object: {birth_memory}")

                logger.info(f"About to call MemoryService.create_memory with profile_id={profile_id}, session_id={session_id}")
                memory_id = await MemoryService.create_memory(birth_memory, profile_id, session_id)
                logger.info(f"=== Birth memory created successfully with ID: {memory_id} ===")

            except Exception as e:
                logger.error(f"Error creating birth memory: {str(e)}")

            # Convert perspective setting to prompt text
            perspective_text = "in first person view" if narrator_perspective == "ego" else "in third person view"

            # Convert style setting to prompt text
            style_text = {
                "professional": "using a clear and professional tone",
                "romantic": "using a warm and emotional tone",
                "optimistic": "using a positive and uplifting tone",
                "neutral": "using a balanced and neutral tone"
            }.get(narrator_style, "using a neutral tone")

            # Convert verbosity setting to prompt text
            verbosity_text = {
                "verbose": "more detailed and elaborate",
                "normal": "similar in length",
                "brief": "more concise and focused"
            }.get(narrator_verbosity, "similar in length")

            # Set temperature based on style
            temperature = {
                "professional": 0.1,
                "neutral": 0.3
            }.get(narrator_style, 0.7)

            logger.debug(f"Using narrative settings - perspective: {perspective_text}, style: {style_text}, verbosity: {verbosity_text}, temperature: {temperature}")
            
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

                            {profile_context}

                            Format each memory {perspective_text}, {style_text}. 
                            Compared to the source text, your description should be {verbosity_text}.

                            For each memory in the "memories" array, provide:
                            {{
                                "description": "Full description of the memory in {language}",
                                "original_description": "Original description of the memory in {language}",
                                "caption": "3-8 word caption that captures the essence in {language}",
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
                    response_format={ "type": "json_object" },
                    temperature=temperature
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
                            caption=memory_data.get('caption'),  
                            original_description=memory_data['original_description'],
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
                    
                    if isinstance(profile_data['subscribed_at'], str):
                        profile_data['subscribed_at'] = datetime.fromisoformat(profile_data['subscribed_at'])
                    else:
                        profile_data['subscribed_at'] = None
                        
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
                "user_id": str(profile_data.user_id),
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

            # Ensure metadata exists and contains narrator settings
            if not profile_data.get('metadata'):
                profile_data['metadata'] = {}

            metadata = profile_data['metadata']
            if not isinstance(metadata, dict):
                metadata = {}

            # Only set defaults if values don't exist
            if 'narrator_style' not in metadata:
                metadata['narrator_style'] = 'neutral'
            if 'narrator_perspective' not in metadata:
                metadata['narrator_perspective'] = 'ego'
            if 'narrator_verbosity' not in metadata:
                metadata['narrator_verbosity'] = 'normal'

            profile_data['metadata'] = metadata

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

    async def get_profile_rating(self, profile_id: UUID, language: str = "en") -> ProfileRating:
        """Get rating statistics for a profile"""
        try:
            logger.debug(f"Fetching rating for profile: {profile_id}")

            # Get memory count from memories table
            memories_result = self.supabase.table('memories')\
                .select('id', count='exact')\
                .eq('profile_id', str(profile_id))\
                .execute()

            memories_count = memories_result.count if memories_result.count else 0

            # Get memories with images by checking image_urls array
            memories_with_images_result = self.supabase.table('memories')\
                .select('image_urls')\
                .eq('profile_id', str(profile_id))\
                .execute()

            # Count memories that have non-empty image_urls array
            memories_with_images = sum(
                1 for memory in memories_with_images_result.data 
                if memory.get('image_urls') and len(memory['image_urls']) > 0
            )

            # Calculate completeness as memories_count / 30
            completeness = min(memories_count / 30, 1.0)

            # Generate rating message
            rating_message = "Your profile shows good progress. "
            if memories_count < 30:
                rating_message += f"Add {30 - memories_count} more memories to reach the minimum for book printing. "
            else:
                rating_message += "You have enough memories to print a book! "

            if memories_with_images < memories_count / 2:
                rating_message += "Consider adding more images to make your memories more vivid."
            else:
                rating_message += "Great job including images with your memories!"

            # Translate the message if language is not English
            if language != "en":
                from services.knowledgemanagement import KnowledgeManagement
                ai_service = KnowledgeManagement()
                rating_message = await ai_service.translate_text(rating_message, language)

            return ProfileRating(
                completeness=completeness,
                memories_count=memories_count,
                memories_with_images=memories_with_images,
                rating=rating_message
            )

        except Exception as e:
            logger.error(f"Error getting profile rating: {str(e)}")
            logger.error(traceback.format_exc())
            raise
            
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