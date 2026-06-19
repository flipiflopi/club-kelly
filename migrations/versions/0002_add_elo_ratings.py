"""Add elo_ratings table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "elo_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("matches_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_elo_ratings_team_id"),
    )
    op.create_index("ix_elo_ratings_team_id", "elo_ratings", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_elo_ratings_team_id", table_name="elo_ratings")
    op.drop_table("elo_ratings")
