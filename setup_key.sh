#!/bin/bash
# Activate venv and load API key into current session only (not saved anywhere)
# Usage: source setup_key.sh

# Activate virtual environment
source .venv/bin/activate

echo "Paste your OpenRouter API key (input will be hidden):"
read -s OPENROUTER_API_KEY

export OPENROUTER_API_KEY

echo ""
echo "✓ Virtual environment activated"
echo "✓ API key loaded into current session"
