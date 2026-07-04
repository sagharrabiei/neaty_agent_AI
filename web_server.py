import os
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure local directory is in sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Load environment variables
load_dotenv()

from neaty_agent import WorkflowInput  # noqa: E402

# Create FastAPI app
app = FastAPI(title="Neaty File Organizer API", version="2.0")


@app.on_event("startup")
async def startup_event():
    import asyncio
    from pubsub_manager import pubsub_manager

    # Initialize the pubsub_manager with current running event loop
    loop = asyncio.get_running_loop()
    await pubsub_manager.initialize(loop=loop)
    # Start background subscriber/worker
    await pubsub_manager.start_worker()


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
    from neaty_agent import scan_directory_node

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

    import uuid
    import asyncio
    from pubsub_manager import pubsub_manager, pending_tasks, task_results

    # Generate a unique task ID
    task_id = str(uuid.uuid4())

    # Create an event to await completion
    event = asyncio.Event()
    pending_tasks[task_id] = event

    try:
        # Publish task details to the Pub/Sub manager
        await pubsub_manager.publish(task_id, source_dir, destination_dir)

        # Wait for the worker to complete processing (with a 5-minute timeout)
        await asyncio.wait_for(event.wait(), timeout=300.0)

        # Retrieve result
        result_data = task_results.get(task_id)
        if not result_data:
            raise HTTPException(
                status_code=500, detail="Task finished but no result was recorded."
            )

        if result_data.get("status") == "error":
            raise HTTPException(
                status_code=500,
                detail={
                    "error": result_data.get(
                        "error", "An error occurred during worker execution."
                    ),
                    "trace": result_data.get("trace", ""),
                },
            )

        # If this is a cloud run/upload session, package the organized results
        import re as re_mod

        match = re_mod.search(r"neaty_run_([a-f0-9\-]+)", source_dir)
        if match:
            session_id = match.group(1)
            session_dir = f"/tmp/neaty_run_{session_id}"
            zip_path = os.path.join(session_dir, "organized.zip")

            # Zip up destination_dir contents
            import zipfile

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for root, _, files in os.walk(destination_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file_path == zip_path:
                            continue
                        rel_path = os.path.relpath(file_path, destination_dir)
                        zip_file.write(file_path, rel_path)

            result_data["download_url"] = f"/api/download/{session_id}"

        return result_data

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504, detail="Task processing timed out on the Pub/Sub worker."
        )
    finally:
        # Clean up global task maps to prevent memory leaks
        pending_tasks.pop(task_id, None)
        task_results.pop(task_id, None)


@app.get("/api/tasks/{task_id}")
def get_task_status(task_id: str):
    from pubsub_manager import pending_tasks, task_results

    if task_id in pending_tasks:
        return {"status": "working", "task_id": task_id}
    elif task_id in task_results:
        return task_results[task_id]
    else:
        raise HTTPException(
            status_code=404, detail="Task not found or already cleaned up."
        )


@app.post("/api/upload")
async def upload_zip(file: UploadFile = File(...)):
    import zipfile
    import uuid
    import shutil

    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400, detail="Only .zip archive uploads are supported."
        )

    session_id = str(uuid.uuid4())
    session_dir = f"/tmp/neaty_run_{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    zip_path = os.path.join(session_dir, "upload.zip")
    source_dir = os.path.join(session_dir, "source")
    destination_dir = os.path.join(session_dir, "organized")

    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(destination_dir, exist_ok=True)

    try:
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue
                target_path = os.path.abspath(os.path.join(source_dir, member))
                if not target_path.startswith(os.path.abspath(source_dir)):
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zip_ref.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)

        from neaty_agent import scan_directory_node
        from neaty_agent import WorkflowInput

        input_data = WorkflowInput(
            source_dir=source_dir, destination_dir=destination_dir
        )
        scan_res = scan_directory_node(input_data)

        return {
            "status": "success",
            "session_id": session_id,
            "source_dir": source_dir,
            "destination_dir": destination_dir,
            "files": [f.model_dump() for f in scan_res.files],
        }
    except Exception as e:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to process zip file: {e}")


@app.get("/api/download/{session_id}")
def download_zip(session_id: str):
    zip_path = f"/tmp/neaty_run_{session_id}/organized.zip"
    if not os.path.exists(zip_path):
        raise HTTPException(
            status_code=404, detail="Organized zip archive not found or expired."
        )
    return FileResponse(
        path=zip_path,
        filename="neaty_organized_files.zip",
        media_type="application/zip",
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

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5050"))
    uvicorn.run("web_server:app", host=host, port=port, reload=True)
