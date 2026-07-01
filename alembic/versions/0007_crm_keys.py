"""crm_keys table for external CRM integrations

Revision ID: 0007_crm_keys
Revises: 0006_sales_phone
Create Date: 2026-06-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_crm_keys"
down_revision: Union[str, None] = "0006_sales_phone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_crm_keys_org_id", "crm_keys", ["org_id"])
    op.create_index("ix_crm_keys_prefix", "crm_keys", ["prefix"])
    op.create_index("ix_crm_keys_key_hash", "crm_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("crm_keys")
