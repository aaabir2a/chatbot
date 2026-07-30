"""chatbot suggested_questions — clickable starter chips in the widget

Revision ID: 0009_suggested_questions
Revises: 0008_webhooks
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_suggested_questions"
down_revision: Union[str, None] = "0008_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chatbots") as batch:
        batch.add_column(sa.Column("suggested_questions", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chatbots") as batch:
        batch.drop_column("suggested_questions")
