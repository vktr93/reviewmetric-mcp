"""ReviewMetric MCP server: pre-submission peer review, text fixes and the ReviewMetric Atlas, from inside Claude.

Reviews: submit a .docx manuscript to the panel of AI referees and read the report back.
Text fixes: get every fix that needs no new experiment, ready to apply to the manuscript.
Atlas: the map of landmark discoveries, their Nobel Prizes and today's frontiers.
Account: RM tokens, the one currency (a review, the text fixes of a review, or 30 days of Atlas sources).
"""
from __future__ import annotations

import json
import os
import uuid

import requests
from mcp.server.fastmcp import FastMCP

INSTRUCTIONS = """ReviewMetric reviews scientific manuscripts before submission and maps science on the ReviewMetric Atlas.
Spending RM tokens: submit_manuscript and prepare_text_fixes use one token each, only when the user asked for that.
unlock_atlas_sources also uses one token: call it with confirm=true ONLY after telling the user the cost and receiving an
explicit "yes" from them in this conversation. Never decide on the user's behalf. Use help_me to show what is possible."""

mcp = FastMCP("ReviewMetric", instructions=INSTRUCTIONS)

API_BASE = os.environ.get("REVIEWMETRIC_API_URL", "https://reviewmetric-api.onrender.com/api/v1").rstrip("/")
SITE = os.environ.get("REVIEWMETRIC_SITE_URL", "https://www.reviewmetric.it.com").rstrip("/")
MAX_BYTES = 20 * 1024 * 1024
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _headers() -> dict:
    key = os.environ.get("REVIEWMETRIC_API_KEY")
    if not key:
        raise ValueError("REVIEWMETRIC_API_KEY is not set. Create a key at " + SITE + "/developers")
    return {"Authorization": f"Bearer {key}"}


def _error(response: requests.Response) -> str:
    try:
        message = response.json().get("error") or response.text
    except ValueError:
        message = response.text
    if response.status_code == 401:
        return f"ReviewMetric rejected the API key (invalid or revoked). Create a new key at {SITE}/developers"
    if response.status_code == 402:
        return f"Not enough RM tokens. Get RM tokens at {SITE}/pricing (1 for $9, 3 for $25, 10 for $70)."
    if response.status_code == 503:
        return "ReviewMetric is under maintenance. Try again later."
    return f"ReviewMetric error ({response.status_code}): {message}"


def _call(method: str, path: str, *, ok=(200,), **kwargs) -> tuple[dict | None, str | None]:
    """(data, None) on success, (None, message for the user) otherwise."""
    try:
        response = requests.request(method, f"{API_BASE}{path}", headers=_headers(), timeout=kwargs.pop("timeout", 30), **kwargs)
    except ValueError as exc:
        return None, str(exc)
    except requests.RequestException as exc:
        return None, f"Could not reach ReviewMetric: {exc}"
    if response.status_code not in ok:
        return None, _error(response)
    try:
        return response.json(), None
    except ValueError:
        return None, "ReviewMetric sent an unreadable answer. Try again in a moment."


def _tokens(n) -> str:
    return f"{n} RM token{'' if n == 1 else 's'}"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
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


def _format_placement(p: dict) -> str:
    lines = [f"## On the ReviewMetric Atlas", f"Your manuscript sits in **{p.get('topic')}** ({p.get('field')})."]
    if p.get("cites_landmarks"):
        lines.append("It cites these landmarks on the map: " + "; ".join(p["cites_landmarks"]) + ".")
    elif p.get("placed_by") == "topic" and p.get("matched_words"):
        lines.append("Placed by its topic: " + ", ".join(p["matched_words"][:5]) + ".")
    else:
        lines.append("Placed by its field: no closer topic is on the map yet.")
    if p.get("closest_on_the_map"):
        lines.append("Closest discoveries: " + "; ".join(p["closest_on_the_map"]) + ".")
    if p.get("frontier_ahead"):
        lines.append("Frontier ahead: " + "; ".join(p["frontier_ahead"]) + ".")
    lines.append(f"See it on the map: {p.get('atlas_url')}")
    return "\n".join(lines)


def _format_star(s: dict) -> str:
    head = f"**{s['title']}**"
    if s.get("kind") == "frontier":
        head += " — frontier"
    elif s.get("year"):
        head += f" ({s['year']})"
    lines = [head + f" · {' · '.join(s.get('fields') or [])}"]
    if s.get("summary"):
        lines.append(s["summary"])
    nb = s.get("nobel")
    if nb:
        cat = {"medicine": "Physiology or Medicine"}.get(nb.get("category"), (nb.get("category") or "").title())
        lines.append(f"Nobel Prize in {cat} {nb.get('year')}: {nb.get('laureates')}.")
    if s.get("builds_on"):
        lines.append("Builds on: " + "; ".join(s["builds_on"]) + ".")
    if s.get("led_to"):
        lines.append("Led to: " + "; ".join(s["led_to"]) + ".")
    src = s.get("source")
    if src:
        lines.append(f"Source: {src.get('authors')} {src.get('title')} {src.get('venue')}. {src.get('url')}")
        if src.get("research_group"):
            lines.append(f"Research group: {src['research_group']}")
    for w in s.get("who_is_pushing") or []:
        lines.append(f"Pushing it: {w.get('group')} — {w.get('authors')} {w.get('title')} {w.get('venue')} ({w.get('year')}). {w.get('url')}")
    if s.get("kind") == "frontier" and s.get("groups_pushing") and not s.get("who_is_pushing"):
        g = s["groups_pushing"]
        lines.append(f"{g} research group{'s are' if g > 1 else ' is'} pushing it (names and papers are part of the Atlas sources).")
    elif s.get("sources_locked"):
        lines.append("Leading paper and research group: part of the Atlas sources.")
    lines.append(f"On the map: {s.get('atlas_url')}")
    return "\n".join(lines)


_LOCKED_NOTE = ("The papers and research groups behind each star are part of the Atlas sources: 30 days for one RM token. "
                "Use unlock_atlas_sources if the user wants them (it asks for their explicit yes first).")


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
HELP = f"""# ReviewMetric in Claude

**Reviews** (one RM token each)
- `submit_manuscript` — send a Word (.docx) manuscript to six AI referees and a handling editor. About 5 minutes.
- `check_analysis_status` — progress, then the full report, where the manuscript sits on the Atlas, and the text fixes available.
- `get_report_json` — the complete report as data.
- `list_my_reviews` — your past reviews with their scores.

**Text fixes** (one RM token per review)
- `get_text_fixes` — free preview of the fixes that need no new experiment; the edits themselves once prepared.
- `prepare_text_fixes` — prepare them. Claude can then apply each edit to your manuscript.

**ReviewMetric Atlas** (the map is free)
- `search_atlas` — find a discovery or a frontier by name or topic.
- `list_frontiers` — the open problems at the edge of science, and who is pushing them.
- `place_on_atlas` — where one of your reviewed manuscripts sits, and the frontier ahead of it.
- `atlas_whats_new` — this week's additions.
- `trace_path` — the chain of discoveries linking two others.
- `unlock_atlas_sources` — the leading paper and research group behind every star, for 30 days (one RM token, only after you say yes).

**Account**
- `account_status` — your RM tokens and Atlas access. Buy tokens at {SITE}/pricing (1 for $9, 3 for $25, 10 for $70).

**Try asking**
- "Review my manuscript at ~/papers/draft.docx and tell me what to fix first."
- "Prepare the text fixes of my last review and apply them to the draft."
- "Where does my manuscript sit on the Atlas, and which frontier is ahead of it?"
- "Who is pushing room-temperature superconductivity right now?"
- "Trace the path from the double helix to AlphaFold."
"""


@mcp.tool()
def help_me() -> str:
    """Show everything ReviewMetric can do in Claude, what costs an RM token, and example requests."""
    return HELP


@mcp.prompt(name="help_me")
def help_me_prompt() -> str:
    """What can ReviewMetric do for me?"""
    return "Show me what ReviewMetric can do here (call help_me), then ask what I would like to do."


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@mcp.tool()
def submit_manuscript(file_path: str) -> str:
    """Submit a local .docx manuscript to the ReviewMetric review panel (uses 1 RM token).

    A panel of specialist AI referees checks novelty against the published literature, whether the
    results support the claims, methods and reproducibility, citation accuracy (including retracted
    references), figures, and clarity, then a handling editor writes prioritised revisions and a
    referee-style report. A review usually takes about 5 minutes.

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
            data, err = _call("POST", "/analyze", ok=(200, 202), timeout=120,
                              files={"file": (os.path.basename(path), fh, DOCX_MIME)})
    except OSError as exc:
        return f"Could not read the file: {exc}"
    if err:
        return err
    acc, _ = _call("GET", "/account")
    left = f"\nYou have {_tokens(acc['rm_tokens'])} left." if acc else ""
    return (f"Submitted. Run ID: {data.get('run_id')}\n"
            f"Track it in the browser: {data.get('report_url', '')}{left}\n\n"
            "Call check_analysis_status with this Run ID about every 60 seconds until it is completed.")


@mcp.tool()
def check_analysis_status(run_id: str) -> str:
    """Check a ReviewMetric review. Returns progress while running; when done, the full report, the
    manuscript's place on the ReviewMetric Atlas, and how many text fixes are available.

    Args:
        run_id: The Run ID returned by submit_manuscript (or listed by list_my_reviews).
    """
    data, err = _call("GET", f"/status/{run_id}")
    if err:
        return err
    status = data.get("status")
    if status == "queued":
        return (f"Queued (position {data.get('queue_position', 0) + 1}, about {data.get('eta_minutes', '?')} min). "
                "Check again in a minute.")
    if status == "running":
        pct = int(100 * float(data.get("progress") or 0))
        return f"Running ({pct}%): {data.get('current_step') or 'working'}. Check again in about a minute."
    if status == "failed":
        return f"The review failed: {data.get('error_message') or 'unknown error'}. The RM token has been returned."
    if status == "cancelled":
        return "This review was cancelled and the RM token returned."
    if status != "completed":
        return f"Status: {status}"
    parts = [_format_report(data.get("summary_report") or {})]
    placed, _ = _call("GET", f"/runs/{run_id}/atlas")
    if placed:
        parts.append(_format_placement(placed))
    fixes, _ = _call("GET", f"/runs/{run_id}/fixes")
    if fixes and not fixes.get("pack") and (fixes.get("preview") or {}).get("count"):
        parts.append(f"## Text fixes\n{fixes['preview']['count']} changes can be made by editing the text alone. "
                     "get_text_fixes shows them for free; prepare_text_fixes prepares the exact edits (1 RM token).")
    return "\n\n".join(parts)


@mcp.tool()
def get_report_json(run_id: str) -> str:
    """Return the complete ReviewMetric report as JSON (all findings, literature, reference checks).

    Args:
        run_id: The Run ID of a completed review.
    """
    data, err = _call("GET", f"/report/{run_id}")
    if err:
        return err
    return json.dumps(data, indent=1)[:200000]


@mcp.tool()
def list_my_reviews(limit: int = 10) -> str:
    """List the user's ReviewMetric reviews, newest first, with their scores and Run IDs.

    Args:
        limit: How many reviews to list (1 to 50).
    """
    data, err = _call("GET", "/reviews", params={"limit": max(1, min(int(limit), 50))})
    if err:
        return err
    reviews = data.get("reviews") or []
    if not reviews:
        return f"No reviews yet. You have {_tokens(data.get('rm_tokens', 0))}; submit_manuscript starts one."
    lines = [f"# Your reviews ({len(reviews)})"]
    for r in reviews:
        when = (r.get("completed_at") or r.get("created_at") or "")[:10]
        score = f" — {_score(r['score'])}, {r.get('recommendation') or ''}" if r.get("score") is not None else ""
        state = "" if r["status"] == "completed" else f" — {r['status']}"
        lines.append(f"- **{r['title']}** ({when}){score}{state}\n  Run ID: {r['run_id']} · {r['report_url']}")
    lines.append(f"\nYou have {_tokens(data.get('rm_tokens', 0))}.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text fixes
# ---------------------------------------------------------------------------
@mcp.tool()
def get_text_fixes(run_id: str) -> str:
    """Text fixes of a completed review: every change that needs no new experiment (wording, overstated
    claims, citations, missing references, method details, typos). Free preview before they are prepared;
    once prepared, the exact edits (where, what to find, what to write) that you can apply to the
    user's manuscript.

    Args:
        run_id: The Run ID of a completed review.
    """
    data, err = _call("GET", f"/runs/{run_id}/fixes")
    if err:
        return err
    pack = data.get("pack")
    if pack and pack.get("status") == "completed":
        result = pack.get("result") or {}
        if not result.get("prompt"):
            return "The fixes were prepared, but no edit could be checked against the manuscript."
        return ("# Text fixes, ready to apply\n"
                "Apply each edit to the user's manuscript exactly as written: find the quoted passage at the given "
                "location and replace it. Edits marked as needing the author's input must be confirmed with the user.\n\n"
                + result["prompt"])
    if pack and pack.get("status") in ("queued", "running"):
        return "The text fixes are being prepared (usually under a minute). Call get_text_fixes again shortly."
    preview = data.get("preview") or {}
    lines = []
    if pack and pack.get("status") == "failed":
        lines.append(f"The last preparation failed: {pack.get('error_message') or 'unknown error'}")
    if not preview.get("count"):
        return "This review has no text fixes to prepare: what remains needs new experiments or analysis."
    lines.append(f"# Up to {preview['count']} changes by editing the text alone")
    for k in preview.get("kinds") or []:
        lines.append(f"- {k['count']} × {k['label']}")
    lines.append("")
    for i in (preview.get("items") or [])[:25]:
        loc = f" [{i['location']}]" if i.get("location") else ""
        lines.append(f"- {i['kind_label']}{loc}: {i['title']}")
    lines.append(f"\nprepare_text_fixes prepares the exact edits, plus a proofreading pass, for 1 RM token "
                 f"(you have {_tokens(data.get('credits', 0))}).")
    return "\n".join(lines)


@mcp.tool()
def prepare_text_fixes(run_id: str) -> str:
    """Prepare the text fixes of a completed review (uses 1 RM token; asking again for the same review is free).
    Only call this when the user asked for the fixes. Then call get_text_fixes to receive the edits.

    Args:
        run_id: The Run ID of a completed review.
    """
    data, err = _call("POST", f"/runs/{run_id}/fixes", ok=(200, 202))
    if err:
        return err
    status = (data.get("pack") or {}).get("status")
    if status == "completed":
        return "The fixes are already prepared. Call get_text_fixes to receive them."
    return (f"Preparing the text fixes (status: {status}). You have {_tokens(data.get('credits', 0))} left. "
            "Call get_text_fixes in about a minute.")


# ---------------------------------------------------------------------------
# Atlas
# ---------------------------------------------------------------------------
@mcp.tool()
def search_atlas(query: str, field: str | None = None, limit: int = 6) -> str:
    """Search the ReviewMetric Atlas, the map of landmark discoveries since 1900, their Nobel Prizes and
    today's frontiers. Matches names, topics and summaries.

    Args:
        query: Words to look for, e.g. "CRISPR", "superconductivity", "neural networks".
        field: Optional field: Physics, Materials, Chemistry, Biology, Medicine or Computer science.
        limit: How many results (1 to 20).
    """
    data, err = _call("GET", "/atlas/search", params={"q": query, "field": field or "", "limit": max(1, min(int(limit), 20))})
    if err:
        return err
    results = data.get("results") or []
    if not results:
        return f"Nothing on the Atlas matches “{query}”. Try a broader word. The whole map: {data.get('atlas_url')}"
    out = [f"# Atlas: {len(results)} result{'s' if len(results) > 1 else ''} for “{query}”", ""]
    out += [_format_star(s) + "\n" for s in results]
    if not data.get("sources_unlocked") and any(s.get("sources_locked") for s in results):
        out.append(_LOCKED_NOTE)
    return "\n".join(out)


@mcp.tool()
def list_frontiers() -> str:
    """The frontiers of the ReviewMetric Atlas: open problems at the edge of science, what each one builds
    on, and the research groups pushing it now."""
    data, err = _call("GET", "/atlas/frontiers")
    if err:
        return err
    fronts = data.get("frontiers") or []
    out = [f"# {len(fronts)} frontiers on the ReviewMetric Atlas", ""]
    out += [_format_star(f) + "\n" for f in fronts]
    if not data.get("sources_unlocked"):
        out.append(_LOCKED_NOTE)
    return "\n".join(out)


@mcp.tool()
def place_on_atlas(run_id: str) -> str:
    """Where one of the user's reviewed manuscripts sits on the ReviewMetric Atlas: its topic, the landmarks
    it cites, the closest discoveries, and the frontier ahead of it.

    Args:
        run_id: The Run ID of a completed review (see list_my_reviews).
    """
    data, err = _call("GET", f"/runs/{run_id}/atlas")
    if err:
        return err
    return _format_placement(data)


@mcp.tool()
def atlas_whats_new() -> str:
    """This week's additions to the ReviewMetric Atlas (updated every week)."""
    data, err = _call("GET", "/atlas/updates", params={"limit": 3})
    if err:
        return err
    ups = data.get("updates") or []
    if not ups:
        return "No updates yet."
    out = [f"# What's new on the ReviewMetric Atlas (version {data.get('version')})"]
    for u in ups:
        out += ["", f"## {u['date']} — {u['title']}", u.get("text", "")]
        out += [f"- {a['title']}: {a['atlas_url']}" for a in u.get("added") or []]
    return "\n".join(out)


@mcp.tool()
def trace_path(from_discovery: str, to_discovery: str) -> str:
    """The chain of discoveries linking two stars of the ReviewMetric Atlas, e.g. from the double helix to
    AlphaFold, or from the Turing machine to the fault-tolerant quantum computer.

    Args:
        from_discovery: Name (or Atlas id) of the first discovery.
        to_discovery: Name (or Atlas id) of the second discovery or frontier.
    """
    try:
        response = requests.get(f"{API_BASE}/atlas/path", headers=_headers(), timeout=30,
                                params={"from": from_discovery, "to": to_discovery})
    except ValueError as exc:
        return str(exc)
    except requests.RequestException as exc:
        return f"Could not reach ReviewMetric: {exc}"
    try:
        data = response.json()
    except ValueError:
        return _error(response)
    if response.status_code not in (200, 404) or "found" not in data:
        return _error(response)
    if not data.get("found"):
        return data.get("error") or "No path found."
    steps = data["steps"]
    out = [f"# From {data['from']} to {data['to']}: {len(steps) - 1} steps across {', '.join(data['fields_crossed'])}"]
    for i, s in enumerate(steps, 1):
        when = "frontier" if s["frontier"] else s.get("year")
        out.append(f"{i}. {s['title']} ({when}){' · Nobel Prize' if s['nobel'] else ''} — {', '.join(s['fields'])}")
    out.append(f"\nOn the map: {data.get('atlas_url')}")
    return "\n".join(out)


@mcp.tool()
def unlock_atlas_sources(confirm: bool = False) -> str:
    """Unlock the Atlas sources for 30 days: the leading paper and research group behind every discovery, and
    who is pushing each frontier. Costs 1 RM token (added to any current access).

    IMPORTANT: first call without confirm to get the cost and the user's balance, tell the user, and ask them.
    Call with confirm=true ONLY if the user then explicitly answered yes in this conversation.

    Args:
        confirm: True only after the user's explicit yes.
    """
    acc, err = _call("GET", "/account")
    if err:
        return err
    tokens = acc.get("rm_tokens", 0)
    current = acc.get("atlas_sources_until")
    if not confirm:
        state = f"Your Atlas sources are unlocked until {current[:10]}; another token adds 30 days. " if current else ""
        if tokens < 1:
            return (f"{state}Unlocking the Atlas sources costs 1 RM token for 30 days, and you have none. "
                    f"Get RM tokens at {SITE}/pricing, then ask again.")
        return (f"{state}Unlocking the Atlas sources costs 1 RM token for 30 days. You have {_tokens(tokens)}.\n"
                "Ask the user: “Do you want to spend 1 RM token to unlock the Atlas sources for 30 days?” "
                "Only if they answer yes, call unlock_atlas_sources again with confirm=true.")
    data, err = _call("POST", "/atlas/unlock", json={"confirm": True, "key": f"mcp-{uuid.uuid4()}"})
    if err:
        return err
    return (f"Done: the Atlas sources are unlocked until {(data.get('until') or '')[:10]}. "
            f"You have {_tokens(data.get('rm_tokens', 0))} left. search_atlas and list_frontiers now include the "
            f"papers and research groups. On the web: {SITE}/atlas")


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
@mcp.tool()
def account_status() -> str:
    """The user's ReviewMetric account: RM tokens left, Atlas access, number of reviews, and prices."""
    data, err = _call("GET", "/account")
    if err:
        return err
    atlas = (f"unlocked until {data['atlas_sources_until'][:10]}" if data.get("atlas_sources_unlocked")
             else "the map is free; sources locked (1 RM token for 30 days)")
    prices = ", ".join(f"{p['tokens']} for ${p['usd']:g}" for p in data.get("prices") or [])
    return (f"# Your ReviewMetric account\n"
            f"- RM tokens: **{data.get('rm_tokens', 0)}**\n"
            f"- Completed reviews: {data.get('completed_reviews', 0)}\n"
            f"- Atlas sources: {atlas}\n\n"
            f"One RM token buys: {', '.join(data.get('one_token_buys') or [])}.\n"
            f"Prices: {prices}. Buy at {data.get('buy_url')}")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
