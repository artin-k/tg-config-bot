from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import WalletWithdrawalRequest, WalletWithdrawalStatus


class WalletWithdrawalsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, withdrawal_id: int) -> WalletWithdrawalRequest | None:
        return await self.session.get(WalletWithdrawalRequest, withdrawal_id)

    async def get_with_details(self, withdrawal_id: int) -> WalletWithdrawalRequest | None:
        return await self.session.scalar(
            select(WalletWithdrawalRequest)
            .options(
                joinedload(WalletWithdrawalRequest.user),
                joinedload(WalletWithdrawalRequest.processed_by_admin),
            )
            .where(WalletWithdrawalRequest.id == withdrawal_id)
        )

    async def get_with_details_for_update(self, withdrawal_id: int) -> WalletWithdrawalRequest | None:
        return await self.session.scalar(
            select(WalletWithdrawalRequest)
            .options(
                joinedload(WalletWithdrawalRequest.user),
                joinedload(WalletWithdrawalRequest.processed_by_admin),
            )
            .where(WalletWithdrawalRequest.id == withdrawal_id)
            .with_for_update(of=WalletWithdrawalRequest)
        )

    async def list_recent_by_user(self, user_id: int, limit: int = 10) -> list[WalletWithdrawalRequest]:
        result = await self.session.scalars(
            select(WalletWithdrawalRequest)
            .where(WalletWithdrawalRequest.user_id == user_id)
            .order_by(WalletWithdrawalRequest.created_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def list_pending(self, limit: int = 10) -> list[WalletWithdrawalRequest]:
        result = await self.session.scalars(
            select(WalletWithdrawalRequest)
            .options(joinedload(WalletWithdrawalRequest.user))
            .where(WalletWithdrawalRequest.status == WalletWithdrawalStatus.PENDING.value)
            .order_by(WalletWithdrawalRequest.created_at.asc())
            .limit(limit)
        )
        return list(result.unique().all())

    async def list_recent(self, limit: int = 10) -> list[WalletWithdrawalRequest]:
        result = await self.session.scalars(
            select(WalletWithdrawalRequest)
            .options(joinedload(WalletWithdrawalRequest.user))
            .order_by(WalletWithdrawalRequest.created_at.desc())
            .limit(limit)
        )
        return list(result.unique().all())

    async def create(
        self,
        *,
        user_id: int,
        amount: int,
        destination_type: str,
        destination_number: str,
        account_holder_name: str | None = None,
        user_note: str | None = None,
    ) -> WalletWithdrawalRequest:
        withdrawal = WalletWithdrawalRequest(
            user_id=user_id,
            amount=amount,
            destination_type=destination_type,
            destination_number=destination_number,
            account_holder_name=account_holder_name,
            user_note=user_note,
            status=WalletWithdrawalStatus.PENDING.value,
        )
        self.session.add(withdrawal)
        await self.session.flush()
        return withdrawal
