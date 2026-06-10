"""widen wallet money columns

Revision ID: 20260608_0009
Revises: fd17ba4d834a
Create Date: 2026-06-08 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0009"
down_revision = "fd17ba4d834a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "wallet_balance",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        existing_server_default="0",
        postgresql_using="wallet_balance::bigint",
    )
    op.alter_column(
        "payments",
        "amount",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using="amount::bigint",
    )
    op.alter_column(
        "wallet_transactions",
        "amount",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using="amount::bigint",
    )
    op.alter_column(
        "wallet_withdrawal_requests",
        "amount",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using="amount::bigint",
    )


def downgrade() -> None:
    op.alter_column(
        "wallet_withdrawal_requests",
        "amount",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="amount::integer",
    )
    op.alter_column(
        "wallet_transactions",
        "amount",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="amount::integer",
    )
    op.alter_column(
        "payments",
        "amount",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="amount::integer",
    )
    op.alter_column(
        "users",
        "wallet_balance",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default="0",
        postgresql_using="wallet_balance::integer",
    )
