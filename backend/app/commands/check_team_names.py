"""
Diagnostic command: checks which teams in upcoming matches are unknown to the model.

A team unknown to DC or Elo causes silent fallback (DC-only or 1500 default),
which may produce poor predictions without any visible error.

Usage:
  uv run python -m backend.app.commands.check_team_names
  uv run python -m backend.app.commands.check_team_names --competition worldcup2026
"""

from __future__ import annotations

import argparse
import difflib
import logging
import sys

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check team name mapping between model and upcoming matches")
    parser.add_argument("--competition", default="worldcup2026")
    args = parser.parse_args()

    from backend.app.database import get_session_factory
    from backend.app.models.competition import Competition
    from backend.app.models.elo_rating import EloRating
    from backend.app.models.match import Match, MatchStatus
    from backend.app.models.model_params import ModelParams
    from backend.app.models.team import Team

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        competition = db.query(Competition).filter_by(slug=args.competition).first()
        if not competition:
            print(f"Competition '{args.competition}' not found in DB. Run seed first.")
            return 1

        # DC model teams
        dc_team_rows = (
            db.query(Team.name)
            .join(ModelParams, ModelParams.team_id == Team.id)
            .filter(ModelParams.competition_id == competition.id)
            .distinct()
            .all()
        )
        dc_teams: set[str] = {r.name for r in dc_team_rows}

        # Elo rated teams (global, not per-competition)
        elo_team_rows = (
            db.query(Team.name)
            .join(EloRating, EloRating.team_id == Team.id)
            .all()
        )
        elo_teams: set[str] = {r.name for r in elo_team_rows}

        # Upcoming matches
        upcoming = (
            db.query(Match)
            .filter(
                Match.competition_id == competition.id,
                Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]),
            )
            .all()
        )

        all_model_teams = dc_teams | elo_teams

        print(f"\n=== Team Name Mapping — {args.competition} ===")
        print(f"DC model:  {len(dc_teams)} teams trained")
        print(f"Elo model: {len(elo_teams)} teams rated")
        print(f"Upcoming:  {len(upcoming)} matches\n")

        issues = 0
        for match in upcoming:
            home = match.home_team.name if match.home_team else "?"
            away = match.away_team.name if match.away_team else "?"
            teams = [(home, "home"), (away, "away")]

            row_issues = []
            for name, side in teams:
                in_dc = name in dc_teams
                in_elo = name in elo_teams
                if not in_dc or not in_elo:
                    missing = []
                    if not in_dc:
                        missing.append("DC")
                    if not in_elo:
                        missing.append("Elo")
                    suggestion = _closest(name, all_model_teams)
                    row_issues.append((name, missing, suggestion))

            label = f"{home} vs {away}"
            if not row_issues:
                print(f"  ✅  {label}")
            else:
                print(f"  ❌  {label}")
                for name, missing, suggestion in row_issues:
                    miss_str = " + ".join(missing)
                    sug_str = f'→ ¿"{suggestion}"?' if suggestion else "→ sin coincidencia"
                    print(f"       [{miss_str}] \"{name}\"  {sug_str}")
                issues += 1

        print()
        if issues == 0:
            print(f"✅ Todos los equipos reconocidos por el modelo.")
        else:
            print(f"⚠️  {issues}/{len(upcoming)} partidos con equipos no reconocidos.")
            print()
            print("Cómo corregir:")
            print("  1. Añade un alias en la tabla 'teams' (short_name) que coincida")
            print("     con el nombre del modelo, o")
            print("  2. Renombra el equipo en la tabla 'teams' para que coincida con el")
            print("     nombre usado en el CSV de Kaggle.")
            print()
            print("Nombres disponibles en el modelo DC (muestra):")
            for t in sorted(dc_teams)[:20]:
                print(f"   {t}")
            if len(dc_teams) > 20:
                print(f"   ... y {len(dc_teams) - 20} más")

    return 0 if issues == 0 else 1


def _closest(name: str, candidates: set[str], n: int = 1, cutoff: float = 0.5) -> str | None:
    matches = difflib.get_close_matches(name, candidates, n=n, cutoff=cutoff)
    return matches[0] if matches else None


if __name__ == "__main__":
    sys.exit(main())
