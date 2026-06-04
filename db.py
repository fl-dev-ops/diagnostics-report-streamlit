"""Read-only data access for the diagnostics Postgres DB.

Only SELECT queries are issued. The connection is opened in read-only mode as a
defensive measure (session is set to READ ONLY).
"""

from __future__ import annotations

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    conn = psycopg2.connect(url)
    conn.set_session(readonly=True, autocommit=True)
    return conn


# One row per diagnostic, joined to its user + profile.
_DIAGNOSTICS_SQL = """
SELECT
    d.id                       AS diag_id,
    d."userId"                 AS user_id,
    u.name                     AS name,
    u.email                    AS email,
    u."phoneNumber"            AS phone,
    p.institution              AS institution,
    p.degree                   AS degree,
    p.stream                   AS stream,
    p."yearOfStudy"            AS year_of_study,
    p."englishLevel"           AS english_level,
    d.status                   AS status,
    d."currentRound"           AS current_round,
    d."selectedBand"           AS selected_band,
    d."selectedJob"            AS selected_job,
    d."finalReport"            AS final_report,
    d."finalReportShareToken"  AS final_report_token,
    u."createdAt"              AS created_at
FROM diagnostic d
JOIN "user" u   ON u.id = d."userId"
LEFT JOIN profile p ON p."userId" = d."userId"
ORDER BY u.name;
"""

# One row per diagnostic round that has a READY report, with its pre-computed
# assessment scores and the session media URLs.
_ROUNDS_SQL = """
SELECT
    dr."diagnosticId"          AS diag_id,
    dr."roundNumber"           AS round_number,
    dr."roundType"             AS round_type,
    dr.status                  AS round_status,
    s.id                       AS session_id,
    s."videoUrl"               AS video_url,
    s."audioUrl"               AS audio_url,
    s."transcriptUrl"          AS transcript_url,
    r."shareToken"             AS report_token,
    r.status                   AS report_status,
    (r.metadata -> 'hydratedReport' -> 'assessment_result' ->> 'total_score')::float      AS total_score,
    (r.metadata -> 'hydratedReport' -> 'assessment_result' ->> 'language_avg')::float      AS language_avg,
    (r.metadata -> 'hydratedReport' -> 'assessment_result' ->> 'thinking_avg')::float      AS thinking_avg,
    (r.metadata -> 'hydratedReport' -> 'assessment_result' ->> 'confidence_avg')::float    AS confidence_avg,
    (r.metadata -> 'hydratedReport' -> 'assessment_result' ->> 'salary_band')              AS salary_band
FROM diagnostic_round dr
JOIN interview_session s ON s.id = dr."sessionId"
LEFT JOIN report r ON r."sessionId" = s.id AND r.status = 'READY'
ORDER BY dr."diagnosticId", dr."roundNumber";
"""


def _fetch(sql: str) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_diagnostics() -> list[dict]:
    return _fetch(_DIAGNOSTICS_SQL)


def fetch_rounds() -> list[dict]:
    return _fetch(_ROUNDS_SQL)
