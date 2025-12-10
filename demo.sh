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

# Provider availability cache
OPENROUTER_VERIFIED="unknown"

# Custom model selection (when not using presets)
CUSTOM_TEXT_MODEL=""
CUSTOM_IMAGE_MODEL=""
USE_CUSTOM_MODELS="false"

# Timing estimates (in minutes) based on empirical testing
# Format: [text_only, with_image]
# Note: Parallel execution (graph+moment+camera) reduces time by ~30%
TIMING_HD=(4 6)       # HD: highest quality with parallel steps
TIMING_BALANCED=(2 4) # Balanced: good middle ground
TIMING_HYPER=(1 2)    # Hyper: fastest (parallel steps)

# Cross-platform millisecond timestamp (macOS doesn't support date +%N)
get_ms() {
    python3 -c "import time; print(int(time.time() * 1000))"
}

# Get timing estimate string
get_timing_estimate() {
    local preset="$1"
    local with_image="$2"

    case "$preset" in
        "$PRESET_HD")
            if [ "$with_image" = "true" ]; then
                echo "~${TIMING_HD[1]} min"
            else
                echo "~${TIMING_HD[0]} min"
            fi
            ;;
        "$PRESET_HYPER")
            if [ "$with_image" = "true" ]; then
                echo "~${TIMING_HYPER[1]} min"
            else
                echo "~${TIMING_HYPER[0]} min"
            fi
            ;;
        *)
            if [ "$with_image" = "true" ]; then
                echo "~${TIMING_BALANCED[1]} min"
            else
                echo "~${TIMING_BALANCED[0]} min"
            fi
            ;;
    esac
}

# Preset selection helper with timing estimates
select_preset() {
    # Reset custom models
    USE_CUSTOM_MODELS="false"
    CUSTOM_TEXT_MODEL=""
    CUSTOM_IMAGE_MODEL=""

    # Check OpenRouter availability for hyper preset
    verify_openrouter

    echo -e "${BOLD}Select Quality Preset:${NC}"
    echo ""
    echo -e "  ${MAGENTA}1)${NC} ${BOLD}HD${NC} - Best quality (Gemini 2.5 Flash + extended thinking)"
    echo -e "     ${DIM}Deeper analysis, high detail | ~${TIMING_HD[0]}-${TIMING_HD[1]} min${NC}"
    echo -e "  ${GREEN}2)${NC} ${BOLD}Balanced${NC} - Good balance (Gemini 2.5 Flash)"
    echo -e "     ${DIM}Recommended default | ~${TIMING_BALANCED[0]}-${TIMING_BALANCED[1]} min${NC}"
    if [ "$OPENROUTER_VERIFIED" = "true" ]; then
        echo -e "  ${CYAN}3)${NC} ${BOLD}Hyper${NC} - Maximum speed (Gemini 2.0 Flash via OpenRouter)"
        echo -e "     ${DIM}Fastest generation | ~${TIMING_HYPER[0]}-${TIMING_HYPER[1]} min${NC}"
    else
        echo -e "  ${DIM}3) Hyper - (unavailable - OpenRouter API key issue)${NC}"
    fi
    echo -e "  ${YELLOW}4)${NC} ${BOLD}Browse models...${NC} - Choose your own"
    echo -e "     ${DIM}Interactive model selection from available providers${NC}"
    if [ "$OPENROUTER_VERIFIED" = "true" ]; then
        echo -e "  ${GREEN}5)${NC} ${BOLD}Free (Best)${NC} - Best free model available"
        echo -e "     ${DIM}Uses highest-capability free model from OpenRouter${NC}"
        echo -e "  ${GREEN}6)${NC} ${BOLD}Free (Fastest)${NC} - Fastest free model"
        echo -e "     ${DIM}Uses smallest/quickest free model from OpenRouter${NC}"
    else
        echo -e "  ${DIM}5) Free (Best) - (unavailable - OpenRouter API key issue)${NC}"
        echo -e "  ${DIM}6) Free (Fastest) - (unavailable - OpenRouter API key issue)${NC}"
    fi
    echo ""
    echo -e "${YELLOW}> ${NC}\c"
    read -r preset_choice

    case "$preset_choice" in
        1)
            CURRENT_PRESET="$PRESET_HD"
            echo -e "${MAGENTA}Using HD preset (~${TIMING_HD[0]}-${TIMING_HD[1]} min)${NC}"
            ;;
        2)
            CURRENT_PRESET="$PRESET_BALANCED"
            echo -e "${GREEN}Using Balanced preset (~${TIMING_BALANCED[0]}-${TIMING_BALANCED[1]} min)${NC}"
            ;;
        3)
            if [ "$OPENROUTER_VERIFIED" = "true" ]; then
                CURRENT_PRESET="$PRESET_HYPER"
                echo -e "${CYAN}Using Hyper preset (~${TIMING_HYPER[0]}-${TIMING_HYPER[1]} min)${NC}"
            else
                echo -e "${YELLOW}Hyper preset unavailable (OpenRouter API key issue)${NC}"
                echo -e "${GREEN}Falling back to Balanced preset${NC}"
                CURRENT_PRESET="$PRESET_BALANCED"
            fi
            ;;
        4)
            browse_models
            ;;
        5)
            if [ "$OPENROUTER_VERIFIED" = "true" ]; then
                select_free_model "best"
            else
                echo -e "${YELLOW}Free models unavailable (OpenRouter API key issue)${NC}"
                echo -e "${GREEN}Falling back to Balanced preset${NC}"
                CURRENT_PRESET="$PRESET_BALANCED"
            fi
            ;;
        6)
            if [ "$OPENROUTER_VERIFIED" = "true" ]; then
                select_free_model "fastest"
            else
                echo -e "${YELLOW}Free models unavailable (OpenRouter API key issue)${NC}"
                echo -e "${GREEN}Falling back to Balanced preset${NC}"
                CURRENT_PRESET="$PRESET_BALANCED"
            fi
            ;;
        *)
            CURRENT_PRESET="$PRESET_BALANCED"
            echo -e "${GREEN}Using Balanced preset (default)${NC}"
            ;;
    esac
    echo ""
}

# Select free model (best or fastest)
select_free_model() {
    local mode="$1"  # "best" or "fastest"

    echo ""
    echo -e "${BOLD}=== Free Model Selection ===${NC}"
    echo -e "${DIM}Fetching available free models from OpenRouter...${NC}"
    echo ""

    # Fetch free models from the API
    free_response=$(curl -s "$API_BASE/api/v1/models/free")

    if [ -z "$free_response" ] || echo "$free_response" | grep -q "error"; then
        echo -e "${RED}Failed to fetch free models. Using balanced preset.${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
        return
    fi

    # Parse the response with Python
    FREE_DATA="$free_response" FREE_MODE="$mode" python3 << 'PYEOF'
import os, json, sys

try:
    data = json.loads(os.environ['FREE_DATA'])
    mode = os.environ.get('FREE_MODE', 'best')

    total = data.get('total', 0)
    note = data.get('note', '')

    print(f"\033[32mFound {total} free models\033[0m")
    if note:
        print(f"\033[2m{note}\033[0m")
    print()

    # Get recommended model based on mode
    if mode == 'best':
        model = data.get('best')
        if model:
            print(f"\033[1mBest Free Model (highest capability):\033[0m")
            print(f"  ID:      \033[36m{model.get('id')}\033[0m")
            print(f"  Name:    {model.get('name')}")
            print(f"  Context: {model.get('context_length', 'N/A'):,} tokens")
            with open('/tmp/free_model_id', 'w') as f:
                f.write(model.get('id', ''))
        else:
            print("\033[31mNo best model available\033[0m")
            sys.exit(1)
    else:  # fastest
        model = data.get('fastest')
        if model:
            print(f"\033[1mFastest Free Model (quickest inference):\033[0m")
            print(f"  ID:      \033[36m{model.get('id')}\033[0m")
            print(f"  Name:    {model.get('name')}")
            print(f"  Context: {model.get('context_length', 'N/A'):,} tokens")
            with open('/tmp/free_model_id', 'w') as f:
                f.write(model.get('id', ''))
        else:
            print("\033[31mNo fastest model available\033[0m")
            sys.exit(1)

    # Show other free models
    all_free = data.get('all_free', [])
    if len(all_free) > 1:
        print()
        print(f"\033[2mOther free models available: {len(all_free) - 1}\033[0m")
        for m in all_free[1:6]:  # Show next 5
            print(f"  \033[2m- {m.get('id')}\033[0m")
        if len(all_free) > 6:
            print(f"  \033[2m... and {len(all_free) - 6} more\033[0m")

except Exception as e:
    print(f"\033[31mError parsing free models: {e}\033[0m")
    sys.exit(1)
PYEOF

    result=$?

    if [ $result -ne 0 ]; then
        echo -e "${RED}Failed to parse free models. Using balanced preset.${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
        return
    fi

    # Read the selected model
    if [ -f /tmp/free_model_id ]; then
        CUSTOM_TEXT_MODEL=$(cat /tmp/free_model_id)
        rm -f /tmp/free_model_id

        if [ -n "$CUSTOM_TEXT_MODEL" ]; then
            echo ""
            echo -e "${YELLOW}Note: Free models do not include image generation.${NC}"
            echo -e "${DIM}You can still generate images with the paid image model.${NC}"
            echo ""
            echo -e "${YELLOW}Use this free model? (y/n)${NC} \c"
            read -r confirm

            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                USE_CUSTOM_MODELS="true"
                CURRENT_PRESET=""
                # Don't set image model - will use default paid model if requested
                echo -e "${GREEN}Using free model: $CUSTOM_TEXT_MODEL${NC}"
            else
                echo -e "${DIM}Cancelled. Using balanced preset.${NC}"
                USE_CUSTOM_MODELS="false"
                CUSTOM_TEXT_MODEL=""
                CURRENT_PRESET="$PRESET_BALANCED"
            fi
        else
            echo -e "${RED}No free model selected. Using balanced preset.${NC}"
            CURRENT_PRESET="$PRESET_BALANCED"
        fi
    else
        echo -e "${RED}Failed to get free model. Using balanced preset.${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
    fi
}

# Browse and select models interactively
browse_models() {
    echo ""
    echo -e "${BOLD}=== Browse Models ===${NC}"
    echo ""

    # Fetch available models
    echo -e "${DIM}Fetching available models...${NC}"
    models_response=$(curl -s "$API_BASE/api/v1/models?fetch_remote=true")

    if [ -z "$models_response" ]; then
        echo -e "${RED}Failed to fetch models. Using balanced preset.${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
        return
    fi

    # Parse and display text models
    echo ""
    echo -e "${CYAN}=== Text Generation Models ===${NC}"
    echo ""
    echo -e "Filter by provider: ${YELLOW}(g)oogle, (o)penrouter, (a)ll${NC} [a]: \c"
    read -r text_provider_filter
    text_provider_filter="${text_provider_filter:-a}"

    echo ""
    echo -e "Search filter (or Enter for all): \c"
    read -r text_search

    # Display text models with Python
    TEXT_MODEL_RESPONSE="$models_response" TEXT_PROVIDER="$text_provider_filter" TEXT_SEARCH="$text_search" python3 << 'PYEOF'
import os, json, sys

data = json.loads(os.environ['TEXT_MODEL_RESPONSE'])
provider_filter = os.environ.get('TEXT_PROVIDER', 'a').lower()
search_filter = os.environ.get('TEXT_SEARCH', '').lower()

models = data.get('models', [])

# Filter for text models
text_models = [m for m in models if 'text' in m.get('capabilities', [])]

# Apply provider filter
if provider_filter == 'g':
    text_models = [m for m in text_models if m.get('provider') == 'google']
elif provider_filter == 'o':
    text_models = [m for m in text_models if m.get('provider') == 'openrouter']

# Apply search filter
if search_filter:
    text_models = [m for m in text_models if search_filter in m.get('id', '').lower() or search_filter in m.get('name', '').lower()]

# Limit to 15 for display
text_models = text_models[:15]

if not text_models:
    print("\033[31mNo matching text models found\033[0m")
    sys.exit(1)

# Write to temp file for bash to read
ids = []
for i, m in enumerate(text_models, 1):
    provider = m.get('provider', 'unknown')[:10]
    model_id = m.get('id', 'unknown')
    name = m.get('name', model_id)[:35]
    ids.append(model_id)
    print(f"  \033[1m{i:2})\033[0m [{provider:10}] {name}")

with open('/tmp/text_model_ids', 'w') as f:
    f.write('\n'.join(ids))
PYEOF

    if [ $? -ne 0 ]; then
        echo -e "${RED}No text models found. Using balanced preset.${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
        return
    fi

    echo ""
    echo -e "${YELLOW}Select text model [1-15]: ${NC}\c"
    read -r text_choice

    # Read selected model
    if [ -f /tmp/text_model_ids ]; then
        text_model_ids=()
        while IFS= read -r line; do
            text_model_ids+=("$line")
        done < /tmp/text_model_ids
        rm -f /tmp/text_model_ids

        idx=$((text_choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#text_model_ids[@]} ]; then
            CUSTOM_TEXT_MODEL="${text_model_ids[$idx]}"
            echo -e "${GREEN}Selected: $CUSTOM_TEXT_MODEL${NC}"
        else
            echo -e "${RED}Invalid selection. Using default.${NC}"
            CURRENT_PRESET="$PRESET_BALANCED"
            return
        fi
    fi

    # Now select image model
    echo ""
    echo -e "${CYAN}=== Image Generation Models ===${NC}"
    echo ""

    # Display image models with Python
    IMAGE_MODEL_RESPONSE="$models_response" python3 << 'PYEOF'
import os, json

data = json.loads(os.environ['IMAGE_MODEL_RESPONSE'])
models = data.get('models', [])

# Filter for image models
image_models = [m for m in models if 'image_generation' in m.get('capabilities', [])]

# Add "none" option
print(f"  \033[1m 1)\033[0m [skip      ] No image generation")

ids = ['none']
for i, m in enumerate(image_models, 2):
    provider = m.get('provider', 'unknown')[:10]
    model_id = m.get('id', 'unknown')
    name = m.get('name', model_id)[:35]
    ids.append(model_id)
    print(f"  \033[1m{i:2})\033[0m [{provider:10}] {name}")

with open('/tmp/image_model_ids', 'w') as f:
    f.write('\n'.join(ids))
PYEOF

    echo ""
    echo -e "${YELLOW}Select image model [1-n]: ${NC}\c"
    read -r image_choice

    # Read selected image model
    if [ -f /tmp/image_model_ids ]; then
        image_model_ids=()
        while IFS= read -r line; do
            image_model_ids+=("$line")
        done < /tmp/image_model_ids
        rm -f /tmp/image_model_ids

        idx=$((image_choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#image_model_ids[@]} ]; then
            selected_image="${image_model_ids[$idx]}"
            if [ "$selected_image" = "none" ]; then
                CUSTOM_IMAGE_MODEL=""
                echo -e "${DIM}No image generation selected${NC}"
            else
                CUSTOM_IMAGE_MODEL="$selected_image"
                echo -e "${GREEN}Selected: $CUSTOM_IMAGE_MODEL${NC}"
            fi
        fi
    fi

    # Set custom mode
    USE_CUSTOM_MODELS="true"
    CURRENT_PRESET=""  # Clear preset when using custom

    echo ""
    echo -e "${BOLD}Custom Configuration:${NC}"
    echo -e "  Text:  ${CYAN}$CUSTOM_TEXT_MODEL${NC}"
    if [ -n "$CUSTOM_IMAGE_MODEL" ]; then
        echo -e "  Image: ${CYAN}$CUSTOM_IMAGE_MODEL${NC}"
    else
        echo -e "  Image: ${DIM}(none)${NC}"
    fi
    echo ""
    echo -e "${YELLOW}Proceed with this configuration? (y/n)${NC} \c"
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo -e "${DIM}Cancelled. Using balanced preset.${NC}"
        USE_CUSTOM_MODELS="false"
        CURRENT_PRESET="$PRESET_BALANCED"
    fi
}

# Build JSON payload with preset or custom models
build_json_payload() {
    local query="$1"
    local generate_image="$2"
    local preset="$3"

    local payload="{\"query\": \"$query\", \"generate_image\": $generate_image"

    if [ "$USE_CUSTOM_MODELS" = "true" ]; then
        # Custom model mode
        if [ -n "$CUSTOM_TEXT_MODEL" ]; then
            payload="$payload, \"text_model\": \"$CUSTOM_TEXT_MODEL\""
        fi
        if [ -n "$CUSTOM_IMAGE_MODEL" ]; then
            payload="$payload, \"image_model\": \"$CUSTOM_IMAGE_MODEL\""
        fi
    elif [ -n "$preset" ]; then
        # Preset mode
        payload="$payload, \"preset\": \"$preset\""
    fi

    payload="$payload}"
    echo "$payload"
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
    echo -e "${BOLD}AI-Powered Temporal Simulation Engine v2.2.0${NC}"
    echo -e "${DIM}Parallel Pipeline | Google Nano Banana | OpenRouter${NC}"
    echo ""
}

print_menu() {
    echo -e "${BOLD}=== Main Menu ===${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} Generate timepoint (sync) - Wait for full result"
    echo -e "  ${GREEN}2)${NC} Generate timepoint (streaming) - See live progress"
    echo -e "  ${GREEN}3)${NC} Generate from template"
    echo -e "  ${CYAN}4)${NC} ${BOLD}RAPID TEST${NC} - One-click hyper + image (streaming)"
    echo -e "  ${GREEN}5)${NC} ${BOLD}RAPID TEST FREE${NC} - One-click fastest free model + image"
    echo -e "  ${GREEN}6)${NC} Browse timepoints"
    echo -e "  ${GREEN}7)${NC} Health check"
    echo -e "  ${GREEN}8)${NC} API documentation"
    echo -e "  ${CYAN}9)${NC} Test endpoints"
    echo -e "  ${MAGENTA}10)${NC} ${BOLD}Model Eval${NC} - Compare model performance"
    echo -e "  ${CYAN}--- Character Interactions ---${NC}"
    echo -e "  ${GREEN}11)${NC} Chat with character"
    echo -e "  ${GREEN}12)${NC} Extend dialog"
    echo -e "  ${GREEN}13)${NC} Survey characters"
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

# Check if OpenRouter is actually working (not just configured)
# This makes a lightweight API call to verify the key is valid
verify_openrouter() {
    if [ "$OPENROUTER_VERIFIED" != "unknown" ]; then
        return  # Already checked
    fi

    # Check if provider reports openrouter as available (key is configured)
    provider_status=$(curl -s "$API_BASE/api/v1/models/providers" 2>/dev/null)
    or_available=$(echo "$provider_status" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    found = any(p.get('provider') == 'openrouter' and p.get('available') for p in d.get('providers', []))
    print('yes' if found else 'no')
except:
    print('no')
" 2>/dev/null || echo "no")

    if [ "$or_available" = "yes" ]; then
        # OpenRouter is configured, test if the API key actually works
        # Use the free models endpoint which makes a real OpenRouter API call
        test_result=$(curl -s -m 10 "$API_BASE/api/v1/models/free" 2>/dev/null)

        # Check for various error indicators
        if echo "$test_result" | grep -qi "error\|401\|403\|Authentication\|Unauthorized\|Invalid"; then
            OPENROUTER_VERIFIED="false"
        elif echo "$test_result" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # If we got a valid response with free models or at least no error, it's working
    if 'error' in d or 'detail' in d:
        print('error')
    elif 'all_free' in d or 'total' in d:
        print('ok')
    else:
        print('unknown')
except:
    print('error')
" 2>/dev/null | grep -q "ok"; then
            OPENROUTER_VERIFIED="true"
        else
            OPENROUTER_VERIFIED="false"
        fi
    else
        OPENROUTER_VERIFIED="false"
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

        # Check if this timepoint has an image and offer to view it
        has_image=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('image_base64') or d.get('has_image') else 'no')" 2>/dev/null || echo "no")

        if [ "$has_image" = "yes" ]; then
            echo -e "${GREEN}This timepoint has an image!${NC}"
            echo -e "View/save image? ${YELLOW}(y/n)${NC} \c"
            read -r view_img
            if [ "$view_img" = "y" ] || [ "$view_img" = "Y" ]; then
                save_image_if_exists "$tp_id"
            fi
        fi
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

    # Build JSON payload with preset or custom models
    json_payload=$(build_json_payload "$query" "$generate_image" "$CURRENT_PRESET")

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

    # Get timing estimate
    time_est=$(get_timing_estimate "$preset" "$generate_image")
    echo -e "${DIM}Estimated time: $time_est${NC}"
    echo ""

    if [ "$generate_image" = "true" ]; then
        echo -e "${YELLOW}Watch the progress (with image generation)...${NC}"
    elif [ "$preset" = "$PRESET_HYPER" ]; then
        echo -e "${CYAN}Hyper mode: Fast generation in progress...${NC}"
    else
        echo -e "${YELLOW}Watch the progress...${NC}"
    fi
    echo ""

    # Build JSON payload with preset or custom models
    json_payload=$(build_json_payload "$query" "$generate_image" "$preset")

    # Clear temp file and record start time
    rm -f /tmp/timepoint_last_id
    echo "$(date +%s)" > /tmp/timepoint_start_time

    curl -N -s -X POST "$API_BASE/api/v1/timepoints/generate/stream" \
        -H "Content-Type: application/json" \
        -d "$json_payload" | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
            data="${line#data: }"
            event=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event',''))" 2>/dev/null || echo "")
            step=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('step',''))" 2>/dev/null || echo "")
            progress=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('progress',0))" 2>/dev/null || echo "0")

            # Calculate elapsed time
            if [ -f /tmp/timepoint_start_time ]; then
                start_ts=$(cat /tmp/timepoint_start_time)
                now_ts=$(date +%s)
                elapsed=$((now_ts - start_ts))
                elapsed_str="${elapsed}s"
            else
                elapsed_str="..."
            fi

            case "$event" in
                "start")
                    # Extract generate_image value and preset from start event data
                    gen_img_val=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('generate_image','?'))" 2>/dev/null || echo "?")
                    preset_val=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('preset','balanced'))" 2>/dev/null || echo "balanced")
                    echo -e "${GREEN}[START]${NC} Initializing pipeline... (preset=$preset_val, image=$gen_img_val)"
                    echo -e "${DIM}Pipeline: judge > timeline > scene > characters > [graph|moment|camera] > dialog > image_prompt${NC}"
                    ;;
                "step_complete")
                    bar=$(printf '%*s' $((progress/5)) '' | tr ' ' '#')
                    empty=$(printf '%*s' $((20-progress/5)) '' | tr ' ' '-')
                    echo -e "${GREEN}[${bar}${empty}] ${progress}%${NC} ${elapsed_str} - Completed: $step"
                    ;;
                "step_error")
                    echo -e "${RED}[ERROR]${NC} ${elapsed_str} - Step failed: $step"
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

        # Build JSON payload with preset or custom models
        json_payload=$(build_json_payload "$query" "$generate_image" "$CURRENT_PRESET")

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

# Rapid test - one-click hyper + image streaming
rapid_test() {
    echo -e "${BOLD}=== RAPID TEST ===${NC}"
    echo ""
    echo -e "${CYAN}One-click hyper speed test with image generation${NC}"
    echo ""

    # Check OpenRouter availability for hyper preset
    verify_openrouter

    # Pick a random template
    template_count=${#TEMPLATES[@]}
    random_idx=$((RANDOM % template_count))
    query="${TEMPLATES[$random_idx]}"

    echo -e "${GREEN}Random template:${NC} ${BOLD}$query${NC}"

    # Use hyper if OpenRouter is available, otherwise fall back to balanced
    if [ "$OPENROUTER_VERIFIED" = "true" ]; then
        echo -e "${DIM}Using: Hyper preset + Image generation + Streaming${NC}"
        echo ""
        CURRENT_PRESET="$PRESET_HYPER"
        USE_CUSTOM_MODELS="false"
        generate_stream "$query" "true" "true" "$PRESET_HYPER"
    else
        echo -e "${YELLOW}OpenRouter unavailable - using Balanced preset instead${NC}"
        echo -e "${DIM}Using: Balanced preset + Image generation + Streaming${NC}"
        echo ""
        CURRENT_PRESET="$PRESET_BALANCED"
        USE_CUSTOM_MODELS="false"
        generate_stream "$query" "true" "true" "$PRESET_BALANCED"
    fi
}

# Rapid test with FREE model - one-click fastest free model + image streaming
rapid_test_free() {
    echo -e "${BOLD}=== RAPID TEST FREE ===${NC}"
    echo ""
    echo -e "${GREEN}One-click test using fastest FREE model${NC}"
    echo ""

    # Check OpenRouter availability first
    verify_openrouter

    if [ "$OPENROUTER_VERIFIED" != "true" ]; then
        echo -e "${YELLOW}OpenRouter unavailable - using Balanced preset instead${NC}"
        echo ""

        # Pick a random template
        template_count=${#TEMPLATES[@]}
        random_idx=$((RANDOM % template_count))
        query="${TEMPLATES[$random_idx]}"

        echo -e "${GREEN}Random template:${NC} ${BOLD}$query${NC}"
        echo -e "${DIM}Using: Balanced preset + Image generation + Streaming${NC}"
        echo ""
        CURRENT_PRESET="$PRESET_BALANCED"
        USE_CUSTOM_MODELS="false"
        generate_stream "$query" "true" "true" "$PRESET_BALANCED"
        return
    fi

    # Fetch fastest free model from API
    echo -e "${DIM}Fetching fastest free model from OpenRouter...${NC}"
    free_response=$(curl -s "$API_BASE/api/v1/models/free")

    if [ -z "$free_response" ] || echo "$free_response" | grep -q "error"; then
        echo -e "${RED}Failed to fetch free models. Falling back to balanced preset.${NC}"
        echo ""

        # Pick a random template
        template_count=${#TEMPLATES[@]}
        random_idx=$((RANDOM % template_count))
        query="${TEMPLATES[$random_idx]}"

        echo -e "${GREEN}Random template:${NC} ${BOLD}$query${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
        USE_CUSTOM_MODELS="false"
        generate_stream "$query" "true" "true" "$PRESET_BALANCED"
        return
    fi

    # Parse the fastest model with debug info
    parse_result=$(echo "$free_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    fastest = data.get('fastest')
    total = data.get('total', 0)
    if fastest and fastest.get('id'):
        print(f'OK:{fastest.get(\"id\")}')
    elif total == 0:
        print('EMPTY:no free models returned')
    elif not fastest:
        print('MISSING:fastest field not in response')
    else:
        print('NOID:fastest model has no id')
except Exception as e:
    print(f'ERROR:{e}')
" 2>/dev/null)

    # Extract model ID if parsing succeeded
    if [[ "$parse_result" == OK:* ]]; then
        fastest_model="${parse_result#OK:}"
    else
        fastest_model=""
    fi

    if [ -z "$fastest_model" ]; then
        # Show why we couldn't get the model
        if [[ "$parse_result" == EMPTY:* ]]; then
            echo -e "${YELLOW}No free models available from OpenRouter.${NC}"
        elif [[ "$parse_result" == MISSING:* ]]; then
            echo -e "${YELLOW}Free models endpoint returned unexpected format.${NC}"
        elif [[ "$parse_result" == ERROR:* ]]; then
            echo -e "${YELLOW}Failed to parse free models response: ${parse_result#ERROR:}${NC}"
        else
            echo -e "${YELLOW}Could not determine fastest free model.${NC}"
        fi
        echo -e "${DIM}Falling back to balanced preset.${NC}"

        # Pick a random template
        template_count=${#TEMPLATES[@]}
        random_idx=$((RANDOM % template_count))
        query="${TEMPLATES[$random_idx]}"

        echo -e "${GREEN}Random template:${NC} ${BOLD}$query${NC}"
        CURRENT_PRESET="$PRESET_BALANCED"
        USE_CUSTOM_MODELS="false"
        generate_stream "$query" "true" "true" "$PRESET_BALANCED"
        return
    fi

    # Pick a random template
    template_count=${#TEMPLATES[@]}
    random_idx=$((RANDOM % template_count))
    query="${TEMPLATES[$random_idx]}"

    echo -e "${GREEN}Random template:${NC} ${BOLD}$query${NC}"
    echo -e "${CYAN}Free model:${NC} ${BOLD}$fastest_model${NC}"
    echo -e "${DIM}Using: Fastest free model + Image generation + Streaming${NC}"
    echo -e "${YELLOW}Note: Free models rotate frequently on OpenRouter${NC}"
    echo ""

    # Set custom model mode with the free model
    USE_CUSTOM_MODELS="true"
    CUSTOM_TEXT_MODEL="$fastest_model"
    CUSTOM_IMAGE_MODEL=""  # Use default paid image model
    CURRENT_PRESET=""

    # Run streaming with free model and image enabled, skip all prompts
    generate_stream "$query" "true" "true" ""
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

    # Check for image
    has_image = tp.get('has_image') or tp.get('image_base64')
    image_icon = '📷' if has_image else '  '

    query_display = tp['query'][:40] + '...' if len(tp['query']) > 40 else tp['query']
    print(f"  \033[1m{i:2})\033[0m [{status_color}{status:10}\033[0m] {image_icon} {query_display}")

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
    echo -e "${CYAN}--- PIPELINE CONFIG ---${NC}"
    echo -e "  Parallelism: ${GREEN}3${NC} concurrent LLM calls (default)"
    echo -e "  ${DIM}Parallel steps: graph, moment, camera${NC}"
    echo -e "  ${DIM}Set PIPELINE_MAX_PARALLELISM env var to adjust (1-5)${NC}"
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

# Image status
has_image = data.get('image_base64') or data.get('has_image')
if has_image:
    print("\033[36m--- IMAGE ---\033[0m")
    print("\033[32m📷 Image: Available\033[0m")
    print("\033[2mUse 'View/save image' option to open or save the generated image\033[0m")
    print()
else:
    print("\033[36m--- IMAGE ---\033[0m")
    print("\033[2m📷 Image: Not generated (use 'Generate image?' option)\033[0m")
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

# Model evaluation - compare model performance
model_eval() {
    echo -e "${BOLD}=== Multi-Model Evaluation ===${NC}"
    echo ""
    echo -e "${DIM}Compare performance across different LLM models${NC}"
    echo ""

    # Show available presets
    echo -e "${CYAN}Available Presets:${NC}"
    presets_response=$(curl -s "$API_BASE/api/v1/eval/models")
    echo "$presets_response" | python3 -c '
import sys, json

try:
    data = json.load(sys.stdin)
    if "detail" in data:
        print("  API Error:", data["detail"])
    else:
        presets = data.get("presets", {})
        if not presets:
            print("  (No presets available)")
        else:
            for name, count in presets.items():
                print("  - " + str(name) + ": " + str(count) + " models")
except json.JSONDecodeError:
    print("  (Invalid response from server)")
except Exception as e:
    print("  (Error:", e, ")")
'
    echo ""

    # Get query
    echo -e "${YELLOW}Enter query to test (e.g., 'battle of thermopylae'):${NC}"
    echo -e "${YELLOW}> ${NC}\c"
    read -r query

    if [ -z "$query" ]; then
        echo -e "${RED}Query cannot be empty${NC}"
        return
    fi

    # Select preset
    echo ""
    echo -e "${YELLOW}Select preset:${NC}"
    echo -e "  ${GREEN}1)${NC} verified (default) - Known working models"
    echo -e "  ${GREEN}2)${NC} google_native - Google API models only"
    echo -e "  ${GREEN}3)${NC} openrouter - OpenRouter models only"
    echo -e "  ${GREEN}4)${NC} all - All available models"
    echo -e "${YELLOW}> ${NC}\c"
    read -r preset_choice

    case "$preset_choice" in
        2) preset="google_native" ;;
        3) preset="openrouter" ;;
        4) preset="all" ;;
        *) preset="verified" ;;
    esac

    echo ""
    echo -e "${CYAN}Running evaluation...${NC}"
    echo -e "  Query:  ${BOLD}$query${NC}"
    echo -e "  Preset: ${BOLD}$preset${NC}"
    echo ""

    # Build JSON payload
    json_payload="{\"query\": \"$query\", \"preset\": \"$preset\", \"timeout_seconds\": 120}"

    # Make API call and get report
    response=$(curl -s -X POST "$API_BASE/api/v1/eval/compare/report" \
        -H "Content-Type: application/json" \
        -d "$json_payload")

    # Extract and print the report (handles both success and error cases)
    echo "$response" | python3 -c '
import sys, json

try:
    data = json.load(sys.stdin)

    # Check for top-level API error
    if "detail" in data:
        print("API Error:", data["detail"])
        sys.exit(1)

    # Print the formatted report
    report = data.get("report", "")
    if report:
        print(report)
    else:
        # Fallback: print comparison summary
        comparison = data.get("comparison", data)
        if comparison:
            print("Query:", comparison.get("query", "N/A"))
            print("Models tested:", comparison.get("models_tested", 0))
            print("Success rate: " + str(comparison.get("success_rate", 0)) + "%")
            fastest = comparison.get("fastest_model")
            if fastest:
                print("Fastest:", fastest)
        else:
            print(json.dumps(data, indent=2))
except json.JSONDecodeError:
    print("Error: Invalid JSON response from server")
    sys.exit(1)
except Exception as e:
    print("Error parsing response:", e)
    sys.exit(1)
'
}

# Test endpoints submenu
test_endpoints() {
    echo -e "${BOLD}=== Test Endpoints ===${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} Health check (/health)"
    echo -e "  ${GREEN}2)${NC} List models (/api/v1/models)"
    echo -e "  ${GREEN}3)${NC} Provider status (/api/v1/models/providers)"
    echo -e "  ${GREEN}4)${NC} Quick generation test (balanced, no image)"
    echo -e "  ${GREEN}5)${NC} Test all endpoints"
    echo -e "  ${RED}b)${NC} Back"
    echo ""
    echo -e "${YELLOW}Select: ${NC}\c"
    read -r test_choice

    case "$test_choice" in
        1) test_health ;;
        2) test_models ;;
        3) test_providers ;;
        4) test_quick_generate ;;
        5) test_all_endpoints ;;
        b|B) return ;;
        *) echo -e "${RED}Invalid option${NC}"; sleep 1 ;;
    esac
}

# Test health endpoint
test_health() {
    echo ""
    echo -e "${CYAN}Testing: GET /health${NC}"

    start_time=$(get_ms)
    response=$(curl -s -w "\n%{http_code}" "$API_BASE/health")
    end_time=$(get_ms)

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    latency=$((end_time - start_time))

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}Status: $http_code (${latency}ms)${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    else
        echo -e "${RED}Status: $http_code (${latency}ms)${NC}"
        echo "$body"
    fi
}

# Test models endpoint
test_models() {
    echo ""
    echo -e "${CYAN}Testing: GET /api/v1/models${NC}"

    start_time=$(get_ms)
    response=$(curl -s -w "\n%{http_code}" "$API_BASE/api/v1/models")
    end_time=$(get_ms)

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    latency=$((end_time - start_time))

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}Status: $http_code (${latency}ms)${NC}"
        # Count models
        model_count=$(echo "$body" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "?")
        echo -e "Found ${BOLD}$model_count${NC} models"
        echo ""
        echo "$body" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for m in data.get('models', [])[:10]:
    status = '\033[32mONLINE\033[0m' if m.get('status') == 'online' else '\033[31mOFFLINE\033[0m'
    print(f\"  {m.get('id', 'unknown')[:40]}: {status}\")
if len(data.get('models', [])) > 10:
    print(f\"  ... and {len(data['models']) - 10} more\")
" 2>/dev/null || echo "$body" | head -50
    else
        echo -e "${RED}Status: $http_code (${latency}ms)${NC}"
        echo "$body"
    fi
}

# Test providers endpoint
test_providers() {
    echo ""
    echo -e "${CYAN}Testing: GET /api/v1/models/providers${NC}"

    start_time=$(get_ms)
    response=$(curl -s -w "\n%{http_code}" "$API_BASE/api/v1/models/providers")
    end_time=$(get_ms)

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    latency=$((end_time - start_time))

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}Status: $http_code (${latency}ms)${NC}"
        echo "$body" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for p in data.get('providers', []):
    name = p.get('name', 'unknown')
    avail = p.get('available', False)
    healthy = p.get('healthy', False)
    if avail and healthy:
        status = '\033[32mHEALTHY\033[0m'
    elif avail:
        status = '\033[33mDEGRADED\033[0m'
    else:
        status = '\033[31mUNAVAILABLE\033[0m'
    print(f\"  {name}: {status}\")
" 2>/dev/null || echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    else
        echo -e "${RED}Status: $http_code (${latency}ms)${NC}"
        echo "$body"
    fi
}

# Quick generation test
test_quick_generate() {
    echo ""
    echo -e "${CYAN}Testing: POST /api/v1/timepoints/generate/sync (balanced, no image)${NC}"
    echo -e "${YELLOW}This will create a test timepoint...${NC}"
    echo ""

    test_query="boston tea party 1773"
    json_payload="{\"query\": \"$test_query\", \"generate_image\": false, \"preset\": \"balanced\"}"

    echo -e "Query: ${BOLD}$test_query${NC}"
    echo -e "${DIM}Starting generation (may take 1-3 minutes)...${NC}"

    start_time=$(date +%s)
    response=$(curl -s -X POST "$API_BASE/api/v1/timepoints/generate/sync" \
        -H "Content-Type: application/json" \
        -d "$json_payload")
    end_time=$(date +%s)
    duration=$((end_time - start_time))

    status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")
    tp_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

    if [ "$status" = "completed" ]; then
        echo -e "${GREEN}Status: completed (${duration}s)${NC}"
        echo -e "  ID: ${CYAN}$tp_id${NC}"
        year=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('year',''))" 2>/dev/null || echo "")
        location=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('location',''))" 2>/dev/null || echo "")
        echo -e "  Year: ${CYAN}$year${NC}"
        echo -e "  Location: ${CYAN}$location${NC}"
    else
        echo -e "${RED}Status: $status (${duration}s)${NC}"
        error=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','Unknown error'))" 2>/dev/null || echo "Unknown error")
        echo -e "  Error: $error"
    fi
}

# Test all endpoints
test_all_endpoints() {
    echo ""
    echo -e "${BOLD}=== Testing All Endpoints ===${NC}"
    echo ""

    # Test health
    echo -e "${CYAN}1/4 Health check...${NC}"
    health_response=$(curl -s -w "%{http_code}" "$API_BASE/health")
    health_code="${health_response: -3}"
    if [ "$health_code" = "200" ]; then
        echo -e "  ${GREEN}Health check passed${NC}"
    else
        echo -e "  ${RED}Health check failed: $health_code${NC}"
    fi

    # Test models
    echo -e "${CYAN}2/4 Models endpoint...${NC}"
    models_response=$(curl -s -w "%{http_code}" "$API_BASE/api/v1/models")
    models_code="${models_response: -3}"
    if [ "$models_code" = "200" ]; then
        echo -e "  ${GREEN}Models endpoint passed${NC}"
    else
        echo -e "  ${RED}Models endpoint failed: $models_code${NC}"
    fi

    # Test providers
    echo -e "${CYAN}3/4 Providers endpoint...${NC}"
    providers_response=$(curl -s -w "%{http_code}" "$API_BASE/api/v1/models/providers")
    providers_code="${providers_response: -3}"
    if [ "$providers_code" = "200" ]; then
        echo -e "  ${GREEN}Providers endpoint passed${NC}"
    else
        echo -e "  ${RED}Providers endpoint failed: $providers_code${NC}"
    fi

    # Test list timepoints
    echo -e "${CYAN}4/4 List timepoints...${NC}"
    list_response=$(curl -s -w "%{http_code}" "$API_BASE/api/v1/timepoints")
    list_code="${list_response: -3}"
    if [ "$list_code" = "200" ]; then
        echo -e "  ${GREEN}List timepoints passed${NC}"
    else
        echo -e "  ${RED}List timepoints failed: $list_code${NC}"
    fi

    echo ""
    echo -e "${BOLD}Summary:${NC}"
    passed=0
    failed=0
    [ "$health_code" = "200" ] && ((passed++)) || ((failed++))
    [ "$models_code" = "200" ] && ((passed++)) || ((failed++))
    [ "$providers_code" = "200" ] && ((passed++)) || ((failed++))
    [ "$list_code" = "200" ] && ((passed++)) || ((failed++))

    if [ $failed -eq 0 ]; then
        echo -e "  ${GREEN}All $passed tests passed!${NC}"
    else
        echo -e "  ${GREEN}$passed passed${NC}, ${RED}$failed failed${NC}"
    fi
}

# =============================================================================
# CHARACTER INTERACTION FUNCTIONS
# =============================================================================

# Helper: Select a timepoint for interaction
select_timepoint_for_interaction() {
    echo -e "${CYAN}Fetching completed timepoints...${NC}"
    response=$(curl -s "$API_BASE/api/v1/timepoints?page_size=100&status=completed")

    total=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null || echo "0")

    if [ "$total" = "0" ]; then
        echo -e "${YELLOW}No completed timepoints found. Generate one first!${NC}"
        return 1
    fi

    echo ""
    echo -e "${BOLD}Select a timepoint:${NC}"
    echo ""

    # Parse and display timepoints
    INTERACTION_TIMEPOINTS="$response" python3 << 'PYEOF'
import os, json

data = json.loads(os.environ['INTERACTION_TIMEPOINTS'])
ids = []
for i, tp in enumerate(data.get('items', []), 1):
    ids.append(tp['id'])
    query_display = tp['query'][:45] + '...' if len(tp['query']) > 45 else tp['query']
    year = tp.get('year', '?')
    location = tp.get('location', 'Unknown')[:25]
    char_count = len(tp.get('characters', {}).get('characters', [])) if tp.get('characters') else 0
    print(f"  \033[1m{i:2})\033[0m {query_display}")
    print(f"      \033[2m{abs(year) if year else '?'} {'BCE' if year and year < 0 else 'CE'} | {location} | {char_count} characters\033[0m")

with open('/tmp/interaction_tp_ids', 'w') as f:
    f.write(','.join(ids))
PYEOF

    echo ""
    echo -e "${YELLOW}Enter number: ${NC}\c"
    read -r tp_choice

    if [ -f /tmp/interaction_tp_ids ]; then
        IFS=',' read -ra TP_IDS < /tmp/interaction_tp_ids || true
        rm -f /tmp/interaction_tp_ids

        idx=$((tp_choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#TP_IDS[@]} ]; then
            SELECTED_TIMEPOINT_ID="${TP_IDS[$idx]}"
            echo -e "${GREEN}Selected timepoint: ${CYAN}${SELECTED_TIMEPOINT_ID:0:8}...${NC}"
            return 0
        fi
    fi

    echo -e "${RED}Invalid selection${NC}"
    return 1
}

# Helper: Select a character from a timepoint
select_character_from_timepoint() {
    local tp_id="$1"
    local allow_multiple="${2:-false}"

    # Fetch timepoint details
    response=$(curl -s "$API_BASE/api/v1/timepoints/$tp_id?full=true")

    # Extract characters
    CHAR_RESPONSE="$response" python3 << 'PYEOF'
import os, json

data = json.loads(os.environ['CHAR_RESPONSE'])
characters = data.get('characters', {}).get('characters', [])

if not characters:
    print("NO_CHARACTERS")
else:
    names = []
    for i, char in enumerate(characters, 1):
        name = char.get('name', 'Unknown')
        role = char.get('role', 'Unknown')[:30]
        names.append(name)
        print(f"  \033[1m{i:2})\033[0m {name} - \033[2m{role}\033[0m")

    with open('/tmp/character_names', 'w') as f:
        f.write('|'.join(names))
PYEOF

    result=$?

    if [ ! -f /tmp/character_names ]; then
        echo -e "${RED}No characters found in this timepoint${NC}"
        return 1
    fi

    IFS='|' read -ra CHAR_NAMES < /tmp/character_names || true
    rm -f /tmp/character_names

    if [ ${#CHAR_NAMES[@]} -eq 0 ]; then
        echo -e "${RED}No characters found${NC}"
        return 1
    fi

    echo ""
    if [ "$allow_multiple" = "true" ]; then
        echo -e "${YELLOW}Enter numbers separated by commas (or 'all'): ${NC}\c"
    else
        echo -e "${YELLOW}Enter number: ${NC}\c"
    fi
    read -r char_choice

    if [ "$allow_multiple" = "true" ]; then
        if [ "$char_choice" = "all" ] || [ "$char_choice" = "ALL" ]; then
            SELECTED_CHARACTERS=("${CHAR_NAMES[@]}")
        else
            SELECTED_CHARACTERS=()
            IFS=',' read -ra CHOICES <<< "$char_choice"
            for choice in "${CHOICES[@]}"; do
                choice=$(echo "$choice" | tr -d ' ')
                idx=$((choice - 1))
                if [ $idx -ge 0 ] && [ $idx -lt ${#CHAR_NAMES[@]} ]; then
                    SELECTED_CHARACTERS+=("${CHAR_NAMES[$idx]}")
                fi
            done
        fi

        if [ ${#SELECTED_CHARACTERS[@]} -eq 0 ]; then
            echo -e "${RED}No valid characters selected${NC}"
            return 1
        fi

        echo -e "${GREEN}Selected: ${SELECTED_CHARACTERS[*]}${NC}"
    else
        idx=$((char_choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#CHAR_NAMES[@]} ]; then
            SELECTED_CHARACTER="${CHAR_NAMES[$idx]}"
            echo -e "${GREEN}Selected: ${CYAN}$SELECTED_CHARACTER${NC}"
            return 0
        else
            echo -e "${RED}Invalid selection${NC}"
            return 1
        fi
    fi

    return 0
}

# Global variable for interaction model
INTERACTION_MODEL=""
INTERACTION_RESPONSE_FORMAT="auto"

# Helper: Select model for character interactions
select_interaction_model() {
    echo ""
    echo -e "${BOLD}Select Model for Interaction:${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} ${BOLD}Default${NC} - Use server default model"
    echo -e "     ${DIM}gemini-2.5-flash (Google native)${NC}"
    echo -e "  ${MAGENTA}2)${NC} ${BOLD}Claude Opus 4.5${NC} - Anthropic frontier reasoning via OpenRouter"
    echo -e "     ${DIM}anthropic/claude-opus-4.5${NC}"
    echo -e "  ${MAGENTA}3)${NC} ${BOLD}Claude Sonnet 4.5${NC} - Anthropic best for coding/agents via OpenRouter"
    echo -e "     ${DIM}anthropic/claude-sonnet-4.5${NC}"
    echo -e "  ${MAGENTA}4)${NC} ${BOLD}Claude Opus 4${NC} - Anthropic flagship via OpenRouter"
    echo -e "     ${DIM}anthropic/claude-opus-4${NC}"
    echo -e "  ${MAGENTA}5)${NC} ${BOLD}Claude Sonnet 4${NC} - Anthropic balanced via OpenRouter"
    echo -e "     ${DIM}anthropic/claude-sonnet-4${NC}"
    echo -e "  ${MAGENTA}6)${NC} ${BOLD}Claude 3.5 Sonnet${NC} - Anthropic via OpenRouter"
    echo -e "     ${DIM}anthropic/claude-3.5-sonnet${NC}"
    echo -e "  ${YELLOW}7)${NC} ${BOLD}GPT-4${NC} - OpenAI via OpenRouter"
    echo -e "     ${DIM}openai/gpt-4${NC}"
    echo -e "  ${CYAN}8)${NC} ${BOLD}Llama 3.1 405B${NC} - Meta flagship via OpenRouter"
    echo -e "     ${DIM}meta-llama/llama-3.1-405b-instruct${NC}"
    echo -e "  ${CYAN}9)${NC} ${BOLD}Llama 3.1 70B${NC} - Meta large via OpenRouter"
    echo -e "     ${DIM}meta-llama/llama-3.1-70b-instruct${NC}"
    echo -e "  ${GREEN}10)${NC} ${BOLD}Qwen 2.5 3B${NC} - Alibaba small/fast via OpenRouter"
    echo -e "     ${DIM}qwen/qwen-2.5-3b-instruct${NC}"
    echo -e "  ${DIM}11)${NC} ${BOLD}Custom...${NC} - Enter model ID"
    echo ""
    echo -e "${YELLOW}Select (default=1): ${NC}\c"
    read -r model_choice

    case "$model_choice" in
        2)
            INTERACTION_MODEL="anthropic/claude-opus-4.5"
            echo -e "${GREEN}Using: anthropic/claude-opus-4.5${NC}"
            ;;
        3)
            INTERACTION_MODEL="anthropic/claude-sonnet-4.5"
            echo -e "${GREEN}Using: anthropic/claude-sonnet-4.5${NC}"
            ;;
        4)
            INTERACTION_MODEL="anthropic/claude-opus-4"
            echo -e "${GREEN}Using: anthropic/claude-opus-4${NC}"
            ;;
        5)
            INTERACTION_MODEL="anthropic/claude-sonnet-4"
            echo -e "${GREEN}Using: anthropic/claude-sonnet-4${NC}"
            ;;
        6)
            INTERACTION_MODEL="anthropic/claude-3.5-sonnet"
            echo -e "${GREEN}Using: anthropic/claude-3.5-sonnet${NC}"
            ;;
        7)
            INTERACTION_MODEL="openai/gpt-4"
            echo -e "${GREEN}Using: openai/gpt-4${NC}"
            ;;
        8)
            INTERACTION_MODEL="meta-llama/llama-3.1-405b-instruct"
            echo -e "${GREEN}Using: meta-llama/llama-3.1-405b-instruct${NC}"
            ;;
        9)
            INTERACTION_MODEL="meta-llama/llama-3.1-70b-instruct"
            echo -e "${GREEN}Using: meta-llama/llama-3.1-70b-instruct${NC}"
            ;;
        10)
            INTERACTION_MODEL="qwen/qwen-2.5-3b-instruct"
            echo -e "${GREEN}Using: qwen/qwen-2.5-3b-instruct${NC}"
            ;;
        11)
            echo -e "${YELLOW}Enter model ID (e.g., 'google/gemini-2.5-flash-preview'): ${NC}\c"
            read -r custom_model
            if [ -n "$custom_model" ]; then
                INTERACTION_MODEL="$custom_model"
                echo -e "${GREEN}Using: $INTERACTION_MODEL${NC}"
            else
                INTERACTION_MODEL=""
                echo -e "${DIM}Using default model${NC}"
            fi
            ;;
        *)
            INTERACTION_MODEL=""
            echo -e "${DIM}Using default model${NC}"
            ;;
    esac

    # Ask about response format
    echo ""
    echo -e "${YELLOW}Response format (s=structured, t=text, Enter=auto): ${NC}\c"
    read -r format_choice

    case "$format_choice" in
        s|S)
            INTERACTION_RESPONSE_FORMAT="structured"
            echo -e "${DIM}Using structured (JSON) responses${NC}"
            ;;
        t|T)
            INTERACTION_RESPONSE_FORMAT="text"
            echo -e "${DIM}Using plain text responses${NC}"
            ;;
        *)
            INTERACTION_RESPONSE_FORMAT="auto"
            echo -e "${DIM}Auto-detecting response format${NC}"
            ;;
    esac
}

# Build interaction JSON with model if specified
build_interaction_payload() {
    local base_payload="$1"

    # Remove trailing }
    local payload="${base_payload%\}}"

    if [ -n "$INTERACTION_MODEL" ]; then
        payload="$payload, \"model\": \"$INTERACTION_MODEL\""
    fi
    if [ "$INTERACTION_RESPONSE_FORMAT" != "auto" ]; then
        payload="$payload, \"response_format\": \"$INTERACTION_RESPONSE_FORMAT\""
    fi

    payload="$payload}"
    echo "$payload"
}

# Chat with a single character
chat_with_character() {
    echo -e "${BOLD}=== Chat with Character ===${NC}"
    echo ""
    echo -e "${DIM}Have a conversation with a historical figure from a timepoint${NC}"
    echo ""

    # Select timepoint
    if ! select_timepoint_for_interaction; then
        return
    fi

    local tp_id="$SELECTED_TIMEPOINT_ID"

    # Select character
    echo ""
    echo -e "${BOLD}Select a character to chat with:${NC}"
    if ! select_character_from_timepoint "$tp_id" "false"; then
        return
    fi

    local character_name="$SELECTED_CHARACTER"

    # Select model
    select_interaction_model

    echo ""
    echo -e "${CYAN}=== Chat with $character_name ===${NC}"
    if [ -n "$INTERACTION_MODEL" ]; then
        echo -e "${DIM}Model: $INTERACTION_MODEL${NC}"
    fi
    echo -e "${DIM}Type 'exit' or 'quit' to end the conversation${NC}"
    echo ""

    # Chat loop
    while true; do
        echo -e "${YELLOW}You: ${NC}\c"
        read -r user_message

        if [ "$user_message" = "exit" ] || [ "$user_message" = "quit" ] || [ -z "$user_message" ]; then
            echo -e "${DIM}Ending conversation...${NC}"
            break
        fi

        # Escape quotes in message for JSON
        escaped_message=$(echo "$user_message" | sed 's/"/\\"/g')

        # Build streaming chat request with model
        base_payload="{\"character\": \"$character_name\", \"message\": \"$escaped_message\"}"
        json_payload=$(build_interaction_payload "$base_payload")

        if [ "$INTERACTION_RESPONSE_FORMAT" = "structured" ]; then
            # Use non-streaming endpoint for structured JSON output
            echo -e "${MAGENTA}$character_name:${NC}"
            response=$(curl -s -X POST "$API_BASE/api/v1/interactions/$tp_id/chat" \
                -H "Content-Type: application/json" \
                -d "$json_payload")

            # Pretty print the JSON response
            echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))" 2>/dev/null || echo "$response"
            echo ""
        else
            # Use streaming endpoint for token-by-token display
            echo -e "${MAGENTA}$character_name: ${NC}\c"

            curl -N -s -X POST "$API_BASE/api/v1/interactions/$tp_id/chat/stream" \
                -H "Content-Type: application/json" \
                -d "$json_payload" | while IFS= read -r line; do
                if [[ "$line" == data:* ]]; then
                    data="${line#data: }"
                    event=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event',''))" 2>/dev/null || echo "")

                    case "$event" in
                        "token")
                            # Token event - data field contains the text chunk directly
                            chunk=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',''))" 2>/dev/null || echo "")
                            if [ -n "$chunk" ]; then
                                echo -n "$chunk"
                            fi
                            ;;
                        "done")
                            # Done event - data field contains the full response
                            # (already printed incrementally via tokens)
                            echo ""  # Add newline after streaming
                            ;;
                        "error")
                            error=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data','Unknown error'))" 2>/dev/null || echo "Error")
                            echo -e "${RED}Error: $error${NC}"
                            ;;
                    esac
                fi
            done

            echo ""
        fi
    done
}

# Extend dialog (generate more dialog)
extend_dialog() {
    echo -e "${BOLD}=== Extend Dialog ===${NC}"
    echo ""
    echo -e "${DIM}Generate additional dialog between characters${NC}"
    echo ""

    # Select timepoint
    if ! select_timepoint_for_interaction; then
        return
    fi

    local tp_id="$SELECTED_TIMEPOINT_ID"

    # Select model
    select_interaction_model

    # Ask about character selection
    echo ""
    echo -e "${YELLOW}Generate dialog for:${NC}"
    echo -e "  ${GREEN}1)${NC} All characters"
    echo -e "  ${GREEN}2)${NC} Select specific characters"
    echo -e "${YELLOW}> ${NC}\c"
    read -r dialog_choice

    local selected_chars=""

    if [ "$dialog_choice" = "2" ]; then
        echo ""
        echo -e "${BOLD}Select characters:${NC}"
        if ! select_character_from_timepoint "$tp_id" "true"; then
            return
        fi

        # Build JSON array of selected characters
        selected_chars=$(printf '"%s",' "${SELECTED_CHARACTERS[@]}" | sed 's/,$//')
    fi

    # Ask for number of lines
    echo ""
    echo -e "${YELLOW}Number of new dialog lines to generate (1-10) [5]: ${NC}\c"
    read -r num_lines
    num_lines="${num_lines:-5}"

    # Ask for optional prompt/topic
    echo -e "${YELLOW}Topic or prompt (optional): ${NC}\c"
    read -r topic

    echo ""
    echo -e "${CYAN}Generating dialog...${NC}"
    if [ -n "$INTERACTION_MODEL" ]; then
        echo -e "${DIM}Model: $INTERACTION_MODEL${NC}"
    fi
    echo ""

    # Build request
    if [ -n "$selected_chars" ]; then
        base_payload="{\"characters\": [$selected_chars], \"num_lines\": $num_lines"
    else
        base_payload="{\"num_lines\": $num_lines"
    fi

    if [ -n "$topic" ]; then
        escaped_topic=$(echo "$topic" | sed 's/"/\\"/g')
        base_payload="$base_payload, \"topic\": \"$escaped_topic\""
    fi
    base_payload="$base_payload}"
    json_payload=$(build_interaction_payload "$base_payload")

    # Stream dialog generation
    curl -N -s -X POST "$API_BASE/api/v1/interactions/$tp_id/dialog/stream" \
        -H "Content-Type: application/json" \
        -d "$json_payload" | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
            data="${line#data: }"
            event=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event',''))" 2>/dev/null || echo "")

            case "$event" in
                "line")
                    if [ "$INTERACTION_RESPONSE_FORMAT" = "structured" ]; then
                        # Show raw JSON for structured format
                        echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('data',{}), indent=2))" 2>/dev/null || echo "$data"
                    else
                        # Parse and display nicely
                        speaker=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('speaker',''))" 2>/dev/null || echo "")
                        text=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('text',''))" 2>/dev/null || echo "")
                        echo -e "${CYAN}$speaker:${NC} \"$text\""
                    fi
                    ;;
                "done")
                    total=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('total_lines',0))" 2>/dev/null || echo "0")
                    echo ""
                    echo -e "${GREEN}Generated $total new dialog lines${NC}"
                    ;;
                "error")
                    error=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data','Unknown error'))" 2>/dev/null || echo "Error")
                    echo -e "${RED}Error: $error${NC}"
                    ;;
            esac
        fi
    done
}

# Survey characters
survey_characters() {
    echo -e "${BOLD}=== Survey Characters ===${NC}"
    echo ""
    echo -e "${DIM}Ask the same question(s) to multiple characters${NC}"
    echo ""

    # Select timepoint
    if ! select_timepoint_for_interaction; then
        return
    fi

    local tp_id="$SELECTED_TIMEPOINT_ID"

    # Select model
    select_interaction_model

    # Ask about character selection
    echo ""
    echo -e "${YELLOW}Survey:${NC}"
    echo -e "  ${GREEN}1)${NC} All characters"
    echo -e "  ${GREEN}2)${NC} Select specific characters"
    echo -e "${YELLOW}> ${NC}\c"
    read -r survey_choice

    local selected_chars=""

    if [ "$survey_choice" = "2" ]; then
        echo ""
        echo -e "${BOLD}Select characters:${NC}"
        if ! select_character_from_timepoint "$tp_id" "true"; then
            return
        fi

        selected_chars=$(printf '"%s",' "${SELECTED_CHARACTERS[@]}" | sed 's/,$//')
    fi

    # Get questions
    echo ""
    echo -e "${YELLOW}Enter your question(s) (one per line, empty line to finish):${NC}"

    questions=()
    while true; do
        echo -e "${YELLOW}Q: ${NC}\c"
        read -r question

        if [ -z "$question" ]; then
            break
        fi

        questions+=("$question")
    done

    if [ ${#questions[@]} -eq 0 ]; then
        echo -e "${RED}No questions provided${NC}"
        return
    fi

    # Build questions JSON array
    questions_json=$(printf '"%s",' "${questions[@]}" | sed 's/,$//' | sed 's/"/\\"/g; s/\\\\"/\\"/g')
    # Properly escape and rebuild
    questions_json=""
    for q in "${questions[@]}"; do
        escaped_q=$(echo "$q" | sed 's/"/\\"/g')
        if [ -n "$questions_json" ]; then
            questions_json="$questions_json, \"$escaped_q\""
        else
            questions_json="\"$escaped_q\""
        fi
    done

    # Ask about execution mode
    echo ""
    echo -e "${YELLOW}Execution mode:${NC}"
    echo -e "  ${GREEN}1)${NC} Parallel (faster)"
    echo -e "  ${GREEN}2)${NC} Sequential (more context-aware)"
    echo -e "${YELLOW}> ${NC}\c"
    read -r mode_choice

    local mode="parallel"
    [ "$mode_choice" = "2" ] && mode="sequential"

    echo ""
    echo -e "${CYAN}Running survey ($mode mode)...${NC}"
    if [ -n "$INTERACTION_MODEL" ]; then
        echo -e "${DIM}Model: $INTERACTION_MODEL${NC}"
    fi
    echo ""

    # Build request
    base_payload="{\"questions\": [$questions_json], \"mode\": \"$mode\", \"include_summary\": true"

    if [ -n "$selected_chars" ]; then
        base_payload="$base_payload, \"characters\": [$selected_chars]"
    fi
    base_payload="$base_payload}"
    json_payload=$(build_interaction_payload "$base_payload")

    # Stream survey responses
    curl -N -s -X POST "$API_BASE/api/v1/interactions/$tp_id/survey/stream" \
        -H "Content-Type: application/json" \
        -d "$json_payload" | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
            data="${line#data: }"
            event=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event',''))" 2>/dev/null || echo "")

            case "$event" in
                "response")
                    char_name=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('character_name',''))" 2>/dev/null || echo "")
                    progress=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('progress',0))" 2>/dev/null || echo "0")

                    if [ "$INTERACTION_RESPONSE_FORMAT" = "structured" ]; then
                        # Show raw JSON for structured format
                        echo -e "${CYAN}[$progress%] $char_name${NC}:"
                        echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('data',{}), indent=2))" 2>/dev/null || echo "$data"
                        echo ""
                    else
                        # Parse and display nicely for text/auto format
                        response=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('response',''))" 2>/dev/null || echo "")
                        sentiment=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('sentiment',''))" 2>/dev/null || echo "")
                        emotional_tone=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('emotional_tone',''))" 2>/dev/null || echo "")
                        key_points=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); kp=d.get('data',{}).get('key_points',[]); print(', '.join(kp) if kp else '')" 2>/dev/null || echo "")

                        echo -e "${CYAN}[$progress%] $char_name${NC} (${DIM}$sentiment${NC}${emotional_tone:+, $emotional_tone}):"
                        echo -e "  \"$response\""
                        [ -n "$key_points" ] && echo -e "  ${DIM}Key points: $key_points${NC}"
                        echo ""
                    fi
                    ;;
                "summary")
                    summary=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',''))" 2>/dev/null || echo "")
                    echo -e "${BOLD}=== Summary ===${NC}"
                    echo "$summary"
                    echo ""
                    ;;
                "done")
                    total=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('total_responses',0))" 2>/dev/null || echo "0")
                    chars=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('characters_surveyed',0))" 2>/dev/null || echo "0")
                    echo -e "${GREEN}Survey complete: $total responses from $chars characters${NC}"
                    ;;
                "error")
                    error=$(echo "$data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data','Unknown error'))" 2>/dev/null || echo "Error")
                    echo -e "${RED}Error: $error${NC}"
                    ;;
            esac
        fi
    done
}

# Main loop
main() {
    check_server

    while true; do
        # Reset OpenRouter verification on each loop so API key changes are detected
        OPENROUTER_VERIFIED="unknown"

        print_header
        print_menu

        echo -e "${YELLOW}Select option: ${NC}\c"
        read -r choice

        case "$choice" in
            1) generate_sync; wait_for_key ;;
            2) generate_stream; wait_for_key ;;
            3) generate_from_template; wait_for_key ;;
            4) rapid_test; wait_for_key ;;
            5) rapid_test_free; wait_for_key ;;
            6) list_timepoints; wait_for_key ;;
            7) health_check; wait_for_key ;;
            8) open_docs; wait_for_key ;;
            9) test_endpoints; wait_for_key ;;
            10) model_eval; wait_for_key ;;
            11) chat_with_character; wait_for_key ;;
            12) extend_dialog; wait_for_key ;;
            13) survey_characters; wait_for_key ;;
            q|Q) echo -e "${GREEN}Goodbye!${NC}"; exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}"; sleep 1 ;;
        esac
    done
}

# Run
main
