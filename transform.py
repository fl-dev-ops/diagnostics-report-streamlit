"""Assemble per-student records from the diagnostics + rounds queries."""

from __future__ import annotations

from typing import Any

import labels


def _round_record(raw: dict | None, round_type: str, base_url: str) -> dict:
    """Normalize one round into a display-ready dict. `raw` is None if not taken."""
    short = labels.ROUND_SHORT[round_type]
    if not raw or raw.get("report_token") is None:
        return {
            "round_type": round_type,
            "display": labels.ROUND_DISPLAY[round_type],
            "short": short,
            "completed": False,
            "total": None,
            "total_label": "—",
            "language_avg": None,
            "thinking_avg": None,
            "confidence_avg": None,
            "salary_band": "—",
            "report_url": None,
            "video_url": None,
            "audio_url": None,
            "recording_url": None,
        }

    total = raw.get("total_score")
    return {
        "round_type": round_type,
        "display": labels.ROUND_DISPLAY[round_type],
        "short": short,
        "completed": True,
        "total": total,
        "total_label": labels.total_label(total),
        "language_avg": raw.get("language_avg"),
        "thinking_avg": raw.get("thinking_avg"),
        "confidence_avg": raw.get("confidence_avg"),
        "language_label": labels.dimension_label(raw.get("language_avg")),
        "thinking_label": labels.dimension_label(raw.get("thinking_avg")),
        "confidence_label": labels.dimension_label(raw.get("confidence_avg")),
        # Prefer the stored band; fall back to deriving from the total.
        "salary_band": raw.get("salary_band") or labels.salary_band(total),
        "report_url": labels.report_url(raw.get("report_token"), base_url),
        "video_url": raw.get("video_url"),
        "audio_url": raw.get("audio_url"),
        "recording_url": labels.recording_url(raw.get("session_id"), base_url),
    }


def build_students(diagnostics: list[dict], rounds: list[dict], base_url: str) -> list[dict]:
    """Return one rich record per diagnostic, rounds pivoted into 4 slots."""
    rounds_by_diag: dict[str, dict[str, dict]] = {}
    for r in rounds:
        rounds_by_diag.setdefault(r["diag_id"], {})[r["round_type"]] = r

    students: list[dict] = []
    for d in diagnostics:
        diag_rounds = rounds_by_diag.get(d["diag_id"], {})
        round_records = {
            rt: _round_record(diag_rounds.get(rt), rt, base_url) for rt in labels.ROUND_TYPES
        }

        completed_types = [rt for rt in labels.ROUND_TYPES if round_records[rt]["completed"]]
        rounds_completed = len(completed_types)

        # Overall: use finalReport when present; else a provisional average of
        # completed round totals (mirrors deriveFinalDiagnosticReport).
        final = d.get("final_report") or {}
        if final.get("overall_score") is not None:
            overall = float(final["overall_score"])
            overall_lang = final.get("language_avg")
            overall_think = final.get("thinking_avg")
            overall_conf = final.get("confidence_avg")
            overall_band = final.get("salary_band") or labels.salary_band(overall)
            is_provisional = False
        elif completed_types:
            totals = [round_records[rt]["total"] for rt in completed_types]
            overall = round(sum(totals) / len(totals), 1)
            overall_lang = _avg([round_records[rt]["language_avg"] for rt in completed_types])
            overall_think = _avg([round_records[rt]["thinking_avg"] for rt in completed_types])
            overall_conf = _avg([round_records[rt]["confidence_avg"] for rt in completed_types])
            overall_band = labels.salary_band(overall)
            is_provisional = True
        else:
            overall = None
            overall_lang = overall_think = overall_conf = None
            overall_band = "—"
            is_provisional = False

        job = d.get("selected_job") or {}
        record = {
            "diag_id": d["diag_id"],
            "name": (d.get("name") or "").strip() or "(no name)",
            "email": d.get("email"),
            "phone": d.get("phone"),
            "institution": d.get("institution"),
            "degree": d.get("degree"),
            "stream": d.get("stream"),
            "year_of_study": d.get("year_of_study"),
            "english_level": d.get("english_level"),
            "status": d.get("status"),
            "current_round": d.get("current_round"),
            "selected_band": d.get("selected_band"),
            "band_label": labels.BAND_LABEL.get(d.get("selected_band"), d.get("selected_band") or "—"),
            "job_title": job.get("title"),
            "job_salary": job.get("salary"),
            "job_companies": job.get("companies") or [],
            "created_at": d.get("created_at"),
            "rounds_completed": rounds_completed,
            "completed_types": completed_types,
            "overall": overall,
            "overall_label": labels.readiness_label(overall),
            "overall_emoji": labels.READINESS_EMOJI.get(labels.readiness_label(overall), ""),
            "overall_language": overall_lang,
            "overall_thinking": overall_think,
            "overall_confidence": overall_conf,
            "overall_salary_band": overall_band,
            "overall_report_url": labels.report_url(d.get("final_report_token"), base_url),
            "is_provisional": is_provisional,
            "rounds": round_records,
        }
        students.append(record)

    return students


def _avg(values: list[Any]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)
