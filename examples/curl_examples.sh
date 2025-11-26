#!/bin/bash
#
# TIMEPOINT Flash - curl Examples
#
# Simple bash script showing API usage with curl.
#
# Make executable: chmod +x curl_examples.sh
# Run: ./curl_examples.sh
#

set -e  # Exit on error

API_BASE="http://localhost:8000"

echo ""
echo "🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌"
echo "TIMEPOINT Flash - curl Examples"
echo "🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌🍌"
echo ""

# Check if jq is installed (optional, for pretty JSON)
if command -v jq &> /dev/null; then
    HAS_JQ=true
else
    HAS_JQ=false
    echo "💡 Tip: Install 'jq' for pretty JSON output: brew install jq"
    echo ""
fi

# Helper function to pretty-print JSON
pretty_json() {
    if [ "$HAS_JQ" = true ]; then
        jq '.'
    else
        cat
    fi
}

# ============================================
# Example 1: Health Check
# ============================================
echo "1️⃣  Health Check"
echo "   GET /health"
echo ""

curl -s "$API_BASE/health" | pretty_json

echo ""
echo "---"
echo ""

# ============================================
# Example 2: Generate a Timepoint
# ============================================
echo "2️⃣  Generate a Timepoint"
echo "   POST /api/timepoint/create"
echo ""

RESPONSE=$(curl -s -X POST "$API_BASE/api/timepoint/create" \
  -H "Content-Type: application/json" \
  -d '{
    "input_query": "Medieval marketplace, London 1250, winter morning",
    "requester_email": "curl_example@example.com"
  }')

echo "$RESPONSE" | pretty_json

# Extract session_id and slug
if [ "$HAS_JQ" = true ]; then
    SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
    SLUG=$(echo "$RESPONSE" | jq -r '.slug')
else
    # Fallback: grep-based extraction (less reliable)
    SESSION_ID=$(echo "$RESPONSE" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
    SLUG=$(echo "$RESPONSE" | grep -o '"slug":"[^"]*"' | cut -d'"' -f4)
fi

echo ""
echo "✅ Session ID: $SESSION_ID"
echo "✅ Slug: $SLUG"
echo ""
echo "---"
echo ""

# ============================================
# Example 3: Check Status (Quick Poll)
# ============================================
echo "3️⃣  Check Status (Quick Poll)"
echo "   GET /api/timepoint/check/$SLUG"
echo ""

curl -s "$API_BASE/api/timepoint/check/$SLUG" | pretty_json

echo ""
echo "---"
echo ""

# ============================================
# Example 4: Stream Progress (SSE)
# ============================================
echo "4️⃣  Stream Progress (Server-Sent Events)"
echo "   GET /api/timepoint/status/$SESSION_ID"
echo ""
echo "   Streaming progress updates..."
echo "   (Press Ctrl+C to stop early)"
echo ""

# Stream SSE events (this will take 40-60 seconds for full generation)
curl -N "$API_BASE/api/timepoint/status/$SESSION_ID" 2>/dev/null | while read line; do
    # Parse SSE format (event: xxx / data: xxx)
    if [[ $line == data:* ]]; then
        # Extract the JSON data part
        JSON_DATA="${line#data: }"

        if [ "$HAS_JQ" = true ]; then
            # Pretty-print the event data
            echo "$JSON_DATA" | jq -c '{event: .agent, message: .message, progress: .progress}'
        else
            echo "$JSON_DATA"
        fi
    fi
done

echo ""
echo "---"
echo ""

# ============================================
# Example 5: Get Timepoint Details
# ============================================
echo "5️⃣  Get Timepoint Details"
echo "   GET /api/timepoint/details/$SLUG"
echo ""

curl -s "$API_BASE/api/timepoint/details/$SLUG" | pretty_json

echo ""
echo "---"
echo ""

# ============================================
# Example 6: List All Timepoints (Feed)
# ============================================
echo "6️⃣  List All Timepoints (Feed)"
echo "   GET /api/feed?limit=3"
echo ""

FEED=$(curl -s "$API_BASE/api/feed?limit=3")

echo "$FEED" | pretty_json

if [ "$HAS_JQ" = true ]; then
    echo ""
    echo "📊 Feed Summary:"
    TOTAL=$(echo "$FEED" | jq -r '.total')
    COUNT=$(echo "$FEED" | jq -r '.timepoints | length')
    echo "   Total timepoints: $TOTAL"
    echo "   Returned: $COUNT"
fi

echo ""
echo "---"
echo ""

# ============================================
# Summary
# ============================================
echo "✨ Done!"
echo ""
echo "📖 All Examples Complete"
echo ""
echo "Next Steps:"
echo "  - View in gallery: http://localhost:8000/"
echo "  - Try the Python client: python3 python_client.py"
echo "  - Stream progress: python3 stream_progress.py"
echo ""
echo "🍌 Built with Gemini Nano Banana"
echo ""
