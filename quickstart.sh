#!/bin/bash
# TIMEPOINT Flash Quickstart v2.3.0
# One-command demo that shows off the best of TIMEPOINT

set -e

# Configuration
API_BASE="http://localhost:8000"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Demo queries (chosen for visual impact and historical significance)
DEMO_QUERIES=(
    "assassination of julius caesar ides of march"
    "neil armstrong first steps on the moon 1969"
    "signing of the declaration of independence"
    "fall of the berlin wall 1989"
    "leonardo da vinci painting the mona lisa"
)

# Pick a random query
RANDOM_INDEX=$((RANDOM % ${#DEMO_QUERIES[@]}))
DEMO_QUERY="${DEMO_QUERIES[$RANDOM_INDEX]}"

echo -e "${CYAN}"
echo "  _____ ___ __  __ _____ ____   ___ ___ _   _ _____ "
echo " |_   _|_ _|  \/  | ____|  _ \ / _ \_ _| \\ | |_   _|"
echo "   | |  | || |\\/| |  _| | |_) | | | | ||  \\| | | |  "
echo "   | |  | || |  | | |___|  __/| |_| | || |\\  | | |  "
echo "   |_| |___|_|  |_|_____|_|    \\___/___|_| \\_| |_|  "
echo -e "${NC}"
echo -e "${BOLD}TIMEPOINT Flash v2.3.0 Quickstart${NC}"
echo ""
echo -e "${DIM}Dial into any moment in history${NC}"
echo ""

# Check if server is running
check_server() {
    if curl -sf "$API_BASE/health" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Start server if not running
start_server() {
    echo -e "${YELLOW}Starting server...${NC}"
    ./run.sh &
    SERVER_PID=$!

    # Wait for server to be ready
    echo -n "Waiting for server"
    for i in {1..30}; do
        if check_server; then
            echo ""
            echo -e "${GREEN}Server is ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo ""
    echo -e "${RED}Server failed to start${NC}"
    echo "Check your .env file has valid API keys"
    exit 1
}

# Check prerequisites
echo -e "${BOLD}Checking setup...${NC}"
echo ""

if [ ! -f .env ]; then
    echo -e "${RED}[FAIL]${NC} No .env file found"
    echo -e "Run ${CYAN}./setup.sh${NC} first"
    exit 1
fi

if ! check_server; then
    echo -e "${YELLOW}[INFO]${NC} Server not running"
    start_server
else
    echo -e "${GREEN}[OK]${NC} Server is running"
fi

# Get health info
echo ""
HEALTH=$(curl -sf "$API_BASE/health" 2>/dev/null || echo '{}')
VERSION=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','unknown'))" 2>/dev/null || echo "unknown")
echo -e "${GREEN}[OK]${NC} TIMEPOINT Flash v$VERSION"

# Check providers
PROVIDERS=$(curl -sf "$API_BASE/api/v1/models/providers" 2>/dev/null || echo '{}')
GOOGLE_OK=$(echo "$PROVIDERS" | python3 -c "
import sys,json
d = json.load(sys.stdin)
for p in d.get('providers', []):
    if p.get('provider') == 'google':
        print('yes' if p.get('available') else 'no')
        break
else:
    print('no')
" 2>/dev/null || echo "no")

OPENROUTER_OK=$(echo "$PROVIDERS" | python3 -c "
import sys,json
d = json.load(sys.stdin)
for p in d.get('providers', []):
    if p.get('provider') == 'openrouter':
        print('yes' if p.get('available') else 'no')
        break
else:
    print('no')
" 2>/dev/null || echo "no")

if [ "$GOOGLE_OK" = "yes" ]; then
    echo -e "${GREEN}[OK]${NC} Google API connected"
else
    echo -e "${YELLOW}[WARN]${NC} Google API not available"
fi

if [ "$OPENROUTER_OK" = "yes" ]; then
    echo -e "${GREEN}[OK]${NC} OpenRouter connected"
fi

echo ""

# Generate demo timepoint
echo -e "${BOLD}Generating your first timepoint...${NC}"
echo ""
echo -e "${CYAN}Query:${NC} ${BOLD}\"$DEMO_QUERY\"${NC}"
echo ""
echo -e "${DIM}This will take 1-2 minutes. Watch the AI pipeline work:${NC}"
echo ""

# Use streaming endpoint with progress display
curl -sfN -X POST "$API_BASE/api/v1/timepoints/generate/stream" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$DEMO_QUERY\", \"preset\": \"balanced\", \"generate_image\": false}" 2>/dev/null | while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue

    # Parse SSE data
    if [[ "$line" == data:* ]]; then
        data="${line#data: }"

        # Parse JSON event
        event=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event',''))" 2>/dev/null || echo "")
        step=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('step',''))" 2>/dev/null || echo "")
        progress=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('progress',0))" 2>/dev/null || echo "0")

        case "$event" in
            "start")
                echo -e "${CYAN}[START]${NC} Initializing pipeline..."
                ;;
            "step_start")
                case "$step" in
                    "judge") echo -e "${DIM}  Validating historical query...${NC}" ;;
                    "timeline") echo -e "${DIM}  Extracting date and location...${NC}" ;;
                    "grounding") echo -e "${DIM}  Verifying facts via Google Search...${NC}" ;;
                    "scene") echo -e "${DIM}  Building scene environment...${NC}" ;;
                    "characters") echo -e "${DIM}  Generating 8 historical figures...${NC}" ;;
                    "graph") echo -e "${DIM}  Mapping relationships...${NC}" ;;
                    "moment") echo -e "${DIM}  Capturing dramatic tension...${NC}" ;;
                    "dialog") echo -e "${DIM}  Writing period dialog...${NC}" ;;
                    "camera") echo -e "${DIM}  Composing visual frame...${NC}" ;;
                    "image_prompt") echo -e "${DIM}  Creating image prompt...${NC}" ;;
                esac
                ;;
            "step_complete")
                case "$step" in
                    "judge") echo -e "${GREEN}[${progress}%]${NC} Query validated" ;;
                    "timeline") echo -e "${GREEN}[${progress}%]${NC} Timeline locked" ;;
                    "grounding") echo -e "${GREEN}[${progress}%]${NC} Facts verified" ;;
                    "scene") echo -e "${GREEN}[${progress}%]${NC} Scene set" ;;
                    "characters") echo -e "${GREEN}[${progress}%]${NC} Characters created" ;;
                    "graph") echo -e "${GREEN}[${progress}%]${NC} Relationships mapped" ;;
                    "moment") echo -e "${GREEN}[${progress}%]${NC} Moment captured" ;;
                    "dialog") echo -e "${GREEN}[${progress}%]${NC} Dialog written" ;;
                    "camera") echo -e "${GREEN}[${progress}%]${NC} Frame composed" ;;
                    "image_prompt") echo -e "${GREEN}[${progress}%]${NC} Image prompt ready" ;;
                esac
                ;;
            "done")
                echo ""
                echo -e "${GREEN}[100%]${NC} Generation complete!"

                # Extract key info
                tp_id=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('timepoint_id',''))" 2>/dev/null || echo "")

                if [ -n "$tp_id" ]; then
                    echo ""
                    echo -e "${BOLD}Timepoint ID:${NC} $tp_id"

                    # Fetch full result
                    RESULT=$(curl -sf "$API_BASE/api/v1/timepoints/$tp_id?full=true" 2>/dev/null || echo '{}')

                    # Extract and display key fields
                    echo ""
                    echo -e "${CYAN}${BOLD}========================================${NC}"
                    echo -e "${BOLD}YOUR TIMEPOINT${NC}"
                    echo -e "${CYAN}${BOLD}========================================${NC}"
                    echo ""

                    echo "$RESULT" | python3 -c "
import sys, json

d = json.load(sys.stdin)

# Date and location
year = d.get('year', '?')
month = d.get('month', '')
day = d.get('day', '')
location = d.get('location', 'Unknown')
time_of_day = d.get('time_of_day', '')

date_str = str(year)
if month:
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    date_str = f'{months[int(month)]} {day}, {year}' if day else f'{months[int(month)]} {year}'

print(f'\033[1mWhen:\033[0m {date_str}' + (f' ({time_of_day})' if time_of_day else ''))
print(f'\033[1mWhere:\033[0m {location}')
print()

# Characters
chars = d.get('characters', {}).get('characters', [])
if chars:
    print('\033[1mCharacters:\033[0m')
    for c in chars[:5]:
        name = c.get('name', 'Unknown')
        role = c.get('role', '')
        desc = c.get('historical_context', c.get('description', ''))[:60]
        print(f'  - {name}' + (f' ({role})' if role else '') + (f': {desc}...' if desc else ''))
    if len(chars) > 5:
        print(f'  ... and {len(chars) - 5} more')
    print()

# Dialog
dialog = d.get('dialog', [])
if dialog:
    print('\033[1mDialog:\033[0m')
    for line in dialog[:4]:
        speaker = line.get('speaker', 'Unknown')
        text = line.get('text', '')[:100]
        print(f'  \033[36m{speaker}:\033[0m \"{text}\"')
    if len(dialog) > 4:
        print(f'  ... and {len(dialog) - 4} more lines')
    print()

# Scene atmosphere
scene = d.get('scene', {})
if scene:
    atmosphere = scene.get('atmosphere', scene.get('mood', ''))
    if atmosphere:
        print(f'\033[1mAtmosphere:\033[0m {atmosphere[:150]}')
        print()
"
                fi
                ;;
            "error"|"step_error")
                error=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','Unknown error'))" 2>/dev/null || echo "Error")
                echo -e "${RED}[ERROR]${NC} $error"
                ;;
        esac
    fi
done

echo ""
echo -e "${CYAN}${BOLD}========================================${NC}"
echo -e "${BOLD}WHAT'S NEXT?${NC}"
echo -e "${CYAN}${BOLD}========================================${NC}"
echo ""
echo -e "  ${CYAN}./demo.sh${NC}              Full interactive demo"
echo -e "  ${CYAN}./eval.sh -i${NC}           Compare AI models"
echo -e "  ${CYAN}http://localhost:8000/docs${NC}  API documentation"
echo ""
echo -e "${DIM}Chat with characters, jump through time, and explore history!${NC}"
echo ""
