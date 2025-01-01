from jose import jwt
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uuid import UUID
import os

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UUID:
   try:
       token = credentials.credentials
       payload = jwt.decode(
           token,
           os.getenv("SUPABASE_JWT_SECRET"),
           algorithms=["HS256"],
           audience="authenticated"
       )
       return UUID(payload["sub"])
   except Exception as e:
       logger.error(f"Auth error: {str(e)}")
       raise HTTPException(status_code=401, detail=str(e))