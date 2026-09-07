"""Entrypoint: `python -m src.gap_scout.main`.

Meant to be triggered ~7:00 AM ET on weekdays by the GitHub Actions workflow
in .github/workflows/gap-scout.yml. Because GitHub Actions cron is UTC-only
and doesn't shift for daylight saving, the workflow fires twice (covering
both EDT and EST) and this script no-ops unless it's actually ~7:00 AM ET,
unless FORCE_RUN is set (used for manual/testing runs).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from src.gap_scout.graph import build_graph


def _should_run_now(tolerance_minutes: int = 20) -> bool:
    if os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes"):
        return True

    now_et = datetime.now(ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5:  # Saturday/Sunday
        return False

    target_minutes = 7 * 60  # 7:00 AM
    now_minutes = now_et.hour * 60 + now_et.minute
    return abs(now_minutes - target_minutes) <= tolerance_minutes


def main() -> None:
    if not _should_run_now():
        print("Not ~7:00 AM ET on a weekday (and FORCE_RUN not set) — skipping.")
        sys.exit(0)

    app = build_graph()
    result = app.invoke(
        {
            "gappers": [],
            "researched": [],
            "assessed": [],
            "market_regime": "",
            "email_body": "",
            "email_sent": False,
            "run_date": "",
        }
    )
    kept = [t for t in result["assessed"] if t.get("keep")]
    print(
        f"Run complete for {result['run_date']}. "
        f"{len(kept)}/{len(result['assessed'])} tickers kept. "
        f"Email sent: {result['email_sent']}"
    )


if __name__ == "__main__":
    main()
