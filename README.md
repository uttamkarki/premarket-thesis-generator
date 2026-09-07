# gap-scout

A LangGraph agent pipeline that runs every weekday at **7:00 AM ET**, scans
for the day's biggest pre-market gappers, researches the catalyst behind each
one, reads the market regime, and emails you a ranked pre-market gap-trading
brief.

## How it works

```
START ──▶ fetch_gappers ──▶ (fan out, one per ticker) ──▶ research_ticker ─┐
  │                                                                        │
  └──▶ market_regime ─────────────────────────────────────────────────────┼──▶ compose_thesis ──▶ send_email ──▶ END
                                     research_ticker ──▶ check_gap_room ──▶ score_ticker ──┘
```

| Node | What it does |
|---|---|
| `fetch_gappers` | Calls Massive's Top Market Movers snapshot for today's top N gap-ups and gap-downs (gainers + losers). |
| `research_ticker` | Runs **in parallel** (via LangGraph `Send`), once per ticker. Pulls recent headlines from FMP and asks Claude to classify the catalyst type, magnitude, and write a 2-sentence summary — as structured JSON, not free text. |
| `check_gap_room` | Pulls a 14-day ATR% from Massive's daily aggregates and compares it to today's gap size, flagging whether the move looks "used up" or has room to extend. |
| `score_ticker` | Combines catalyst magnitude + gap room into a 1–5 conviction score and a keep/drop decision. |
| `market_regime` | Pulls SPY trend + VIX level/trend from Massive and outputs a one-line risk-on / risk-off / neutral read. |
| `compose_thesis` | Feeds the surviving, ranked tickers + regime read to Claude to draft the final HTML brief. |
| `send_email` | Wraps the brief in a clean HTML shell and sends it via the Gmail API. |

State is a single shared `GraphState` `TypedDict` (see `src/gap_scout/state.py`).
The `researched` list uses an additive (`operator.add`) reducer since it's
filled by parallel fan-out; `assessed` is a plain field that gets fully
recomputed by `check_gap_room` and then `score_ticker`.

## Data providers used

- **Market data (gappers, prices, ATR, SPY/VIX):** [Massive](https://massive.com) (`MASSIVE_API_KEY`)
- **News / catalysts:** [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs) (`FMP_API_KEY`)
- **LLM (catalyst classification + thesis drafting):** Anthropic Claude, via `langchain-anthropic` (`ANTHROPIC_API_KEY`)
- **Email:** Gmail API with OAuth (`GMAIL_TOKEN_JSON_B64`, `EMAIL_TO`)

### Swapping providers later

Each provider is isolated behind a small client class:
- `src/gap_scout/clients/massive_client.py`
- `src/gap_scout/clients/fmp_client.py`
- `src/gap_scout/clients/gmail_client.py`

To swap, e.g., FMP for Finnhub or Benzinga news: write a new client with a
`stock_news(ticker, limit)` method returning the same shape (list of dicts
with `title`, `text`, `publishedDate`), then point `research_ticker.py`'s
import at it. Same pattern for market data or email.

## Project layout

```
premarket-thesis-generator/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── src/
│   └── gap_scout/
│       ├── config.py          # env var loading
│       ├── state.py           # GraphState TypedDict
│       ├── graph.py           # StateGraph assembly (nodes + Send fan-out)
│       ├── main.py            # entrypoint, ET-time guard
│       ├── clients/
│       │   ├── massive_client.py
│       │   ├── fmp_client.py
│       │   └── gmail_client.py
│       └── nodes/
│           ├── fetch_gappers.py
│           ├── research_ticker.py
│           ├── check_gap_room.py
│           ├── score_ticker.py
│           ├── market_regime.py
│           ├── compose_thesis.py
│           └── send_email.py
├── scripts/
│   └── gmail_oauth_setup.py   # one-time local OAuth token generator
└── .github/
    └── workflows/
        └── gap-scout.yml      # scheduled trigger (cron)
```

## Setup

### 1. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Get API keys

- **Massive**: sign up at https://massive.com/dashboard, grab your key.
- **FMP**: sign up at https://site.financialmodelingprep.com, grab your key.
- **Anthropic**: create a key at https://console.anthropic.com.

### 3. Generate a Gmail OAuth token (one-time, local)

1. In [Google Cloud Console](https://console.cloud.google.com/), enable the
   **Gmail API** on a project and create an **OAuth Client ID** of type
   **Desktop app**.
2. Download the client secret JSON, save it as `scripts/client_secret.json`
   (already git-ignored — never commit it).
3. Run:
   ```bash
   python scripts/gmail_oauth_setup.py
   ```
4. Sign in via the browser window that opens, grant the `gmail.send` scope.
5. Copy the printed base64 string.

### 4. Configure environment

```bash
cp .env.example .env
```

Fill in `MASSIVE_API_KEY`, `FMP_API_KEY`, `ANTHROPIC_API_KEY`,
`GMAIL_TOKEN_JSON_B64` (from step 3), and `EMAIL_TO`.

### 5. Test it locally

The pipeline only runs near 7:00 AM ET by default. For a local test run at
any time of day, set `FORCE_RUN=true` in `.env`, then:

```bash
python -m src.gap_scout.main
```

### 6. Deploy the schedule (GitHub Actions)

This repo already includes `.github/workflows/gap-scout.yml`, which runs on
a weekday cron scheduled to land at 7:00 AM ET (it fires at both possible UTC
offsets to cover daylight saving; `main.py`'s time guard makes sure only one
of the two actually sends an email).

Add the following as **repository secrets** (Settings → Secrets and
variables → Actions):

- `MASSIVE_API_KEY`
- `FMP_API_KEY`
- `ANTHROPIC_API_KEY`
- `GMAIL_TOKEN_JSON_B64`
- `EMAIL_TO`

Push to `main` and the workflow will pick up the schedule automatically. You
can also trigger it manually from the **Actions** tab
(`workflow_dispatch`, defaults to `force: true` so it always runs).

Why GitHub Actions cron instead of Lambda or a long-running process: this
job is a once-a-day, short-lived batch task with no need to be always-on, so
a scheduled CI job is the simplest thing that works — free on public repos,
no infrastructure to manage, and secrets are handled natively.

## Notes / things you may want to tune

- `NUM_GAPPERS_PER_DIRECTION` (default 5) controls how many gap-ups and
  gap-downs get pulled (10 tickers total by default).
- `check_gap_room`'s "used up" vs "room to extend" thresholds (150% / 80% of
  14-day ATR%) are a reasonable starting point, not gospel — tune them in
  `src/gap_scout/nodes/check_gap_room.py` as you see how they perform.
- `score_ticker`'s conviction formula is intentionally simple (catalyst
  magnitude + gap room, clamped 1–5) — tune weights in
  `src/gap_scout/nodes/score_ticker.py`.
- The Anthropic model defaults to `claude-sonnet-4-6`; override via
  `ANTHROPIC_MODEL` in `.env`.
