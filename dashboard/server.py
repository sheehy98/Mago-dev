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
from dotenv import dotenv_values

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


# Load port maps from env files using dotenv
def _load_ports(suffix=""):
    """Load env files with given suffix and return service port map."""
    env = dotenv_values(ROOT_DIR / f".env{suffix}")
    env.update(dotenv_values(ROOT_DIR / "data" / f".env{suffix}"))
    env.update(dotenv_values(ROOT_DIR / "frontend" / f".env{suffix}"))
    return {
        "postgresql": int(env.get("POSTGRES_INTERNAL_PORT", "5432") if not suffix else env.get("POSTGRES_PORT", "5432")),
        "minio": int(env.get("MINIO_INTERNAL_PORT", "9000") if not suffix else env.get("MINIO_PORT", "9000")),
        "api": int(env.get("API_PORT", "3461")),
        "frontend": int(env.get("VITE_PORT", "3460")),
    }


DEV_PORTS = _load_ports()
PROD_PORTS = _load_ports(".production")


# Dashboard port
DASHBOARD_PORT = 3470

# Venv python path
VENV_PYTHON = str(ROOT_DIR / ".venv" / "bin" / "python")

# Current environment mode ("dev" or "production")
current_mode = "dev"

# Command definitions
# Each command is a shell string run via bash -c, with cwd set to ROOT_DIR
# Commands tagged with supports_prod=True get -p appended in production mode
COMMANDS = {

    # Service management — scripts support -p natively
    "services/launch": {
        "cmd": "bash data/scripts/launch.sh && bash api/scripts/launch.sh && bash frontend/scripts/launch.sh",
        "prod_cmd": "bash data/scripts/launch.sh -p && bash api/scripts/launch.sh -p && bash frontend/scripts/launch.sh -p",
    },
    "services/kill": {
        "cmd": "bash frontend/scripts/kill.sh; bash api/scripts/kill.sh; bash data/scripts/kill.sh",
        "prod_cmd": "bash frontend/scripts/kill.sh -p; bash api/scripts/kill.sh -p; bash data/scripts/kill.sh -p",
    },

    # ETL — dev.env handles .env loading, -p flag selects production
    "etl/reset-tables": {
        "cmd": "source .venv/bin/activate && python -m dev.etl.reset_tables",
        "prod_cmd": "source .venv/bin/activate && python -m dev.etl.reset_tables -p",
    },
    "etl/reset-buckets": {
        "cmd": "source .venv/bin/activate && python -m dev.etl.reset_bucket",
        "prod_cmd": "source .venv/bin/activate && python -m dev.etl.reset_bucket -p",
    },
    "etl/reset-all": {
        "cmd": "source .venv/bin/activate && python -m dev.etl.reset_all",
        "prod_cmd": "source .venv/bin/activate && python -m dev.etl.reset_all -p",
    },
    "etl/snapshot-tables": {
        "cmd": "source .venv/bin/activate && python -m dev.etl.snapshot_tables",
        "prod_cmd": "source .venv/bin/activate && python -m dev.etl.snapshot_tables -p",
    },
    "etl/snapshot-buckets": {
        "cmd": "source .venv/bin/activate && python -m dev.etl.snapshot_buckets",
        "prod_cmd": "source .venv/bin/activate && python -m dev.etl.snapshot_buckets -p",
    },
    "etl/snapshot-all": {
        "cmd": "source .venv/bin/activate && python -m dev.etl.snapshot_all",
        "prod_cmd": "source .venv/bin/activate && python -m dev.etl.snapshot_all -p",
    },

    # Linting — not environment-specific
    "lint/bash": {"cmd": "bash scripts/lint.sh"},
    "lint/python": {"cmd": "bash scripts/lint-api.sh"},
    "lint/frontend": {"cmd": "bash frontend/scripts/lint.sh"},
    "lint/all": {"cmd": "bash scripts/lint.sh && bash scripts/lint-api.sh && bash frontend/scripts/lint.sh"},

    # Validation — always runs against dev
    "validate/catalog": {"cmd": "source .venv/bin/activate && python -m dev.schema.validate_data_catalog"},
    "validate/translations": {"cmd": "source .venv/bin/activate && python -m dev.translations.validate_translations"},
    "validate/all": {"cmd": "source .venv/bin/activate && python -m dev.schema.validate_data_catalog && python -m dev.translations.validate_translations"},

    # Data — always runs against dev
    "data/generate-translations": {"cmd": "source .venv/bin/activate && python -m dev.translations.generate_translations"},

    # Tests — always use isolated containers, not environment-specific
    "tests/api": {"cmd": "bash scripts/run_tests.sh"},
    "tests/api-no-coverage": {"cmd": "bash scripts/run_tests.sh --no-coverage"},
    "tests/browser": {"cmd": "bash scripts/run_tests.sh -m browser --no-coverage"},
    "tests/browser-headed": {"cmd": "bash scripts/run_tests.sh -m browser --no-coverage --headed"},
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
        # Build a clean env — only essentials, so subprocesses
        # don't inherit stale env vars from the parent process
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "TERM": os.environ.get("TERM", "xterm"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        }

        # Pass mode to subprocess so dev.env picks it up
        if current_mode == "production":
            clean_env["MAGO_ENV"] = "production"

        process = await asyncio.create_subprocess_exec(
            "bash", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT_DIR),
            env=clean_env,
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


def get_command(command_key: str) -> str | None:
    """
    Get the shell command for a command key, respecting current mode.

    @param command_key (str): Key into COMMANDS dict
    @returns str | None - Shell command string, or None if not found
    """

    entry = COMMANDS.get(command_key)
    if entry is None:
        return None

    # Use production command if in production mode and one exists
    if current_mode == "production" and "prod_cmd" in entry:
        return entry["prod_cmd"]

    return entry["cmd"]


def start_task(command_key: str) -> dict:
    """
    Start a new background task and return its ID.

    @param command_key (str): Key into COMMANDS dict
    @returns dict - Task ID and command string, or error
    """

    # Look up the command
    command = get_command(command_key)
    if command is None:
        return {"error": f"Unknown command: {command_key}"}

    # Generate a short task ID
    task_id = str(uuid.uuid4())[:8]

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
    logger.info("Started task %s (%s): %s", task_id, current_mode, command_key)

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


@app.get("/mode")
async def get_mode():
    """Get the current environment mode."""
    return {"mode": current_mode}


@app.post("/mode/{mode}")
async def set_mode(mode: str):
    """Switch between dev and production mode."""
    global current_mode
    if mode not in ("dev", "production"):
        return JSONResponse({"error": "Mode must be 'dev' or 'production'"}, status_code=400)
    current_mode = mode
    logger.info("Switched to %s mode", mode)
    return {"mode": current_mode}


@app.get("/status")
async def get_status():
    """Check which services are running by probing their ports."""
    ports = PROD_PORTS if current_mode == "production" else DEV_PORTS
    return {
        name: {"port": port, "running": check_port(port)}
        for name, port in ports.items()
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
