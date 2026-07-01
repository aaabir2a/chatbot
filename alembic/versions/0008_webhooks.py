"""org outbound webhook config

Revision ID: 0008_webhooks
Revises: 0007_crm_keys
Create Date: 2026-06-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_webhooks"
down_revision: Union[str, None] = "0007_crm_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("webhook_url", sa.String(length=1024), nullable=True))
        batch.add_column(sa.Column("webhook_secret", sa.String(length=128), nullable=True))
        batch.add_column(
            sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("webhook_enabled")
        batch.drop_column("webhook_secret")
        batch.drop_column("webhook_url")
