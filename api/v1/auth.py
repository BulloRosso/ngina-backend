# api/v1/auth.py
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Optional, Any
from pydantic import BaseModel
from uuid import UUID
import logging
import os
from services.usermanagement import UserManagementService, UserData
from dependencies.auth import get_current_user
from supabase import create_client, Client
from datetime import datetime
from httpx import Response
import httpx

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

class VerificationRequest(BaseModel):
    code: str
    user_id: str

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class MFAVerifyRequest(BaseModel):
    factor_id: str
    code: str
    challenge_id: Optional[str] = None
    access_token: Optional[str] = None 
    refresh_token: Optional[str] = None

class MFAChallengeRequest(BaseModel):
    factor_id: str

class MFAChallengeResponse(BaseModel):
    id: str
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    
class TOTPFactorData(BaseModel):
    qr_code: str
    secret: str

class MFAEnrollResponse(BaseModel):
    id: str
    totp: Optional[TOTPFactorData]
    phone: Optional[str] = None  # Make phone field optional

async def create_mfa_challenge(client: Client, factor_id: str) -> dict:
    """Create MFA challenge using direct API call."""
    try:
        session = client.auth.get_session()
        base_url = os.getenv("SUPABASE_URL")
        url = f"{base_url}/auth/v1/factors/{factor_id}/challenge"

        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "apikey": os.getenv("SUPABASE_KEY"),
            "Content-Type": "application/json"
        }

        logger.info(f"Making MFA challenge request to: {url}")
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Raw challenge response data: {data}")
            return data

    except Exception as e:
        logger.error(f"Error creating challenge: {str(e)}")
        if isinstance(e, httpx.HTTPError):
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        import traceback
        logger.error(traceback.format_exc())
        raise e

async def get_mfa_qr_code(client, user_email: str) -> dict:
    """Get MFA QR code via new factor"""
    try:
        # Delete existing unverified factors first
        factors = client.auth.mfa.list_factors()
        for factor in factors.all:
            if factor.status == 'unverified':
                try:
                    # Use raw API call to avoid validation issues
                    base_url = os.getenv("SUPABASE_URL")
                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.delete(
                            f"{base_url}/auth/v1/factors/{factor.id}",
                            headers={
                                "Authorization": f"Bearer {client.auth.get_session().access_token}",
                                "apikey": os.getenv("SUPABASE_KEY")
                            }
                        )
                        response.raise_for_status()
                        logger.info(f"Unenrolled old factor: {factor.id}")
                except Exception as e:
                    logger.error(f"Error unenrolling factor: {str(e)}")

        # Create new factor with unique name
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Use raw API call to avoid validation issues
        base_url = os.getenv("SUPABASE_URL")
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{base_url}/auth/v1/factors",
                headers={
                    "Authorization": f"Bearer {client.auth.get_session().access_token}",
                    "apikey": os.getenv("SUPABASE_KEY"),
                    "Content-Type": "application/json"
                },
                json={
                    "issuer": "Noblivion",
                    "factor_type": "totp",
                    "friendly_name": f"MFA for {user_email}_{timestamp}"
                }
            )
            response.raise_for_status()
            enroll_data = response.json()

            logger.info(f"Raw enroll response: {enroll_data}")

            if 'totp' not in enroll_data:
                raise Exception("No TOTP data in enroll response")

            return {
                "factor_id": enroll_data.get('id'),
                "qr_code": enroll_data.get('totp', {}).get('qr_code'),
                "secret": enroll_data.get('totp', {}).get('secret')
            }

    except Exception as e:
        logger.error(f"Error getting QR code: {str(e)}")
        if isinstance(e, httpx.HTTPError):
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        import traceback
        logger.error(traceback.format_exc())
        raise e

@router.post("/signup")
async def signup(request: SignupRequest):
    try:
        service = UserManagementService()
        user = await service.create_user(UserData(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            password=request.password
        ))

        return {
            "user": user,
            "message": "User created successfully"
        }
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mfa-factors")
async def list_mfa_factors():
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        response = supabase_client.auth.mfa.list_factors()
        return {
            "totp": response.totp
        }

    except Exception as e:
        logger.error(f"List MFA factors error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
@router.post("/login")
async def login(login_data: LoginRequest):
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        try:
            # Authenticate user
            auth_response = supabase_client.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })

            if not auth_response.user:
                raise HTTPException(status_code=401, detail="Invalid credentials")

            user = auth_response.user
            session = auth_response.session
            is_validated = user.email_confirmed_at is not None

            mfa_required = False
            mfa_data = None

            try:
                # Get current MFA settings
                aal = supabase_client.auth.mfa.get_authenticator_assurance_level()
                logger.info(f"Current AAL: {aal}")
                factors = supabase_client.auth.mfa.list_factors()
                logger.info(f"MFA factors: {factors}")

                existing_factors = factors.all

                if existing_factors:
                    unverified_factor = next((f for f in existing_factors if f.status == 'unverified'), None)
                    factor_to_use = unverified_factor or existing_factors[0]

                    if unverified_factor:
                        # For unverified factor, get new QR code
                        try:
                            qr_data = await get_mfa_qr_code(
                                client=supabase_client, 
                                user_email=user.email
                            )
                            mfa_required = True
                            mfa_data = {
                                "factor_id": qr_data["factor_id"],
                                "qr_code": qr_data["qr_code"],
                                "secret": qr_data["secret"],
                                "needs_setup": True
                            }
                        except Exception as qr_error:
                            logger.error(f"Error getting QR code: {str(qr_error)}")
                            mfa_required = False
                    else:
                        # For verified factor, create challenge
                        try:
                            challenge_data = await create_mfa_challenge(
                                client=supabase_client,
                                factor_id=factor_to_use.id
                            )
                            if challenge_data and 'id' in challenge_data:
                                mfa_required = True
                                mfa_data = {
                                    "challenge_id": challenge_data['id'],
                                    "factor_id": factor_to_use.id,
                                    "needs_setup": False
                                }
                        except Exception as challenge_error:
                            logger.error(f"MFA challenge error: {str(challenge_error)}")
                            mfa_required = False
                else:
                    # No existing factors - create new one
                    try:
                        qr_data = await get_mfa_qr_code(
                            client=supabase_client,
                            user_email=user.email
                        )
                        mfa_required = True
                        mfa_data = {
                            "factor_id": qr_data["factor_id"],
                            "qr_code": qr_data["qr_code"],
                            "secret": qr_data["secret"],
                            "needs_setup": True
                        }
                        logger.info(f"New MFA factor created: {mfa_data}")
                    except Exception as enroll_error:
                        logger.error(f"MFA enrollment error: {str(enroll_error)}")
                        mfa_required = False

            except Exception as e:
                logger.error(f"Error checking MFA status: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())

            # Always return the session token, even with MFA required
            response_data = {
                "access_token": session.access_token,  # Changed this line
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.user_metadata.get('first_name', ''),
                    "last_name": user.user_metadata.get('last_name', ''),
                    "is_validated": is_validated
                },
                "mfa_required": mfa_required,
                "mfa_data": mfa_data
            }

            logger.info(f"Login response data: {response_data}")
            return response_data

        except Exception as e:
            logger.error(f"Supabase auth error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=401, detail="Invalid credentials")

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/verify-email")
async def verify_email(verification_data: VerificationRequest):
    try:
        service = UserManagementService()
        verified = await service.verify_email(
            UUID(verification_data.user_id),
            verification_data.code
        )
        return {"verified": verified}
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/validation-status/{user_id}")
async def check_validation_status(user_id: str):
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        user_response = supabase_client.auth.admin.get_user_by_id(user_id)
        is_validated = False

        if user_response.user.identities:
            identity = user_response.user.identities[0]
            is_validated = identity.identity_data['email_verified']

        return {
            "is_validated": is_validated,
            "user_id": user_id
        }
    except Exception as e:
        logger.error(f"Validation status check error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/request-password-reset")
async def request_password_reset(request: PasswordResetRequest):
    try:
        service = UserManagementService()
        await service.request_password_reset(request.email)

        # For security, always return success even if email doesn't exist
        return {"message": "If the email exists, a reset link has been sent."}
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return {"message": "If the email exists, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm):
    try:
        service = UserManagementService()
        success = await service.reset_password(request.token, request.new_password)

        if not success:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        return {"message": "Password has been reset successfully"}
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get user profile settings"""
    try:
        # Verify user is accessing their own profile
        if str(current_user["id"]) != user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot access another user's profile"
            )

        service = UserManagementService()
        result = await service.get_user_profile(user_id)

        if not result:
            raise HTTPException(status_code=404, detail="User not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile")
async def update_user_profile(
    profile_update: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Update user profile settings"""
    try:
        service = UserManagementService()
        result = await service.update_user_profile_settings(
            str(current_user["id"]),
            profile_update
        )
        return result
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        service = UserManagementService()
        # Supabase will verify the token and return user info
        user = await service.get_user_by_id(token)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/verify-mfa")
async def verify_mfa(request: MFAVerifyRequest):
    try:
        logger.info(f"Received MFA verification request: {request}")

        base_url = os.getenv("SUPABASE_URL")
        headers = {
            "apikey": os.getenv("SUPABASE_KEY"),
            "Content-Type": "application/json"
        }
        if request.access_token:
            headers["Authorization"] = f"Bearer {request.access_token}"

        async with httpx.AsyncClient() as client:
            # Always create a new challenge
            challenge_response = await client.post(
                f"{base_url}/auth/v1/factors/{request.factor_id}/challenge",
                headers=headers,
                json={}
            )
            challenge_response.raise_for_status()
            challenge_data = challenge_response.json()
            challenge_id = challenge_data["id"]
            logger.info(f"Challenge created: {challenge_data}")

            # Verify code with new challenge
            verify_response = await client.post(
                f"{base_url}/auth/v1/factors/{request.factor_id}/verify",
                headers=headers,
                json={
                    "challenge_id": challenge_id,
                    "code": request.code
                }
            )
            verify_response.raise_for_status()
            verify_data = verify_response.json()
            logger.info(f"Verification response: {verify_data}")

            return {
                "access_token": verify_data["access_token"],
                "refresh_token": verify_data["refresh_token"],
                "message": "MFA verification successful"
            }

    except httpx.HTTPError as e:
        logger.error(f"HTTP error during MFA verification: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    except Exception as e:
        logger.error(f"MFA verification error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/enroll-mfa")
async def enroll_mfa():
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        response = supabase_client.auth.mfa.enroll({
            "factor_type": "totp",
            "issuer": "Noblivion"
        })

        return response

    except Exception as e:
        logger.error(f"MFA enrollment error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/challenge-mfa")
async def challenge_mfa(request: MFAChallengeRequest):
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        response = supabase_client.auth.mfa.challenge({
            "factor_id": request.factor_id
        })

        return response

    except Exception as e:
        logger.error(f"MFA challenge error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mfa-level")
async def get_mfa_level():
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        response = supabase_client.auth.mfa.get_authenticator_assurance_level()
        return {
            "currentLevel": response.current_level,
            "nextLevel": response.next_level
        }

    except Exception as e:
        logger.error(f"MFA level check error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))