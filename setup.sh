#!/bin/bash
# TIMEPOINT Flash - One-Command Setup Script
# Sets up everything needed to run tp demo

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}🎬 TIMEPOINT FLASH - Setup${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check Python version
echo -e "${BLUE}[1/6] Checking Python version...${NC}"
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}✗ Python not found${NC}"
    echo "Please install Python 3.11 or higher"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo -e "${RED}✗ Python $PYTHON_VERSION detected${NC}"
    echo "TIMEPOINT Flash requires Python 3.11 or higher"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}[2/6] Installing dependencies...${NC}"

if command -v uv &> /dev/null; then
    echo "Using uv for fast installation..."
    uv sync
    echo -e "${GREEN}✓ Dependencies installed with uv${NC}"
elif command -v pip &> /dev/null || command -v pip3 &> /dev/null; then
    echo "Using pip for installation..."
    if command -v pip3 &> /dev/null; then
        pip3 install -e .
    else
        pip install -e .
    fi
    echo -e "${GREEN}✓ Dependencies installed with pip${NC}"
else
    echo -e "${RED}✗ Neither uv nor pip found${NC}"
    echo "Please install pip or uv to continue"
    exit 1
fi
echo ""

# Setup .env file
echo -e "${BLUE}[3/6] Configuring environment...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env from template${NC}"
    else
        echo -e "${YELLOW}⚠ No .env.example found, creating minimal .env${NC}"
        cat > .env << EOF
# Minimal configuration for TIMEPOINT Flash
DATABASE_URL=sqlite:///./timepoint_local.db
OPENROUTER_API_KEY=your_key_here
EOF
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Check for API key
if grep -q "your_key_here" .env || ! grep -q "OPENROUTER_API_KEY" .env; then
    echo ""
    echo -e "${YELLOW}⚠ OPENROUTER_API_KEY not configured${NC}"
    echo ""
    echo "To use TIMEPOINT Flash, you need an OpenRouter API key."
    echo "Get a free key at: https://openrouter.ai/keys"
    echo ""
    read -p "Enter your OpenRouter API key (or press Enter to skip): " API_KEY

    if [ ! -z "$API_KEY" ]; then
        # Update .env file
        if grep -q "OPENROUTER_API_KEY" .env; then
            # Replace existing line
            sed -i.bak "s/OPENROUTER_API_KEY=.*/OPENROUTER_API_KEY=$API_KEY/" .env
            rm -f .env.bak
        else
            # Add new line
            echo "OPENROUTER_API_KEY=$API_KEY" >> .env
        fi
        echo -e "${GREEN}✓ API key saved to .env${NC}"
    else
        echo -e "${YELLOW}⚠ Skipped API key setup${NC}"
        echo "You can add it later by editing .env file"
    fi
fi
echo ""

# Ensure tp script exists and is executable
echo -e "${BLUE}[4/6] Setting up CLI tool...${NC}"

if [ ! -f "tp" ]; then
    echo -e "${YELLOW}⚠ tp script not found, creating it...${NC}"
    cat > tp << 'EOF'
#!/bin/bash
# TIMEPOINT Flash CLI Wrapper
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$VIRTUAL_ENV" ] && [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
exec python3 -m app.cli "$@"
EOF
fi

chmod +x tp
echo -e "${GREEN}✓ CLI tool ready${NC}"
echo ""

# Validate installation
echo -e "${BLUE}[5/6] Validating installation...${NC}"

# Test if we can import app
if ./tp --version &> /dev/null; then
    echo -e "${GREEN}✓ CLI working correctly${NC}"
else
    echo -e "${RED}✗ CLI validation failed${NC}"
    echo "There may be issues with the installation"
    exit 1
fi

# Check if API key is set
if grep -q "your_key_here" .env 2>/dev/null || [ ! -f ".env" ]; then
    HAS_API_KEY=false
else
    source .env
    if [ ! -z "$OPENROUTER_API_KEY" ] && [ "$OPENROUTER_API_KEY" != "your_key_here" ]; then
        HAS_API_KEY=true
    else
        HAS_API_KEY=false
    fi
fi

echo ""

# Print success message
echo -e "${BLUE}[6/6] Setup complete!${NC}"
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✨ TIMEPOINT Flash is ready!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

if [ "$HAS_API_KEY" = true ]; then
    echo -e "${GREEN}✓ OpenRouter API key configured${NC}"
    echo ""
    echo "Try the demo:"
    echo -e "  ${BLUE}./tp demo${NC}"
    echo ""
    echo "Or generate a custom scene:"
    echo -e "  ${BLUE}./tp generate \"Medieval marketplace, London 1250\"${NC}"
else
    echo -e "${YELLOW}⚠ OpenRouter API key not configured${NC}"
    echo ""
    echo "To use TIMEPOINT Flash:"
    echo "1. Get a free API key from: https://openrouter.ai/keys"
    echo "2. Add it to .env file:"
    echo -e "   ${BLUE}echo \"OPENROUTER_API_KEY=your_key\" >> .env${NC}"
    echo "3. Run the demo:"
    echo -e "   ${BLUE}./tp demo${NC}"
fi

echo ""
echo "Other commands:"
echo -e "  ${BLUE}./tp list${NC}                    - List all timepoints"
echo -e "  ${BLUE}./tp serve --open-browser${NC}    - Start gallery"
echo -e "  ${BLUE}./test.sh fast${NC}               - Run tests"
echo ""
echo "Documentation:"
echo "  README.md      - Full documentation"
echo "  QUICKSTART.md  - Quick start guide"
echo "  AGENTS.md      - AI agent architecture"
echo ""
echo -e "${BLUE}================================================${NC}"
