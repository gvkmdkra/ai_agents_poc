"""
JWT Authentication Module
Provides token validation and user extraction for API endpoints
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import settings
from .logging import get_logger
from .exceptions import AuthenticationError

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


def create_jwt_token(
    payload: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT token with the given payload

    Args:
        payload: Data to encode in the token
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = payload.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


def extract_userid_from_token(token: str) -> Optional[int]:
    """
    Extract userid from JWT token

    Args:
        token: JWT token string

    Returns:
        User ID or None if not found
    """
    payload = decode_jwt_token(token)
    if payload:
        # Try different common field names for user ID
        for field in ["userid", "user_id", "id", "sub"]:
            if field in payload:
                try:
                    return int(payload[field])
                except (ValueError, TypeError):
                    continue
    return None


async def get_optional_userid(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[int]:
    """
    Dependency that extracts userid from JWT token (optional)

    Returns:
        User ID if valid token provided, None otherwise
    """
    token = None

    # Try Bearer token from security scheme
    if credentials and credentials.credentials:
        token = credentials.credentials

    # Try Authorization header directly
    elif authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

    if token:
        userid = extract_userid_from_token(token)
        if userid:
            logger.debug(f"Extracted userid {userid} from JWT")
            return userid

    return None


async def get_required_userid(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> int:
    """
    Dependency that requires valid JWT token with userid

    Raises:
        HTTPException: If no valid token or userid not found
    """
    userid = await get_optional_userid(authorization, credentials)

    if userid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid JWT token with userid required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return userid


async def get_jwt_payload(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Dependency that returns the full JWT payload

    Returns:
        Full JWT payload or None
    """
    token = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    elif authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

    if token:
        return decode_jwt_token(token)

    return None


class JWTValidator:
    """
    JWT validation utility class for more complex validation scenarios
    """

    def __init__(self, required_claims: Optional[list] = None):
        """
        Initialize validator

        Args:
            required_claims: List of claims that must be present in token
        """
        self.required_claims = required_claims or []

    def validate(self, token: str) -> Dict[str, Any]:
        """
        Validate token and return payload

        Args:
            token: JWT token string

        Returns:
            Decoded payload

        Raises:
            AuthenticationError: If validation fails
        """
        payload = decode_jwt_token(token)

        if not payload:
            raise AuthenticationError("Invalid or expired token")

        # Check required claims
        for claim in self.required_claims:
            if claim not in payload:
                raise AuthenticationError(
                    f"Missing required claim: {claim}",
                    details={"missing_claim": claim}
                )

        return payload

    def get_userid(self, token: str) -> int:
        """
        Get userid from token

        Args:
            token: JWT token string

        Returns:
            User ID

        Raises:
            AuthenticationError: If userid not found
        """
        payload = self.validate(token)

        for field in ["userid", "user_id", "id", "sub"]:
            if field in payload:
                try:
                    return int(payload[field])
                except (ValueError, TypeError):
                    continue

        raise AuthenticationError("User ID not found in token")
