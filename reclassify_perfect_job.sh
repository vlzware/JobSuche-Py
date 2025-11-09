#!/bin/bash
# Simple wrapper to re-classify existing jobs with perfect-job workflow
# Usage: ./reclassify_perfect_job.sh "Category Name" "description_file.txt or direct text" [session_directory]

set -e

if [ $# -lt 2 ]; then
    echo "Usage: ./reclassify_perfect_job.sh \"Category Name\" \"description_file.txt or direct text\" [session_directory]"
    echo ""
    echo "Examples:"
    echo "  # Using a file (recommended for multi-paragraph descriptions)"
    echo "  ./reclassify_perfect_job.sh \"My Ideal Role\" perfect_job_description.txt"
    echo ""
    echo "  # Using direct text (for simple descriptions)"
    echo "  ./reclassify_perfect_job.sh \"My Ideal Role\" \"Backend with Python, Docker, AWS, remote work\""
    echo ""
    echo "If no session directory is provided, the most recent one will be used."
    exit 1
fi

CATEGORY="$1"
DESCRIPTION="$2"

# Function to get the latest session directory
get_latest_session() {
    ls -1dt data/searches/2* 2>/dev/null | head -1
}

# Get session directory from third argument or use latest
SESSION_DIR="${3:-$(get_latest_session)}"

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
echo "Re-classifying jobs (perfect-job workflow)"
echo "================================================"
echo "Using session: $SESSION_DIR"
echo "Category: $CATEGORY"
echo ""

python main.py --classify-only --workflow perfect-job \
    --input "$SESSION_DIR" \
    --perfect-job-category "$CATEGORY" \
    --perfect-job-description "$DESCRIPTION"

echo ""
echo "Done! Results in:"
echo "  $(ls -1t data/searches/*/analysis_report.txt | head -1)"
