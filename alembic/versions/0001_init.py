"""init multi-tenant schema

Revision ID: 0001_init
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "chatbots",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("org_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=255), nullable=False),
        sa.Column("welcome_message", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chatbots_org_id", "chatbots", ["org_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("chatbot_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chatbot_id"], ["chatbots.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_api_keys_chatbot_id", "api_keys", ["chatbot_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("chatbot_id", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chatbot_id"], ["chatbots.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_documents_chatbot_id", "documents", ["chatbot_id"])

    op.create_table(
        "chat_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chatbot_id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("assistant_message", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chatbot_id"], ["chatbots.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_logs_chatbot_id", "chat_logs", ["chatbot_id"])
    op.create_index("ix_chat_logs_session_id", "chat_logs", ["session_id"])


def downgrade() -> None:
    op.drop_table("chat_logs")
    op.drop_table("documents")
    op.drop_table("api_keys")
    op.drop_index("ix_chatbots_org_id", table_name="chatbots")
    op.drop_table("chatbots")
    op.drop_table("organizations")
