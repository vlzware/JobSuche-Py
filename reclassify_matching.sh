#!/bin/bash
# Simple wrapper to re-classify existing jobs with matching workflow
# Usage: ./reclassify_matching.sh [options] [session_directory]
#
# Options:
#   --cv FILE                Path to CV file
#   --perfect-job-description TEXT_OR_FILE   Perfect job description (text or file path)
#
# At least one of --cv or --perfect-job-description is required.
# Providing both is recommended for best results!

set -e

CV_FILE=""
PERFECT_JOB_DESC=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cv)
            CV_FILE="$2"
            shift 2
            ;;
        --perfect-job-description)
            PERFECT_JOB_DESC="$2"
            shift 2
            ;;
        *)
            # Assume it's the session directory
            SESSION_DIR="$1"
            shift
            ;;
    esac
done

# Validate at least one input is provided
if [ -z "$CV_FILE" ] && [ -z "$PERFECT_JOB_DESC" ]; then
    echo "Error: At least one of --cv or --perfect-job-description is required"
    echo ""
    echo "Usage: ./reclassify_matching.sh [options] [session_directory]"
    echo ""
    echo "Options:"
    echo "  --cv FILE                          Path to CV file"
    echo "  --perfect-job-description TEXT     Perfect job description (text or file path)"
    echo ""
    echo "Examples:"
    echo "  # CV only"
    echo "  ./reclassify_matching.sh --cv cv.md"
    echo ""
    echo "  # Perfect job description only"
    echo "  ./reclassify_matching.sh --perfect-job-description perfect_job.txt"
    echo ""
    echo "  # Both (recommended for best results!)"
    echo "  ./reclassify_matching.sh --cv cv.md --perfect-job-description perfect_job.txt"
    echo ""
    echo "If no session directory is provided, the most recent one will be used."
    exit 1
fi

# Validate CV file exists if provided
if [ -n "$CV_FILE" ] && [ ! -f "$CV_FILE" ]; then
    echo "Error: CV file not found: $CV_FILE"
    echo ""
    echo "Looking for CV files:"
    ls -1 cv.* 2>/dev/null || echo "  (none found with pattern cv.*)"
    exit 1
fi

# Function to get the latest session directory
get_latest_session() {
    ls -1dt data/searches/2* 2>/dev/null | head -1
}

# Get session directory or use latest
if [ -z "$SESSION_DIR" ]; then
    SESSION_DIR="$(get_latest_session)"
fi

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
echo "Re-classifying jobs (Matching workflow)"
echo "================================================"
echo "Using session: $SESSION_DIR"
[ -n "$CV_FILE" ] && echo "Using CV: $CV_FILE"
[ -n "$PERFECT_JOB_DESC" ] && echo "Using perfect job description: ${PERFECT_JOB_DESC:0:50}..."
[ -n "$CV_FILE" ] && [ -n "$PERFECT_JOB_DESC" ] && echo ""
[ -n "$CV_FILE" ] && [ -n "$PERFECT_JOB_DESC" ] && echo "✓ Using BOTH inputs for best matching results!"
echo ""

# Build command with appropriate flags
CMD="python main.py --classify-only --workflow matching --input \"$SESSION_DIR\""
[ -n "$CV_FILE" ] && CMD="$CMD --cv \"$CV_FILE\""
[ -n "$PERFECT_JOB_DESC" ] && CMD="$CMD --perfect-job-description \"$PERFECT_JOB_DESC\""

eval $CMD

echo ""
echo "Done! Results in:"
echo "  $(ls -1t data/searches/*/analysis_report.txt | head -1)"
