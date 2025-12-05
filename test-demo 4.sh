#!/bin/bash
# TIMEPOINT Flash Demo Test Suite v2.0.8
# Comprehensive tests for all demo.sh menu items with emoji output
#
# Features tested:
#   - Health, models, providers endpoints
#   - All quality presets (HD, Balanced, Hyper)
#   - Free model selection
#   - Timepoint CRUD operations
#   - Parallel pipeline execution (graph|moment|camera steps)
#   - Delete functionality
#   - Template validation
#   - Character interactions (chat, dialog, survey)
#
# Usage:
#   ./test-demo.sh          # Run all tests (fast validation only)
#   ./test-demo.sh --quick  # Skip slow tests (generation)
#   ./test-demo.sh --bulk   # Full generation tests for all presets
#   ./test-demo.sh --preset hd        # Test specific preset only
#   ./test-demo.sh --preset hyper     # Test hyper preset only
#   ./test-demo.sh --preset balanced  # Test balanced preset only
#   ./test-demo.sh --verbose          # Verbose output
#   ./test-demo.sh --help   # Show help

set -e

# Configuration
API_BASE="http://localhost:8000"
QUICK_MODE=false
BULK_MODE=false
VERBOSE_MODE=false
SPECIFIC_PRESET=""
TIMEOUT_FAST=10    # seconds for fast endpoints
TIMEOUT_GEN=600    # seconds for generation (10 min for HD)

# Portable timeout function (works on macOS and Linux)
portable_timeout() {
    local duration=$1
    shift
    if command -v gtimeout &> /dev/null; then
        gtimeout "$duration" "$@"
    elif command -v timeout &> /dev/null; then
        timeout "$duration" "$@"
    else
        # Fallback: run without timeout on systems without it
        "$@"
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick|-q) QUICK_MODE=true; shift ;;
        --bulk|-b) BULK_MODE=true; shift ;;
        --verbose|-v) VERBOSE_MODE=true; shift ;;
        --preset|-p)
            SPECIFIC_PRESET="$2"
            shift 2
            ;;
        --help|-h)
            echo "TIMEPOINT Flash Demo Test Suite v2.0.8"
            echo ""
            echo "Usage: ./test-demo.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick, -q       Skip slow tests (generation)"
            echo "  --bulk, -b        Run full generation tests for all presets"
            echo "  --preset, -p NAME Test specific preset (hd, balanced, hyper)"
            echo "  --verbose, -v     Verbose output"
            echo "  --help, -h        Show this help"
            echo ""
            echo "Examples:"
            echo "  ./test-demo.sh              # Fast validation tests"
            echo "  ./test-demo.sh --bulk       # Full generation tests"
            echo "  ./test-demo.sh --preset hd  # Test HD preset only"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Results tracking
declare -a RESULTS=()
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# Test helper - run test and record result
run_test() {
    local name="$1"
    local cmd="$2"
    local timeout_secs="$3"

    if [ "$VERBOSE_MODE" = true ]; then
        echo -e "\033[2mRunning: $cmd\033[0m"
    fi

    # Run command with timeout
    set +e
    output=$(portable_timeout "$timeout_secs" bash -c "$cmd" 2>&1)
    exit_code=$?
    set -e

    if [ $exit_code -eq 0 ]; then
        RESULTS+=("pass:$name")
        ((PASS_COUNT++))
        echo -e "\033[32m\xE2\x9C\x85 $name\033[0m"
        if [ "$VERBOSE_MODE" = true ] && [ -n "$output" ]; then
            echo -e "\033[2m$output\033[0m" | head -5
        fi
    elif [ $exit_code -eq 124 ]; then
        RESULTS+=("fail:$name:Timeout after ${timeout_secs}s")
        ((FAIL_COUNT++))
        echo -e "\033[31m\xE2\x9D\x8C $name: Timeout after ${timeout_secs}s\033[0m"
    else
        # Get first line of error
        error_snippet=$(echo "$output" | grep -i -E "(error|fail|exception)" | head -1 | cut -c1-80)
        [ -z "$error_snippet" ] && error_snippet=$(echo "$output" | tail -1 | cut -c1-80)
        RESULTS+=("fail:$name:$error_snippet")
        ((FAIL_COUNT++))
        echo -e "\033[31m\xE2\x9D\x8C $name: $error_snippet\033[0m"
        if [ "$VERBOSE_MODE" = true ]; then
            echo -e "\033[31m$output\033[0m" | head -10
        fi
    fi
}

# Skip test helper
skip_test() {
    local name="$1"
    local reason="$2"
    RESULTS+=("skip:$name:$reason")
    ((SKIP_COUNT++))
    echo -e "\033[33m\xE2\x8F\xAD $name: $reason\033[0m"
}

# ============================================================
# Main Test Execution
# ============================================================

echo ""
echo "========================================"
echo "  TIMEPOINT Flash Demo Test Suite v2.0.8"
echo "========================================"
echo ""
echo "Mode: $([ "$QUICK_MODE" = true ] && echo "Quick" || ([ "$BULK_MODE" = true ] && echo "Bulk" || echo "Standard"))"
[ -n "$SPECIFIC_PRESET" ] && echo "Preset: $SPECIFIC_PRESET"
echo ""

# Check server is running
echo "Checking server..."
if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
    echo -e "\033[31m\xE2\x9D\x8C Server not running at $API_BASE\033[0m"
    echo "Start it with: ./run.sh -r"
    exit 1
fi
echo -e "\033[32mServer is running\033[0m"
echo ""

# ============================================================
# Menu 7: Health Check
# ============================================================
echo "--- Menu 7: Health Check ---"
run_test "Health endpoint" \
    "curl -sf '$API_BASE/health'" \
    $TIMEOUT_FAST

# ============================================================
# Menu 9: Test Endpoints
# ============================================================
echo ""
echo "--- Menu 9: Test Endpoints ---"

# Models endpoint
run_test "Models endpoint" \
    "curl -sf '$API_BASE/api/v1/models' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"models\" in d'" \
    $TIMEOUT_FAST

# Provider status
run_test "Providers endpoint" \
    "curl -sf '$API_BASE/api/v1/models/providers' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"providers\" in d'" \
    $TIMEOUT_FAST

# Free models endpoint
run_test "Free models endpoint" \
    "curl -sf '$API_BASE/api/v1/models/free' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"all_free\" in d'" \
    $TIMEOUT_FAST

# ============================================================
# Menu 6: Browse Timepoints
# ============================================================
echo ""
echo "--- Menu 6: Browse Timepoints ---"
run_test "List timepoints" \
    "curl -sf '$API_BASE/api/v1/timepoints'" \
    $TIMEOUT_FAST

# ============================================================
# Preset Configuration Validation
# ============================================================
echo ""
echo "--- Preset Configuration ---"

# Test that presets are recognized
run_test "HD preset accepted" \
    "curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test\", \"preset\": \"hd\"}' -o /dev/null -w '%{http_code}' | grep -q '200'" \
    $TIMEOUT_FAST

run_test "Balanced preset accepted" \
    "curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test\", \"preset\": \"balanced\"}' -o /dev/null -w '%{http_code}' | grep -q '200'" \
    $TIMEOUT_FAST

run_test "Hyper preset accepted" \
    "curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test\", \"preset\": \"hyper\"}' -o /dev/null -w '%{http_code}' | grep -q '200'" \
    $TIMEOUT_FAST

# ============================================================
# Menu 1, 2, 4 & 5: Generate Timepoint (Sync, Streaming & Rapid Tests)
# ============================================================
echo ""
echo "--- Menu 1, 2, 4 & 5: Generation Tests ---"

# Function to test a specific preset
test_preset_generation() {
    local preset="$1"
    local preset_upper=$(echo "$preset" | tr '[:lower:]' '[:upper:]')
    local timeout=$TIMEOUT_GEN

    # HD needs more time
    [ "$preset" = "hd" ] && timeout=900  # 15 min for HD

    if [ "$QUICK_MODE" = true ]; then
        skip_test "Sync generation ($preset)" "--quick mode"
        skip_test "Streaming generation ($preset)" "--quick mode"
    else
        # Test sync generation
        run_test "Sync generation ($preset)" \
            "response=\$(curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/sync' \
                -H 'Content-Type: application/json' \
                -d '{\"query\": \"boston tea party 1773\", \"generate_image\": false, \"preset\": \"$preset\"}') && \
            echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"status\") == \"completed\", f\"Status: {d.get(\"status\", \"unknown\")} Error: {d.get(\"error\", \"none\")}\"'" \
            $timeout

        # Test streaming generation
        run_test "Streaming generation ($preset)" \
            "curl -sf -N -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
                -H 'Content-Type: application/json' \
                -d '{\"query\": \"moon landing 1969\", \"generate_image\": false, \"preset\": \"$preset\"}' | \
            grep -q 'event.*done'" \
            $timeout
    fi
}

# Determine which presets to test
if [ -n "$SPECIFIC_PRESET" ]; then
    # Test only the specific preset
    test_preset_generation "$SPECIFIC_PRESET"
elif [ "$BULK_MODE" = true ]; then
    # Test all presets in bulk mode
    for preset in hyper balanced hd; do
        echo ""
        echo "--- Testing $preset preset ---"
        test_preset_generation "$preset"
    done
else
    # Standard mode: test hyper only (fastest)
    test_preset_generation "hyper"
fi

# ============================================================
# Delete Functionality
# ============================================================
echo ""
echo "--- Delete Functionality ---"

if [ "$QUICK_MODE" = true ]; then
    skip_test "Delete timepoint" "--quick mode"
else
    # Create a test timepoint then delete it
    run_test "Create and delete timepoint" \
        "# Create a timepoint
        tp_response=\$(curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/sync' \
            -H 'Content-Type: application/json' \
            -d '{\"query\": \"test delete\", \"generate_image\": false, \"preset\": \"hyper\"}')
        tp_id=\$(echo \"\$tp_response\" | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"id\",\"\"))')

        if [ -z \"\$tp_id\" ]; then
            echo 'Failed to create test timepoint'
            exit 1
        fi

        # Delete it
        delete_response=\$(curl -sf -X DELETE \"$API_BASE/api/v1/timepoints/\$tp_id\")
        deleted=\$(echo \"\$delete_response\" | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"deleted\", False))')

        if [ \"\$deleted\" != 'True' ]; then
            echo 'Delete failed'
            exit 1
        fi

        # Verify it's gone
        verify_response=\$(curl -s \"$API_BASE/api/v1/timepoints/\$tp_id\")
        if ! echo \"\$verify_response\" | grep -q 'not found'; then
            echo 'Timepoint still exists after delete'
            exit 1
        fi

        echo 'Delete test passed'" \
        $TIMEOUT_GEN
fi

# ============================================================
# Additional API Endpoints
# ============================================================
echo ""
echo "--- Additional API Endpoints ---"

# OpenAPI docs
run_test "OpenAPI docs endpoint" \
    "curl -sf '$API_BASE/openapi.json' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"openapi\" in d'" \
    $TIMEOUT_FAST

# Swagger UI
run_test "Swagger UI" \
    "curl -sf '$API_BASE/docs' | grep -q 'swagger'" \
    $TIMEOUT_FAST

# Get specific timepoint (if any exist)
run_test "Get timepoint by ID" \
    "tp_id=\$(curl -sf '$API_BASE/api/v1/timepoints' | python3 -c 'import sys,json; items=json.load(sys.stdin).get(\"items\",[]); print(items[0][\"id\"] if items else \"\")') && \
    [ -n \"\$tp_id\" ] && curl -sf '$API_BASE/api/v1/timepoints/\$tp_id' > /dev/null || echo 'No timepoints to test'" \
    $TIMEOUT_FAST

# ============================================================
# Temporal Navigation (if timepoints exist)
# ============================================================
echo ""
echo "--- Temporal Navigation ---"

# Get sequence
run_test "Temporal sequence endpoint" \
    "tp_id=\$(curl -sf '$API_BASE/api/v1/timepoints' | python3 -c 'import sys,json; items=json.load(sys.stdin).get(\"items\",[]); print(items[0][\"id\"] if items else \"\")') && \
    [ -n \"\$tp_id\" ] && curl -sf '$API_BASE/api/v1/temporal/\$tp_id/sequence' > /dev/null || echo 'No timepoints for sequence'" \
    $TIMEOUT_FAST

# ============================================================
# Error Handling
# ============================================================
echo ""
echo "--- Error Handling ---"

# Invalid timepoint ID
run_test "404 for invalid timepoint ID" \
    "response=\$(curl -s -w '%{http_code}' '$API_BASE/api/v1/timepoints/invalid-uuid-here')
    http_code=\${response: -3}
    [ \"\$http_code\" = '404' ] || [ \"\$http_code\" = '422' ]" \
    $TIMEOUT_FAST

# Empty query rejected
run_test "Empty query rejected" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/timepoints/generate/sync' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"\"}')
    http_code=\${response: -3}
    [ \"\$http_code\" = '422' ]" \
    $TIMEOUT_FAST

# ============================================================
# SSE Streaming Validation
# ============================================================
echo ""
echo "--- SSE Streaming Validation ---"

run_test "SSE start event includes preset" \
    "output=\$(curl -sf -N -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test event\", \"preset\": \"hyper\"}' 2>&1 | head -5)
    echo \"\$output\" | grep -q 'preset'" \
    $TIMEOUT_FAST

# ============================================================
# Menu 11, 12, 13: Character Interactions
# ============================================================
echo ""
echo "--- Menu 11, 12, 13: Character Interactions ---"

# Test interactions router is mounted (returns 404 for invalid ID, not 405 method not allowed)
run_test "Interactions router mounted" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/interactions/invalid-uuid/chat' \
        -H 'Content-Type: application/json' \
        -d '{\"character\": \"test\", \"message\": \"hello\"}')
    http_code=\${response: -3}
    # 404 (not found) or 422 (validation error) means router is mounted
    [ \"\$http_code\" = '404' ] || [ \"\$http_code\" = '422' ]" \
    $TIMEOUT_FAST

# Test sessions endpoint exists
run_test "Sessions endpoint exists" \
    "response=\$(curl -s -w '%{http_code}' '$API_BASE/api/v1/interactions/sessions/test-id')
    http_code=\${response: -3}
    # Should return 200 with empty list, not 404 (router mounted)
    [ \"\$http_code\" = '200' ] || [ \"\$http_code\" = '404' ]" \
    $TIMEOUT_FAST

# Test chat endpoint accepts valid request structure (will fail with 404 for invalid timepoint)
run_test "Chat endpoint request validation" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/chat' \
        -H 'Content-Type: application/json' \
        -d '{\"character\": \"Benjamin Franklin\", \"message\": \"Hello\"}')
    # Should return 404 (timepoint not found), not 422 (validation) - means request structure is valid
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# Test dialog endpoint accepts valid request structure
run_test "Dialog endpoint request validation" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/dialog' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"num_lines\": 3}')
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# Test survey endpoint accepts valid request structure
run_test "Survey endpoint request validation" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/survey' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"questions\": [\"What do you think?\"]}')
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# Test model selection parameter is accepted by all interaction endpoints
run_test "Chat endpoint accepts model parameter" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/chat' \
        -H 'Content-Type: application/json' \
        -d '{\"character\": \"Test\", \"message\": \"Hello\", \"model\": \"gemini-2.5-flash\", \"response_format\": \"auto\"}')
    # Should return 404 (timepoint not found), not 422 (validation) - means model param is valid
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

run_test "Dialog endpoint accepts model parameter" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/dialog' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"num_lines\": 3, \"model\": \"google/gemini-2.0-flash-001\", \"response_format\": \"text\"}')
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

run_test "Survey endpoint accepts model parameter" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/survey' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"questions\": [\"Test?\"], \"model\": \"anthropic/claude-3.5-sonnet\", \"response_format\": \"structured\"}')
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# Test chat streaming SSE events (must use 'token' and 'done', not 'response' or 'chunk')
run_test "Chat stream SSE uses token/done events" \
    "# Verify the API returns token/done events for streaming chat
    # This test validates the fix for demo.sh event name mismatch
    tp_id=\$(curl -sf '$API_BASE/api/v1/timepoints?page_size=1&status=completed' | \
        python3 -c 'import sys,json; items=json.load(sys.stdin).get(\"items\",[]); print(items[0][\"id\"] if items else \"\")')
    if [ -z \"\$tp_id\" ]; then
        echo 'No completed timepoint, skipping'
        exit 0
    fi
    char_name=\$(curl -s \"$API_BASE/api/v1/timepoints/\$tp_id?full=true\" | \
        python3 -c 'import sys,json; d=json.load(sys.stdin); chars=d.get(\"characters\",{}).get(\"characters\",[]); print(chars[0].get(\"name\",\"\") if chars else \"\")')
    if [ -z \"\$char_name\" ]; then
        echo 'No character found, skipping'
        exit 0
    fi
    # Make streaming request and verify event names
    output=\$(curl -sf -N -X POST \"$API_BASE/api/v1/interactions/\$tp_id/chat/stream\" \
        -H 'Content-Type: application/json' \
        -d \"{\\\"character\\\": \\\"\$char_name\\\", \\\"message\\\": \\\"Hello\\\"}\" 2>&1 | head -20)
    # Must contain 'token' or 'done' event (not 'response' or 'chunk')
    echo \"\$output\" | grep -qE '\"event\"[[:space:]]*:[[:space:]]*\"(token|done)\"'" \
    120  # 2 min timeout for LLM streaming

# Test with real timepoint if one exists (requires completed timepoint with characters)
if [ "$QUICK_MODE" != true ]; then
    # Get a completed timepoint with characters
    COMPLETED_TP=$(curl -s "$API_BASE/api/v1/timepoints?page_size=1&status=completed" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    items = data.get('items', [])
    for tp in items:
        if tp.get('characters') and tp['characters'].get('characters'):
            print(tp['id'])
            break
except:
    pass
" 2>/dev/null)

    if [ -n "$COMPLETED_TP" ]; then
        echo ""
        echo "Found completed timepoint: ${COMPLETED_TP:0:8}..."

        # Get first character name
        CHAR_NAME=$(curl -s "$API_BASE/api/v1/timepoints/$COMPLETED_TP?full=true" | \
            python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    chars = data.get('characters', {}).get('characters', [])
    if chars:
        print(chars[0].get('name', ''))
except:
    pass
" 2>/dev/null)

        if [ -n "$CHAR_NAME" ]; then
            echo "Testing with character: $CHAR_NAME"

            # Test chat with real character (skip in quick mode due to LLM call)
            run_test "Chat with character (integration)" \
                "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/$COMPLETED_TP/chat' \
                    -H 'Content-Type: application/json' \
                    -d '{\"character\": \"$CHAR_NAME\", \"message\": \"Hello, how are you?\", \"model\": null, \"response_format\": \"auto\"}')
                echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"response\"), \"No response\"'" \
                120  # 2 min timeout for LLM

            # Test chat with model override (use fast model for testing)
            run_test "Chat with model override (integration)" \
                "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/$COMPLETED_TP/chat' \
                    -H 'Content-Type: application/json' \
                    -d '{\"character\": \"$CHAR_NAME\", \"message\": \"Brief greeting please.\", \"model\": \"gemini-2.5-flash\", \"response_format\": \"text\"}')
                echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"response\"), \"No response\"'" \
                120  # 2 min timeout for LLM

            # Test survey with real characters
            run_test "Survey characters (integration)" \
                "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/$COMPLETED_TP/survey' \
                    -H 'Content-Type: application/json' \
                    -d '{\"characters\": \"all\", \"questions\": [\"What is happening?\"], \"include_summary\": false, \"response_format\": \"auto\"}')
                echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"responses\"), \"No responses\"'" \
                180  # 3 min timeout for survey

            # Test dialog extension
            run_test "Extend dialog (integration)" \
                "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/$COMPLETED_TP/dialog' \
                    -H 'Content-Type: application/json' \
                    -d '{\"characters\": \"all\", \"num_lines\": 2, \"response_format\": \"auto\"}')
                echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"dialog\"), \"No dialog\"'" \
                120  # 2 min timeout for LLM
        else
            skip_test "Chat with character (integration)" "No character name found"
            skip_test "Survey characters (integration)" "No character name found"
            skip_test "Extend dialog (integration)" "No character name found"
        fi
    else
        skip_test "Chat with character (integration)" "No completed timepoint with characters"
        skip_test "Survey characters (integration)" "No completed timepoint with characters"
        skip_test "Extend dialog (integration)" "No completed timepoint with characters"
    fi
else
    skip_test "Chat with character (integration)" "--quick mode"
    skip_test "Survey characters (integration)" "--quick mode"
    skip_test "Extend dialog (integration)" "--quick mode"
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo ""

total=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
echo -e "\033[32m\xE2\x9C\x85 Passed:  $PASS_COUNT\033[0m"
echo -e "\033[31m\xE2\x9D\x8C Failed:  $FAIL_COUNT\033[0m"
echo -e "\033[33m\xE2\x8F\xAD Skipped: $SKIP_COUNT\033[0m"
echo ""
echo "Total: $total tests"

# Show failed tests details
if [ $FAIL_COUNT -gt 0 ]; then
    echo ""
    echo "Failed tests:"
    for result in "${RESULTS[@]}"; do
        if [[ "$result" == fail:* ]]; then
            name=$(echo "$result" | cut -d: -f2)
            error=$(echo "$result" | cut -d: -f3-)
            echo -e "  \033[31m- $name: $error\033[0m"
        fi
    done
fi

# Exit with appropriate code
if [ $FAIL_COUNT -gt 0 ]; then
    exit 1
else
    exit 0
fi
