"""add controld_device_id to vpn_services

Revision ID: 20260606_0008
Revises: e8ce696ed17a
Create Date: 2026-06-06 13:30:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260606_0008"
down_revision = "e8ce696ed17a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE vpn_services ADD COLUMN IF NOT EXISTS controld_device_id VARCHAR(128);"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE vpn_services DROP COLUMN IF EXISTS controld_device_id;"
    )
