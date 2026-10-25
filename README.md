<h1 align="center">ReviewMetric MCP Server</h1>

<p align="center"><strong>Know what reviewers will say before you submit — from inside Claude.</strong></p>

---

ReviewMetric is a pre-submission review service for researchers. This MCP server lets Claude send a local
`.docx` manuscript to ReviewMetric's panel of specialist AI referees and bring the report back into your chat.

## What the panel checks

| Referee | What it looks at |
|---|---|
| Novelty & positioning | Your claims against the closest published, peer-reviewed work (retrieved from OpenAlex and ReviewMetric's vetted library), plus related papers you may have missed |
| Claims & evidence | Whether each main claim is supported by your results; numbers that disagree between abstract, results and tables |
| Methods & reproducibility | Design, controls, statistics, and a field-appropriate reproducibility checklist |
| Citation integrity | Whether cited papers support the sentences they are attached to; retracted, uncited or missing references |
| Figures | Captions, legibility, units, and agreement with the text |
| Clarity | Title, abstract, structure, language, terminology |
| Handling editor | Readiness recommendation, prioritised revisions and a referee-style report |

Every issue points to a location in your manuscript. Scores come from fixed rubrics, not from a single AI guess.

## Installation (Claude Desktop)

1. Create an API key in the ReviewMetric developer portal: https://www.reviewmetric.it.com/developer-portal
2. Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "review-metric": {
      "command": "uvx",
      "args": ["reviewmetric-mcp"],
      "env": { "REVIEWMETRIC_API_KEY": "rvk_live_..." }
    }
  }
}
```

3. Ask Claude: *"Review my manuscript at /Users/me/papers/draft.docx with ReviewMetric."*

## Tools

- `submit_manuscript(file_path)` — uploads the `.docx` (uses 1 credit) and returns a Run ID.
- `check_analysis_status(run_id)` — progress while running; the full report (summary, scores, priority actions, issues, missing related work, referee report) when done.
- `get_report_json(run_id)` — the complete report as JSON.

A review usually takes 5 to 15 minutes. If the file cannot be reviewed (unreadable, too short, not a manuscript), the credit is refunded automatically.

## Data

Manuscripts are processed by ReviewMetric's API and the AI providers it uses under their paid API terms (no training
on your data). See the ReviewMetric website for the current data-retention policy.

<!-- mcp-name: io.github.vktr93/reviewmetric-mcp -->
