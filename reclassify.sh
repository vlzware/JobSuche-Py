#!/bin/bash
# Simple wrapper to re-classify existing jobs with multi-category workflow
# Usage: ./reclassify.sh [session_directory]

set -e

# Function to get the latest session directory
get_latest_session() {
    ls -1dt data/searches/2* 2>/dev/null | head -1
}

# Get session directory from argument or use latest
SESSION_DIR="${1:-$(get_latest_session)}"

if [ -z "$SESSION_DIR" ]; then
    echo "Error: No session directory found and none specified"
    echo "Usage: ./reclassify.sh [session_directory]"
    echo ""
    echo "Available sessions:"
    ls -1dt data/searches/2* 2>/dev/null | head -5 || echo "  (none found)"
    exit 1
fi

if [ ! -d "$SESSION_DIR" ]; then
    echo "Error: Session directory not found: $SESSION_DIR"
    exit 1
fi

echo "================================================"
echo "Re-classifying jobs (multi-category workflow)"
echo "================================================"
echo "Using session: $SESSION_DIR"
echo ""

python main.py --classify-only --workflow multi-category --input "$SESSION_DIR"

echo ""
echo "Done! Compare results:"
echo "  Original: $SESSION_DIR/analysis_report.txt"
echo "  New:      $(ls -1t data/searches/*/analysis_report.txt | head -1)"
