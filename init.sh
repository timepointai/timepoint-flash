#!/bin/bash
set -e

echo "🔧 Setting up TIMEPOINT Flash API..."

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "🚀 Installing dependencies..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. source .venv/bin/activate"
echo "  2. cp .env.example .env && edit with your API keys"
echo "  3. alembic upgrade head  # Run database migrations"
echo "  4. uvicorn app.main:app --reload  # Start the server"
echo ""
echo "API will be available at: http://localhost:5000"
echo "API docs at: http://localhost:5000/api/docs"
