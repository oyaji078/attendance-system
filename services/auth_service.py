from __future__ import annotations

import logging
import secrets
from uuid import UUID

from app.core.config import Settings
from app.core.security import create_session_token, hash_password, verify_password
from db.models.entities import AdminUser
from db.repositories.admin_users import AdminUserRepository
from db.schemas.auth import AdminUserRead

LOGGER = logging.getLogger(__name__)


class AuthenticationError(ValueError):
    pass


class AuthService:
    def __init__(self, admin_repository: AdminUserRepository, settings: Settings) -> None:
        self.admin_repository = admin_repository
        self.settings = settings

    async def ensure_default_admin(self) -> None:
        if await self.admin_repository.count() > 0:
            return
        password = self.settings.default_admin_password
        generated = False
        if not password:
            password = secrets.token_urlsafe(18)
            generated = True
        user = await self.admin_repository.create(
            username=self.settings.default_admin_username,
            email=self.settings.default_admin_email,
            full_name="Administrator Lokal",
            password_hash=hash_password(password),
            is_active=True,
            role="admin",
        )
        if generated:
            LOGGER.warning(
                "default_admin_created_generated_password",
                extra={"username": user.username},
            )
        else:
            LOGGER.info("default_admin_created", extra={"username": user.username})

    async def authenticate(self, username: str, password: str) -> AdminUser:
        user = await self.admin_repository.get_by_login(username)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthenticationError("Username atau kata sandi salah.")
        return user

    async def get_active_user(self, admin_id: UUID) -> AdminUser | None:
        user = await self.admin_repository.get_by_id(admin_id)
        if user is None or not user.is_active:
            return None
        return user

    def create_token(self, user: AdminUser) -> str:
        return create_session_token(
            admin_id=user.id,
            username=user.username,
            secret_key=self.settings.auth_secret_key,
            ttl_seconds=self.settings.admin_session_ttl_seconds,
        )


def admin_user_read(user: AdminUser, lecturer_name: str | None = None) -> AdminUserRead:
    return AdminUserRead(
        admin_id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        lecturer_id=user.lecturer_id,
        lecturer_name=lecturer_name,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
