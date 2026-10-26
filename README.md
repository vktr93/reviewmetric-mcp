<h1 align="center">ReviewMetric MCP Server</h1>

<p align="center"><strong>Know what reviewers will say before you submit — from inside Claude.<br>Then fix the text in one go, and see where your work sits on the map of science.</strong></p>

---

ReviewMetric is a pre-submission review service for researchers. This MCP server lets Claude send a local
`.docx` manuscript to ReviewMetric's panel of specialist AI referees, bring the report back into your chat,
prepare the text fixes Claude can apply to your file, and explore the ReviewMetric Atlas: landmark discoveries,
their Nobel Prizes and the frontiers research groups are pushing now.

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

1. Create an API key at https://www.reviewmetric.it.com/developers
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

## Commands

Ask *"What can ReviewMetric do?"* (the `help_me` command) for the full list inside Claude.

| Command | What it does | Cost |
|---|---|---|
| `help_me` | Everything ReviewMetric can do in Claude, with examples | Free |
| `submit_manuscript(file_path)` | Sends the `.docx` to the referees; returns a Run ID | 1 RM token |
| `check_analysis_status(run_id)` | Progress; when done, the report, its place on the Atlas and the text fixes available | Free |
| `get_report_json(run_id)` | The complete report as JSON | Free |
| `list_my_reviews(limit)` | Your reviews with scores and Run IDs | Free |
| `get_text_fixes(run_id)` | Preview of the fixes that need no new experiment; the exact edits once prepared | Free |
| `prepare_text_fixes(run_id)` | Prepares the edits, which Claude can then apply to your manuscript | 1 RM token |
| `search_atlas(query, field, limit)` | Finds discoveries and frontiers on the Atlas | Free |
| `list_frontiers()` | The frontiers, what they build on, who is pushing them | Free |
| `place_on_atlas(run_id)` | Where your manuscript sits, the landmarks it cites, the frontier ahead | Free |
| `atlas_whats_new()` | This week's additions to the Atlas | Free |
| `trace_path(from, to)` | The chain of discoveries linking two stars | Free |
| `unlock_atlas_sources(confirm)` | The paper and research group behind every star, for 30 days | 1 RM token |
| `account_status()` | RM tokens left, Atlas access, prices | Free |

**Spending tokens.** RM tokens are ReviewMetric's one currency (1 for $9, 3 for $25, 10 for $70; your first is free).
Claude never unlocks the Atlas sources on its own: it tells you the cost and waits for your explicit *yes* in the chat.

A review usually takes about 5 minutes. If the file cannot be reviewed (unreadable, too short, not a manuscript), the RM token is returned automatically.

**Try asking**
- *"Review my manuscript at ~/papers/draft.docx and tell me what to fix first."*
- *"Prepare the text fixes of my last review and apply them to the draft."*
- *"Where does my manuscript sit on the Atlas, and which frontier is ahead of it?"*
- *"Who is pushing room-temperature superconductivity right now?"*
- *"Trace the path from the double helix to AlphaFold."*

## Data

Manuscripts are processed by ReviewMetric's API and the AI providers it uses under their paid API terms (no training
on your data). See the ReviewMetric website for the current data-retention policy.

<!-- mcp-name: io.github.vktr93/reviewmetric-mcp -->
