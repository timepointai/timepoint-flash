#!/bin/bash
# TIMEPOINT Flash Multi-Model Evaluation CLI
# Compare model performance on the same prompt
#
# Usage:
#   ./eval.sh "your query"                    # Quick eval with verified models
#   ./eval.sh "query" --preset google_native  # Use specific preset
#   ./eval.sh --interactive                   # Interactive mode
#   ./eval.sh --help                          # Show help

set -e

# Configuration
API_BASE="http://localhost:8000"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

usage() {
    echo "TIMEPOINT Flash Multi-Model Evaluation v2.0.11"
    echo ""
    echo "Usage: ./eval.sh [query] [options]"
    echo ""
    echo "Options:"
    echo "  -p, --preset PRESET   Use preset: verified, google_native, openrouter, all"
    echo "  -t, --timeout SECS    Timeout per model (default: 120)"
    echo "  -i, --interactive     Interactive mode"
    echo "  --help                Show this help"
    echo ""
    echo "Examples:"
    echo "  ./eval.sh \"battle of thermopylae\"        # Eval with verified models"
    echo "  ./eval.sh \"moon landing\" -p google_native # Use Google models only"
    echo "  ./eval.sh -i                              # Interactive mode"
    echo ""
    exit 0
}

check_server() {
    if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
        echo -e "${RED}Error: Server not running at $API_BASE${NC}"
        echo -e "Start it with: ${CYAN}./run.sh -r${NC}"
        exit 1
    fi
}

print_header() {
    echo -e "${CYAN}"
    echo "  _____ ___ __  __ _____ ____   ___ ___ _   _ _____ "
    echo " |_   _|_ _|  \/  | ____|  _ \ / _ \_ _| \\ | |_   _|"
    echo "   | |  | || |\\/| |  _| | |_) | | | | ||  \\| | | |  "
    echo "   | |  | || |  | | |___|  __/| |_| | || |\\  | | |  "
    echo "   |_| |___|_|  |_|_____|_|    \\___/___|_| \\_| |_|  "
    echo -e "${NC}"
    echo -e "${BOLD}Multi-Model Evaluation v2.0.11${NC}"
    echo ""
}

list_presets() {
    echo -e "${BOLD}Available Presets:${NC}"
    response=$(curl -s --max-time 5 "$API_BASE/api/v1/eval/models" 2>/dev/null)

    if [ -z "$response" ]; then
        echo "  (Unable to fetch - server may be starting up)"
        echo ""
        return
    fi

    echo "$response" | python3 -c '
import sys, json

try:
    data = json.load(sys.stdin)

    # Check for API error
    if "detail" in data:
        print("  API Error:", data["detail"])
        sys.exit(0)

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
}

run_eval() {
    local query="$1"
    local preset="${2:-verified}"
    local timeout="${3:-120}"

    echo -e "${CYAN}Running evaluation...${NC}"
    echo -e "  Query:   ${BOLD}$query${NC}"
    echo -e "  Preset:  ${BOLD}$preset${NC}"
    echo -e "  Timeout: ${BOLD}${timeout}s${NC}"
    echo ""

    # Build JSON payload
    json_payload="{\"query\": \"$query\", \"preset\": \"$preset\", \"timeout_seconds\": $timeout}"

    # Make API call and get report
    response=$(curl -s -X POST "$API_BASE/api/v1/eval/compare/report" \
        -H "Content-Type: application/json" \
        -d "$json_payload")

    # Extract and print the report (handles both success and error cases)
    echo "$response" | python3 -c '
import sys, json

try:
    data = json.load(sys.stdin)

    # Check for top-level error (API error, not model errors)
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

interactive_mode() {
    print_header
    check_server

    while true; do
        echo -e "${BOLD}=== Model Evaluation ===${NC}"
        echo ""

        # Show presets
        list_presets

        # Get query
        echo -e "${YELLOW}Enter query (or 'q' to quit):${NC}"
        echo -e "${YELLOW}> ${NC}\c"
        read -r query

        if [ "$query" = "q" ] || [ "$query" = "Q" ]; then
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
        fi

        if [ -z "$query" ]; then
            echo -e "${RED}Query cannot be empty${NC}"
            continue
        fi

        # Get preset
        echo ""
        echo -e "${YELLOW}Select preset (1-4):${NC}"
        echo "  1) verified (default)"
        echo "  2) google_native"
        echo "  3) openrouter"
        echo "  4) all"
        echo -e "${YELLOW}> ${NC}\c"
        read -r preset_choice

        case "$preset_choice" in
            2) preset="google_native" ;;
            3) preset="openrouter" ;;
            4) preset="all" ;;
            *) preset="verified" ;;
        esac

        echo ""
        run_eval "$query" "$preset"

        echo ""
        echo -e "${DIM}Press Enter to continue...${NC}"
        read -r
        clear
    done
}

# Parse arguments
QUERY=""
PRESET="verified"
TIMEOUT=120
INTERACTIVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--preset)
            PRESET="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -i|--interactive)
            INTERACTIVE=true
            shift
            ;;
        --help)
            usage
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            ;;
        *)
            QUERY="$1"
            shift
            ;;
    esac
done

# Run
check_server

if [ "$INTERACTIVE" = true ]; then
    interactive_mode
elif [ -n "$QUERY" ]; then
    print_header
    run_eval "$QUERY" "$PRESET" "$TIMEOUT"
else
    usage
fi
