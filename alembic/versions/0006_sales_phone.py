"""chatbot sales_phone for contact/no-answer lead prompts

Revision ID: 0006_sales_phone
Revises: 0005_lead_email
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_sales_phone"
down_revision: Union[str, None] = "0005_lead_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chatbots") as batch:
        batch.add_column(sa.Column("sales_phone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chatbots") as batch:
        batch.drop_column("sales_phone")
