"""Read-only data access for the diagnostics Postgres DB.

Only SELECT queries are issued. The connection is opened in read-only mode as a
defensive measure (session is set to READ ONLY).
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_DATABASE_CLIENT_QUERY_PARAMETERS = {
    "advancedSafeModeLevel",
    "driverVersion",
    "env",
    "lazyload",
    "name",
    "safeModeLevel",
    "statusColor",
    "tLSMode",
    "usePrivateKey",
}


def _sanitize_url(url: str) -> str:
    """Remove database-client UI metadata that libpq cannot parse."""
    parts = urlsplit(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key not in _DATABASE_CLIENT_QUERY_PARAMETERS
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _connect(url: str):
    if not url:
        raise RuntimeError("Database URL is not set (see .env.example)")
    conn = psycopg2.connect(_sanitize_url(url))
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

_PROD_REPORTS_SQL = """
SELECT
    r.id                    AS report_id,
    r."shareToken"          AS report_token,
    r."completedAt"         AS report_completed_at,
    d.id                    AS diag_id,
    d.status                AS diagnostic_status,
    d."selectedBand"        AS selected_band,
    d."createdAt"           AS diagnostic_created_at,
    u.name                  AS name,
    u.email                 AS email,
    u."phoneNumber"         AS phone,
    p.institution           AS institution,
    p.degree                AS degree,
    p.stream                AS stream,
    dr."roundNumber"        AS round_number,
    dr."roundType"          AS round_type,
    r."reportJson"          AS report_json
FROM report r
JOIN interview_session s ON s.id = r."sessionId"
JOIN diagnostic_round dr ON dr."sessionId" = s.id
JOIN diagnostic d ON d.id = dr."diagnosticId"
JOIN "user" u ON u.id = d."userId"
LEFT JOIN profile p ON p."userId" = u.id
WHERE r.status = 'READY'
  AND r."reportJson" IS NOT NULL
ORDER BY r."completedAt" DESC NULLS LAST, u.name, dr."roundNumber";
"""


def _fetch(url: str, sql: str) -> list[dict]:
    conn = _connect(url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_diagnostics(url: str) -> list[dict]:
    return _fetch(url, _DIAGNOSTICS_SQL)


def fetch_rounds(url: str) -> list[dict]:
    return _fetch(url, _ROUNDS_SQL)


def fetch_prod_reports(url: str) -> list[dict]:
    return _fetch(url, _PROD_REPORTS_SQL)
