<h1 align="center">Review Metric MCP Server</h1>

<p align="center">
  <strong>Connect Claude to the world's most advanced 15-agent scientific peer review pipeline.</strong>
</p>

---

# 🔬 What is Review Metric?
Review Metric is a powerful AI tool designed for researchers, academics, and scientists. By installing this MCP server, you give Claude the ability to securely submit your local `.docx` manuscripts to a sophisticated 15-agent pipeline that rigorously analyzes your work for methodological flaws, novelty, and literature alignment.

## 🎥 See it in Action
![Review Metric Claude Desktop Demo](https://raw.githubusercontent.com/vktr93/reviewmetric-mcp/main/demo.gif)

### ✨ Key Features
* **Multi-Agent Rigor:** Your manuscript is analyzed by 15 specialized AI agents, simulating a real-world peer review panel.
* **Comprehensive Scoring:** Receive a definitive 0-100 quality score to gauge your readiness for journal submission.
* **Zero Data Retention:** Your unpublished work is completely secure. We enforce strict zero-data retention, meaning your research is **never** used for AI training.
* **Local File Access:** Claude can securely read manuscripts directly from your computer without you having to copy/paste massive documents into the chat.

---

#### 🚀 Installation for Claude Desktop

To install this tool, simply add the following configuration to your `claude_desktop_config.json` file. 

*(Note: You will need your personal API key from the Review Metric web dashboard https://www.reviewmetric.it.com/).*
```json
{
  "mcpServers": {
    "review-metric": {
      "command": "uvx",
      "args": ["reviewmetric-mcp"],
      "env": {
        "REVIEWMETRIC_API_KEY": "your_api_key_here"
      }
    }
  }
}