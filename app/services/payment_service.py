from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Order, OrderStatus, Payment, PaymentStatus, VPNServiceStatus
from app.repositories.services import ServicesRepository
from app.services.order_service import OrderService
from app.services.vpn_panel import VPNPanelService


class PaymentApprovalError(Exception):
    pass


class PaymentExpiredError(PaymentApprovalError):
    pass


class PaymentAlreadyProcessedError(PaymentApprovalError):
    pass


@dataclass(frozen=True)
class ApprovedPaymentResult:
    user_telegram_id: int
    custom_username: str
    plan_title: str
    volume_gb: int
    duration_days: int
    config_link: str
    subscription_link: str


@dataclass(frozen=True)
class RejectedPaymentResult:
    user_telegram_id: int


class PaymentService:
    def __init__(self, session: AsyncSession, vpn_panel: VPNPanelService) -> None:
        self.session = session
        self.vpn_panel = vpn_panel

    async def attach_receipt(self, payment: Payment, receipt_file_id: str) -> None:
        payment.receipt_file_id = receipt_file_id
        await self.session.commit()

    async def approve_payment(self, payment_id: int) -> ApprovedPaymentResult:
        payment = await self._load_payment_for_update(payment_id)
        if payment is None:
            raise PaymentApprovalError("Payment not found")

        order = payment.order
        if payment.status != PaymentStatus.PENDING.value:
            raise PaymentAlreadyProcessedError("Payment already processed")
        if self._is_unpaid_order_expired(order, payment):
            order.status = OrderStatus.EXPIRED.value
            payment.status = PaymentStatus.EXPIRED.value
            await self.session.commit()
            raise PaymentExpiredError("Order expired")

        now = datetime.now(timezone.utc)
        plan = order.plan
        user = order.user
        username = order.custom_username or f"user{user.telegram_id}"

        payment.status = PaymentStatus.APPROVED.value
        payment.verified_at = now
        order.status = OrderStatus.PAID.value
        order.paid_at = now
        await self.session.flush()

        order.status = OrderStatus.CREATING_SERVICE.value
        provisioned = await self.vpn_panel.provision_user(
            username=username,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_days,
        )

        services = ServicesRepository(self.session)
        await services.create(
            user_id=user.id,
            order_id=order.id,
            plan_id=plan.id,
            username=username,
            config_link=provisioned.config_link,
            subscription_link=provisioned.subscription_link,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_days,
            expire_at=now + timedelta(days=plan.duration_days),
            status=VPNServiceStatus.ACTIVE.value,
        )

        order.status = OrderStatus.COMPLETED.value
        order.completed_at = now
        await self.session.commit()

        return ApprovedPaymentResult(
            user_telegram_id=user.telegram_id,
            custom_username=username,
            plan_title=plan.title,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_days,
            config_link=provisioned.config_link,
            subscription_link=provisioned.subscription_link,
        )

    async def reject_payment(self, payment_id: int) -> RejectedPaymentResult:
        payment = await self._load_payment_for_update(payment_id)
        if payment is None:
            raise PaymentApprovalError("Payment not found")
        if payment.status != PaymentStatus.PENDING.value:
            raise PaymentAlreadyProcessedError("Payment already processed")

        payment.status = PaymentStatus.REJECTED.value
        payment.verified_at = datetime.now(timezone.utc)
        payment.order.status = OrderStatus.FAILED.value
        await self.session.commit()
        return RejectedPaymentResult(user_telegram_id=payment.user.telegram_id)

    async def _load_payment_for_update(self, payment_id: int) -> Payment | None:
        return await self.session.scalar(
            select(Payment)
            .options(
                joinedload(Payment.user),
                joinedload(Payment.order).joinedload(Order.user),
                joinedload(Payment.order).joinedload(Order.plan),
            )
            .where(Payment.id == payment_id)
            .with_for_update(of=Payment)
        )

    @staticmethod
    def _is_unpaid_order_expired(order: Order, payment: Payment) -> bool:
        if payment.receipt_file_id:
            return False
        return OrderService.is_order_expired(order)
