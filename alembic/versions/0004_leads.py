"""lead capture: leads table + chatbot/conversation flags

Revision ID: 0004_leads
Revises: 0003_handoff
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_leads"
down_revision: Union[str, None] = "0003_handoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chatbots") as batch:
        batch.add_column(
            sa.Column("lead_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(
            sa.Column("lead_after_messages", sa.Integer(), nullable=False, server_default="3")
        )

    with op.batch_alter_table("conversations") as batch:
        batch.add_column(
            sa.Column("lead_prompted", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("lead_captured", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "leads",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("chatbot_id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chatbot_id"], ["chatbots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_leads_chatbot_id", "leads", ["chatbot_id"])
    op.create_index("ix_leads_conversation_id", "leads", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("leads")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("lead_captured")
        batch.drop_column("lead_prompted")
    with op.batch_alter_table("chatbots") as batch:
        batch.drop_column("lead_after_messages")
        batch.drop_column("lead_enabled")
