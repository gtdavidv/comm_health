"""Initial schema: posts, comments, fetch_records

Revision ID: 001
Revises:
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reddit_id", sa.String(20), nullable=False),
        sa.Column("subreddit", sa.String(100), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("num_comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("reddit_id", name="uq_posts_reddit_id"),
    )
    op.create_index("ix_posts_subreddit_created", "posts", ["subreddit", "created_utc"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reddit_id", sa.String(20), nullable=False),
        sa.Column("post_reddit_id", sa.String(20), nullable=False),
        sa.Column("subreddit", sa.String(100), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("reddit_id", name="uq_comments_reddit_id"),
    )
    op.create_index("ix_comments_subreddit_created", "comments", ["subreddit", "created_utc"])
    op.create_index("ix_comments_post_reddit_id", "comments", ["post_reddit_id"])

    op.create_table(
        "fetch_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("subreddit", sa.String(100), nullable=False),
        sa.Column("fetched_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("post_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fetch_records_subreddit", "fetch_records", ["subreddit"])


def downgrade() -> None:
    op.drop_table("fetch_records")
    op.drop_table("comments")
    op.drop_table("posts")
