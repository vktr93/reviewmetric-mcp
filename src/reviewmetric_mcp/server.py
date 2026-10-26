"""ReviewMetric MCP server: lets Claude submit a .docx manuscript to the ReviewMetric
review panel and read back the report."""
from __future__ import annotations

import json
import os

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ReviewMetric")

API_BASE = os.environ.get("REVIEWMETRIC_API_URL", "https://reviewmetric-api.onrender.com/api/v1").rstrip("/")
MAX_BYTES = 20 * 1024 * 1024
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _headers() -> dict:
    key = os.environ.get("REVIEWMETRIC_API_KEY")
    if not key:
        raise ValueError("REVIEWMETRIC_API_KEY is not set. Create a key in the ReviewMetric developer portal.")
    return {"Authorization": f"Bearer {key}"}


def _error(response: requests.Response) -> str:
    try:
        message = response.json().get("error") or response.text
    except ValueError:
        message = response.text
    if response.status_code == 401:
        return "ReviewMetric rejected the API key (invalid or revoked). Create a new key in the developer portal."
    if response.status_code == 402:
        return "Not enough RM tokens. Get RM tokens at https://www.reviewmetric.it.com/pricing"
    if response.status_code == 503:
        return "ReviewMetric is under maintenance. Try again later."
    return f"ReviewMetric error ({response.status_code}): {message}"


def _score(value) -> str:
    return "n/a" if value is None else f"{float(value):.0f}/100"


def _format_report(rep: dict) -> str:
    lines = [f"# ReviewMetric report: {rep.get('manuscript_title', 'manuscript')}"]
    if rep.get("overall_score") is not None:
        lines.append(f"**Overall: {_score(rep['overall_score'])} ({rep.get('grade', '')})** — "
                     f"{rep.get('recommendation_label', rep.get('recommendation', ''))}")
    if rep.get("recommendation_rationale"):
        lines.append(rep["recommendation_rationale"])
    if rep.get("executive_summary"):
        lines += ["", "## Summary", rep["executive_summary"]]
    if rep.get("dimensions"):
        lines += ["", "## Scores"]
        lines += [f"- {d['label']}: {_score(d.get('score'))} — {d.get('summary', '')}" for d in rep["dimensions"]]
    if rep.get("priority_actions"):
        lines += ["", "## Priority actions"]
        for a in rep["priority_actions"]:
            lines.append(f"{a.get('priority', '-')}. **{a.get('title')}** ({a.get('effort', '')} effort): "
                         f"{a.get('why', '')} {a.get('how', '')}".strip())
    if rep.get("issues"):
        lines += ["", "## Issues found"]
        for i in rep["issues"]:
            loc = f" [{i['location']}]" if i.get("location") else ""
            lines.append(f"- ({i.get('severity')}) {i.get('title')}{loc}: {i.get('detail', '')} → {i.get('suggestion', '')}")
    if rep.get("retracted_references"):
        lines += ["", "## Retracted references"]
        lines += [f"- [{r.get('number')}] {r.get('title') or r.get('text', '')[:120]}" for r in rep["retracted_references"]]
    if rep.get("missing_citations"):
        lines += ["", "## Related work you may have missed"]
        for m in rep["missing_citations"]:
            p = m.get("paper") or {}
            doi = f" https://doi.org/{p['doi']}" if p.get("doi") else ""
            lines.append(f"- {p.get('title')} ({p.get('year')}){doi} — {m.get('why', '')}")
    if rep.get("referee_report"):
        lines += ["", "## Referee-style report", rep["referee_report"]]
    if rep.get("ai_generated_review") and not rep.get("executive_summary"):  # reports made before v2
        r = rep["ai_generated_review"]
        lines += ["", r.get("overall_assessment", ""), r.get("suggestions_for_improvement", "")]
    if rep.get("report_url"):
        lines += ["", f"Full interactive report: {rep['report_url']}"]
    return "\n".join(lines)


@mcp.tool()
def submit_manuscript(file_path: str) -> str:
    """Submit a local .docx manuscript to the ReviewMetric review panel (uses 1 RM token).

    A panel of specialist AI referees checks novelty against the published literature, whether the
    results support the claims, methods and reproducibility, citation accuracy (including retracted
    references), figures, and clarity, then a handling editor writes prioritised revisions and a
    referee-style report. A review usually takes 5-15 minutes.

    Args:
        file_path: Absolute path to the .docx file on this computer.
    """
    path = os.path.expanduser(file_path)
    if not os.path.isfile(path):
        return f"File not found: {path}"
    if not path.lower().endswith(".docx"):
        return "ReviewMetric accepts Word documents (.docx) only. Save the manuscript as .docx and try again."
    if os.path.getsize(path) > MAX_BYTES:
        return "The file is larger than 20 MB. Remove supplementary material or large embedded media and try again."
    try:
        with open(path, "rb") as fh:
            response = requests.post(f"{API_BASE}/analyze", headers=_headers(),
                                     files={"file": (os.path.basename(path), fh, DOCX_MIME)}, timeout=120)
    except ValueError as exc:
        return str(exc)
    except requests.RequestException as exc:
        return f"Could not reach ReviewMetric: {exc}"
    if response.status_code not in (200, 202):
        return _error(response)
    data = response.json()
    return (f"Submitted. Run ID: {data.get('run_id')}\n"
            f"Track it in the browser: {data.get('report_url', '')}\n\n"
            "Call check_analysis_status with this Run ID about every 60 seconds until it is completed.")


@mcp.tool()
def check_analysis_status(run_id: str) -> str:
    """Check a ReviewMetric review. Returns progress while running, or the full report when done.

    Args:
        run_id: The Run ID returned by submit_manuscript.
    """
    try:
        response = requests.get(f"{API_BASE}/status/{run_id}", headers=_headers(), timeout=30)
    except ValueError as exc:
        return str(exc)
    except requests.RequestException as exc:
        return f"Could not reach ReviewMetric: {exc}"
    if response.status_code != 200:
        return _error(response)
    data = response.json()
    status = data.get("status")
    if status == "queued":
        return (f"Queued (position {data.get('queue_position', 0) + 1}, about {data.get('eta_minutes', '?')} min). "
                "Check again in a minute.")
    if status == "running":
        pct = int(100 * float(data.get("progress") or 0))
        return f"Running ({pct}%): {data.get('current_step') or 'working'}. Check again in about a minute."
    if status == "completed":
        return _format_report(data.get("summary_report") or {})
    if status == "failed":
        return f"The review failed: {data.get('error_message') or 'unknown error'}. The RM token has been returned."
    if status == "cancelled":
        return "This review was cancelled and the RM token returned."
    return f"Status: {status}"


@mcp.tool()
def get_report_json(run_id: str) -> str:
    """Return the complete ReviewMetric report as JSON (all findings, literature, reference checks).

    Args:
        run_id: The Run ID of a completed review.
    """
    try:
        response = requests.get(f"{API_BASE}/report/{run_id}", headers=_headers(), timeout=30)
    except ValueError as exc:
        return str(exc)
    except requests.RequestException as exc:
        return f"Could not reach ReviewMetric: {exc}"
    if response.status_code != 200:
        return _error(response)
    return json.dumps(response.json(), indent=1)[:200000]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
