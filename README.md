1) Create an account at https://www.reviewmetric.it.com/

2) Credit your account (you have one free credit to test)

3) Go to the developper portal from the dashboard and generate an API key (REVIEWMETRIC_API_KEY)

4) Modify the claude_desktop_config.json with this code (DO NOT FORGET TO REPLACE WITH YOUR API KEY):

```json
{
  "mcpServers": {
    "review-metric": {
      "command": "uvx",
      "args": ["reviewmetric-mcp"],
      "env": {
        "REVIEWMETRIC_API_KEY": "your_api_key_from_the_web_dashboard"
      }
    }
  }
}

