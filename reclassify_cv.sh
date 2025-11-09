#!/bin/bash
# Simple wrapper to re-classify existing jobs with cv-based workflow
# Usage: ./reclassify_cv.sh [cv_file] [session_directory]

set -e

# Default CV file
DEFAULT_CV="cv.md"

# Get CV file from first argument or use default
CV_FILE="${1:-$DEFAULT_CV}"

if [ ! -f "$CV_FILE" ]; then
    echo "Error: CV file not found: $CV_FILE"
    echo ""
    echo "Usage: ./reclassify_cv.sh [cv_file] [session_directory]"
    echo ""
    echo "Looking for CV files:"
    ls -1 cv.* 2>/dev/null || echo "  (none found with pattern cv.*)"
    exit 1
fi

# Function to get the latest session directory
get_latest_session() {
    ls -1dt data/searches/2* 2>/dev/null | head -1
}

# Get session directory from second argument or use latest
SESSION_DIR="${2:-$(get_latest_session)}"

if [ -z "$SESSION_DIR" ]; then
    echo "Error: No session directory found"
    echo "Available sessions:"
    ls -1dt data/searches/2* 2>/dev/null | head -5 || echo "  (none found)"
    exit 1
fi

if [ ! -d "$SESSION_DIR" ]; then
    echo "Error: Session directory not found: $SESSION_DIR"
    exit 1
fi

echo "================================================"
echo "Re-classifying jobs (CV-based workflow)"
echo "================================================"
echo "Using session: $SESSION_DIR"
echo "Using CV: $CV_FILE"
echo ""

python main.py --classify-only --workflow cv-based \
    --input "$SESSION_DIR" \
    --cv "$CV_FILE"

echo ""
echo "Done! Results in:"
echo "  $(ls -1t data/searches/*/analysis_report.txt | head -1)"
