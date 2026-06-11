"""lead email field + skip re-prompt counter

Revision ID: 0005_lead_email
Revises: 0004_leads
Create Date: 2026-06-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_lead_email"
down_revision: Union[str, None] = "0004_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("email", sa.String(length=320), nullable=True))
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("lead_next_at", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("lead_next_at")
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("email")
