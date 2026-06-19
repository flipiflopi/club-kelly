"""
Telegram notifications for Club Kelly.

Sends a message for every World Cup match:
  - Bet placed: which outcome, stake, edge, odds
  - No bet: why not (no edge vs market)
  - Bet resolved: won/lost, P&L, new bankroll
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_HASHTAGS = "#ClubKelly #Mundial2026"

_OUTCOME_ES = {
    "home": None,   # replaced by home team name
    "draw": "Empate",
    "away": None,   # replaced by away team name
    "over": "Más goles",
    "under": "Menos goles",
    "yes": "Ambos marcan",
    "no": "No ambos marcan",
}


def _outcome_label(outcome: str, home: str, away: str) -> str:
    if outcome == "home":
        return home
    if outcome == "away":
        return away
    return _OUTCOME_ES.get(outcome, outcome)


def _format_date(dt: datetime) -> str:
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%-d %b %H:%M UTC")
    except Exception:
        return str(dt)


def _send(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
        logger.info("Telegram message sent to %s", chat_id)
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


# ── Public notification functions ─────────────────────────────────────────────


def notify_no_bet(
    home_team: str,
    away_team: str,
    match_date: datetime,
    round_name: str | None,
    predictions: list[dict],
    token: str,
    chat_id: str,
) -> None:
    """
    Called when the model evaluated a match but decided not to bet.
    predictions: list of {"outcome", "model_probability", "market_odds", "edge_pct"}
    """
    round_str = f" · {round_name}" if round_name else ""
    date_str = _format_date(match_date)

    # Best pick (highest model probability)
    best = max(predictions, key=lambda p: p["model_probability"]) if predictions else None

    lines = [
        f"⚖️ <b>Sin apuesta</b>",
        f"🏟 {home_team} vs {away_team}",
        f"📅 {date_str}{round_str}",
        "",
    ]

    if best:
        label = _outcome_label(best["outcome"], home_team, away_team)
        prob = best["model_probability"]
        odds = best.get("market_odds")
        edge = best.get("edge_pct")
        lines.append("📊 Mejor opción del modelo:")
        odds_str = f" | Cuota @{odds:.2f}" if odds else ""
        edge_str = f" | Edge {edge:+.1f}%" if edge is not None else ""
        lines.append(f"  {label}: {prob:.0f}%{odds_str}{edge_str}")
        lines.append("")
        lines.append("❌ Sin edge suficiente vs el mercado")
    else:
        lines.append("❌ Sin predicciones (equipos fuera del modelo)")

    lines.extend(["", _HASHTAGS])
    _send(token, chat_id, "\n".join(lines))


def notify_bet_placed(
    home_team: str,
    away_team: str,
    match_date: datetime,
    round_name: str | None,
    bets: list[dict],
    current_bankroll: float,
    token: str,
    chat_id: str,
) -> None:
    """
    Called when one or more bets are placed on a match.
    bets: list of {"outcome", "model_probability", "market_odds", "edge_pct",
                   "stake_amount", "stake_pct", "decimal_odds"}
    """
    round_str = f" · {round_name}" if round_name else ""
    date_str = _format_date(match_date)

    lines = [
        f"🎯 <b>Nueva apuesta</b>",
        f"🏟 {home_team} vs {away_team}",
        f"📅 {date_str}{round_str}",
        "",
    ]

    for bet in bets:
        label = _outcome_label(bet["outcome"], home_team, away_team)
        model_pct = bet.get("model_probability", 0)
        edge = bet.get("edge_pct")
        stake = bet["stake_amount"]
        stake_pct = bet["stake_pct"]
        odds = bet["decimal_odds"]

        lines.append(f"✅ <b>{label}</b>")
        edge_str = f" | Edge <b>{edge:+.1f}%</b>" if edge is not None else ""
        lines.append(f"📊 Modelo: {model_pct:.0f}%{edge_str}")
        lines.append(f"📈 Cuota: @{odds:.2f}")
        lines.append(f"💰 Stake: <b>{stake:.0f}€</b> ({stake_pct:.1f}% bankroll)")

    lines.extend([
        "",
        f"🏦 Bankroll: {current_bankroll:,.0f}€",
        "",
        _HASHTAGS,
    ])
    _send(token, chat_id, "\n".join(lines))


def notify_bet_resolved(
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    bets: list[dict],
    bankroll_before: float,
    bankroll_after: float,
    token: str,
    chat_id: str,
) -> None:
    """
    Called when bets on a finished match are resolved.
    bets: list of {"outcome", "decimal_odds", "stake_amount",
                   "profit_loss", "status"}
    """
    total_pl = sum(b["profit_loss"] for b in bets)
    all_won = all(b["status"] == "won" for b in bets)
    all_lost = all(b["status"] == "lost" for b in bets)

    if all_won:
        header = "✅ <b>¡ACERTAMOS!</b>"
    elif all_lost:
        header = "❌ <b>Fallamos</b>"
    else:
        header = "↔️ <b>Resultado mixto</b>"

    bankroll_change_pct = (bankroll_after - bankroll_before) / bankroll_before * 100 if bankroll_before else 0

    lines = [
        header,
        f"🏟 {home_team} {home_score}-{away_score} {away_team}",
        "",
    ]

    for bet in bets:
        label = _outcome_label(bet["outcome"], home_team, away_team)
        pl = bet["profit_loss"]
        pl_str = f"+{pl:.0f}€" if pl >= 0 else f"{pl:.0f}€"
        lines.append(f"  Apostamos: {label} @{bet['decimal_odds']:.2f}")
        lines.append(f"  Stake: {bet['stake_amount']:.0f}€ → <b>{pl_str}</b>")

    lines.extend([
        "",
        f"🏦 Bankroll: {bankroll_before:,.0f}€ → <b>{bankroll_after:,.0f}€</b> ({bankroll_change_pct:+.1f}%)",
        "",
        _HASHTAGS,
    ])
    _send(token, chat_id, "\n".join(lines))
