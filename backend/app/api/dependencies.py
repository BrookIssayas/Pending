import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.messages import ErrorMessages, LogMessages
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
security = HTTPBearer()


def validate_jwt_token(token: str) -> str:
    """
    Extract and validate JWT token, return user_id

    Args:
        token: JWT token string

    Returns:
        user_id extracted from token

    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Decode and verify token
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "require_exp": True,
            },
            audience="authenticated",
        )

        # Extract user_id from sub claim
        user_id: Any = payload.get("sub")
        if not user_id:
            logger.warning(LogMessages.JWT_MISSING_SUB)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.INVALID_TOKEN_MISSING_USER,
            )

        return str(user_id)

    except JWTError as err:
        logger.warning(LogMessages.JWT_VALIDATION_FAILED.format(error=err))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.INVALID_TOKEN,
        ) from err


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    user_id = validate_jwt_token(token)
    return user_id


def get_auth_service() -> AuthService:
    return AuthService()