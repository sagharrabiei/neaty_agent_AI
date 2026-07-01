import os
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure local directory is in sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Load environment variables
load_dotenv()

from neaty_agent import app as adk_app, WorkflowInput, InMemoryRunner  # noqa: E402

# Create FastAPI app
app = FastAPI(title="Neaty File Organizer API", version="2.0")


# Request schemas
class EnvConfig(BaseModel):
    GEMINI_API_KEY: Optional[str] = ""
    GOOGLE_API_KEY: Optional[str] = ""
    GOOGLE_GENAI_USE_ENTERPRISE: Optional[str] = ""
    GOOGLE_CLOUD_PROJECT: Optional[str] = ""
    GOOGLE_CLOUD_LOCATION: Optional[str] = ""
    HTTP_PROXY: Optional[str] = ""
    HTTPS_PROXY: Optional[str] = ""


class ScanRequest(BaseModel):
    source_dir: str


class OrganizeRequest(BaseModel):
    source_dir: str
    destination_dir: Optional[str] = None


# API Endpoints
@app.get("/api/env")
def get_env():
    # Reload from disk
    load_dotenv(override=True)
    return {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        "GOOGLE_GENAI_USE_ENTERPRISE": os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", ""),
        "GOOGLE_CLOUD_PROJECT": os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        "GOOGLE_CLOUD_LOCATION": os.getenv("GOOGLE_CLOUD_LOCATION", ""),
        "HTTP_PROXY": os.getenv("HTTP_PROXY", ""),
        "HTTPS_PROXY": os.getenv("HTTPS_PROXY", ""),
    }


@app.post("/api/env")
def save_env(config: EnvConfig):
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    # Read existing comments/variables
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    # Build updated key-value map
    config_dict = config.model_dump()
    updated_keys = set(config_dict.keys())
    new_lines = []

    # Keep track of keys we've already written
    written_keys = set()

    for line in existing_lines:
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("#"):
            new_lines.append(line)
            continue

        # Check if line matches an existing variable we want to update
        parts = line_strip.split("=", 1)
        key = parts[0].strip()
        if key in updated_keys:
            val = config_dict[key] or ""
            new_lines.append(f"{key}={val}\n")
            written_keys.add(key)
        else:
            new_lines.append(line)

    # Append any keys that weren't in the original file
    for key, val in config_dict.items():
        if key not in written_keys:
            val = val or ""
            new_lines.append(f"{key}={val}\n")

    # Write back to .env
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Reload variables into python environment
    load_dotenv(override=True)

    # Set proxy environment variables actively for the running process as well
    for key in ["HTTP_PROXY", "HTTPS_PROXY"]:
        val = getattr(config, key)
        if val:
            os.environ[key] = val
        else:
            os.environ.pop(key, None)

    return {
        "status": "success",
        "message": "Environment configuration updated successfully.",
    }


@app.post("/api/scan")
def scan_directory(req: ScanRequest):
    source_dir = os.path.abspath(req.source_dir)
    if not os.path.exists(source_dir):
        raise HTTPException(status_code=400, detail="Source directory does not exist.")

    # Import the internal scanning function directly to perform the scan
    from neaty_agent import scan_directory_node, WorkflowInput

    try:
        # Default destination_dir inside source_dir for the mock schema
        destination_dir = os.path.join(source_dir, "organized_output")
        input_data = WorkflowInput(
            source_dir=source_dir, destination_dir=destination_dir
        )

        # Runs the deterministic scanner node
        scan_res = scan_directory_node(input_data)

        # Return scan result details
        return {
            "status": "success",
            "source_dir": scan_res.source_dir,
            "destination_dir": scan_res.destination_dir,
            "files": [f.model_dump() for f in scan_res.files],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/organize")
async def organize_directory(req: OrganizeRequest):
    source_dir = os.path.abspath(req.source_dir)
    if not os.path.exists(source_dir):
        raise HTTPException(status_code=400, detail="Source directory does not exist.")

    destination_dir = req.destination_dir
    if not destination_dir:
        destination_dir = os.path.join(source_dir, "organized_output")
    destination_dir = os.path.abspath(destination_dir)

    # Ensure proxy variables from current env are set correctly
    load_dotenv(override=True)

    runner = InMemoryRunner(app=adk_app)
    workflow_input = WorkflowInput(
        source_dir=source_dir, destination_dir=destination_dir
    )

    try:
        # Run ADK agent workflow in async mode
        result = await runner.run_debug(workflow_input.model_dump_json())

        # Locate the saved report
        report_path = os.path.join(destination_dir, "ORGANIZATION_REPORT.md")
        report_content = ""
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()

        return {
            "status": "success",
            "message": "Files organized successfully!",
            "destination_dir": destination_dir,
            "report": report_content,
            "result_summary": str(result),
        }
    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        # Clean the trace for API response
        raise HTTPException(
            status_code=500, detail={"error": str(e), "trace": error_trace}
        )


# Serve static frontend files
if os.path.exists(os.path.join(os.path.dirname(__file__), "static")):
    app.mount(
        "/",
        StaticFiles(
            directory=os.path.join(os.path.dirname(__file__), "static"), html=True
        ),
        name="static",
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_server:app", host="127.0.0.1", port=5050, reload=True)
