"""Label, salary-band and URL helpers.

Thresholds are ported verbatim from the diagnostics app so the dashboard matches
what students/admins see in the product:

- Readiness label   -> src/components/diagnostics/interview-readiness-score.tsx
- Dimension label   -> src/components/diagnostics/report-view.tsx (>=80 HIGH, >=50 MID, <50 LOW)
- Salary band       -> src/lib/report-generation/diagnostic-scoring.ts (getSalaryBandForScore)

The round-Total label (Excellent / Good / Average / Poor) is not defined in the product
code; we use a consistent banding that reproduces the reference spreadsheet.
"""

from __future__ import annotations

# roundType (DB) -> display name. Order matches roundNumber 1..4.
ROUND_TYPES = ["screening", "behavioural", "technical-thinking", "career-readiness"]

ROUND_DISPLAY = {
    "screening": "Screening",
    "behavioural": "Behavioural",
    "technical-thinking": "Tech Thinking",
    "career-readiness": "Career Readiness",
}

# Short prefixes mirroring the reference spreadsheet column groups.
ROUND_SHORT = {
    "screening": "Scr",
    "behavioural": "Beh",
    "technical-thinking": "Tech",
    "career-readiness": "CR",
}

BAND_LABEL = {
    "band1": "Band 1 · SDE @ IT Services (₹6-10 LPA)",
    "band2": "Band 2 · SDE @ Product (₹8-15 LPA)",
    "band3": "Band 3 · SDE @ MAANG+ (₹20-40 LPA)",
}


def readiness_label(score: float | None) -> str:
    """Overall readiness label from overall_score (inclusive ranges, 0-100)."""
    if score is None:
        return "—"
    if score <= 50:
        return "No Hire"
    if score <= 70:
        return "Hold"
    if score <= 90:
        return "Hire"
    return "Strong Hire"


READINESS_EMOJI = {
    "No Hire": "😟",
    "Hold": "🤔",
    "Hire": "🙂",
    "Strong Hire": "🎉",
    "—": "",
}


def dimension_label(avg: float | None) -> str:
    """Language / Thinking / Confidence label: >=80 HIGH, >=50 MID, <50 LOW."""
    if avg is None:
        return "—"
    if avg >= 80:
        return "HIGH"
    if avg >= 50:
        return "MID"
    return "LOW"


def total_label(score: float | None) -> str:
    """Per-round Total label: >=90 Excellent, >=70 Good, >=50 Average, <50 Poor."""
    if score is None:
        return "—"
    if score >= 90:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Average"
    return "Poor"


def salary_band(total_score: float | None) -> str:
    """Salary band from a total score (matches getSalaryBandForScore)."""
    if total_score is None:
        return "—"
    if total_score >= 80:
        return "₹35+ LPA"
    if total_score >= 50:
        return "₹15-35 LPA"
    return "₹3.5-15 LPA"


def report_url(share_token: str | None, base: str) -> str | None:
    if not share_token:
        return None
    return f"{base.rstrip('/')}/d/{share_token}"


def recording_url(session_id: str | None, base: str) -> str | None:
    if not session_id:
        return None
    return f"{base.rstrip('/')}/session/{session_id}/recording"
