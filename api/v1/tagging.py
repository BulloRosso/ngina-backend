# api/v1/tagging.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict
from pydantic import BaseModel, UUID4
from supabase import create_client
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tagging", tags=["tagging"])

class TagNode(BaseModel):
    category: str
    name: str
    full_tag: str
    children: List['TagNode'] = []  # Using List with default empty list

# Update Pydantic model
TagNode.model_rebuild()

class TagCreate(BaseModel):
    tags: str

class TagService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def get_tag_tree(self) -> List[Dict]:
        try:
            result = self.supabase.table("tags")\
                .select("category_name,tag_name")\
                .execute()

            logger.debug(f"Raw tag data: {result.data}")

            # Group by category
            categories = {}
            for tag in result.data:
                category = tag["category_name"]
                name = tag["tag_name"]
                if category not in categories:
                    categories[category] = []
                categories[category].append(name)

            # Build tree structure
            tree = []
            for category, tags in categories.items():
                category_node = {
                    "id": category,  # Add id for TreeView
                    "category": category,
                    "name": category,
                    "full_tag": category,
                    "children": []
                }

                for tag_name in tags:
                    child = {
                        "id": f"{category}:{tag_name}",  # Add id for TreeView
                        "category": category,
                        "name": tag_name,
                        "full_tag": f"{category}:{tag_name}",
                        "children": []
                    }
                    category_node["children"].append(child)

                tree.append(category_node)

            logger.debug(f"Generated tree structure: {tree}")
            return tree

        except Exception as e:
            logger.error(f"Error getting tag tree: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_autocomplete(self, query: str) -> List[str]:
        try:
            if len(query) < 2:
                return []

            result = self.supabase.table("tags")\
                .select("category_name,tag_name")\
                .or_(f"tag_name.ilike.%{query}%,category_name.ilike.%{query}%")\
                .limit(10)\
                .execute()

            return [f"{tag['category_name']}:{tag['tag_name']}" for tag in result.data]

        except Exception as e:
            logger.error(f"Error in autocomplete: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_agent_tags(self, agent_id: str) -> str:
        try:
            result = self.supabase.table("agent_tags")\
                .select("tags")\
                .eq("agent_id", agent_id)\
                .execute()

            if not result.data:
                return ""
            return result.data[0].get("tags", "")
        except Exception as e:
            logger.error(f"Error getting agent tags: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def set_agent_tags(self, agent_id: str, tags: str) -> str:
        try:
            result = self.supabase.table("agent_tags")\
                .upsert({"agent_id": agent_id, "tags": tags})\
                .execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to set tags")
            return tags
        except Exception as e:
            logger.error(f"Error setting agent tags: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def delete_agent_tags(self, agent_id: str) -> bool:
        try:
            self.supabase.table("agent_tags")\
                .delete()\
                .eq("agent_id", agent_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting agent tags: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

# Static routes first
@router.get("/tree")
async def get_tag_tree():
    """Get hierarchical tag structure"""
    service = TagService()
    return await service.get_tag_tree()

@router.get("/autocomplete")
async def get_autocomplete(q: str = Query(..., description="Search query")):
    """Get tag suggestions for autocomplete"""
    service = TagService()
    return await service.get_autocomplete(q)

# Dynamic routes after static ones
@router.get("/{agent_id}")
async def get_agent_tags(agent_id: str):
    """Get tags for a specific agent"""
    service = TagService()
    tags = await service.get_agent_tags(agent_id)
    return {"tags": tags}

@router.post("/{agent_id}")
async def set_agent_tags(agent_id: str, tag_data: TagCreate):
    """Set tags for a specific agent"""
    service = TagService()
    tags = await service.set_agent_tags(agent_id, tag_data.tags)
    return {"tags": tags}

@router.delete("/{agent_id}")
async def delete_agent_tags(agent_id: str):
    """Delete all tags for a specific agent"""
    service = TagService()
    await service.delete_agent_tags(agent_id)
    return {"success": True}