#!/bin/bash

#
# Configuration
#

# Get the location of the script's parent directory and change to that directory
base_dir="$(dirname "$0")"
cd "$base_dir" || { echo "Failed to change directory"; exit 1; }
base_dir="$(pwd)"

# Parent directory (Mago root — .env and .venv live here)
parent_dir="$(cd "$base_dir/../.." && pwd)"

# Dashboard port
DASHBOARD_PORT=3470

# Exit on any error
set -e

#
# Constants
#

# Script paths
KILL_SCRIPT="$base_dir/kill.sh"

#
# Functions
#

# Check if a port is in use
#
# @param [port] [port number]
# @returns [0 if port is in use, 1 if not]
check_port() {
    local port=$1
    if lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

#
# Main Execution
#

# Kill existing dashboard process
echo "Terminating any existing dashboard process..."
bash "$KILL_SCRIPT"

# Check if port is available
if check_port "$DASHBOARD_PORT"; then
    echo "Port $DASHBOARD_PORT is still in use after cleanup"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$parent_dir/.venv" ]; then
    echo "Python virtual environment not found. Run setup_venv.sh first."
    exit 1
fi

# Activate virtual environment
source "$parent_dir/.venv/bin/activate"

# Create log directory
LOG_FOLDER_NAME="$(date +%Y-%m-%d_%H-%M-%S)"
mkdir -p "$base_dir/logs/$LOG_FOLDER_NAME"

# Trap Ctrl+C to kill the server
trap 'echo "Shutting down dashboard..."; bash "$KILL_SCRIPT"; exit 0' INT TERM

# Start the dashboard server in the foreground
echo "Starting dashboard on port $DASHBOARD_PORT..."
cd "$parent_dir"
python dev/dashboard/server.py 2>&1 | tee "$base_dir/logs/$LOG_FOLDER_NAME/dashboard.log"
