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

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "TIMEPOINT Flash Server"
    echo ""
    echo "Usage: ./run.sh [options]"
    echo ""
    echo "Options:"
    echo "  -r, --reload      Enable auto-reload (development mode)"
    echo "  -p, --port PORT   Set port (default: 8000)"
    echo "  -h, --host HOST   Set host (default: 127.0.0.1)"
    echo "  -w, --workers N   Number of workers (default: 1, ignored with --reload)"
    echo "  -d, --debug       Enable debug logging"
    echo "  -P, --prod        Production mode (0.0.0.0, 4 workers, no reload)"
    echo "  --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  ./run.sh -r              # Development with auto-reload"
    echo "  ./run.sh -r -p 3000      # Dev mode on port 3000"
    echo "  ./run.sh -P              # Production mode"
    echo "  ./run.sh -w 4            # 4 workers"
    echo ""
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--reload)
            RELOAD="--reload"
            shift
            ;;
        -p|--port)
            PORT="$2"
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
echo -e "${GREEN}Starting TIMEPOINT Flash Server v2.0.3${NC}"
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
echo -e "  HD:       Gemini 3 Pro + Nano Banana Pro (2K images)"
echo -e "  Balanced: Gemini 2.5 Flash + Nano Banana"
echo -e "  Hyper:    Llama 3.1 8B + fast image gen (OpenRouter)"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Run server
exec $CMD
