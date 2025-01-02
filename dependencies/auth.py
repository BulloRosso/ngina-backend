# dependencies/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import logging
import os
from uuid import UUID

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Keep the old name for backwards compatibility
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UUID:
    """Dependency that extracts and validates UUID from JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            os.getenv("SUPABASE_JWT_SECRET"),
            algorithms=["HS256"],
            audience="authenticated"
        )

        # Extract the sub claim which contains the UUID
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID found")

        try:
            return UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid user ID format")

    except jwt.JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))

# New name for the same function
get_current_user_dependency = get_current_user