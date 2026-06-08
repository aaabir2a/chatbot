"""conversations + messages (human-agent handoff)

Revision ID: 0003_handoff
Revises: 0002_auth_status
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_handoff"
down_revision: Union[str, None] = "0002_auth_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("chatbot_id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default="ai"),
        sa.Column("waiting_for_human", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assigned_agent_id", sa.String(length=64), nullable=True),
        sa.Column("assigned_agent_name", sa.String(length=255), nullable=True),
        sa.Column("unread", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chatbot_id"], ["chatbots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chatbot_id", "session_id", name="uq_conv_chatbot_session"),
    )
    op.create_index("ix_conversations_chatbot_id", "conversations", ["chatbot_id"])
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("sender", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("agent_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
