"""
Authentication API Routes
User registration, login, and session management
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Header
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import hashlib

from app.core.config import settings
from app.core.logging import get_logger
from app.core.jwt_auth import create_jwt_token, decode_jwt_token
from app.db import get_db, User

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    name: str = Field(..., description="Full name")
    company: Optional[str] = Field(default=None, description="Company name")


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="Password")


class AuthResponse(BaseModel):
    """Authentication response with token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    """User profile response"""
    id: int
    email: str
    name: Optional[str]
    company: Optional[str]
    tenant_id: Optional[str]
    is_verified: bool
    created_at: datetime


# ============================================
# HELPER FUNCTIONS
# ============================================

def hash_password(password: str) -> str:
    """Hash password with salt"""
    salt = settings.secret_key[:16] if settings.secret_key else "default-salt-key"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == password_hash


def create_user_token(user: User) -> tuple[str, int]:
    """Create JWT token for user"""
    expires_hours = settings.jwt_expiration_hours
    token = create_jwt_token(
        payload={
            "userid": user.id,
            "email": user.email,
            "tenant_id": user.tenant_id
        },
        expires_delta=timedelta(hours=expires_hours)
    )
    return token, expires_hours * 3600


# ============================================
# ENDPOINTS
# ============================================

@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account
    """
    try:
        # Check if email already exists
        existing = db.query(User).filter(User.email == request.email).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        # Create user
        user = User(
            email=request.email,
            password_hash=hash_password(request.password),
            name=request.name,
            company=request.company,
            is_active=True,
            is_verified=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create token
        token, expires_in = create_user_token(user)

        logger.info(f"New user registered: {user.email}")

        return AuthResponse(
            access_token=token,
            expires_in=expires_in,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "company": user.company
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email and password
    """
    try:
        # Find user
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Account is deactivated"
            )

        # Update last login
        user.last_login_at = datetime.utcnow()
        db.commit()

        # Create token
        token, expires_in = create_user_token(user)

        logger.info(f"User logged in: {user.email}")

        return AuthResponse(
            access_token=token,
            expires_in=expires_in,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "company": user.company,
                "tenant_id": user.tenant_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/token")
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token endpoint
    """
    request = LoginRequest(email=form_data.username, password=form_data.password)
    return await login(request, db)


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get current user profile
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")
    payload = decode_jwt_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("userid")
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        company=user.company,
        tenant_id=user.tenant_id,
        is_verified=user.is_verified,
        created_at=user.created_at
    )


@router.post("/logout")
async def logout():
    """
    Logout (client should discard token)
    """
    return {"message": "Logged out successfully"}
