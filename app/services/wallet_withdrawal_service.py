from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    User,
    WalletTransaction,
    WalletTransactionStatus,
    WalletTransactionType,
    WalletWithdrawalRequest,
    WalletWithdrawalStatus,
)
from app.repositories.wallet_transactions import WalletTransactionsRepository
from app.repositories.wallet_withdrawals import WalletWithdrawalsRepository


class WalletWithdrawalError(Exception):
    pass


class InsufficientWalletBalanceForWithdrawal(WalletWithdrawalError):
    pass


class WalletWithdrawalAlreadyProcessedError(WalletWithdrawalError):
    pass


@dataclass(frozen=True)
class WalletWithdrawalResult:
    withdrawal: WalletWithdrawalRequest
    user_telegram_id: int
    amount: int
    wallet_balance: int


class WalletWithdrawalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_request(
        self,
        *,
        user_id: int,
        amount: int,
        destination_type: str,
        destination_number: str,
        account_holder_name: str | None = None,
        user_note: str | None = None,
    ) -> WalletWithdrawalRequest:
        user = await self.session.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None:
            raise WalletWithdrawalError("User not found")
        if user.wallet_balance < amount:
            raise InsufficientWalletBalanceForWithdrawal("Insufficient wallet balance")

        user.wallet_balance -= amount
        withdrawal = await WalletWithdrawalsRepository(self.session).create(
            user_id=user.id,
            amount=amount,
            destination_type=destination_type,
            destination_number=destination_number,
            account_holder_name=account_holder_name,
            user_note=user_note,
        )
        await WalletTransactionsRepository(self.session).create(
            user_id=user.id,
            amount=-amount,
            type=WalletTransactionType.WITHDRAWAL_REQUEST.value,
            status=WalletTransactionStatus.PENDING.value,
            description="درخواست برداشت از کیف پول",
            related_withdrawal_id=withdrawal.id,
        )
        await self.session.commit()
        return withdrawal

    async def mark_paid(self, withdrawal_id: int, *, admin_user_id: int | None) -> WalletWithdrawalResult:
        withdrawal = await WalletWithdrawalsRepository(self.session).get_with_details_for_update(withdrawal_id)
        if withdrawal is None:
            raise WalletWithdrawalError("Withdrawal not found")
        if withdrawal.status != WalletWithdrawalStatus.PENDING.value:
            raise WalletWithdrawalAlreadyProcessedError("Withdrawal already processed")

        now = datetime.now(timezone.utc)
        withdrawal.status = WalletWithdrawalStatus.PAID.value
        withdrawal.processed_by_admin_id = admin_user_id
        withdrawal.approved_at = now
        withdrawal.paid_at = now
        await self._set_request_transaction_status(
            withdrawal.id,
            WalletTransactionStatus.APPROVED.value,
            now,
        )
        await WalletTransactionsRepository(self.session).create(
            user_id=withdrawal.user_id,
            amount=0,
            type=WalletTransactionType.WITHDRAWAL_PAID.value,
            status=WalletTransactionStatus.APPROVED.value,
            description="برداشت پرداخت شد",
            related_withdrawal_id=withdrawal.id,
            approved_at=now,
        )
        await self.session.commit()
        return WalletWithdrawalResult(
            withdrawal=withdrawal,
            user_telegram_id=withdrawal.user.telegram_id,
            amount=withdrawal.amount,
            wallet_balance=withdrawal.user.wallet_balance,
        )

    async def reject(
        self,
        withdrawal_id: int,
        *,
        admin_user_id: int | None,
        admin_note: str | None = None,
    ) -> WalletWithdrawalResult:
        withdrawal = await WalletWithdrawalsRepository(self.session).get_with_details_for_update(withdrawal_id)
        if withdrawal is None:
            raise WalletWithdrawalError("Withdrawal not found")
        if withdrawal.status != WalletWithdrawalStatus.PENDING.value:
            raise WalletWithdrawalAlreadyProcessedError("Withdrawal already processed")

        now = datetime.now(timezone.utc)
        withdrawal.status = WalletWithdrawalStatus.REJECTED.value
        withdrawal.processed_by_admin_id = admin_user_id
        withdrawal.admin_note = admin_note
        withdrawal.rejected_at = now
        withdrawal.user.wallet_balance += withdrawal.amount
        await self._set_request_transaction_status(
            withdrawal.id,
            WalletTransactionStatus.REJECTED.value,
            now,
        )
        await WalletTransactionsRepository(self.session).create(
            user_id=withdrawal.user_id,
            amount=withdrawal.amount,
            type=WalletTransactionType.WITHDRAWAL_REJECTED_REFUND.value,
            status=WalletTransactionStatus.APPROVED.value,
            description="بازگشت مبلغ برداشت رد شده",
            related_withdrawal_id=withdrawal.id,
            approved_at=now,
        )
        await self.session.commit()
        return WalletWithdrawalResult(
            withdrawal=withdrawal,
            user_telegram_id=withdrawal.user.telegram_id,
            amount=withdrawal.amount,
            wallet_balance=withdrawal.user.wallet_balance,
        )

    async def _set_request_transaction_status(
        self,
        withdrawal_id: int,
        status: str,
        approved_at: datetime,
    ) -> None:
        transaction = await self.session.scalar(
            select(WalletTransaction)
            .where(
                WalletTransaction.related_withdrawal_id == withdrawal_id,
                WalletTransaction.type == WalletTransactionType.WITHDRAWAL_REQUEST.value,
            )
            .with_for_update()
        )
        if transaction is None:
            return
        transaction.status = status
        transaction.approved_at = approved_at
