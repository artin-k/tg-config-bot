# Open app/services/payment_service.py
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import Settings
from app.models import (
    Order,
    OrderKind,
    OrderStatus,
    Payment,
    PaymentStatus,
    VPNServiceStatus,
    WalletTransactionStatus,
    WalletTransactionType,
)
from app.repositories.dice_rolls import DiceRollsRepository
from app.repositories.services import ServicesRepository
from app.repositories.wallet_transactions import WalletTransactionsRepository
from app.services.affiliate_service import AffiliateService
from app.services.controld import create_dns_device, ControlDService  # Control D Integration
from app.services.order_service import OrderService
from app.services.referral_service import ReferralService
from app.services.settings_service import AppSettingsService


class PaymentApprovalError(Exception):
    pass


class PaymentExpiredError(PaymentApprovalError):
    pass


class PaymentAlreadyProcessedError(PaymentApprovalError):
    pass


class InsufficientWalletBalanceError(PaymentApprovalError):
    def __init__(self, *, required_amount: int, wallet_balance: int) -> None:
        self.required_amount = required_amount
        self.wallet_balance = wallet_balance
        super().__init__("Insufficient wallet balance")


@dataclass(frozen=True)
class ApprovedPaymentResult:
    user_telegram_id: int
    order_kind: str
    service_username: str
    plan_title: str
    volume_gb: int
    duration_days: int
    config_link: str | None
    subscription_link: str | None
    new_expire_at: datetime | None = None
    wallet_balance: int | None = None
    waiting_inventory: bool = False
    plan_id: int | None = None
    resolver_id: str | None = None
    stamp: str | None = None

    # --- ADDED: Control D Legacy IP Attributes ---
    ipv4: str | None = None
    ipv6: str | None = None
    # ----------------------------------------------


@dataclass(frozen=True)
class RejectedPaymentResult:
    user_telegram_id: int


class PaymentService:
    def __init__(self, session: AsyncSession, vpn_panel: object = None, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings
        self.app_settings = AppSettingsService(session)

    async def attach_receipt(self, payment: Payment, receipt_file_id: str) -> None:
        payment.receipt_file_id = receipt_file_id
        payment.status = PaymentStatus.PENDING.value
        await self.session.commit()

    async def approve_payment(self, payment_id: int) -> ApprovedPaymentResult:
        payment = await self._load_payment_for_update(payment_id)
        if payment is None:
            raise PaymentApprovalError("Payment not found")

        order = payment.order
        if order is None:
            raise PaymentApprovalError("Payment is not connected to an order")
        if payment.status != PaymentStatus.PENDING.value:
            raise PaymentAlreadyProcessedError("Payment already processed")
        if self._is_unpaid_order_expired(order, payment):
            order.status = OrderStatus.EXPIRED.value
            payment.status = PaymentStatus.EXPIRED.value
            await self.session.commit()
            raise PaymentExpiredError("Order expired")
        if order.order_kind == OrderKind.RENEWAL.value and order.renewal_service is None:
            raise PaymentApprovalError("Renewal service not found")

        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.APPROVED.value
        payment.verified_at = now
        order.status = OrderStatus.PAID.value
        order.paid_at = now
        await self.session.flush()

        order.status = OrderStatus.CREATING_SERVICE.value
        result = await self._complete_order(order, now)

        if not result.waiting_inventory:
            order.status = OrderStatus.COMPLETED.value
            order.completed_at = now
            await self._record_discount_usage(order, now)
            if self.settings is not None:
                await AffiliateService(self.session, self.settings).create_commissions_for_order(order.id)
        await self.session.commit()

        return result

    async def reject_payment(self, payment_id: int) -> RejectedPaymentResult:
        payment = await self._load_payment_for_update(payment_id)
        if payment is None:
            raise PaymentApprovalError("Payment not found")
        if payment.status != PaymentStatus.PENDING.value:
            raise PaymentAlreadyProcessedError("Payment already processed")

        payment.status = PaymentStatus.REJECTED.value
        payment.verified_at = datetime.now(timezone.utc)
        if payment.order:
            payment.order.status = OrderStatus.FAILED.value
            if self.settings is not None:
                await AffiliateService(self.session, self.settings).reverse_order_commissions(payment.order.id)
        await self.session.commit()
        return RejectedPaymentResult(user_telegram_id=payment.user.telegram_id)

    async def pay_order_from_wallet(self, order_id: int, user_id: int) -> ApprovedPaymentResult:
        payment = await self.session.scalar(
            select(Payment)
            .options(
                joinedload(Payment.user),
                joinedload(Payment.order).joinedload(Order.user),
                joinedload(Payment.order).joinedload(Order.plan),
                joinedload(Payment.order).joinedload(Order.renewal_service),
            )
            .where(Payment.order_id == order_id, Payment.user_id == user_id)
            .with_for_update(of=Payment)
        )
        if payment is None or payment.order is None:
            raise PaymentApprovalError("Payment not found")

        order = payment.order
        user = payment.user
        if payment.status != PaymentStatus.PENDING.value:
            raise PaymentAlreadyProcessedError("Payment already processed")
        if OrderService.is_order_expired(order):
            order.status = OrderStatus.EXPIRED.value
            payment.status = PaymentStatus.EXPIRED.value
            await self.session.commit()
            raise PaymentExpiredError("Order expired")
        if user.wallet_balance < order.amount:
            raise InsufficientWalletBalanceError(required_amount=order.amount, wallet_balance=user.wallet_balance)

        now = datetime.now(timezone.utc)
        user.wallet_balance -= order.amount
        payment.method = "wallet"
        payment.status = PaymentStatus.APPROVED.value
        payment.verified_at = now
        order.status = OrderStatus.PAID.value
        order.paid_at = now

        transaction_type = (
            WalletTransactionType.RENEWAL.value
            if order.order_kind == OrderKind.RENEWAL.value
            else WalletTransactionType.PURCHASE.value
        )
        await WalletTransactionsRepository(self.session).create(
            user_id=user.id,
            amount=-order.amount,
            type=transaction_type,
            status=WalletTransactionStatus.APPROVED.value,
            description=f"پرداخت سفارش {order.tracking_code}",
            related_order_id=order.id,
            related_payment_id=payment.id,
            approved_at=now,
        )
        await self.session.flush()

        order.status = OrderStatus.CREATING_SERVICE.value
        result = await self._complete_order(order, now)
        if not result.waiting_inventory:
            order.status = OrderStatus.COMPLETED.value
            order.completed_at = now
            await self._record_discount_usage(order, now)
            if self.settings is not None:
                await AffiliateService(self.session, self.settings).create_commissions_for_order(order.id)
        await self.session.commit()

        return ApprovedPaymentResult(
            **{**result.__dict__, "wallet_balance": user.wallet_balance},
        )

    async def _load_payment_for_update(self, payment_id: int) -> Payment | None:
        return await self.session.scalar(
            select(Payment)
            .options(
                joinedload(Payment.user),
                joinedload(Payment.order).joinedload(Order.user),
                joinedload(Payment.order).joinedload(Order.plan),
                joinedload(Payment.order).joinedload(Order.renewal_service),
            )
            .where(Payment.id == payment_id)
            .with_for_update(of=Payment)
        )

    @staticmethod
    def _is_unpaid_order_expired(order: Order, payment: Payment) -> bool:
        return OrderService.is_order_expired(order)

    async def _complete_order(self, order: Order, now: datetime) -> ApprovedPaymentResult:
        if order.order_kind == OrderKind.RENEWAL.value:
            return await self._complete_renewal(order, now)
        return await self._complete_purchase(order, now)

    async def _record_discount_usage(self, order: Order, now: datetime) -> None:
        if not order.discount_code or order.discount_amount <= 0:
            return

        dice_roll = await DiceRollsRepository(self.session).get_by_discount_code(order.discount_code)
        if dice_roll is not None:
            dice_roll.used = True

        await WalletTransactionsRepository(self.session).create(
            user_id=order.user_id,
            amount=order.discount_amount,
            type=WalletTransactionType.DISCOUNT.value,
            status=WalletTransactionStatus.APPROVED.value,
            description=f"تخفیف سفارش {order.tracking_code}",
            related_order_id=order.id,
            related_payment_id=order.payment.id if order.payment else None,
            approved_at=now,
        )


    async def _complete_purchase(self, order: Order, now: datetime) -> ApprovedPaymentResult:
        plan = order.plan
        user = order.user
        username = order.custom_username or f"user{user.telegram_id}"

        # 1. Fetch the Control D Profile ID mapped to this plan
        profile_id = plan.controld_profile_id
        if not profile_id:
            profile_id = self.settings.controld_profile_id if self.settings else ""

        if not profile_id:
            raise PaymentApprovalError("Control D Profile ID is not configured for this plan")

        # 2. Generate a unique name using order tracking code to prevent collisions
        unique_device_name = f"tg_user_{user.telegram_id}_{order.tracking_code}"
        
        # 3. Call Control D API with the plan's duration_hours
        dns_data = await create_dns_device(
            tg_user_id=user.telegram_id, 
            profile_id=profile_id,
            duration_hours=plan.duration_hours,
            device_name=unique_device_name
        )
        
        if dns_data is None:
            order.status = OrderStatus.FAILED.value
            await self.session.commit()
            raise PaymentApprovalError("Failed to provision DNS endpoint on Control D API")

       # Locate the return statement of your _complete_purchase function (around line 304) and update:

        config_link = dns_data["doh"]
        subscription_link = dns_data["dot"]
        device_id = dns_data["device_id"]
        ipv4 = dns_data.get("ipv4")
        ipv6 = dns_data.get("ipv6")
        
        # --- FIXED: Extract advanced parameters ---
        resolver_id = dns_data.get("resolver_id")
        stamp = dns_data.get("stamp")
        # -------------------------------------------

        services = ServicesRepository(self.session)
        new_service = await services.create(
            user_id=user.id,
            order_id=order.id,
            plan_id=plan.id,
            config_inventory_id=None,
            username=username,
            config_link=config_link,
            subscription_link=subscription_link,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_hours,
            expire_at=now + timedelta(hours=plan.duration_hours),
            status=VPNServiceStatus.ACTIVE.value,
        )
        
        new_service.controld_device_id = device_id
        await self.session.flush()

        reward_amount = await self.app_settings.get_referral_reward_amount()
        await ReferralService(self.session).grant_first_purchase_reward(
            user=user,
            order=order,
            amount=reward_amount,
        )

        return ApprovedPaymentResult(
            user_telegram_id=user.telegram_id,
            order_kind=OrderKind.PURCHASE.value,
            service_username=username,
            plan_title=plan.title,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_hours,
            config_link=config_link,
            subscription_link=subscription_link,
            plan_id=plan.id,
            ipv4=ipv4,
            ipv6=ipv6,
            # --- FIXED: Return advanced fields ---
            resolver_id=resolver_id,
            stamp=stamp
            # --------------------------------------
        )

    async def _complete_renewal(self, order: Order, now: datetime) -> ApprovedPaymentResult:
        plan = order.plan
        user = order.user
        service = order.renewal_service
        if service is None:
            raise PaymentApprovalError("Renewal service not found")

        # Since active DNS configurations on Control D do not auto-expire unless we manually delete them,
        # we can renew the customer locally simply by extending their expire date in our database.
        current_expire = service.expire_at
        if current_expire.tzinfo is None:
            current_expire = current_expire.replace(tzinfo=timezone.utc)

        # --- FIXED: Accumulate time using hours instead of days ---
        if current_expire > now:
            new_expire_at = current_expire + timedelta(hours=plan.duration_hours)
        else:
            new_expire_at = now + timedelta(hours=plan.duration_hours)
        # ----------------------------------------------------------

        service.expire_at = new_expire_at
        service.status = VPNServiceStatus.ACTIVE.value
        await self.session.flush()

        # --- FIXED: Update the TTL on Control D for the renewal ---
        new_disable_ttl = int(new_expire_at.timestamp())
        controld_service = ControlDService(self.settings)
        await controld_service.update_device(
            device_id=service.controld_device_id,
            disable_ttl=new_disable_ttl
        )
        # ----------------------------------------------------------

        return ApprovedPaymentResult(
            user_telegram_id=user.telegram_id,
            order_kind=OrderKind.RENEWAL.value,
            service_username=service.username,
            plan_title=plan.title,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_hours,  # Pass hours cleanly
            config_link=service.config_link,
            subscription_link=service.subscription_link,
            new_expire_at=new_expire_at,
            plan_id=plan.id,
        )