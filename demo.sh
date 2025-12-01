#!/bin/bash
# TIMEPOINT Flash Demo CLI
# Interactive menu for generating historical timepoints

set -e

# Configuration
API_BASE="http://localhost:8000"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Store timepoint IDs for quick access
declare -a TIMEPOINT_IDS=()

# Quality presets
PRESET_HD="hd"
PRESET_HYPER="hyper"
PRESET_BALANCED="balanced"
CURRENT_PRESET=""

# Preset selection helper
select_preset() {
    echo -e "${BOLD}Select Quality Preset:${NC}"
    echo ""
    echo -e "  ${MAGENTA}1)${NC} ${BOLD}HD${NC} - Best quality (Gemini 3 Pro + Nano Banana Pro)"
    echo -e "     ${DIM}2K images, high reasoning, slowest but best fidelity${NC}"
    echo -e "  ${GREEN}2)${NC} ${BOLD}Balanced${NC} - Good balance (Gemini 2.5 Flash + Nano Banana)"
    echo -e "     ${DIM}Default mode, good speed and quality${NC}"
    echo -e "  ${CYAN}3)${NC} ${BOLD}Hyper${NC} - Maximum speed (Llama 3.1 8B + fast image gen)"
    echo -e "     ${DIM}OpenRouter, fastest generation, reduced tokens${NC}"
    echo ""
    echo -e "${YELLOW}> ${NC}\c"
    read -r preset_choice

    case "$preset_choice" in
        1) CURRENT_PRESET="$PRESET_HD"; echo -e "${MAGENTA}Using HD preset (Nano Banana Pro)${NC}" ;;
        3) CURRENT_PRESET="$PRESET_HYPER"; echo -e "${CYAN}Using Hyper preset (OpenRouter)${NC}" ;;
        *) CURRENT_PRESET="$PRESET_BALANCED"; echo -e "${GREEN}Using Balanced preset (Nano Banana)${NC}" ;;
    esac
    echo ""
}

# Sample templates
declare -a TEMPLATES=(
    "signing of the declaration of independence"
    "assassination of Julius Caesar"
    "moon landing 1969"
    "battle of thermopylae"
    "fall of the berlin wall"
    "boston tea party 1773"
    "coronation of napoleon"
    "wright brothers first flight"
    "martin luther king i have a dream speech"
    "fall of rome 476 AD"
)

# Functions
print_header() {
    clear
    echo -e "${CYAN}"
    echo "  _____ ___ __  __ _____ ____   ___ ___ _   _ _____   _____ _        _    ____  _   _ "
    echo " |_   _|_ _|  \/  | ____|  _ \ / _ \_ _| \ | |_   _| |  ___| |      / \  / ___|| | | |"
    echo "   | |  | || |\/| |  _| | |_) | | | | ||  \| | | |   | |_  | |     / _ \ \___ \| |_| |"
    echo "   | |  | || |  | | |___|  __/| |_| | || |\  | | |   |  _| | |___ / ___ \ ___) |  _  |"
    echo "   |_| |___|_|  |_|_____|_|    \___/___|_| \_| |_|   |_|   |_____/_/   \_\____/|_| |_|"
    echo -e "${NC}"
    echo -e "${BOLD}AI-Powered Temporal Simulation Engine v2.0.3${NC}"
    echo -e "${DIM}Google Nano Banana Pro | OpenRouter | Quality Presets${NC}"
    echo ""
}

print_menu() {
    echo -e "${BOLD}=== Main Menu ===${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} Generate timepoint (sync) - Wait for full result"
    echo -e "  ${GREEN}2)${NC} Generate timepoint (streaming) - See live progress"
    echo -e "  ${GREEN}3)${NC} Generate from template"
    echo -e "  ${GREEN}4)${NC} Browse timepoints"
    echo -e "  ${GREEN}5)${NC} Health check"
    echo -e "  ${GREEN}6)${NC} API documentation"
    echo -e "  ${RED}q)${NC} Quit"
    echo ""
}

check_server() {
    if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
        echo -e "${RED}Error: Server not running at $API_BASE${NC}"
        echo -e "Start it with: ${CYAN}./run.sh -r${NC}"
        exit 1
    fi
}

wait_for_key() {
    echo ""
    echo -e "${DIM}Press any key to continue...${NC}"
    read -n 1 -s
}

# Save image from timepoint if it exists
save_image_if_exists() {
    local tp_id="$1"

    # Fetch timepoint with image data (include_image=true required for base64)
    response=$(curl -s "$API_BASE/api/v1/timepoints/$tp_id?include_image=true")
    image_b64=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('image_base64','') or '')" 2>/dev/null || echo "")

    if [ -n "$image_b64" ] && [ "$image_b64" != "None" ]; then
        # Create images directory
        mkdir -p images
        image_file="images/timepoint_${tp_id:0:8}.png"

        # Decode and save
        echo "$image_b64" | base64 -d > "$image_file" 2>/dev/null

        if [ -f "$image_file" ] && [ -s "$image_file" ]; then
            echo -e "${GREEN}Image saved to: ${CYAN}$image_file${NC}"

            # Try to open the image
            if command -v open &> /dev/null; then
                echo -e "Opening image..."
                open "$image_file"
            elif command -v xdg-open &> /dev/null; then
                xdg-open "$image_file"
            fi
        fi
    fi
}

# Shared function to view timepoint by ID
view_timepoint_by_id() {
    local tp_id="$1"
    local show_links="${2:-true}"

    if [ -z "$tp_id" ]; then
        echo -e "${RED}ID cannot be empty${NC}"
        return 1
    fi

    response=$(curl -s "$API_BASE/api/v1/timepoints/$tp_id?full=true")

    if echo "$response" | grep -q "not found"; then
        echo -e "${RED}Timepoint not found${NC}"
        return 1
    fi

    print_report "$response" ""

    if [ "$show_links" = "true" ]; then
        echo ""
        echo -e "${CYAN}--- VIEW LINKS ---${NC}"
        echo -e "  ${BOLD}API (JSON):${NC}  $API_BASE/api/v1/timepoints/$tp_id?full=true"
        echo -e "  ${BOLD}Swagger:${NC}     $API_BASE/docs#/timepoints/get_timepoint_api_v1_timepoints__timepoint_id__get"
        echo ""
    fi

    return 0
}

# Generate sync - with auto-redirect to view
generate_sync() {
    echo -e "${BOLD}=== Synchronous Generation ===${NC}"
    echo ""
    echo -e "Enter your temporal query (e.g., 'battle of gettysburg'):"
    echo -e "${YELLOW}> ${NC}\c"
    read -r query

    if [ -z "$query" ]; then
        echo -e "${RED}Query cannot be empty${NC}"
        return
    fi

    echo ""
    select_preset

    echo -e "Generate image? (adds ~30s) ${YELLOW}(y/n)${NC} \c"
    read -r gen_image
    generate_image="false"
    if [ "$gen_image" = "y" ] || [ "$gen_image" = "Y" ]; then
        generate_image="true"
    fi

    echo ""
    echo -e "${CYAN}Generating timepoint for: ${BOLD}$query${NC}"
    if [ "$generate_image" = "true" ]; then
        echo -e "${YELLOW}This may take 5-10 minutes (with image)...${NC}"
    else
        if [ "$CURRENT_PRESET" = "$PRESET_HYPER" ]; then
            echo -e "${CYAN}Hyper mode: Should complete in ~1-2 minutes...${NC}"
        else
            echo -e "${YELLOW}This may take 5-10 minutes...${NC}"
        fi
    fi
    echo ""

    start_time=$(date +%s)

    # Build JSON payload with preset
    json_payload="{\"query\": \"$query\", \"generate_image\": $generate_image"
    if [ -n "$CURRENT_PRESET" ]; then
        json_payload="$json_payload, \"preset\": \"$CURRENT_PRESET\""
    fi
    json_payload="$json_payload}"

    response=$(curl -s -X POST "$API_BASE/api/v1/timepoints/generate/sync" \
        -H "Content-Type: application/json" \
        -d "$json_payload")

    end_time=$(date +%s)
    duration=$((end_time - start_time))

    # Extract timepoint ID
    tp_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
    status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")

    print_report "$response" "$duration"

    if [ -n "$tp_id" ] && [ "$status" = "completed" ]; then
        echo ""
        echo -e "${GREEN}Timepoint created successfully!${NC}"
        echo ""
        echo -e "${CYAN}--- VIEW LINKS ---${NC}"
        echo -e "  ${BOLD}API (JSON):${NC}  $API_BASE/api/v1/timepoints/$tp_id?full=true"
        echo -e "  ${BOLD}ID:${NC}          $tp_id"
        echo ""
        # Check if image was generated and save it
        if [ "$generate_image" = "true" ]; then
            save_image_if_exists "$tp_id"
        fi
    elif [ "$status" = "failed" ]; then
        echo -e "${RED}Generation failed. Check server logs for details.${NC}"
    fi
}

# Generate streaming - with result capture and auto-redirect
generate_stream() {
    local query="$1"
    local skip_prompt="${2:-false}"
    local generate_image="${3:-false}"
    local preset="${4:-}"

    if [ "$skip_prompt" = "false" ]; then
        echo -e "${BOLD}=== Streaming Generation ===${NC}"
        echo ""
        echo -e "Enter your temporal query (e.g., 'french revolution'):"
        echo -e "${YELLOW}> ${NC}\c"
        read -r query

        if [ -z "$query" ]; then
            echo -e "${RED}Query cannot be empty${NC}"
            return
        fi

        echo ""
        select_preset
        preset="$CURRENT_PRESET"

        echo -e "Generate image? (adds ~30s) ${YELLOW}(y/n)${NC} \c"
        read -r gen_image
        if [ "$gen_image" = "y" ] || [ "$gen_image" = "Y" ]; then
            generate_image="true"
        fi
    fi

    if [ -z "$query" ]; then
        echo -e "${RED}Query cannot be empty${NC}"
        return
    fi

    echo ""
    echo -e "${CYAN}Streaming generation for: ${BOLD}$query${NC}"
    if [ "$generate_image" = "true" ]; then
        echo -e "${YELLOW}Watch the progress (with image generation)...${NC}"
    elif [ "$preset" = "$PRESET_HYPER" ]; then
        echo -e "${CYAN}Hyper mode: Fast generation in progress...${NC}"
    else
        echo -e "${YELLOW}Watch the progress...${NC}"
    fi
    echo ""

    # Build JSON payload with preset
    json_payload="{\"query\": \"$query\", \"generate_image\": $generate_image"
    if [ -n "$preset" ]; then
        json_payload="$json_payload, \"preset\": \"$preset\""
    fi
    json_payload="$json_payload}"

    # Clear temp file
    rm -f /tmp/timepoint_last_id

    curl -N -s -X POST "$API_BASE/api/v1/timepoints/generate/stream" \
        -H "Content-Type: application/json" \
        -d "$json_payload" | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
            data="${line#data: }"
            event=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event',''))" 2>/dev/null || echo "")
            step=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('step',''))" 2>/dev/null || echo "")
            progress=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('progress',0))" 2>/dev/null || echo "0")

            case "$event" in
                "start")
                    echo -e "${GREEN}[START]${NC} Initializing pipeline..."
                    ;;
                "step_complete")
                    bar=$(printf '%*s' $((progress/5)) '' | tr ' ' '#')
                    empty=$(printf '%*s' $((20-progress/5)) '' | tr ' ' '-')
                    echo -e "${GREEN}[${bar}${empty}] ${progress}%${NC} Completed: $step"
                    ;;
                "step_error")
                    echo -e "${RED}[ERROR]${NC} Step failed: $step"
                    ;;
                "done")
                    echo ""
                    echo -e "${GREEN}[COMPLETE]${NC} Generation finished!"
                    timepoint_id=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('timepoint_id',''))" 2>/dev/null || echo "")
                    slug=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('slug',''))" 2>/dev/null || echo "")
                    year=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('year',''))" 2>/dev/null || echo "")
                    location=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('location',''))" 2>/dev/null || echo "")
                    latency=$(echo "$data" | python3 -c "import sys,json; print(d.get('data',{}).get('total_latency_ms',0)//1000)" 2>/dev/null || echo "")

                    if [ -n "$timepoint_id" ]; then
                        echo ""
                        echo -e "${BOLD}Timepoint Created:${NC}"
                        echo -e "  ID:       ${CYAN}$timepoint_id${NC}"
                        echo -e "  Slug:     ${CYAN}$slug${NC}"
                        echo -e "  Year:     ${CYAN}$year${NC}"
                        echo -e "  Location: ${CYAN}$location${NC}"
                        if [ -n "$latency" ] && [ "$latency" != "0" ]; then
                            echo -e "  Time:     ${CYAN}${latency}s${NC}"
                        fi
                        # Write ID to temp file for later use
                        echo "$timepoint_id" > /tmp/timepoint_last_id
                    fi
                    ;;
                "error")
                    error=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','Unknown'))" 2>/dev/null || echo "Unknown")
                    echo -e "${RED}[FATAL ERROR]${NC} $error"
                    ;;
            esac
        fi
    done

    # After streaming completes, offer to view details
    if [ -f /tmp/timepoint_last_id ]; then
        final_tp_id=$(cat /tmp/timepoint_last_id)
        rm -f /tmp/timepoint_last_id

        echo ""
        echo -e "${CYAN}--- VIEW LINKS ---${NC}"
        echo -e "  ${BOLD}API (JSON):${NC}  $API_BASE/api/v1/timepoints/$final_tp_id?full=true"
        echo ""

        # Save image if it was generated
        if [ "$generate_image" = "true" ]; then
            save_image_if_exists "$final_tp_id"
        fi

        echo -e "${YELLOW}View full report? (y/n)${NC} \c"
        read -r view_choice

        if [ "$view_choice" = "y" ] || [ "$view_choice" = "Y" ]; then
            echo ""
            view_timepoint_by_id "$final_tp_id" "false"
        fi
    fi
}

# Template selection - improved flow
generate_from_template() {
    echo -e "${BOLD}=== Generate from Template ===${NC}"
    echo ""
    echo "Select a historical moment:"
    echo ""

    for i in "${!TEMPLATES[@]}"; do
        echo -e "  ${GREEN}$((i+1)))${NC} ${TEMPLATES[$i]}"
    done
    echo ""
    echo -e "${YELLOW}Enter number (1-${#TEMPLATES[@]}): ${NC}\c"
    read -r choice

    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#TEMPLATES[@]}" ]; then
        query="${TEMPLATES[$((choice-1))]}"
        echo ""
        echo -e "${CYAN}Selected: ${BOLD}$query${NC}"
        echo ""

        select_preset

        echo -e "Generate image? (adds ~30s) ${YELLOW}(y/n)${NC} \c"
        read -r gen_image
        generate_image="false"
        if [ "$gen_image" = "y" ] || [ "$gen_image" = "Y" ]; then
            generate_image="true"
        fi
        echo ""
        echo -e "Generation mode:"
        echo -e "  ${GREEN}1)${NC} Sync (wait for complete result)"
        echo -e "  ${GREEN}2)${NC} Streaming (live progress)"
        echo -e "${YELLOW}> ${NC}\c"
        read -r mode

        # Build JSON payload with preset
        json_payload="{\"query\": \"$query\", \"generate_image\": $generate_image"
        if [ -n "$CURRENT_PRESET" ]; then
            json_payload="$json_payload, \"preset\": \"$CURRENT_PRESET\""
        fi
        json_payload="$json_payload}"

        if [ "$mode" = "1" ]; then
            echo ""
            if [ "$CURRENT_PRESET" = "$PRESET_HYPER" ]; then
                echo -e "${CYAN}Hyper mode: Should complete in ~1-2 minutes...${NC}"
            else
                echo -e "${YELLOW}Generating... (5-10 minutes)${NC}"
            fi
            start_time=$(date +%s)
            response=$(curl -s -X POST "$API_BASE/api/v1/timepoints/generate/sync" \
                -H "Content-Type: application/json" \
                -d "$json_payload")
            end_time=$(date +%s)
            duration=$((end_time - start_time))

            tp_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
            print_report "$response" "$duration"

            if [ -n "$tp_id" ]; then
                echo ""
                echo -e "${CYAN}--- VIEW LINKS ---${NC}"
                echo -e "  ${BOLD}API (JSON):${NC}  $API_BASE/api/v1/timepoints/$tp_id?full=true"
                echo ""
                # Check if image was generated and save it
                save_image_if_exists "$tp_id"
            fi
        else
            # Use streaming with pre-set query and preset
            generate_stream "$query" "true" "$generate_image" "$CURRENT_PRESET"
        fi
    else
        echo -e "${RED}Invalid selection${NC}"
    fi
}

# List/Browse timepoints - with number selection
list_timepoints() {
    echo -e "${BOLD}=== Browse Timepoints ===${NC}"
    echo ""

    response=$(curl -s "$API_BASE/api/v1/timepoints?page_size=50")

    total=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null || echo "0")

    if [ "$total" = "0" ]; then
        echo -e "${YELLOW}No timepoints found. Generate one first!${NC}"
        return
    fi

    echo -e "${CYAN}Found $total timepoint(s):${NC}"
    echo ""

    # Parse and display with numbers, extract IDs to temp file
    TIMEPOINT_JSON="$response" python3 << 'PYEOF'
import os, json

data = json.loads(os.environ['TIMEPOINT_JSON'])
ids = []
for i, tp in enumerate(data.get('items', []), 1):
    ids.append(tp['id'])
    status = tp['status']
    if status == 'completed':
        status_color = '\033[32m'
    elif status == 'processing':
        status_color = '\033[33m'
    else:
        status_color = '\033[31m'

    query_display = tp['query'][:42] + '...' if len(tp['query']) > 42 else tp['query']
    print(f"  \033[1m{i:2})\033[0m [{status_color}{status:10}\033[0m] {query_display}")

    if tp.get('year'):
        era = 'BCE' if tp['year'] < 0 else 'CE'
        loc = tp.get('location', 'Unknown')[:30]
        print(f"      \033[2m{abs(tp['year'])} {era} | {loc}\033[0m")
    print()

# Write IDs to temp file
with open('/tmp/timepoint_ids', 'w') as f:
    f.write(','.join(ids))
PYEOF

    # Read IDs from temp file (|| true prevents set -e from exiting on EOF)
    TIMEPOINT_IDS=()
    if [ -f /tmp/timepoint_ids ]; then
        IFS=',' read -ra TIMEPOINT_IDS < /tmp/timepoint_ids || true
        rm -f /tmp/timepoint_ids
    fi

    # Interactive selection loop
    echo ""
    while true; do
        echo -e "${YELLOW}Enter number to view, 'd' to delete, or Enter to go back:${NC} \c"
        read -r selection

        # Empty input - go back
        if [ -z "$selection" ]; then
            break
        fi

        # Delete option
        if [ "$selection" = "d" ] || [ "$selection" = "D" ]; then
            echo -e "${YELLOW}Enter number to delete:${NC} \c"
            read -r del_num
            if [[ "$del_num" =~ ^[0-9]+$ ]]; then
                idx=$((del_num - 1))
                if [ $idx -ge 0 ] && [ $idx -lt ${#TIMEPOINT_IDS[@]} ]; then
                    delete_by_id "${TIMEPOINT_IDS[$idx]}"
                    # Refresh list
                    echo ""
                    echo -e "${DIM}Refreshing list...${NC}"
                    sleep 1
                    list_timepoints
                    return
                else
                    echo -e "${RED}Invalid number${NC}"
                fi
            fi
            continue
        fi

        # Number selection - view details
        if [[ "$selection" =~ ^[0-9]+$ ]]; then
            idx=$((selection - 1))
            if [ $idx -ge 0 ] && [ $idx -lt ${#TIMEPOINT_IDS[@]} ]; then
                echo ""
                view_timepoint_by_id "${TIMEPOINT_IDS[$idx]}"
                echo ""
            else
                echo -e "${RED}Invalid number. Enter 1-${#TIMEPOINT_IDS[@]}${NC}"
            fi
        else
            echo -e "${RED}Invalid input${NC}"
        fi
    done
}

# Delete by ID (helper)
delete_by_id() {
    local tp_id="$1"

    echo -e "${RED}Are you sure you want to delete this timepoint? (y/n)${NC} \c"
    read -r confirm

    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        response=$(curl -s -X DELETE "$API_BASE/api/v1/timepoints/$tp_id")
        deleted=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('deleted', False))" 2>/dev/null || echo "false")

        if [ "$deleted" = "True" ]; then
            echo -e "${GREEN}Deleted successfully${NC}"
        else
            echo -e "${RED}Delete failed${NC}"
            echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        fi
    else
        echo "Cancelled."
    fi
}

# Health check
health_check() {
    echo -e "${BOLD}=== Health Check ===${NC}"
    echo ""

    response=$(curl -s "$API_BASE/health")
    status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "error")

    if [ "$status" = "healthy" ]; then
        echo -e "${GREEN}Server Status: HEALTHY${NC}"
    else
        echo -e "${RED}Server Status: $status${NC}"
    fi

    echo ""
    echo "Full response:"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

    echo ""
    echo -e "${CYAN}--- ENDPOINTS ---${NC}"
    echo -e "  Health:    $API_BASE/health"
    echo -e "  API:       $API_BASE/api/v1/timepoints"
    echo -e "  Docs:      $API_BASE/docs"
    echo ""
}

# Print formatted report
print_report() {
    local response="$1"
    local duration="$2"

    echo ""
    echo -e "${BOLD}+------------------------------------------------------------------+${NC}"
    echo -e "${BOLD}|                    TIMEPOINT GENERATION REPORT                   |${NC}"
    echo -e "${BOLD}+------------------------------------------------------------------+${NC}"
    echo ""

    # Parse response with Python for reliable JSON handling
    REPORT_JSON="$response" REPORT_DURATION="$duration" python3 << 'PYEOF'
import os, json

try:
    data = json.loads(os.environ['REPORT_JSON'])
except:
    print("Error parsing response")
    exit(1)

duration = os.environ.get('REPORT_DURATION', '')

# Header info
print(f"\033[1mQuery:\033[0m {data.get('query', 'N/A')}")
print(f"\033[1mStatus:\033[0m {data.get('status', 'N/A')}")
if duration:
    print(f"\033[1mGeneration Time:\033[0m {duration} seconds")
print()

# Temporal coordinates
print("\033[36m--- TEMPORAL COORDINATES ---\033[0m")
year = data.get('year')
if year:
    era = "BCE" if year < 0 else "CE"
    print(f"Year: {abs(year)} {era}")
if data.get('month'):
    print(f"Month: {data['month']}")
if data.get('day'):
    print(f"Day: {data['day']}")
if data.get('season'):
    print(f"Season: {data['season']}")
if data.get('time_of_day'):
    print(f"Time of Day: {data['time_of_day']}")
if data.get('era'):
    print(f"Historical Era: {data['era']}")
if data.get('location'):
    print(f"Location: {data['location']}")
print()

# Scene
if data.get('scene'):
    print("\033[36m--- SCENE ---\033[0m")
    scene = data['scene']
    if scene.get('setting'):
        setting = scene['setting']
        print(f"Setting: {setting[:200]}{'...' if len(setting) > 200 else ''}")
    if scene.get('atmosphere'):
        atm = scene['atmosphere']
        print(f"Atmosphere: {atm[:200]}{'...' if len(atm) > 200 else ''}")
    print()

# Characters
if data.get('characters') and data['characters'].get('characters'):
    print("\033[36m--- CHARACTERS ---\033[0m")
    for char in data['characters']['characters'][:5]:
        print(f"  - {char.get('name', 'Unknown')}: {char.get('role', 'N/A')}")
        if char.get('description'):
            desc = char['description']
            print(f"    {desc[:80]}{'...' if len(desc) > 80 else ''}")
    if len(data['characters']['characters']) > 5:
        print(f"  ... and {len(data['characters']['characters']) - 5} more")
    print()

# Dialog
if data.get('dialog'):
    print("\033[36m--- DIALOG ---\033[0m")
    for line in data['dialog'][:5]:
        speaker = line.get('speaker', 'Unknown')
        text = line.get('text', line.get('line', ''))[:80]
        print(f"  {speaker}: \"{text}{'...' if len(line.get('text', line.get('line', ''))) > 80 else ''}\"")
    if len(data['dialog']) > 5:
        print(f"  ... and {len(data['dialog']) - 5} more lines")
    print()

# Image Prompt
if data.get('image_prompt'):
    print("\033[36m--- IMAGE PROMPT ---\033[0m")
    prompt = data['image_prompt']
    print(f"{prompt[:400]}{'...' if len(prompt) > 400 else ''}")
    print()

# Error
if data.get('error'):
    print(f"\033[31mError: {data['error']}\033[0m")
    print()

print("\033[1m+------------------------------------------------------------------+\033[0m")
PYEOF
}

# Open docs
open_docs() {
    echo -e "${BOLD}=== API Documentation ===${NC}"
    echo ""
    echo -e "Interactive docs available at:"
    echo -e "  ${CYAN}$API_BASE/docs${NC} (Swagger UI)"
    echo -e "  ${CYAN}$API_BASE/redoc${NC} (ReDoc)"
    echo ""

    if command -v open &> /dev/null; then
        echo -e "Opening in browser..."
        open "$API_BASE/docs"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$API_BASE/docs"
    fi
}

# Main loop
main() {
    check_server

    while true; do
        print_header
        print_menu

        echo -e "${YELLOW}Select option: ${NC}\c"
        read -r choice

        case "$choice" in
            1) generate_sync; wait_for_key ;;
            2) generate_stream; wait_for_key ;;
            3) generate_from_template; wait_for_key ;;
            4) list_timepoints; wait_for_key ;;
            5) health_check; wait_for_key ;;
            6) open_docs; wait_for_key ;;
            q|Q) echo -e "${GREEN}Goodbye!${NC}"; exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}"; sleep 1 ;;
        esac
    done
}

# Run
main
