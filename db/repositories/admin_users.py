from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AdminUser


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(AdminUser.id)))
        return int(result.scalar_one())

    async def get_by_id(self, admin_id: UUID) -> AdminUser | None:
        result = await self.session.execute(select(AdminUser).where(AdminUser.id == admin_id))
        return result.scalar_one_or_none()

    async def get_by_login(self, login: str) -> AdminUser | None:
        result = await self.session.execute(
            select(AdminUser).where(or_(AdminUser.username == login, AdminUser.email == login))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        username: str,
        email: str | None,
        full_name: str,
        password_hash: str,
        is_active: bool = True,
        role: str = "admin",
        lecturer_id: UUID | None = None,
    ) -> AdminUser:
        user = AdminUser(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            lecturer_id=lecturer_id,
            is_active=is_active,
        )
        self.session.add(user)
        await self.session.flush()
        return user
