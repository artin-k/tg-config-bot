"""add wallet withdrawal requests

Revision ID: 20260516_0007
Revises: 20260514_0006
Create Date: 2026-05-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.config import get_settings


revision = "20260516_0007"
down_revision = "20260514_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallet_withdrawal_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("destination_type", sa.String(length=32), nullable=False),
        sa.Column("destination_number", sa.String(length=64), nullable=False),
        sa.Column("account_holder_name", sa.String(length=255), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("processed_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["processed_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_wallet_withdrawal_requests_processed_by_admin_id"), "wallet_withdrawal_requests", ["processed_by_admin_id"])
    op.create_index(op.f("ix_wallet_withdrawal_requests_status"), "wallet_withdrawal_requests", ["status"])
    op.create_index(op.f("ix_wallet_withdrawal_requests_user_id"), "wallet_withdrawal_requests", ["user_id"])

    op.add_column("wallet_transactions", sa.Column("related_withdrawal_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_wallet_transactions_related_withdrawal_id_wallet_withdrawal_requests"),
        "wallet_transactions",
        "wallet_withdrawal_requests",
        ["related_withdrawal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_wallet_transactions_related_withdrawal_id"), "wallet_transactions", ["related_withdrawal_id"])

    settings = get_settings()
    op.execute(
        """
        INSERT INTO settings (key, value, value_type, description)
        VALUES
            ('WALLET_MIN_WITHDRAW_AMOUNT', '{min_withdraw}', 'int', 'کمترین مبلغ مجاز برای برداشت از کیف پول'),
            ('WALLET_MAX_WITHDRAW_AMOUNT', '{max_withdraw}', 'int', 'بیشترین مبلغ مجاز برداشت از کیف پول؛ 0 یعنی بدون محدودیت')
        ON CONFLICT (key) DO NOTHING
        """.format(
            min_withdraw=int(settings.wallet_min_withdraw_amount),
            max_withdraw=int(settings.wallet_max_withdraw_amount),
        )
    )

    op.execute(
        """
        INSERT INTO wallet_transactions (
            user_id,
            amount,
            type,
            status,
            description,
            approved_at,
            created_at,
            updated_at
        )
        SELECT
            id,
            affiliate_balance,
            'referral_reward',
            'approved',
            'انتقال مانده کمیسیون به کیف پول',
            now(),
            now(),
            now()
        FROM users
        WHERE affiliate_balance > 0
        """
    )
    op.execute(
        """
        UPDATE users
        SET wallet_balance = wallet_balance + affiliate_balance,
            affiliate_total_paid = affiliate_total_paid + affiliate_balance,
            affiliate_balance = 0
        WHERE affiliate_balance > 0
        """
    )
    op.execute(
        """
        UPDATE affiliate_commissions
        SET status = 'paid',
            paid_at = COALESCE(paid_at, now())
        WHERE status = 'approved'
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM settings WHERE key IN ('WALLET_MIN_WITHDRAW_AMOUNT', 'WALLET_MAX_WITHDRAW_AMOUNT')")

    op.drop_index(op.f("ix_wallet_transactions_related_withdrawal_id"), table_name="wallet_transactions")
    op.drop_constraint(
        op.f("fk_wallet_transactions_related_withdrawal_id_wallet_withdrawal_requests"),
        "wallet_transactions",
        type_="foreignkey",
    )
    op.drop_column("wallet_transactions", "related_withdrawal_id")

    op.drop_index(op.f("ix_wallet_withdrawal_requests_user_id"), table_name="wallet_withdrawal_requests")
    op.drop_index(op.f("ix_wallet_withdrawal_requests_status"), table_name="wallet_withdrawal_requests")
    op.drop_index(op.f("ix_wallet_withdrawal_requests_processed_by_admin_id"), table_name="wallet_withdrawal_requests")
    op.drop_table("wallet_withdrawal_requests")
