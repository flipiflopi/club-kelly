# Football Prediction System

Paper trading system for football match predictions. Uses Dixon-Coles statistical model to generate probabilities, detects edge vs bookmaker odds, and simulates bets with fractional Kelly sizing. No real money involved.

Designed from day 1 to support multiple competitions (World Cup 2026 → La Liga → Champions League) without rewriting the prediction engine.

## Architecture

```
engine/          Statistical engine — completely competition-agnostic
  models/        Dixon-Coles (Poisson + rho + time decay xi)
  markets/       Market modules self-register (1X2, O/U 1.5/2.5/3.5, BTTS)
  decision/      Pure functions: edge detection, Kelly sizing, risk filters

adapters/        Data sources behind abstract interfaces
  fixtures/      worldcup2026 GitHub API
  odds/          The Odds API
  historical/    Kaggle international football results (training data)

backend/         FastAPI + SQLAlchemy
  app/models/    PostgreSQL schema (competitions, teams, players, matches, predictions, bets, bankroll)
  app/api/v1/    REST endpoints + n8n webhook receivers
  app/services/  Bet resolution, metrics (Brier score, ROI, CLV, win rate by market)

competitions/    One YAML per competition — adding a new one = creating a file here
training/        Offline model training + backtesting scripts

frontend/        Vite + React + TypeScript + Tailwind (2 views: Upcoming / History)
```

## Quick Start (local development)

### Prerequisites
- Docker + Docker Compose
- Python 3.12 + [uv](https://github.com/astral-sh/uv)
- Node.js 20+

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set POSTGRES_PASSWORD and SECRET_KEY
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

Services:
- Backend API: http://localhost:8000
- Frontend:    http://localhost:3000
- PostgreSQL:  localhost:5432 (exposed in dev via docker-compose.override.yml)

### 3. Run database migrations

```bash
# First time only — creates all tables
docker compose exec backend alembic upgrade head
```

### 4. Train the initial model (requires Kaggle data)

Download the [Kaggle international football results](https://www.kaggle.com/datasets/martj42/international-football-results) CSV and place it at `training/data/results.csv`.

```bash
uv run python -m training.train_dixon_coles --competition worldcup2026 --min-date 2010-01-01
```

### 5. Run tests

```bash
uv run pytest                    # all tests
uv run pytest tests/engine/      # engine only (no DB required)
uv run pytest -v                 # verbose
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `SECRET_KEY` | Yes | App secret key |
| `INITIAL_BANKROLL` | No | Starting paper bankroll in € (default: 1000) |
| `THE_ODDS_API_KEY` | For odds | The Odds API key (free tier: 500 req/month) |
| `ANTHROPIC_API_KEY` | For reasoning text | Claude API key |
| `GITHUB_TOKEN` | Optional | Avoids GitHub API rate limits for fixture source |
| `WEBHOOK_API_KEY` | Optional | API key for n8n webhook endpoints (empty = no auth) |

## n8n Webhook Endpoints

Configure these in your n8n workflows. All return JSON. Optionally pass `X-API-Key` header.

| Endpoint | Method | When to call | What it does |
|---|---|---|---|
| `POST /v1/webhooks/sync-fixtures` | POST | Every 60s | Fetches upcoming fixtures from worldcup2026 API |
| `POST /v1/webhooks/sync-results` | POST | Every 5 min | Fetches recent results, updates match scores, resolves open bets |
| `POST /v1/webhooks/run-predictions` | POST | After sync-fixtures | Runs full prediction pipeline on new fixtures |

## Frontend API Endpoints (polled every 30-60s)

| Endpoint | Description |
|---|---|
| `GET /v1/matches/upcoming` | Upcoming + live matches with predictions |
| `GET /v1/matches/past` | Historical matches with results |
| `GET /v1/bets` | All simulated bets |
| `GET /v1/bets/open` | Currently open bets |
| `GET /v1/bankroll/snapshot` | Current balance, ROI, win rate |
| `GET /v1/bankroll/history` | Event log for bankroll chart |

## Adding a New Competition

1. Create `competitions/<slug>.yaml` following the schema in `competitions/_schema.yaml`
2. Insert a row into the `competitions` table (or via a seed script)
3. Write or reuse a fixture adapter in `adapters/fixtures/`
4. Run `training/train_dixon_coles.py` with the new competition slug
5. Done — the engine picks up the new competition through `competition_id`, no code changes

## Decision Pipeline

```
Layer 1 — Dixon-Coles          P(score matrix) for each match
Layer 2 — Edge detection       compare model prob vs market prob (after vig removal)
Layer 3 — Fractional Kelly     size stake = f* × kelly_multiplier × current_bankroll
Layer 4 — Risk filters         cap per-bet%, cap daily exposure%, enforce odds range
Layer 5 — Claude API (text)    generate explanation in Spanish (non-decision, pure text)
```

Layers 1-4 are 100% deterministic Python. Claude API only writes the explanation text — it never influences the bet decision or sizing.

## Deployment (Hetzner + Coolify)

1. Push to GitHub
2. In Coolify: create a new app pointing to this repo
3. Set environment variables in Coolify's UI (same as `.env`)
4. Coolify builds and deploys via `docker-compose.yml`
5. Run `alembic upgrade head` once via Coolify's exec panel

## Metrics Tracked

- **Brier Score**: calibration (when model says 70%, does it happen 70% of the time?)
- **ROI**: cumulative return on total simulated stake
- **Win rate by market**: separate tracking for 1X2 / Over/Under / BTTS
- **CLV (Closing Line Value)**: odds at bet time vs closing odds before kick-off
