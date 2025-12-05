#!/bin/bash
# TIMEPOINT Flash Server Runner
# Usage: ./run.sh [options]

set -e

# Default values
HOST="127.0.0.1"
PORT="8000"
RELOAD=""
WORKERS="1"
LOG_LEVEL="info"
KILL_EXISTING="false"
ADAPTIVE_PORT="true"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if a port is in use
port_in_use() {
    lsof -i:"$1" >/dev/null 2>&1
}

# Kill process on a port
kill_port() {
    local port="$1"
    local pids=$(lsof -ti:"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Killing existing process(es) on port $port...${NC}"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
        return 0
    fi
    return 1
}

# Find an available port starting from the given port
find_available_port() {
    local port="$1"
    local max_tries=10
    local try=0

    while [ $try -lt $max_tries ]; do
        if ! port_in_use "$port"; then
            echo "$port"
            return 0
        fi
        port=$((port + 1))
        try=$((try + 1))
    done

    # No available port found
    echo ""
    return 1
}

usage() {
    echo "TIMEPOINT Flash Server"
    echo ""
    echo "Usage: ./run.sh [options]"
    echo ""
    echo "Options:"
    echo "  -r, --reload      Enable auto-reload (development mode)"
    echo "  -p, --port PORT   Set port (default: 8000, auto-finds available)"
    echo "  -h, --host HOST   Set host (default: 127.0.0.1)"
    echo "  -w, --workers N   Number of workers (default: 1, ignored with --reload)"
    echo "  -d, --debug       Enable debug logging"
    echo "  -P, --prod        Production mode (0.0.0.0, 4 workers, no reload)"
    echo "  -k, --kill        Kill existing process on port before starting"
    echo "  -n, --no-adaptive Disable adaptive port (fail if port in use)"
    echo "  --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  ./run.sh -r              # Development with auto-reload"
    echo "  ./run.sh -r -p 3000      # Dev mode on port 3000"
    echo "  ./run.sh -P              # Production mode"
    echo "  ./run.sh -w 4            # 4 workers"
    echo "  ./run.sh -k              # Kill existing and start"
    echo ""
    exit 0
}

# Parse arguments
REQUESTED_PORT=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--reload)
            RELOAD="--reload"
            shift
            ;;
        -p|--port)
            PORT="$2"
            REQUESTED_PORT="$2"
            shift 2
            ;;
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -d|--debug)
            LOG_LEVEL="debug"
            shift
            ;;
        -P|--prod)
            HOST="0.0.0.0"
            WORKERS="4"
            RELOAD=""
            LOG_LEVEL="warning"
            shift
            ;;
        -k|--kill)
            KILL_EXISTING="true"
            shift
            ;;
        -n|--no-adaptive)
            ADAPTIVE_PORT="false"
            shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Check for .env file
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Create one with: cp .env.example .env"
    echo ""
fi

# Handle port conflicts
if [ "$KILL_EXISTING" = "true" ]; then
    # Kill any existing process on the port
    if port_in_use "$PORT"; then
        kill_port "$PORT"
    fi
elif port_in_use "$PORT"; then
    if [ "$ADAPTIVE_PORT" = "true" ]; then
        ORIGINAL_PORT="$PORT"
        PORT=$(find_available_port "$PORT")
        if [ -z "$PORT" ]; then
            echo -e "${RED}Error: Could not find available port (tried $ORIGINAL_PORT-$((ORIGINAL_PORT + 9)))${NC}"
            echo -e "Use ${CYAN}-k${NC} to kill existing process, or ${CYAN}-p PORT${NC} to specify different port"
            exit 1
        fi
        if [ "$PORT" != "$ORIGINAL_PORT" ]; then
            echo -e "${YELLOW}Port $ORIGINAL_PORT in use, using port $PORT instead${NC}"
            echo ""
        fi
    else
        echo -e "${RED}Error: Port $PORT is already in use${NC}"
        echo -e "Use ${CYAN}-k${NC} to kill existing process, or ${CYAN}-p PORT${NC} to specify different port"
        exit 1
    fi
fi

# Build command
CMD="python3.10 -m uvicorn app.main:app --host $HOST --port $PORT --log-level $LOG_LEVEL"

if [ -n "$RELOAD" ]; then
    CMD="$CMD $RELOAD"
else
    CMD="$CMD --workers $WORKERS"
fi

# Print startup info
echo -e "${CYAN}"
echo "  _____ ___ __  __ _____ ____   ___ ___ _   _ _____"
echo " |_   _|_ _|  \/  | ____|  _ \ / _ \_ _| \\ | |_   _|"
echo "   | |  | || |\\/| |  _| | |_) | | | | ||  \\| | | |"
echo "   | |  | || |  | | |___|  __/| |_| | || |\\  | | |"
echo "   |_| |___|_|  |_|_____|_|    \\___/___|_| \\_| |_|"
echo -e "${NC}"
echo -e "${GREEN}Starting TIMEPOINT Flash Server v2.0.11${NC}"
echo ""
echo -e "  Host:     ${CYAN}$HOST${NC}"
echo -e "  Port:     ${CYAN}$PORT${NC}"
echo -e "  Workers:  ${CYAN}$WORKERS${NC}"
echo -e "  Reload:   ${CYAN}$([ -n "$RELOAD" ] && echo "enabled" || echo "disabled")${NC}"
echo -e "  Log:      ${CYAN}$LOG_LEVEL${NC}"
echo ""
echo -e "  API:      ${CYAN}http://$HOST:$PORT${NC}"
echo -e "  Docs:     ${CYAN}http://$HOST:$PORT/docs${NC}"
echo -e "  Health:   ${CYAN}http://$HOST:$PORT/health${NC}"
echo ""
echo -e "${GREEN}Quality Presets:${NC}"
echo -e "  HD:       Gemini 2.5 Flash (extended thinking) + Nano Banana"
echo -e "  Balanced: Gemini 2.5 Flash + Nano Banana"
echo -e "  Hyper:    Gemini 2.0 Flash via OpenRouter + Nano Banana (fastest)"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Run server
exec $CMD
