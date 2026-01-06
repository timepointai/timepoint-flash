#!/bin/bash
# TIMEPOINT Flash Setup Script v2.3.0
# One-command setup for new users

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  _____ ___ __  __ _____ ____   ___ ___ _   _ _____ "
echo " |_   _|_ _|  \/  | ____|  _ \ / _ \_ _| \\ | |_   _|"
echo "   | |  | || |\\/| |  _| | |_) | | | | ||  \\| | | |  "
echo "   | |  | || |  | | |___|  __/| |_| | || |\\  | | |  "
echo "   |_| |___|_|  |_|_____|_|    \\___/___|_| \\_| |_|  "
echo -e "${NC}"
echo -e "${BOLD}TIMEPOINT Flash v2.3.0 Setup${NC}"
echo ""

# Track setup status
SETUP_OK=true

# Check Python version
echo -e "${BOLD}Checking prerequisites...${NC}"
echo ""

check_python() {
    if command -v python3.10 &> /dev/null; then
        PYTHON_CMD="python3.10"
        echo -e "${GREEN}[OK]${NC} Python 3.10 found"
        return 0
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
        echo -e "${GREEN}[OK]${NC} Python 3.11 found"
        return 0
    elif command -v python3.12 &> /dev/null; then
        PYTHON_CMD="python3.12"
        echo -e "${GREEN}[OK]${NC} Python 3.12 found"
        return 0
    elif command -v python3 &> /dev/null; then
        PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
        PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON_CMD="python3"
            echo -e "${GREEN}[OK]${NC} Python $PY_VERSION found"
            return 0
        fi
    fi

    echo -e "${RED}[FAIL]${NC} Python 3.10+ required"
    echo -e "       Install from: ${CYAN}https://www.python.org/downloads/${NC}"
    SETUP_OK=false
    return 1
}

check_pip() {
    if $PYTHON_CMD -m pip --version &> /dev/null; then
        echo -e "${GREEN}[OK]${NC} pip is available"
        return 0
    else
        echo -e "${RED}[FAIL]${NC} pip not found"
        echo -e "       Try: ${CYAN}$PYTHON_CMD -m ensurepip --upgrade${NC}"
        SETUP_OK=false
        return 1
    fi
}

check_env() {
    if [ -f .env ]; then
        echo -e "${GREEN}[OK]${NC} .env file exists"

        # Check if it has a real API key (not placeholder)
        if grep -q "your-google-api-key-here\|your-openrouter-api-key-here" .env 2>/dev/null; then
            echo -e "${YELLOW}[WARN]${NC} .env has placeholder API keys"
            echo -e "       Edit ${CYAN}.env${NC} and add your API key(s)"
            echo -e "       Get a key at: ${CYAN}https://aistudio.google.com${NC}"
        fi
        return 0
    elif [ -f .env.example ]; then
        echo -e "${YELLOW}[INFO]${NC} Creating .env from .env.example..."
        cp .env.example .env
        echo -e "${GREEN}[OK]${NC} .env file created"
        echo -e "${YELLOW}[ACTION]${NC} Edit ${CYAN}.env${NC} and add your API key(s)"
        echo -e "         Get a key at: ${CYAN}https://aistudio.google.com${NC}"
        return 0
    else
        echo -e "${RED}[FAIL]${NC} No .env.example found"
        SETUP_OK=false
        return 1
    fi
}

# Run checks
check_python
check_pip
echo ""

# Install dependencies
echo -e "${BOLD}Installing dependencies...${NC}"
echo ""

if [ "$SETUP_OK" = true ]; then
    echo -e "Running: ${CYAN}$PYTHON_CMD -m pip install -e .${NC}"
    echo ""

    if $PYTHON_CMD -m pip install -e . 2>&1 | while read line; do
        # Show progress but filter verbose output
        if [[ "$line" == *"Successfully"* ]] || [[ "$line" == *"Installing"* ]] || [[ "$line" == *"Requirement"* ]]; then
            echo -e "  ${GREEN}>${NC} $line"
        fi
    done; then
        echo ""
        echo -e "${GREEN}[OK]${NC} Dependencies installed"
    else
        echo -e "${RED}[FAIL]${NC} Installation failed"
        SETUP_OK=false
    fi
else
    echo -e "${RED}Skipping installation - fix prerequisites first${NC}"
fi

echo ""

# Check/create .env
check_env

echo ""

# Make scripts executable
echo -e "${BOLD}Setting up scripts...${NC}"
chmod +x run.sh demo.sh eval.sh setup.sh 2>/dev/null || true
chmod +x tests/test-demo.sh 2>/dev/null || true
echo -e "${GREEN}[OK]${NC} Scripts are executable"

echo ""

# Final summary
echo "========================================"
if [ "$SETUP_OK" = true ]; then
    echo -e "${GREEN}${BOLD}Setup Complete!${NC}"
    echo ""
    echo -e "Next steps:"
    echo -e "  1. ${CYAN}Edit .env${NC} with your API key (if not done)"
    echo -e "  2. ${CYAN}./run.sh -r${NC} to start the server"
    echo -e "  3. ${CYAN}./demo.sh${NC} to open the interactive demo"
    echo ""
    echo -e "Or try the quick start:"
    echo -e "  ${CYAN}./quickstart.sh${NC}"
    echo ""
    echo -e "API docs will be at: ${CYAN}http://localhost:8000/docs${NC}"
else
    echo -e "${RED}${BOLD}Setup Incomplete${NC}"
    echo ""
    echo -e "Please fix the issues above and run ${CYAN}./setup.sh${NC} again."
fi
echo "========================================"
