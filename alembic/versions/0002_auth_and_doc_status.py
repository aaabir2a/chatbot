"""org auth fields + document status

Revision ID: 0002_auth_status
Revises: 0001_init
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_auth_status"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("email", sa.String(length=320), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch.create_index("ix_organizations_email", ["email"], unique=True)

    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "status", sa.String(length=20), nullable=False, server_default="done"
            )
        )
        batch.add_column(sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("error")
        batch.drop_column("status")
    with op.batch_alter_table("organizations") as batch:
        batch.drop_index("ix_organizations_email")
        batch.drop_column("password_hash")
        batch.drop_column("email")
