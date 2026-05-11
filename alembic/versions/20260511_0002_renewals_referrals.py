"""add renewal orders and referral rewards

Revision ID: 20260511_0002
Revises: 20260510_0001
Create Date: 2026-05-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0002"
down_revision = "20260510_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("order_kind", sa.String(length=32), server_default="purchase", nullable=False),
    )
    op.add_column("orders", sa.Column("service_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_orders_service_id"), "orders", ["service_id"], unique=False)
    op.create_foreign_key(
        "fk_orders_service_id_vpn_services",
        "orders",
        "vpn_services",
        ["service_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_id", sa.Integer(), nullable=False),
        sa.Column("referred_user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("referred_user_id"),
    )
    op.create_index(op.f("ix_referral_rewards_order_id"), "referral_rewards", ["order_id"], unique=False)
    op.create_index(op.f("ix_referral_rewards_referred_user_id"), "referral_rewards", ["referred_user_id"], unique=False)
    op.create_index(op.f("ix_referral_rewards_referrer_id"), "referral_rewards", ["referrer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_referral_rewards_referrer_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_referred_user_id"), table_name="referral_rewards")
    op.drop_index(op.f("ix_referral_rewards_order_id"), table_name="referral_rewards")
    op.drop_table("referral_rewards")
    op.drop_constraint("fk_orders_service_id_vpn_services", "orders", type_="foreignkey")
    op.drop_index(op.f("ix_orders_service_id"), table_name="orders")
    op.drop_column("orders", "service_id")
    op.drop_column("orders", "order_kind")
