from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import Settings, get_settings
from app.models import (
    AffiliateBeneficiaryType,
    AffiliateCommission,
    AffiliateCommissionStatus,
    Order,
    OrderStatus,
    PaymentStatus,
    User,
    WalletTransactionStatus,
    WalletTransactionType,
)
from app.repositories.wallet_transactions import WalletTransactionsRepository
from app.repositories.users import UsersRepository
from app.utils.formatting import calculate_commission_amount
from app.utils.tracking import generate_referral_code

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AffiliateSummary:
    root_configured: bool
    total_users: int
    root_owner: User | None
    direct_root_users: int
    total_downline_users: int
    orphan_users: int
    completed_orders: int
    total_revenue: int
    root_total_commission: int
    root_paid_commission: int
    root_unpaid_commission: int
    direct_referral_commissions: int
    today_orders: int
    today_revenue: int
    week_orders: int
    week_revenue: int
    month_orders: int
    month_revenue: int


@dataclass(frozen=True)
class ReferralUserStats:
    user: User
    referred_by: User | None
    direct_referrals: int
    total_downline: int
    orders_count: int
    successful_orders_amount: int
    root_commission_from_user: int
    direct_commission_from_user: int
    services_count: int


async def ensure_root_owner(session: AsyncSession, settings: Settings | None = None) -> User | None:
    settings = settings or get_settings()
    if settings.root_admin_telegram_id is None:
        return None

    user = await UsersRepository(session).get_by_telegram_id(settings.root_admin_telegram_id)
    if user is None:
        return None

    if not user.referral_code:
        user.referral_code = generate_referral_code(user.telegram_id)
    user.is_root_admin = True
    user.is_admin = True
    user.referred_by_id = None
    user.referral_depth = 0
    user.referral_path = f"/{user.id}/"
    await session.flush()
    return user


class AffiliateService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def ensure_root_owner(self) -> User | None:
        return await ensure_root_owner(self.session, self.settings)

    async def get_root_owner(self) -> User | None:
        return await self.ensure_root_owner()

    async def apply_start_referral(
        self,
        *,
        user: User,
        is_new_user: bool,
        referral_code: str | None,
    ) -> None:
        if self._is_configured_root(user):
            await self._promote_root_owner(user)
            return

        await self._ensure_referral_path(user)
        if not is_new_user:
            return

        referrer = await self._resolve_start_referrer(user=user, referral_code=referral_code)
        if referrer is None and self.settings.affiliate_default_to_root:
            root = await self.ensure_root_owner()
            if root is not None and root.id != user.id:
                referrer = root

        if referrer is None:
            user.referral_depth = 0
            user.referral_path = f"/{user.id}/"
            await self.session.flush()
            return

        await self.assign_referrer(user=user, referrer=referrer)

    async def assign_referrer(self, *, user: User, referrer: User) -> bool:
        if user.id == referrer.id:
            return False
        if user.referred_by_id is not None:
            return False
        if self._would_create_cycle(user=user, referrer=referrer):
            return False

        await self._ensure_referral_path(referrer)
        user.referred_by_id = referrer.id
        user.referral_depth = (referrer.referral_depth or 0) + 1
        user.referral_path = f"{self._path_prefix(referrer)}{user.id}/"
        await self.session.flush()
        return True

    async def create_commissions_for_order(self, order_id: int) -> list[AffiliateCommission]:
        order = await self.session.scalar(
            select(Order)
            .options(
                joinedload(Order.user),
                joinedload(Order.payment),
                joinedload(Order.vpn_service),
                joinedload(Order.renewal_service),
            )
            .where(Order.id == order_id)
            .with_for_update(of=Order)
        )
        if order is None or order.status != OrderStatus.COMPLETED.value:
            return []
        if order.payment is not None and order.payment.status != PaymentStatus.APPROVED.value:
            return []

        buyer = order.user
        if buyer is None or self._is_root_user(buyer):
            return []

        base_amount = self._commission_base_amount(order)
        if base_amount <= 0:
            return []

        created: list[AffiliateCommission] = []
        root = await self.ensure_root_owner()
        root_created = False
        if root is not None and root.id != buyer.id and self.settings.owner_commission_percent > 0:
            commission = await self._create_approved_commission(
                order=order,
                buyer=buyer,
                beneficiary=root,
                beneficiary_type=AffiliateBeneficiaryType.ROOT_OWNER.value,
                level=0,
                base_amount=base_amount,
                percent=self.settings.owner_commission_percent,
                description=f"کمیسیون مالک ریشه برای سفارش {order.tracking_code}",
            )
            if commission is not None:
                created.append(commission)
                root_created = True

        if self.settings.referral_commission_percent > 0 and buyer.referred_by_id:
            referrer = await self.session.get(User, buyer.referred_by_id, with_for_update=True)
            if (
                referrer is not None
                and referrer.id != buyer.id
                and referrer.affiliate_enabled
                and not (root_created and root is not None and referrer.id == root.id)
            ):
                commission = await self._create_approved_commission(
                    order=order,
                    buyer=buyer,
                    beneficiary=referrer,
                    beneficiary_type=AffiliateBeneficiaryType.DIRECT_REFERRER.value,
                    level=1,
                    base_amount=base_amount,
                    percent=self.settings.referral_commission_percent,
                    description=f"کمیسیون معرف مستقیم برای سفارش {order.tracking_code}",
                )
                if commission is not None:
                    created.append(commission)

        await self.session.flush()
        return created

    async def mark_commission_paid(self, commission_id: int) -> AffiliateCommission | None:
        commission = await self.session.scalar(
            select(AffiliateCommission)
            .options(joinedload(AffiliateCommission.beneficiary))
            .where(AffiliateCommission.id == commission_id)
            .with_for_update(of=AffiliateCommission)
        )
        if commission is None or commission.status != AffiliateCommissionStatus.APPROVED.value:
            return commission

        now = datetime.now(timezone.utc)
        beneficiary = commission.beneficiary
        beneficiary.affiliate_balance = max(beneficiary.affiliate_balance - commission.commission_amount, 0)
        beneficiary.affiliate_total_paid += commission.commission_amount
        commission.status = AffiliateCommissionStatus.PAID.value
        commission.paid_at = now
        await self.session.flush()
        return commission

    async def mark_all_root_approved_paid(self) -> int:
        root = await self.ensure_root_owner()
        if root is None:
            return 0
        commissions = await self.session.scalars(
            select(AffiliateCommission)
            .options(joinedload(AffiliateCommission.beneficiary))
            .where(
                AffiliateCommission.beneficiary_user_id == root.id,
                AffiliateCommission.status == AffiliateCommissionStatus.APPROVED.value,
            )
            .with_for_update(of=AffiliateCommission)
        )
        count = 0
        for commission in commissions.unique().all():
            await self.mark_commission_paid(commission.id)
            count += 1
        return count

    async def reverse_order_commissions(self, order_id: int) -> int:
        commissions = await self.session.scalars(
            select(AffiliateCommission)
            .options(joinedload(AffiliateCommission.beneficiary))
            .where(
                AffiliateCommission.order_id == order_id,
                AffiliateCommission.status.in_(
                    [AffiliateCommissionStatus.APPROVED.value, AffiliateCommissionStatus.PENDING.value]
                ),
            )
            .with_for_update(of=AffiliateCommission)
        )
        count = 0
        for commission in commissions.unique().all():
            if commission.status == AffiliateCommissionStatus.APPROVED.value:
                beneficiary = commission.beneficiary
                beneficiary.affiliate_balance = max(beneficiary.affiliate_balance - commission.commission_amount, 0)
                beneficiary.affiliate_total_earned = max(
                    beneficiary.affiliate_total_earned - commission.commission_amount,
                    0,
                )
            commission.status = AffiliateCommissionStatus.REVERSED.value
            count += 1
        return count

    async def summary(self) -> AffiliateSummary:
        root = await self.ensure_root_owner()
        users_repo = UsersRepository(self.session)
        total_users = await users_repo.count_all()
        orphan_users = await self.count_orphans()
        direct_root_users = await users_repo.count_referrals(root.id) if root is not None else 0
        total_downline_users = await self.count_downline_users(root) if root is not None else 0
        completed_orders, total_revenue = await self._orders_stats()
        today_orders, today_revenue = await self._orders_stats(since=self._start_of_today())
        week_orders, week_revenue = await self._orders_stats(since=datetime.now(timezone.utc) - timedelta(days=7))
        month_orders, month_revenue = await self._orders_stats(since=self._start_of_month())
        root_total_commission = (
            await self._sum_commissions(
                beneficiary_id=root.id,
                beneficiary_type=AffiliateBeneficiaryType.ROOT_OWNER.value,
            )
            if root
            else 0
        )
        root_paid_commission = (
            await self._sum_commissions(
                beneficiary_id=root.id,
                beneficiary_type=AffiliateBeneficiaryType.ROOT_OWNER.value,
                status=AffiliateCommissionStatus.PAID.value,
            )
            if root
            else 0
        )
        root_unpaid_commission = (
            await self._sum_commissions(
                beneficiary_id=root.id,
                beneficiary_type=AffiliateBeneficiaryType.ROOT_OWNER.value,
                status=AffiliateCommissionStatus.APPROVED.value,
            )
            if root
            else 0
        )
        direct_referral_commissions = await self._sum_commissions(
            beneficiary_type=AffiliateBeneficiaryType.DIRECT_REFERRER.value,
        )
        return AffiliateSummary(
            root_configured=self.settings.root_admin_telegram_id is not None,
            total_users=total_users,
            root_owner=root,
            direct_root_users=direct_root_users,
            total_downline_users=total_downline_users,
            orphan_users=orphan_users,
            completed_orders=completed_orders,
            total_revenue=total_revenue,
            root_total_commission=root_total_commission,
            root_paid_commission=root_paid_commission,
            root_unpaid_commission=root_unpaid_commission,
            direct_referral_commissions=direct_referral_commissions,
            today_orders=today_orders,
            today_revenue=today_revenue,
            week_orders=week_orders,
            week_revenue=week_revenue,
            month_orders=month_orders,
            month_revenue=month_revenue,
        )

    async def direct_referrals_with_sales(
        self,
        *,
        parent_id: int,
        page: int = 0,
        page_size: int = 10,
    ) -> tuple[list[tuple[User, int, int, int]], bool]:
        offset = max(page, 0) * page_size
        result = await self.session.execute(
            select(
                User,
                func.count(Order.id).label("orders_count"),
                func.coalesce(func.sum(Order.amount), 0).label("revenue"),
            )
            .outerjoin(
                Order,
                and_(Order.user_id == User.id, Order.status == OrderStatus.COMPLETED.value),
            )
            .where(User.referred_by_id == parent_id)
            .group_by(User.id)
            .order_by(User.created_at.asc())
            .offset(offset)
            .limit(page_size + 1)
        )
        rows = [(row[0], int(row[1] or 0), int(row[2] or 0)) for row in result.all()]
        has_next = len(rows) > page_size
        visible_rows = rows[:page_size]
        enriched: list[tuple[User, int, int, int]] = []
        for user, orders_count, revenue in visible_rows:
            children_count = await UsersRepository(self.session).count_referrals(user.id)
            enriched.append((user, orders_count, revenue, children_count))
        return enriched, has_next

    async def user_detail(self, user: User) -> ReferralUserStats:
        direct_referrals = await UsersRepository(self.session).count_referrals(user.id)
        total_downline = await self.count_downline_users(user)
        orders_count = int(
            await self.session.scalar(
                select(func.count()).select_from(Order).where(
                    Order.user_id == user.id,
                    Order.status == OrderStatus.COMPLETED.value,
                )
            )
            or 0
        )
        successful_orders_amount = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(Order.amount), 0)).where(
                    Order.user_id == user.id,
                    Order.status == OrderStatus.COMPLETED.value,
                )
            )
            or 0
        )
        services_count = int(
            await self.session.scalar(
                select(func.count()).select_from(User).join(User.services).where(User.id == user.id)
            )
            or 0
        )
        root_commission = await self._sum_commissions(
            buyer_id=user.id,
            beneficiary_type=AffiliateBeneficiaryType.ROOT_OWNER.value,
        )
        direct_commission = await self._sum_commissions(
            buyer_id=user.id,
            beneficiary_type=AffiliateBeneficiaryType.DIRECT_REFERRER.value,
        )
        referred_by = await self.session.get(User, user.referred_by_id) if user.referred_by_id else None
        return ReferralUserStats(
            user=user,
            referred_by=referred_by,
            direct_referrals=direct_referrals,
            total_downline=total_downline,
            orders_count=orders_count,
            successful_orders_amount=successful_orders_amount,
            root_commission_from_user=root_commission,
            direct_commission_from_user=direct_commission,
            services_count=services_count,
        )

    async def referral_page_stats(self, user: User) -> dict[str, int]:
        direct_count = await UsersRepository(self.session).count_referrals(user.id)
        successful_referral_orders = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Order)
                .join(User, Order.user_id == User.id)
                .where(User.referred_by_id == user.id, Order.status == OrderStatus.COMPLETED.value)
            )
            or 0
        )
        total_commission = await self._sum_commissions(beneficiary_id=user.id)
        unpaid_commission = await self._sum_commissions(
            beneficiary_id=user.id,
            status=AffiliateCommissionStatus.APPROVED.value,
        )
        return {
            "direct_count": direct_count,
            "successful_referral_orders": successful_referral_orders,
            "total_commission": total_commission,
            "unpaid_commission": unpaid_commission,
        }

    async def commission_totals(self) -> dict[str, int]:
        return {
            "total": await self._sum_commissions(),
            "approved": await self._sum_commissions(status=AffiliateCommissionStatus.APPROVED.value),
            "paid": await self._sum_commissions(status=AffiliateCommissionStatus.PAID.value),
            "root": await self._sum_commissions(beneficiary_type=AffiliateBeneficiaryType.ROOT_OWNER.value),
            "direct": await self._sum_commissions(beneficiary_type=AffiliateBeneficiaryType.DIRECT_REFERRER.value),
        }

    async def recent_commissions(
        self,
        *,
        limit: int = 10,
        beneficiary_type: str | None = None,
        status: str | None = None,
    ) -> list[AffiliateCommission]:
        conditions = []
        if beneficiary_type is not None:
            conditions.append(AffiliateCommission.beneficiary_type == beneficiary_type)
        if status is not None:
            conditions.append(AffiliateCommission.status == status)
        result = await self.session.scalars(
            select(AffiliateCommission)
            .options(
                joinedload(AffiliateCommission.buyer),
                joinedload(AffiliateCommission.beneficiary),
                joinedload(AffiliateCommission.order),
            )
            .where(*conditions)
            .order_by(AffiliateCommission.created_at.desc())
            .limit(limit)
        )
        return list(result.unique().all())

    async def approved_root_commissions(self, *, limit: int = 10) -> list[AffiliateCommission]:
        root = await self.ensure_root_owner()
        if root is None:
            return []
        result = await self.session.scalars(
            select(AffiliateCommission)
            .options(
                joinedload(AffiliateCommission.buyer),
                joinedload(AffiliateCommission.beneficiary),
                joinedload(AffiliateCommission.order),
            )
            .where(
                AffiliateCommission.beneficiary_user_id == root.id,
                AffiliateCommission.status == AffiliateCommissionStatus.APPROVED.value,
            )
            .order_by(AffiliateCommission.created_at.asc())
            .limit(limit)
        )
        return list(result.unique().all())

    async def recent_downline_orders(
        self,
        *,
        page: int = 0,
        page_size: int = 10,
    ) -> tuple[list[Order], bool]:
        root = await self.ensure_root_owner()
        user_ids: list[int]
        if root is None:
            result = await self.session.scalars(select(User.id).where(User.referred_by_id.is_not(None)))
            user_ids = list(result.all())
        else:
            user_ids = await self._downline_user_ids(root)

        if not user_ids:
            return [], False

        result = await self.session.scalars(
            select(Order)
            .options(
                joinedload(Order.user).joinedload(User.referred_by),
                joinedload(Order.plan),
            )
            .where(Order.status == OrderStatus.COMPLETED.value, Order.user_id.in_(user_ids))
            .order_by(Order.created_at.desc())
            .offset(max(page, 0) * page_size)
            .limit(page_size + 1)
        )
        orders = list(result.unique().all())
        return orders[:page_size], len(orders) > page_size

    async def count_orphans(self) -> int:
        root = await self.ensure_root_owner()
        conditions = [User.referred_by_id.is_(None), User.is_root_admin.is_(False)]
        if root is not None:
            conditions.append(User.id != root.id)
        return int(await self.session.scalar(select(func.count()).select_from(User).where(*conditions)) or 0)

    async def attach_orphans_to_root(self) -> int:
        root = await self.ensure_root_owner()
        if root is None:
            return 0
        await self._ensure_referral_path(root)
        result = await self.session.scalars(
            select(User)
            .where(
                User.id != root.id,
                User.referred_by_id.is_(None),
                User.is_root_admin.is_(False),
            )
            .order_by(User.id.asc())
        )
        count = 0
        for user in result.all():
            user.referred_by_id = root.id
            user.referral_depth = (root.referral_depth or 0) + 1
            user.referral_path = f"{self._path_prefix(root)}{user.id}/"
            count += 1
        await self.session.flush()
        return count

    async def attach_user_to_root(self, user: User) -> bool:
        root = await self.ensure_root_owner()
        if root is None or user.id == root.id or user.referred_by_id is not None or user.is_root_admin:
            return False
        return await self.assign_referrer(user=user, referrer=root)

    async def count_downline_users(self, user: User | None) -> int:
        if user is None:
            return 0
        return len(await self._downline_user_ids(user))

    async def rebuild_commissions_for_completed_orders(self) -> tuple[int, int, int]:
        result = await self.session.scalars(
            select(Order.id).where(Order.status == OrderStatus.COMPLETED.value).order_by(Order.id.asc())
        )
        processed = 0
        created_total = 0
        skipped = 0
        for order_id in result.all():
            processed += 1
            created = await self.create_commissions_for_order(order_id)
            if created:
                created_total += len(created)
            else:
                skipped += 1
        return processed, created_total, skipped

    async def _resolve_start_referrer(self, *, user: User, referral_code: str | None) -> User | None:
        if not referral_code:
            return None
        referrer = await UsersRepository(self.session).get_by_referral_code(referral_code)
        if referrer is None or referrer.id == user.id or not referrer.affiliate_enabled:
            return None
        await self._ensure_referral_path(referrer)
        if self._would_create_cycle(user=user, referrer=referrer):
            return None
        return referrer

    async def _promote_root_owner(self, user: User) -> None:
        if not user.referral_code:
            user.referral_code = generate_referral_code(user.telegram_id)
        user.is_root_admin = True
        user.is_admin = True
        user.referred_by_id = None
        user.referral_depth = 0
        user.referral_path = f"/{user.id}/"
        await self.session.flush()

    async def _ensure_referral_path(self, user: User) -> None:
        if user.referral_path and user.referral_path.endswith(f"/{user.id}/"):
            return
        if user.referred_by_id:
            parent = await self.session.get(User, user.referred_by_id)
            if parent is not None and parent.id != user.id and not self._would_create_cycle(user=user, referrer=parent):
                await self._ensure_referral_path(parent)
                user.referral_depth = (parent.referral_depth or 0) + 1
                user.referral_path = f"{self._path_prefix(parent)}{user.id}/"
                await self.session.flush()
                return
        user.referral_depth = 0
        user.referral_path = f"/{user.id}/"
        await self.session.flush()

    async def _create_approved_commission(
        self,
        *,
        order: Order,
        buyer: User,
        beneficiary: User,
        beneficiary_type: str,
        level: int,
        base_amount: int,
        percent: float,
        description: str,
    ) -> AffiliateCommission | None:
        commission_amount = calculate_commission_amount(base_amount, percent)
        if commission_amount <= 0:
            return None

        existing = await self.session.scalar(
            select(AffiliateCommission)
            .where(
                AffiliateCommission.order_id == order.id,
                AffiliateCommission.beneficiary_user_id == beneficiary.id,
            )
            .with_for_update()
        )
        if existing is not None:
            return None

        now = datetime.now(timezone.utc)
        commission = AffiliateCommission(
            order_id=order.id,
            buyer_user_id=buyer.id,
            beneficiary_user_id=beneficiary.id,
            beneficiary_type=beneficiary_type,
            level=level,
            base_amount=base_amount,
            percent=float(percent),
            commission_amount=commission_amount,
            status=AffiliateCommissionStatus.PAID.value,
            description=description,
            approved_at=now,
            paid_at=now,
        )
        beneficiary.wallet_balance += commission_amount
        beneficiary.affiliate_total_earned += commission_amount
        beneficiary.affiliate_total_paid += commission_amount
        self.session.add(commission)
        await self.session.flush()
        await WalletTransactionsRepository(self.session).create(
            user_id=beneficiary.id,
            amount=commission_amount,
            type=WalletTransactionType.REFERRAL_REWARD.value,
            status=WalletTransactionStatus.APPROVED.value,
            description="کمیسیون زیرمجموعه‌گیری",
            related_order_id=order.id,
            approved_at=now,
        )
        logger.info(
            "affiliate_commission_created",
            commission_id=commission.id,
            order_id=order.id,
            buyer_user_id=buyer.id,
            beneficiary_user_id=beneficiary.id,
            beneficiary_type=beneficiary_type,
            commission_amount=commission_amount,
        )
        return commission

    def _commission_base_amount(self, order: Order) -> int:
        final_amount = getattr(order, "final_amount", None)
        if self.settings.commission_base == "final_amount" and final_amount is not None:
            return int(final_amount or 0)
        return int(order.amount or 0)

    def _is_configured_root(self, user: User) -> bool:
        return self.settings.root_admin_telegram_id is not None and user.telegram_id == self.settings.root_admin_telegram_id

    def _is_root_user(self, user: User) -> bool:
        return bool(user.is_root_admin or self._is_configured_root(user))

    def _would_create_cycle(self, *, user: User, referrer: User) -> bool:
        if user.id == referrer.id:
            return True
        return bool(referrer.referral_path and f"/{user.id}/" in referrer.referral_path)

    def _path_prefix(self, user: User) -> str:
        if user.referral_path:
            return user.referral_path
        return f"/{user.id}/"

    async def _downline_user_ids(self, root: User) -> list[int]:
        await self._ensure_referral_path(root)
        prefix = self._path_prefix(root)
        path_result = await self.session.scalars(
            select(User.id).where(User.id != root.id, User.referral_path.like(f"{prefix}%"))
        )
        ids = set(path_result.all())

        rows = await self.session.execute(select(User.id, User.referred_by_id))
        children_by_parent: dict[int, list[int]] = defaultdict(list)
        for user_id, referrer_id in rows.all():
            if referrer_id is not None and user_id != referrer_id:
                children_by_parent[int(referrer_id)].append(int(user_id))

        queue: deque[int] = deque(children_by_parent.get(root.id, []))
        while queue:
            user_id = queue.popleft()
            if user_id == root.id:
                continue
            ids.add(user_id)
            queue.extend(children_by_parent.get(user_id, []))
        return list(ids)

    async def _orders_stats(
        self,
        *,
        since: datetime | None = None,
        user_ids: list[int] | None = None,
    ) -> tuple[int, int]:
        conditions = [Order.status == OrderStatus.COMPLETED.value]
        if since is not None:
            conditions.append(Order.created_at >= since)
        if user_ids is not None:
            if not user_ids:
                return 0, 0
            conditions.append(Order.user_id.in_(user_ids))
        row = await self.session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.amount), 0),
            ).where(*conditions)
        )
        count, revenue = row.one()
        return int(count or 0), int(revenue or 0)

    async def _sum_commissions(
        self,
        *,
        beneficiary_id: int | None = None,
        buyer_id: int | None = None,
        beneficiary_type: str | None = None,
        status: str | None = None,
    ) -> int:
        conditions = []
        if beneficiary_id is not None:
            conditions.append(AffiliateCommission.beneficiary_user_id == beneficiary_id)
        if buyer_id is not None:
            conditions.append(AffiliateCommission.buyer_user_id == buyer_id)
        if beneficiary_type is not None:
            conditions.append(AffiliateCommission.beneficiary_type == beneficiary_type)
        if status is not None:
            conditions.append(AffiliateCommission.status == status)
        return int(
            await self.session.scalar(
                select(func.coalesce(func.sum(AffiliateCommission.commission_amount), 0)).where(*conditions)
            )
            or 0
        )

    @staticmethod
    def _start_of_today() -> datetime:
        now = datetime.now(timezone.utc)
        return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    @staticmethod
    def _start_of_month() -> datetime:
        now = datetime.now(timezone.utc)
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)
