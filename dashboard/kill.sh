#!/bin/bash

#
# Configuration
#

# Dashboard port
DASHBOARD_PORT=3470

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

# Check if dashboard is running
if ! check_port "$DASHBOARD_PORT"; then
    echo "Dashboard is not running on port $DASHBOARD_PORT"
    exit 0
fi

# Get PIDs
pids=$(lsof -t -i :"$DASHBOARD_PORT" 2>/dev/null || true)
if [ -z "$pids" ]; then
    echo "Dashboard is not running on port $DASHBOARD_PORT"
    exit 0
fi

# Kill the processes
echo "Killing dashboard on port $DASHBOARD_PORT..."
while IFS= read -r pid; do
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null || true
    fi
done <<< "$pids"

# Wait for termination
for _ in {1..5}; do
    if ! check_port "$DASHBOARD_PORT"; then
        echo "Dashboard terminated successfully"
        exit 0
    fi
    sleep 1
done

# Force kill
echo "Force killing dashboard..."
pids=$(lsof -t -i :"$DASHBOARD_PORT" 2>/dev/null || true)
while IFS= read -r pid; do
    if [ -n "$pid" ]; then
        kill -9 "$pid" 2>/dev/null || true
    fi
done <<< "$pids"

if ! check_port "$DASHBOARD_PORT"; then
    echo "Dashboard force-terminated successfully"
    exit 0
fi

echo "Failed to terminate dashboard on port $DASHBOARD_PORT"
exit 1
