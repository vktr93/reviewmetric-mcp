import os
import requests
import json
from mcp.server.fastmcp import FastMCP

# Initialize the MCP Server
mcp = FastMCP("ReviewMetric")

# Configuration (Ensure your Flask API is running on this port)
API_BASE = os.environ.get("REVIEWMETRIC_API_URL", "https://reviewmetric-api.onrender.com/api/v1")

# The API key Claude will use to authenticate with your Flask backend
# You must generate a key from your Developer Portal and set it in your environment
API_KEY = os.environ.get("REVIEWMETRIC_API_KEY")

def get_headers():
    if not API_KEY:
        raise ValueError("REVIEWMETRIC_API_KEY environment variable is missing.")
    return {"Authorization": f"Bearer {API_KEY}"}

@mcp.tool()
def submit_manuscript(file_path: str) -> str:
    """
    Submits a locally saved .docx manuscript to the ReviewMetric 11-agent AI pipeline.
    
    Args:
        file_path: The absolute path on the local computer to the .docx file.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}. Please check the path."
    if not file_path.endswith('.docx'):
        return "Error: ReviewMetric currently only supports .docx files."

    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
            response = requests.post(f"{API_BASE}/analyze", headers=get_headers(), files=files)
        
        if response.status_code in [200, 202]:
            data = response.json()
            run_id = data.get('run_id')
            return f"Success! Manuscript submitted to ReviewMetric. The Run ID is: {run_id}. \n\nClaude, please use the `check_analysis_status` tool with this Run ID to poll for the results every 15 seconds."
        elif response.status_code == 402:
            return "Error: Insufficient ReviewMetric credits. Please top up your account."
        else:
            return f"API Error ({response.status_code}): {response.text}"
            
    except Exception as e:
        return f"Failed to connect to ReviewMetric server: {str(e)}"

@mcp.tool()
def check_analysis_status(run_id: str) -> str:
    """
    Checks the status or retrieves the final report of a ReviewMetric analysis.
    
    Args:
        run_id: The unique UUID of the analysis run.
    """
    try:
        response = requests.get(f"{API_BASE}/status/{run_id}", headers=get_headers())
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status == 'queued':
                pos = data.get('queue_position', 0) + 1
                eta = data.get('eta_minutes', '?')
                return f"Status: QUEUED. Position in line: {pos}. Estimated time: {eta} minutes. Claude, wait a bit and check again."
                
            elif status == 'running':
                step = data.get("current_step", "Processing...")
                return f"Status: RUNNING. Current Step: {step}. Claude, wait 45 seconds and check again. If you hit your tool loop limit, gracefully tell the user the current step and ask them to prompt you to check again."
                
            elif status == 'completed':
                # Return the beautiful JSON report directly to Claude's brain!
                report = data.get("summary_report", {})
                return f"Status: COMPLETED. Here is the final ReviewMetric JSON report. Claude, please summarize this for the user:\n\n{json.dumps(report, indent=2)}"
                
            elif status == 'failed':
                error = data.get("error_message", "Unknown error")
                return f"Status: FAILED. The pipeline crashed with error: {error}"
            
            else:
                return f"Status: {status.upper()}"
                
        else:
            return f"API Error ({response.status_code}): {response.text}"
            
    except Exception as e:
        return f"Failed to connect to ReviewMetric server: {str(e)}"

if __name__ == "__main__":
    # This command starts the stdio server required by Claude Desktop
    mcp.run()