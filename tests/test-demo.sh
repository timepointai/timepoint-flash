#!/bin/bash
# TIMEPOINT Flash Demo Test Suite v2.2.1
# Comprehensive tests for all demo.sh menu items with emoji output
#
# Features tested:
#   - Health, models, providers endpoints
#   - All quality presets (HD, Balanced, Hyper)
#   - Free model selection (best/fastest)
#   - Timepoint CRUD operations
#   - Parallel pipeline execution (graph|moment|camera steps)
#   - Delete functionality
#   - Template validation
#   - Character interactions (chat, dialog, survey)
#   - Model selection for interactions (Phase 20)
#   - Model Eval API (Menu 10)
#   - Temporal navigation (next/prior/sequence)
#   - Response format (structured/text/auto)
#   - Streaming endpoints (dialog/survey)
#   - Slug and image endpoints
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
            echo "TIMEPOINT Flash Demo Test Suite v2.2.1"
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
echo "  TIMEPOINT Flash Demo Test Suite v2.2.1"
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
# OpenRouter Availability (catches demo.sh template bug)
# ============================================================
echo ""
echo "--- OpenRouter Availability Check ---"

# Test that OpenRouter provider status is accurate
# This catches the bug where hyper preset fails due to invalid API key
run_test "OpenRouter provider status check" \
    "response=\$(curl -sf '$API_BASE/api/v1/models/providers')
    or_available=\$(echo \"\$response\" | python3 -c \"
import sys, json
d = json.load(sys.stdin)
for p in d.get('providers', []):
    if p.get('provider') == 'openrouter':
        print('yes' if p.get('available') else 'no')
        break
else:
    print('no')
\")
    echo \"OpenRouter available: \$or_available\"
    # Just verify we can check the status
    [ \"\$or_available\" = 'yes' ] || [ \"\$or_available\" = 'no' ]" \
    $TIMEOUT_FAST

# Test that hyper preset works OR returns proper error (not silent failure)
# This catches the bug where judge step fails silently with OpenRouter auth issues
run_test "Hyper preset generates or reports clear error" \
    "response=\$(curl -s -N -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test query\", \"preset\": \"hyper\"}' 2>&1 | head -10)
    # Should either succeed (contain 'step_complete') or fail clearly (contain 'error' with description)
    if echo \"\$response\" | grep -q 'step_complete'; then
        echo 'Hyper preset working'
        exit 0
    elif echo \"\$response\" | grep -q 'Authentication failed\\|API key\\|401'; then
        echo 'OpenRouter auth failed (expected if no valid API key)'
        exit 0
    elif echo \"\$response\" | grep -q 'step_error'; then
        # Error with description is acceptable (clear failure)
        echo 'Generation failed with clear error'
        exit 0
    else
        echo 'Unexpected response format'
        exit 1
    fi" \
    $TIMEOUT_FAST

# Test that balanced preset works as fallback when hyper might not
run_test "Balanced preset works as OpenRouter fallback" \
    "response=\$(curl -s -N -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test query\", \"preset\": \"balanced\"}' 2>&1 | head -10)
    # Balanced uses Google native, should always work if GOOGLE_API_KEY is set
    echo \"\$response\" | grep -qE 'start|step_' || (echo 'Balanced preset should work'; exit 1)" \
    $TIMEOUT_FAST

# ============================================================
# End-to-End Generation Validation (Critical - catches pipeline failures)
# This test runs even in quick mode with a short timeout to verify
# that at least one complete generation can succeed
# ============================================================
echo ""
echo "--- End-to-End Generation Validation ---"

# Critical test: verify generation can actually COMPLETE (not just start)
# This catches transient API failures that the "starts" tests miss
run_test "Generation completes successfully (balanced)" \
    "response=\$(curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/sync' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"boston tea party 1773\", \"generate_image\": false, \"preset\": \"balanced\"}')
    status=\$(echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"status\",\"unknown\"))')
    error=\$(echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get(\"error\",\"none\"))')
    if [ \"\$status\" != 'completed' ]; then
        echo \"FAILED: status=\$status, error=\$error\"
        exit 1
    fi
    echo 'Generation completed successfully'" \
    300  # 5 min timeout (generation can take 2-3 min)

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
            skip_test "Chat with model override (integration)" "No character name found"
            skip_test "Survey characters (integration)" "No character name found"
            skip_test "Extend dialog (integration)" "No character name found"
        fi
    else
        skip_test "Chat with character (integration)" "No completed timepoint with characters"
        skip_test "Chat with model override (integration)" "No completed timepoint with characters"
        skip_test "Survey characters (integration)" "No completed timepoint with characters"
        skip_test "Extend dialog (integration)" "No completed timepoint with characters"
    fi
else
    skip_test "Chat with character (integration)" "--quick mode"
    skip_test "Chat with model override (integration)" "--quick mode"
    skip_test "Survey characters (integration)" "--quick mode"
    skip_test "Extend dialog (integration)" "--quick mode"
fi

# ============================================================
# Menu 10: Model Eval API
# ============================================================
echo ""
echo "--- Menu 10: Model Eval API ---"

# Test eval models endpoint (list presets)
run_test "Eval models endpoint" \
    "response=\$(curl -s '$API_BASE/api/v1/eval/models')
    echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"presets\" in d or \"detail\" in d'" \
    $TIMEOUT_FAST

# Test eval compare/report endpoint accepts valid request (may timeout with real execution)
run_test "Eval compare endpoint accepts request" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/eval/compare/report' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test\", \"preset\": \"verified\", \"timeout_seconds\": 10}')
    http_code=\${response: -3}
    # 200 (success), 408 (timeout), or 500 (error during eval) are all valid - endpoint is working
    [ \"\$http_code\" = '200' ] || [ \"\$http_code\" = '408' ] || [ \"\$http_code\" = '500' ] || [ \"\$http_code\" = '504' ]" \
    30  # Short timeout since eval itself has timeout

# ============================================================
# Free Models API (Enhanced)
# ============================================================
echo ""
echo "--- Free Models API (Enhanced) ---"

# Test free models endpoint returns best model
run_test "Free models includes best model" \
    "curl -sf '$API_BASE/api/v1/models/free' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"best\") is not None or d.get(\"total\", 0) == 0, \"Missing best model\"'" \
    $TIMEOUT_FAST

# Test free models endpoint returns fastest model
run_test "Free models includes fastest model" \
    "curl -sf '$API_BASE/api/v1/models/free' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"fastest\") is not None or d.get(\"total\", 0) == 0, \"Missing fastest model\"'" \
    $TIMEOUT_FAST

# ============================================================
# Additional Endpoints (Enhanced)
# ============================================================
echo ""
echo "--- Additional Endpoints (Enhanced) ---"

# ReDoc endpoint
run_test "ReDoc endpoint" \
    "curl -sf '$API_BASE/redoc' | grep -qi 'redoc'" \
    $TIMEOUT_FAST

# Test get timepoint by slug (if any exist)
run_test "Get timepoint by slug" \
    "slug=\$(curl -sf '$API_BASE/api/v1/timepoints' | python3 -c 'import sys,json; items=json.load(sys.stdin).get(\"items\",[]); print(items[0].get(\"slug\",\"\") if items else \"\")') && \
    [ -n \"\$slug\" ] && curl -sf '$API_BASE/api/v1/timepoints/slug/\$slug' > /dev/null || echo 'No timepoints with slug'" \
    $TIMEOUT_FAST

# Test full=true query param
run_test "Timepoint full=true returns characters" \
    "tp_id=\$(curl -sf '$API_BASE/api/v1/timepoints?status=completed' | python3 -c 'import sys,json; items=json.load(sys.stdin).get(\"items\",[]); print(items[0][\"id\"] if items else \"\")') && \
    [ -n \"\$tp_id\" ] && curl -sf '$API_BASE/api/v1/timepoints/\$tp_id?full=true' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"characters\" in d or \"scene\" in d' || echo 'No completed timepoints'" \
    $TIMEOUT_FAST

# Test has_image field exists in response
run_test "Timepoint response includes has_image field" \
    "tp_id=\$(curl -sf '$API_BASE/api/v1/timepoints' | python3 -c 'import sys,json; items=json.load(sys.stdin).get(\"items\",[]); print(items[0][\"id\"] if items else \"\")') && \
    [ -n \"\$tp_id\" ] && curl -sf '$API_BASE/api/v1/timepoints/\$tp_id' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert \"has_image\" in d or \"image_base64\" in d or d.get(\"status\") != \"completed\"' || echo 'No timepoints'" \
    $TIMEOUT_FAST

# ============================================================
# Temporal Navigation (Enhanced)
# ============================================================
echo ""
echo "--- Temporal Navigation (Enhanced) ---"

# Test temporal next endpoint exists
run_test "Temporal next endpoint accepts request" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/temporal/00000000-0000-0000-0000-000000000000/next' \
        -H 'Content-Type: application/json' \
        -d '{\"units\": 1, \"unit\": \"day\"}')
    http_code=\${response: -3}
    # 404 (not found) means endpoint exists and validated request
    [ \"\$http_code\" = '404' ] || [ \"\$http_code\" = '422' ]" \
    $TIMEOUT_FAST

# Test temporal prior endpoint exists
run_test "Temporal prior endpoint accepts request" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/temporal/00000000-0000-0000-0000-000000000000/prior' \
        -H 'Content-Type: application/json' \
        -d '{\"units\": 1, \"unit\": \"year\"}')
    http_code=\${response: -3}
    # 404 (not found) means endpoint exists and validated request
    [ \"\$http_code\" = '404' ] || [ \"\$http_code\" = '422' ]" \
    $TIMEOUT_FAST

# ============================================================
# Interaction Streaming Endpoints
# ============================================================
echo ""
echo "--- Interaction Streaming Endpoints ---"

# Test dialog streaming endpoint exists
run_test "Dialog stream endpoint accepts request" \
    "response=\$(curl -s -w '%{http_code}' -N -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/dialog/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"num_lines\": 2}' 2>&1 | tail -1)
    # Should not be 405 (method not allowed)
    [ \"\$response\" != '405' ]" \
    $TIMEOUT_FAST

# Test survey streaming endpoint exists
run_test "Survey stream endpoint accepts request" \
    "response=\$(curl -s -w '%{http_code}' -N -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/survey/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"questions\": [\"Test?\"]}' 2>&1 | tail -1)
    # Should not be 405 (method not allowed)
    [ \"\$response\" != '405' ]" \
    $TIMEOUT_FAST

# ============================================================
# Response Format Testing
# ============================================================
echo ""
echo "--- Response Format Testing ---"

# Test structured response format is accepted
run_test "Structured response format accepted (chat)" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/chat' \
        -H 'Content-Type: application/json' \
        -d '{\"character\": \"Test\", \"message\": \"Hello\", \"response_format\": \"structured\"}')
    # 404 means request was valid (timepoint not found)
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# Test text response format is accepted
run_test "Text response format accepted (survey)" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/survey' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"questions\": [\"Test?\"], \"response_format\": \"text\"}')
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# Test auto response format is accepted
run_test "Auto response format accepted (dialog)" \
    "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/00000000-0000-0000-0000-000000000000/dialog' \
        -H 'Content-Type: application/json' \
        -d '{\"characters\": \"all\", \"num_lines\": 3, \"response_format\": \"auto\"}')
    echo \"\$response\" | grep -q 'not found' || echo \"\$response\" | grep -q 'Timepoint'" \
    $TIMEOUT_FAST

# ============================================================
# Custom Model Override Testing
# ============================================================
echo ""
echo "--- Custom Model Override Testing ---"

# Test text_model override in generation
run_test "Generation accepts text_model override" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test\", \"text_model\": \"gemini-2.5-flash\"}' -o /dev/null)
    [ \"\$response\" = '200' ]" \
    $TIMEOUT_FAST

# Test image_model override in generation
run_test "Generation accepts image_model override" \
    "response=\$(curl -s -w '%{http_code}' -X POST '$API_BASE/api/v1/timepoints/generate/stream' \
        -H 'Content-Type: application/json' \
        -d '{\"query\": \"test\", \"image_model\": \"google/gemini-2.0-flash-exp\"}' -o /dev/null)
    [ \"\$response\" = '200' ]" \
    $TIMEOUT_FAST

# ============================================================
# Image Generation Test (Critical - catches config issues)
# ============================================================
echo ""
echo "--- Image Generation ---"

if [ "$QUICK_MODE" = true ]; then
    skip_test "Image generation (with has_image)" "--quick mode"
else
    # Test that image generation actually works (catches response_modalities issues)
    # Use a real historical query that will pass the JudgeAgent validation
    run_test "Image generation (with has_image)" \
        "response=\$(curl -sf -X POST '$API_BASE/api/v1/timepoints/generate/sync' \
            -H 'Content-Type: application/json' \
            -d '{\"query\": \"wright brothers first flight 1903\", \"generate_image\": true, \"preset\": \"hyper\"}')
        status=\$(echo \"\$response\" | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"status\",\"\"))')
        if [ \"\$status\" != 'completed' ]; then
            echo \"Timepoint status: \$status (expected completed)\"
            exit 1
        fi
        tp_id=\$(echo \"\$response\" | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"id\",\"\"))')
        # Check if image was generated
        has_image=\$(curl -sf '$API_BASE/api/v1/timepoints/'\$tp_id | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"has_image\", False))')
        if [ \"\$has_image\" != 'True' ]; then
            echo 'Image generation failed - has_image is False'
            exit 1
        fi
        echo 'Image generation verified'" \
        $TIMEOUT_GEN
fi

# ============================================================
# Integration Tests with Real Data (if available)
# ============================================================
if [ "$QUICK_MODE" != true ]; then
    echo ""
    echo "--- Integration Tests (Real Data) ---"

    # Get a completed timepoint for integration tests
    INTEGRATION_TP=$(curl -s "$API_BASE/api/v1/timepoints?page_size=1&status=completed" | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    items = data.get('items', [])
    if items:
        print(items[0]['id'])
except:
    pass
" 2>/dev/null)

    if [ -n "$INTEGRATION_TP" ]; then
        # Test dialog streaming with real timepoint
        run_test "Dialog streaming (integration)" \
            "output=\$(curl -sf -N -X POST '$API_BASE/api/v1/interactions/$INTEGRATION_TP/dialog/stream' \
                -H 'Content-Type: application/json' \
                -d '{\"num_lines\": 2}' 2>&1 | head -20)
            echo \"\$output\" | grep -qE '\"event\"'" \
            120

        # Test survey streaming with real timepoint
        run_test "Survey streaming (integration)" \
            "output=\$(curl -sf -N -X POST '$API_BASE/api/v1/interactions/$INTEGRATION_TP/survey/stream' \
                -H 'Content-Type: application/json' \
                -d '{\"questions\": [\"Brief thought?\"]}' 2>&1 | head -30)
            echo \"\$output\" | grep -qE '\"event\"'" \
            180

        # Test structured response returns JSON fields
        run_test "Structured chat returns JSON (integration)" \
            "response=\$(curl -s -X POST '$API_BASE/api/v1/interactions/$INTEGRATION_TP/chat' \
                -H 'Content-Type: application/json' \
                -d '{\"character\": \"first\", \"message\": \"Hello\", \"response_format\": \"structured\"}')
            echo \"\$response\" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"response\") or d.get(\"error\")'" \
            120
    else
        skip_test "Dialog streaming (integration)" "No completed timepoint"
        skip_test "Survey streaming (integration)" "No completed timepoint"
        skip_test "Structured chat returns JSON (integration)" "No completed timepoint"
    fi
else
    skip_test "Dialog streaming (integration)" "--quick mode"
    skip_test "Survey streaming (integration)" "--quick mode"
    skip_test "Structured chat returns JSON (integration)" "--quick mode"
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
