import logging
from typing import Any

from app.core.constants import OAuth, Supabase
from app.core.messages import ErrorMessages, LogMessages
from app.core.supabase_client import get_supabase_client
from app.schemas.auth import UserCreate, UserLogin
from app.services.db_service import get_db_service

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations"""

    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.db_service = get_db_service()

    async def signup(self, user_data: UserCreate) -> dict[str, Any]:
        """Register a new user in Supabase Auth"""
        try:
            auth_response = self.client.auth.sign_up(
                {
                    "email": user_data.email,
                    "password": user_data.password,
                    "options": {
                        "data": {
                            Supabase.FULL_NAME_FIELD: user_data.full_name,
                        }
                    },
                }
            )

            if not hasattr(auth_response, "user") or not auth_response.user:
                raise ValueError(
                    f"{ErrorMessages.REGISTRATION_FAILED}: Could not create user"
                )

            logger.info(LogMessages.USER_CREATED.format(user_id=auth_response.user.id))

            return self._build_auth_dict(auth_response)

        except Exception as e:
            logger.error(f"Signup error: {e!s}")
            raise ValueError(f"{ErrorMessages.REGISTRATION_FAILED}: {e!s}") from e

    async def login(self, user_data: UserLogin) -> dict[str, Any]:
        """Authenticate a user with email and password"""
        try:
            auth_response = self.client.auth.sign_in_with_password(
                {
                    "email": user_data.email,
                    "password": user_data.password,
                }
            )

            if (
                not hasattr(auth_response, "user")
                or not auth_response.user
                or not auth_response.session
            ):
                raise ValueError(
                    f"{ErrorMessages.AUTHENTICATION_FAILED}: Invalid credentials"
                )

            logger.info(
                LogMessages.USER_LOGGED_IN.format(user_id=auth_response.user.id)
            )
            return self._build_auth_dict(auth_response)

        except Exception as e:
            logger.error(f"Login error: {e!s}")
            raise ValueError(f"{ErrorMessages.AUTHENTICATION_FAILED}: {e!s}") from e

    async def logout(self, token: str) -> bool:
        try:
            self.client.auth.sign_out()
            logger.info(LogMessages.USER_LOGGED_OUT)
            return True
        except Exception as e:
            logger.error(f"Logout error: {e!s}")
            return False

    async def request_password_reset(self, email: str) -> bool:
        try:
            self.client.auth.reset_password_for_email(email)
            return True
        except Exception as e:
            logger.error(f"Password reset error: {e!s}")
            return False

    async def oauth_login(self, provider: str, redirect_url: str) -> dict[str, Any]:
        """Initiate OAuth login flow - let Supabase handle PKCE"""
        if provider != OAuth.GOOGLE:
            raise ValueError(f"Unsupported provider: {provider}")

        # Let Supabase handle PKCE internally - just pass the redirect URL
        auth_response = self.client.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {
                    "redirect_to": redirect_url,
                    "scopes": "https://www.googleapis.com/auth/gmail.readonly",
                },
            }
        )

        return {"auth_url": auth_response.url}

    async def handle_oauth_callback(
        self, provider: str, code: str, redirect_url: str
    ) -> dict[str, Any]:
        """Handle OAuth callback - let Supabase handle PKCE code exchange"""
        if provider != OAuth.GOOGLE:
            raise ValueError(f"Unsupported provider: {provider}")

        try:
            # Pass proper CodeExchangeParams format - Supabase will get code_verifier from storage
            code_exchange_params = {"auth_code": code, "redirect_to": redirect_url}

            auth_response = self.client.auth.exchange_code_for_session(
                code_exchange_params
            )

            if not auth_response.user or not auth_response.session:
                raise ValueError("Failed to exchange code for session")

            user = auth_response.user
            session = auth_response.session

            # Extract Google OAuth provider tokens
            provider_token = session.provider_token
            provider_refresh_token = session.provider_refresh_token

            # Store provider tokens in the dedicated, isolated database table
            if provider_token:
                await get_db_service().upsert_provider_token(
                    user_id=user.id,
                    provider=provider,
                    access_token=provider_token,
                    refresh_token=provider_refresh_token,
                )

            logger.info(
                LogMessages.USER_LOGGED_IN.format(user_id=auth_response.user.id)
            )
            return self._build_auth_dict(auth_response)

        except Exception as e:
            logger.error(f"OAuth callback error: {e!s}")
            raise ValueError(f"OAuth authentication failed: {e!s}") from e

    def _build_auth_dict(self, auth_response: Any) -> dict[str, Any]:
        """Build auth dict in format expected by format_auth_response helper"""
        user_metadata = auth_response.user.user_metadata
        if isinstance(user_metadata, str):
            logger.warning(f"User metadata is string instead of dict: {user_metadata}")
            user_metadata = {}
        elif user_metadata is None:
            user_metadata = {}

        full_name = ""
        if isinstance(user_metadata, dict):
            full_name = user_metadata.get(Supabase.FULL_NAME_FIELD, "")

        user_dict = {
            "id": auth_response.user.id,
            "email": auth_response.user.email,
            "user_metadata": user_metadata,
            "full_name": full_name,
            "created_at": auth_response.user.created_at,
        }

        session_dict = {}
        if auth_response.session:
            session_obj = auth_response.session
            access_token = getattr(session_obj, "access_token", None)
            refresh_token = getattr(session_obj, "refresh_token", None)

            if access_token:
                session_dict = {
                    "access_token": access_token,
                    "refresh_token": refresh_token or "",
                }

        return {
            "user": user_dict,
            "session": session_dict,
        }