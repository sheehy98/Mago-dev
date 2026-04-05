#
# Imports
#

# Standard library
import asyncio
import logging
import os
import subprocess
import uuid

# Third party
from pathlib import Path

# FastAPI
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# Environment variables
from dotenv import load_dotenv

# Logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


#
# Constants
#

# Paths
DASHBOARD_DIR = Path(__file__).parent
DEV_DIR = DASHBOARD_DIR.parent
ROOT_DIR = DEV_DIR.parent

# Load environment variables from all .env files
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "data" / ".env")
load_dotenv(ROOT_DIR / "frontend" / ".env")

# Service ports
PORTS = {
    "postgresql": int(os.getenv("POSTGRES_PORT", "3463")),
    "minio": int(os.getenv("MINIO_EXTERNAL_PORT", "3462")),
    "api": int(os.getenv("API_PORT", "3461")),
    "frontend": int(os.getenv("VITE_PORT", "3460")),
}

# Dashboard port
DASHBOARD_PORT = 3470

# Venv python path
VENV_PYTHON = str(ROOT_DIR / ".venv" / "bin" / "python")

# Command definitions
# Each command is a shell string run via bash -c, with cwd set to ROOT_DIR
COMMANDS = {

    # Service management — sub-scripts handle their own env
    "services/launch": "bash data/scripts/launch.sh && bash api/scripts/launch.sh && bash frontend/scripts/launch.sh",
    "services/kill": "bash frontend/scripts/kill.sh; bash api/scripts/kill.sh; bash data/scripts/kill.sh",

    # ETL — need .env sourced and venv activated
    "etl/reset-tables": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.etl.reset_tables",
    "etl/reset-buckets": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.etl.reset_bucket",
    "etl/reset-all": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.etl.reset_all",
    "etl/snapshot-tables": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.etl.snapshot_tables",
    "etl/snapshot-buckets": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.etl.snapshot_buckets",
    "etl/snapshot-all": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.etl.snapshot_all",

    # Linting — scripts handle their own env
    "lint/bash": "bash scripts/lint.sh",
    "lint/python": "bash scripts/lint-api.sh",
    "lint/frontend": "bash frontend/scripts/lint.sh",

    # Validation — need .env sourced and venv activated
    "validate/catalog": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.schema.validate_data_catalog",
    "validate/translations": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.translations.validate_translations",
    "validate/all": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.schema.validate_data_catalog && python -m dev.translations.validate_translations",

    # Data — need .env sourced and venv activated
    "data/generate-translations": "set -a && source .env && set +a && source .venv/bin/activate && python -m dev.translations.generate_translations",

    # Lint all — run all three linters sequentially
    "lint/all": "bash scripts/lint.sh && bash scripts/lint-api.sh && bash frontend/scripts/lint.sh",

    # Tests — scripts handle their own env
    "tests/api": "bash scripts/run_tests.sh",
    "tests/api-no-coverage": "bash scripts/run_tests.sh --no-coverage",
    "tests/browser": "bash scripts/run_tests.sh -m browser --no-coverage",
    "tests/browser-headed": "bash scripts/run_tests.sh -m browser --no-coverage --headed",
}


#
# Task Registry
#

# In-memory store for running and completed tasks
tasks: dict = {}


#
# App
#

app = FastAPI(title="Mago Dev Dashboard")


#
# Helper Functions
#


def check_port(port: int) -> bool:
    """
    Check if a port is listening using lsof.

    @param port (int): Port number to check
    @returns bool - True if port is in use
    """
    result = subprocess.run(
        ["lsof", "-i", f":{port}"],
        capture_output=True,
        timeout=5,
    )
    return result.returncode == 0


async def run_task(command: str, task_id: str):
    """
    Run a shell command as a subprocess and capture output line by line.

    @param command (str): Shell command string to execute
    @param task_id (str): Task ID to store output under
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "bash", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT_DIR),
        )

        tasks[task_id]["process"] = process

        # Stream output line by line
        async for line in process.stdout:
            text = line.decode("utf-8", errors="replace").rstrip("\n")
            tasks[task_id]["lines"].append(text)

        await process.wait()
        tasks[task_id]["status"] = "completed" if process.returncode == 0 else "failed"
        tasks[task_id]["exit_code"] = process.returncode

    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["lines"].append(f"Error: {e}")
        tasks[task_id]["exit_code"] = 1


def start_task(command_key: str) -> dict:
    """
    Start a new background task and return its ID.

    @param command_key (str): Key into COMMANDS dict
    @returns dict - Task ID and command string, or error
    """

    # Look up the command
    if command_key not in COMMANDS:
        return {"error": f"Unknown command: {command_key}"}

    # Generate a short task ID
    task_id = str(uuid.uuid4())[:8]
    command = COMMANDS[command_key]

    # Register the task
    tasks[task_id] = {
        "command_key": command_key,
        "command": command,
        "status": "running",
        "lines": [],
        "process": None,
        "exit_code": None,
    }

    # Launch the subprocess in the background
    asyncio.create_task(run_task(command, task_id))
    logger.info("Started task %s: %s", task_id, command_key)

    return {"task_id": task_id, "command": command_key}


#
# Routes
#


@app.get("/")
async def serve_dashboard():
    """Serve the dashboard HTML page."""
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/favicon.png")
async def serve_favicon():
    """Serve the favicon."""
    return FileResponse(ROOT_DIR / "frontend" / "public" / "favicon.png")


@app.get("/status")
async def get_status():
    """Check which services are running by probing their ports."""
    return {
        name: {"port": port, "running": check_port(port)}
        for name, port in PORTS.items()
    }


@app.get("/tasks")
async def list_tasks():
    """List all tasks with their current status."""
    return {
        task_id: {
            "command_key": info["command_key"],
            "status": info["status"],
            "exit_code": info["exit_code"],
        }
        for task_id, info in tasks.items()
    }


@app.post("/run/{command_key:path}")
async def run_command(command_key: str):
    """
    Start a task by command key (e.g. services/launch, etl/reset-all).

    @param command_key (str): Key matching a COMMANDS entry
    @returns dict - Task ID or error
    """
    result = start_task(command_key)
    if "error" in result:
        return JSONResponse(result, status_code=400)
    return result


@app.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """
    SSE stream of a task's stdout/stderr output.

    @param task_id (str): Task ID to stream
    @returns StreamingResponse - Server-sent events
    """

    # Check task exists
    if task_id not in tasks:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    async def event_stream():
        task = tasks[task_id]
        sent = 0

        while True:

            # Send any new lines since last check
            while sent < len(task["lines"]):
                line = task["lines"][sent]

                # Escape newlines in the data field
                yield f"data: {line}\n\n"
                sent += 1

            # If the task is done, send a final event and stop
            if task["status"] != "running":
                yield f"event: done\ndata: {task['exit_code']}\n\n"
                break

            # Poll for new output
            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


#
# Main
#

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
