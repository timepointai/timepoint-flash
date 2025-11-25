#!/bin/bash
set -e

# Test runner script for Timepoint Flash
# Usage:
#   ./test.sh fast    - Run fast unit tests only
#   ./test.sh e2e     - Run e2e integration tests (requires API key)
#   ./test.sh all     - Run all tests
#   ./test.sh         - Run fast tests by default

MODE="${1:-fast}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Timepoint Flash Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠ Virtual environment not activated${NC}"
    echo "Attempting to activate .venv..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}✗ No .venv found. Run ./init.sh first.${NC}"
        exit 1
    fi
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}⚠ pytest not found. Installing test dependencies...${NC}"
    pip install -e ".[dev]"
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
elif [ -f ".env.dev" ]; then
    export $(cat .env.dev | grep -v '^#' | xargs)
fi

# Check for API key if running e2e tests
if [[ "$MODE" == "e2e" ]] || [[ "$MODE" == "all" ]]; then
    if [[ -z "$OPENROUTER_API_KEY" ]]; then
        echo -e "${RED}✗ OPENROUTER_API_KEY not set${NC}"
        echo "Please set OPENROUTER_API_KEY in .env or export it:"
        echo "  export OPENROUTER_API_KEY='your-api-key'"
        exit 1
    fi
    echo -e "${GREEN}✓ OPENROUTER_API_KEY found${NC}"
fi

echo ""
echo -e "${BLUE}Running tests in mode: ${YELLOW}$MODE${NC}"
echo ""

case "$MODE" in
    fast)
        echo -e "${BLUE}Running fast unit tests...${NC}"
        pytest -m fast -v
        ;;
    e2e)
        echo -e "${BLUE}Running e2e integration tests (this may take several minutes)...${NC}"
        pytest -m e2e -v --tb=short
        ;;
    all)
        echo -e "${BLUE}Running all tests...${NC}"
        pytest -v
        ;;
    coverage)
        echo -e "${BLUE}Running tests with coverage report...${NC}"
        pytest -v --cov=app --cov-report=html --cov-report=term-missing
        echo ""
        echo -e "${GREEN}✓ Coverage report generated in htmlcov/index.html${NC}"
        ;;
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo "Usage: ./test.sh [fast|e2e|all|coverage]"
        exit 1
        ;;
esac

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ Some tests failed${NC}"
    echo -e "${RED}========================================${NC}"
fi

exit $EXIT_CODE
