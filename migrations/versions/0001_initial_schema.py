"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-19

Creates all tables from scratch:
  teams, competitions, matches, market_types, model_params,
  predictions, simulated_bets, bankroll_history,
  players, player_match_stats
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── teams ─────────────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("short_name", sa.String(10), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=True),
        sa.Column("team_type", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_teams_id", "teams", ["id"])

    # ── competitions ──────────────────────────────────────────────────────────
    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("competition_type", sa.String(32), nullable=False),
        sa.Column("season", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competitions_slug", "competitions", ["slug"], unique=True)

    # ── players ───────────────────────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("position", sa.String(8), nullable=True),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_players_team_id", "players", ["team_id"])

    # ── matches ───────────────────────────────────────────────────────────────
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("match_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("round", sa.String(64), nullable=True),
        sa.Column("venue", sa.String(128), nullable=True),
        sa.Column("is_neutral", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_matches_competition_id", "matches", ["competition_id"])
    op.create_index("ix_matches_match_date", "matches", ["match_date"])

    # ── player_match_stats ────────────────────────────────────────────────────
    op.create_table(
        "player_match_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("minutes_played", sa.Integer(), nullable=True),
        sa.Column("goals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("yellow_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("red_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shots_on_target", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_player_match_stats_match_id", "player_match_stats", ["match_id"])
    op.create_index("ix_player_match_stats_player_id", "player_match_stats", ["player_id"])

    # ── market_types ──────────────────────────────────────────────────────────
    op.create_table(
        "market_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_types_slug", "market_types", ["slug"], unique=True)

    # ── model_params ──────────────────────────────────────────────────────────
    op.create_table(
        "model_params",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("attack_strength", sa.Float(), nullable=False),
        sa.Column("defense_strength", sa.Float(), nullable=False),
        sa.Column("home_advantage", sa.Float(), nullable=False),
        sa.Column("rho", sa.Float(), nullable=False),
        sa.Column("matches_used", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_params_competition_id", "model_params", ["competition_id"])
    op.create_index("ix_model_params_team_id", "model_params", ["team_id"])

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("market_type_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("model_probability", sa.Float(), nullable=False),
        sa.Column("market_odds", sa.Float(), nullable=True),
        sa.Column("market_probability", sa.Float(), nullable=True),
        sa.Column("edge", sa.Float(), nullable=True),
        sa.Column("closing_odds", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["market_type_id"], ["market_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_match_id", "predictions", ["match_id"])

    # ── simulated_bets ────────────────────────────────────────────────────────
    op.create_table(
        "simulated_bets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("stake_amount", sa.Float(), nullable=False),
        sa.Column("stake_pct", sa.Float(), nullable=False),
        sa.Column("bankroll_before", sa.Float(), nullable=False),
        sa.Column("kelly_fraction", sa.Float(), nullable=False),
        sa.Column("decimal_odds", sa.Float(), nullable=False),
        sa.Column("reasoning_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("profit_loss", sa.Float(), nullable=True),
        sa.Column("bankroll_after", sa.Float(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prediction_id"),
    )
    op.create_index("ix_simulated_bets_prediction_id", "simulated_bets", ["prediction_id"])
    op.create_index("ix_simulated_bets_match_id", "simulated_bets", ["match_id"])

    # ── bankroll_history ──────────────────────────────────────────────────────
    op.create_table(
        "bankroll_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("amount_change", sa.Float(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=False),
        sa.Column("reference_bet_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reference_bet_id"], ["simulated_bets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bankroll_history_reference_bet_id", "bankroll_history", ["reference_bet_id"])


def downgrade() -> None:
    op.drop_table("bankroll_history")
    op.drop_table("simulated_bets")
    op.drop_table("predictions")
    op.drop_table("model_params")
    op.drop_table("market_types")
    op.drop_table("player_match_stats")
    op.drop_table("matches")
    op.drop_table("players")
    op.drop_table("competitions")
    op.drop_table("teams")
