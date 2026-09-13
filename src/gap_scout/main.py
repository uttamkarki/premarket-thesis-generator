"""Entrypoint: `python -m src.gap_scout.main`.

Meant to be triggered ~8:15 AM ET on weekdays. GitHub Actions' own
`schedule:` cron trigger proved unreliable in practice -- runs were landing
3.5-5 hours late (a known GitHub Actions limitation: scheduled triggers are
low-priority and get queued behind everything else, especially at common
round-number UTC times). The workflow is now triggered externally instead,
via cron-job.org calling the GitHub API's workflow_dispatch endpoint at
8:05 AM ET daily -- that's a normal-priority trigger path, not the
deprioritized schedule queue, so it actually fires on time.

This script still no-ops unless it's actually close to 8:15 AM ET, as a
safety net in case the external trigger itself fires early/late/twice on
a given day, unless FORCE_RUN is set (used for manual/testing runs).
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

    target_minutes = 8 * 60 + 15  # 8:15 AM
    now_minutes = now_et.hour * 60 + now_et.minute
    return abs(now_minutes - target_minutes) <= tolerance_minutes


def main() -> None:
    if not _should_run_now():
        print("Not ~8:15 AM ET on a weekday (and FORCE_RUN not set) — skipping.")
        sys.exit(0)

    app = build_graph()
    result = app.invoke(
        {
            "gappers": [],
            "stocks_in_play_path": "",
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