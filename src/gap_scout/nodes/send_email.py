"""Node 7: wrap the drafted brief in an HTML shell and send via Gmail."""
from __future__ import annotations

from src.gap_scout.clients.gmail_client import send_email as gmail_send
from src.gap_scout.config import EMAIL_TO
from src.gap_scout.state import GraphState

_WRAPPER = """<div style="font-family: -apple-system, Helvetica, Arial, sans-serif; \
max-width: 640px; margin: 0 auto; color: #111;">
{body}
<hr style="margin-top: 24px; border: none; border-top: 1px solid #ddd;" />
<p style="font-size: 12px; color: #888;">Automated gap-scout brief. Not investment advice.</p>
</div>"""


def send_email(state: GraphState) -> dict:
    html = _WRAPPER.format(body=state["email_body"])
    subject = f"Pre-market gap brief — {state['run_date']}"
    gmail_send(EMAIL_TO, subject, html)
    return {"email_sent": True}
