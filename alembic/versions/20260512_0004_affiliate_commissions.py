"""add root affiliate commissions

Revision ID: 20260512_0004
Revises: 20260511_0003
Create Date: 2026-05-12 00:00:00.000000
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "20260512_0004"
down_revision = "20260511_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_depth", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("referral_path", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("is_root_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("affiliate_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("users", sa.Column("affiliate_balance", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("affiliate_total_earned", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("affiliate_total_paid", sa.Integer(), server_default="0", nullable=False))

    op.execute("UPDATE users SET referral_path = '/' || CAST(id AS VARCHAR) || '/' WHERE referral_path IS NULL")
    root_telegram_id = (os.getenv("ROOT_ADMIN_TELEGRAM_ID") or "").strip()
    if root_telegram_id.isdigit():
        op.execute(
            sa.text(
                """
                UPDATE users
                SET is_root_admin = true,
                    is_admin = true,
                    referred_by_id = NULL,
                    referral_depth = 0,
                    referral_path = '/' || CAST(id AS VARCHAR) || '/'
                WHERE telegram_id = :telegram_id
                """
            ).bindparams(telegram_id=int(root_telegram_id))
        )
    op.execute(
        """
        WITH RECURSIVE referral_tree(id, depth, path) AS (
            SELECT id, 0, '/' || CAST(id AS VARCHAR) || '/'
            FROM users
            WHERE referred_by_id IS NULL
            UNION ALL
            SELECT users.id,
                   referral_tree.depth + 1,
                   referral_tree.path || CAST(users.id AS VARCHAR) || '/'
            FROM users
            JOIN referral_tree ON users.referred_by_id = referral_tree.id
            WHERE POSITION('/' || CAST(users.id AS VARCHAR) || '/' IN referral_tree.path) = 0
        )
        UPDATE users
        SET referral_depth = referral_tree.depth,
            referral_path = referral_tree.path
        FROM referral_tree
        WHERE users.id = referral_tree.id
        """
    )

    op.create_table(
        "affiliate_commissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("buyer_user_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_user_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_type", sa.String(length=32), nullable=False),
        sa.Column("level", sa.Integer(), server_default="0", nullable=False),
        sa.Column("base_amount", sa.Integer(), nullable=False),
        sa.Column("percent", sa.Float(), nullable=False),
        sa.Column("commission_amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="approved", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["beneficiary_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id", "beneficiary_user_id", name="uq_affiliate_commissions_order_beneficiary"),
    )
    op.create_index(op.f("ix_affiliate_commissions_beneficiary_user_id"), "affiliate_commissions", ["beneficiary_user_id"])
    op.create_index(op.f("ix_affiliate_commissions_buyer_user_id"), "affiliate_commissions", ["buyer_user_id"])
    op.create_index(op.f("ix_affiliate_commissions_order_id"), "affiliate_commissions", ["order_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_affiliate_commissions_order_id"), table_name="affiliate_commissions")
    op.drop_index(op.f("ix_affiliate_commissions_buyer_user_id"), table_name="affiliate_commissions")
    op.drop_index(op.f("ix_affiliate_commissions_beneficiary_user_id"), table_name="affiliate_commissions")
    op.drop_table("affiliate_commissions")
    op.drop_column("users", "affiliate_total_paid")
    op.drop_column("users", "affiliate_total_earned")
    op.drop_column("users", "affiliate_balance")
    op.drop_column("users", "affiliate_enabled")
    op.drop_column("users", "is_root_admin")
    op.drop_column("users", "referral_path")
    op.drop_column("users", "referral_depth")
