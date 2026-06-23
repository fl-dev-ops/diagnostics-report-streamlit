"""Diagnostics cohort report dashboard (read-only)."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

import db
import labels
import transform

st.set_page_config(page_title="Diagnostics Cohort Report", layout="wide")

DEV_REPORT_BASE_URL = os.environ.get(
    "DEV_REPORT_BASE_URL", "https://dev.diagnostics.intervoo.ai"
)
PROD_REPORT_BASE_URL = os.environ.get(
    "PROD_REPORT_BASE_URL", "https://diagnostics.intervoo.ai"
)


@st.cache_data(ttl=300, show_spinner="Loading diagnostics from DB…")
def load_dev() -> list[dict]:
    url = os.environ.get("DEV_DATABASE_URL")
    if not url:
        raise RuntimeError("DEV_DATABASE_URL is not set (see .env.example)")
    diagnostics = db.fetch_diagnostics(url)
    rounds = db.fetch_rounds(url)
    return transform.build_students(diagnostics, rounds, DEV_REPORT_BASE_URL)


@st.cache_data(ttl=300, show_spinner="Loading production reports from DB…")
def load_prod_reports() -> list[dict]:
    url = os.environ.get("PROD_DATABASE_URL")
    if not url:
        raise RuntimeError("PROD_DATABASE_URL is not set (see .env.example)")
    if not hasattr(db, "fetch_prod_reports"):
        raise RuntimeError(
            "app.py and db.py are out of sync. Deploy the current db.py and restart Streamlit."
        )
    return db.fetch_prod_reports(url)


def fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def score_cell(total, label) -> str:
    if total is None:
        return "—"
    return f"{total:.1f} ({label})"


def stat(col, label: str, value: str) -> None:
    """Compact stat (smaller than st.metric) so text values don't truncate."""
    col.markdown(
        f"<div style='line-height:1.25;margin-bottom:0.9rem'>"
        f"<div style='font-size:0.78rem;color:#808495'>{label}</div>"
        f"<div style='font-size:1.35rem;font-weight:600'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def render_text_content(value, heading: str | None = None) -> None:
    """Render only string content from a nested report value."""
    if isinstance(value, str):
        if value.strip():
            if heading:
                st.markdown(f"**{heading}**")
            st.write(value)
        return

    if isinstance(value, dict):
        for key, child in value.items():
            render_text_content(child, key.replace("_", " ").title())
        return

    if isinstance(value, list):
        if heading:
            st.markdown(f"**{heading}**")
        for child in value:
            render_text_content(child)


def text_list(value) -> str:
    """Join report text arrays for compact table display."""
    if not isinstance(value, list):
        return ""
    return "\n".join(str(item) for item in value if isinstance(item, str) and item.strip())


# ----------------------------------------------------------------------------- env toggle
env = st.sidebar.segmented_control(
    "Environment", ["Prod", "Dev"], default="Prod", selection_mode="single"
) or "Prod"
st.sidebar.divider()

if env == "Prod":
    st.title("Diagnostics Reports — Prod")
    try:
        reports = load_prod_reports()
    except Exception as exc:
        st.error(f"Failed to load data: {exc}")
        st.stop()

    if not reports:
        st.info("No completed reports found.")
        st.stop()

    search = st.text_input("Search name / email").strip().lower()
    round_filter = st.multiselect(
        "Round",
        [labels.ROUND_DISPLAY[round_type] for round_type in labels.ROUND_TYPES],
        default=[],
    )

    filtered_reports = []
    for report in reports:
        round_name = labels.ROUND_DISPLAY.get(
            report["round_type"], report["round_type"] or f"Round {report['round_number']}"
        )
        haystack = f"{report['name'] or ''} {report['email'] or ''}".lower()
        if search and search not in haystack:
            continue
        if round_filter and round_name not in round_filter:
            continue
        filtered_reports.append(report)

    rows = []
    for report in filtered_reports:
        content = report["report_json"] or {}
        rows.append(
            {
                "Name": report["name"] or "(no name)",
                "Email": report["email"] or "—",
                "Phone": report["phone"] or "—",
                "Institution": report["institution"] or "—",
                "Degree / Stream": " / ".join(
                    value for value in (report["degree"], report["stream"]) if value
                )
                or "—",
                "Diagnostic Status": report["diagnostic_status"],
                "Band": report["selected_band"] or "—",
                "Round": labels.ROUND_DISPLAY.get(
                    report["round_type"],
                    report["round_type"] or f"Round {report['round_number']}",
                ),
                "Report Completed": report["report_completed_at"],
                "Education Summary": content.get("education_summary", ""),
                "Aspiration": content.get("aspiration_statement", ""),
                "Reality": content.get("reality_statement", ""),
                "Strengths": text_list(content.get("strengths")),
                "Improvement Areas": text_list(content.get("improvement_areas")),
                "Report": (
                    f"{PROD_REPORT_BASE_URL.rstrip('/')}/d/{report['report_token']}"
                    if report["report_token"]
                    else None
                ),
            }
        )

    st.caption(f"{len(filtered_reports)} of {len(reports)} completed reports")
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Report": st.column_config.LinkColumn("Report", display_text="open"),
            "Report Completed": st.column_config.DatetimeColumn(
                "Report Completed", format="YYYY-MM-DD HH:mm"
            ),
        },
    )

    if not filtered_reports:
        st.info("No reports match the current filters.")
        st.stop()

    options = {
        (
            f"{report['name'] or '(no name)'} — "
            f"{labels.ROUND_DISPLAY.get(report['round_type'], report['round_type'])} — "
            f"{report['report_id']}"
        ): report
        for report in filtered_reports
    }
    selected = st.selectbox("Report text detail", list(options))
    report = options[selected]
    report_json = report["report_json"] or {}
    for field, value in report_json.items():
        if field == "assessment_result":
            continue
        render_text_content(value, field.replace("_", " ").title())
    st.stop()

# ----------------------------------------------------------------------------- data (Dev)
try:
    students = load_dev()
except Exception as exc:  # surface connection/query errors clearly
    st.error(f"Failed to load data: {exc}")
    st.stop()

ALL_ROUND_DISPLAYS = [labels.ROUND_DISPLAY[rt] for rt in labels.ROUND_TYPES]
SECTION_OPTIONS = ["Overall"] + ALL_ROUND_DISPLAYS

# ----------------------------------------------------------------------------- sidebar
st.sidebar.title("Filters")

search = st.sidebar.text_input("Search name / email").strip().lower()

status_filter = st.sidebar.multiselect(
    "Diagnostic status", ["COMPLETED", "IN_PROGRESS"], default=[]
)

rounds_count_filter = st.sidebar.multiselect(
    "Number of rounds completed", [0, 1, 2, 3, 4], default=[],
    help="e.g. pick 4 for students who completed all rounds, 3 for three rounds.",
)

specific_rounds = st.sidebar.multiselect(
    "Completed specific rounds (all selected)", ALL_ROUND_DISPLAYS, default=[],
    help="Student must have a ready report for every round selected here.",
)

visible_sections = st.sidebar.multiselect(
    "Round sections to display", SECTION_OPTIONS, default=SECTION_OPTIONS,
)

readiness_filter = st.sidebar.multiselect(
    "Readiness label", ["No Hire", "Hold", "Hire", "Strong Hire"], default=[]
)

band_filter = st.sidebar.multiselect(
    "Target band", ["band1", "band2", "band3"], default=[]
)

score_range = st.sidebar.slider("Overall score range", 0, 100, (0, 100))

# Date range over diagnostic created_at.
_dates = [s["created_at"].date() for s in students if s.get("created_at")]
date_range = None
if _dates:
    _min, _max = min(_dates), max(_dates)
    date_range = st.sidebar.date_input(
        "Created date range", value=(_min, _max), min_value=_min, max_value=_max,
        help="Filter students by the date their diagnostic was created.",
    )

# map selected display names -> round_type
specific_round_types = [rt for rt in labels.ROUND_TYPES if labels.ROUND_DISPLAY[rt] in specific_rounds]
visible_round_types = [rt for rt in labels.ROUND_TYPES if labels.ROUND_DISPLAY[rt] in visible_sections]
show_overall = "Overall" in visible_sections

# ----------------------------------------------------------------------------- filter
def keep(s: dict) -> bool:
    if search:
        hay = f"{s['name']} {s.get('email') or ''}".lower()
        if search not in hay:
            return False
    if status_filter and s["status"] not in status_filter:
        return False
    if rounds_count_filter and s["rounds_completed"] not in rounds_count_filter:
        return False
    if specific_round_types and not all(rt in s["completed_types"] for rt in specific_round_types):
        return False
    if readiness_filter and s["overall_label"] not in readiness_filter:
        return False
    if band_filter and s["selected_band"] not in band_filter:
        return False
    if s["overall"] is not None and not (score_range[0] <= s["overall"] <= score_range[1]):
        return False
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        created = s.get("created_at")
        if created is None or not (date_range[0] <= created.date() <= date_range[1]):
            return False
    return True


filtered = [s for s in students if keep(s)]

# ----------------------------------------------------------------------------- header
st.title("Diagnostics Cohort Report — Dev")
c1, c2, c3 = st.columns(3)
c1.metric("Students (filtered)", len(filtered))
c2.metric("Total diagnostics", len(students))
c3.metric("Completed all 4 rounds", sum(1 for s in students if s["rounds_completed"] == 4))

# ----------------------------------------------------------------------------- table
st.subheader("Cohort overview")

rows = []
for s in filtered:
    row = {
        "Name": s["name"],
        "Status": s["status"],
        "Created": s["created_at"].date().isoformat() if s.get("created_at") else "—",
        "Rounds": f"{s['rounds_completed']}/4",
        "Band": s["selected_band"] or "—",
    }
    if show_overall:
        row["Readiness Score"] = None if s["overall"] is None else round(s["overall"], 1)
        row["Readiness"] = (
            "—" if s["overall"] is None
            else f"{s['overall_label']}{'*' if s['is_provisional'] else ''}"
        )
    for rt in visible_round_types:
        rr = s["rounds"][rt]
        disp = rr["display"]
        row[f"{disp} Total Score"] = score_cell(rr["total"], rr["total_label"])
        row[f"{disp} Language Score"] = score_cell(rr["language_avg"], rr.get("language_label", "—"))
        row[f"{disp} Thinking Score"] = score_cell(rr["thinking_avg"], rr.get("thinking_label", "—"))
        row[f"{disp} Confidence Score"] = score_cell(rr["confidence_avg"], rr.get("confidence_label", "—"))
        row[f"{disp} report"] = rr["report_url"]
    rows.append(row)

df = pd.DataFrame(rows)

col_config: dict = {}
if show_overall:
    col_config["Readiness Score"] = st.column_config.NumberColumn("Readiness Score", format="%.1f")
for rt in visible_round_types:
    disp = labels.ROUND_DISPLAY[rt]
    col_config[f"{disp} report"] = st.column_config.LinkColumn(f"{disp} report", display_text="open")

st.caption("`*` = provisional overall (not all 4 rounds completed yet).")
st.dataframe(df, use_container_width=True, hide_index=True, column_config=col_config)

# ----------------------------------------------------------------------------- drill-down
st.subheader("Student detail")

if not filtered:
    st.info("No students match the current filters.")
    st.stop()

options = {f"{s['name']} — {s['status']} ({s['rounds_completed']}/4)": s for s in filtered}
chosen_key = st.selectbox("Select a student", list(options.keys()))
s = options[chosen_key]

# Identity
st.markdown("### Identity")
i1, i2, i3 = st.columns(3)
with i1:
    st.markdown(f"**Name:** {s['name']}")
    st.markdown(f"**Email:** {fmt(s.get('email'))}")
    st.markdown(f"**Phone:** {fmt(s.get('phone'))}")
with i2:
    st.markdown(f"**Institution:** {fmt(s.get('institution'))}")
    st.markdown(f"**Degree / Stream:** {fmt(s.get('degree'))} / {fmt(s.get('stream'))}")
    st.markdown(f"**English level:** {fmt(s.get('english_level'))}")
with i3:
    st.markdown(f"**Target band:** {s['band_label']}")
    st.markdown(f"**Target role:** {fmt(s.get('job_title'))}")
    if s.get("job_companies"):
        st.markdown(f"**Target companies:** {', '.join(s['job_companies'])}")

# Overall
if show_overall:
    st.markdown("### Overall Diagnostic")
    if s["overall"] is None:
        st.info("No rounds completed yet — no overall readiness.")
    else:
        o1, o2, o3, o4 = st.columns(4)
        stat(o1, "Readiness score", f"{s['overall']:.1f}")
        stat(o2, "Readiness", f"{s['overall_emoji']} {s['overall_label']}")
        stat(o3, "Salary band", s["overall_salary_band"])
        stat(o4, "Rounds completed", f"{s['rounds_completed']}/4")
        d1, d2, d3 = st.columns(3)
        d1.markdown(f"**Language:** {fmt(s['overall_language'])} ({labels.dimension_label(s['overall_language'])})")
        d2.markdown(f"**Thinking:** {fmt(s['overall_thinking'])} ({labels.dimension_label(s['overall_thinking'])})")
        d3.markdown(f"**Confidence:** {fmt(s['overall_confidence'])} ({labels.dimension_label(s['overall_confidence'])})")
        if s["is_provisional"]:
            st.caption("Provisional — computed from completed rounds; final report not generated yet.")

# Rounds
for rt in visible_round_types:
    rr = s["rounds"][rt]
    icon = "✅" if rr["completed"] else "⬜"
    with st.expander(f"{icon} {rr['display']} round", expanded=False):
        if not rr["completed"]:
            st.caption("Not taken yet.")
            continue
        m1, m2, m3, m4 = st.columns(4)
        stat(m1, f"Total ({rr['total_label']})", f"{rr['total']:.1f}")
        stat(m2, f"Language ({rr['language_label']})", fmt(rr["language_avg"]))
        stat(m3, f"Thinking ({rr['thinking_label']})", fmt(rr["thinking_avg"]))
        stat(m4, f"Confidence ({rr['confidence_label']})", fmt(rr["confidence_avg"]))
        st.markdown(
            f"**Label:** {rr['total_label']}  ·  **Salary band:** {rr['salary_band']}  ·  "
            f"**Lang/Think/Conf:** {rr['language_label']} / {rr['thinking_label']} / {rr['confidence_label']}"
        )
        link_bits = []
        if rr["report_url"]:
            link_bits.append(f"[Report]({rr['report_url']})")
        if rr["video_url"]:
            link_bits.append(f"[Video]({rr['video_url']})")
        if rr["audio_url"]:
            link_bits.append(f"[Audio]({rr['audio_url']})")
        if link_bits:
            st.markdown("  ·  ".join(link_bits))
