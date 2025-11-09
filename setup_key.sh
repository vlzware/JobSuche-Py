#!/bin/bash
# Load API key into current session only (not saved anywhere)
# Usage: source setup_key.sh

echo "Paste your OpenRouter API key (input will be hidden):"
read -s OPENROUTER_API_KEY

export OPENROUTER_API_KEY

echo ""
echo "✓ Key loaded into current session"
