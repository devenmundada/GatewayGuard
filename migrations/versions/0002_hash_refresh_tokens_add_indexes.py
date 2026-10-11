"""store refresh tokens hashed; index user_id foreign keys

Existing refresh tokens are deleted (they were stored in plain text and cannot be
converted without the originals), so every user simply logs in again once.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token"), table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "token")
    op.add_column(
        "refresh_tokens", sa.Column("token_hash", sa.String(length=64), nullable=False)
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.execute("DELETE FROM refresh_tokens")
    op.drop_column("refresh_tokens", "token_hash")
    op.add_column(
        "refresh_tokens", sa.Column("token", sa.String(length=500), nullable=False)
    )
    op.create_index(op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=True)
