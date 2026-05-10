"""initial schema

Revision ID: 20260510_0001
Revises:
Create Date: 2026-05-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260510_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("wallet_balance", sa.Integer(), server_default="0", nullable=False),
        sa.Column("referral_code", sa.String(length=64), nullable=False),
        sa.Column("referred_by_id", sa.Integer(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["referred_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("referral_code"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index(op.f("ix_users_referral_code"), "users", ["referral_code"], unique=False)
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=False)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("volume_gb", sa.Integer(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("custom_username", sa.String(length=64), nullable=True),
        sa.Column("tracking_code", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending_username", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tracking_code"),
    )
    op.create_index(op.f("ix_orders_plan_id"), "orders", ["plan_id"], unique=False)
    op.create_index(op.f("ix_orders_tracking_code"), "orders", ["tracking_code"], unique=False)
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("authority", sa.String(length=255), nullable=True),
        sa.Column("ref_id", sa.String(length=255), nullable=True),
        sa.Column("receipt_file_id", sa.String(length=255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_payments_order_id"), "payments", ["order_id"], unique=False)
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)

    op.create_table(
        "vpn_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("config_link", sa.Text(), nullable=True),
        sa.Column("subscription_link", sa.Text(), nullable=True),
        sa.Column("volume_gb", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_vpn_services_order_id"), "vpn_services", ["order_id"], unique=False)
    op.create_index(op.f("ix_vpn_services_plan_id"), "vpn_services", ["plan_id"], unique=False)
    op.create_index(op.f("ix_vpn_services_user_id"), "vpn_services", ["user_id"], unique=False)
    op.create_index(op.f("ix_vpn_services_username"), "vpn_services", ["username"], unique=False)

    plans_table = sa.table(
        "plans",
        sa.column("title", sa.String),
        sa.column("description", sa.Text),
        sa.column("duration_days", sa.Integer),
        sa.column("volume_gb", sa.Integer),
        sa.column("price", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        plans_table,
        [
            {
                "title": "⚡ پلن S | 1 ماهه",
                "description": None,
                "duration_days": 30,
                "volume_gb": 5,
                "price": 1100000,
                "is_active": True,
                "sort_order": 10,
            },
            {
                "title": "💎 پلن L | 1 ماهه",
                "description": None,
                "duration_days": 30,
                "volume_gb": 10,
                "price": 2100000,
                "is_active": True,
                "sort_order": 20,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vpn_services_username"), table_name="vpn_services")
    op.drop_index(op.f("ix_vpn_services_user_id"), table_name="vpn_services")
    op.drop_index(op.f("ix_vpn_services_plan_id"), table_name="vpn_services")
    op.drop_index(op.f("ix_vpn_services_order_id"), table_name="vpn_services")
    op.drop_table("vpn_services")
    op.drop_index(op.f("ix_payments_user_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_order_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_tracking_code"), table_name="orders")
    op.drop_index(op.f("ix_orders_plan_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_table("plans")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_index(op.f("ix_users_referral_code"), table_name="users")
    op.drop_table("users")
