#!/usr/bin/env python3
"""
Disable a job in the database by clearing its text content and marking it as failed.
The job remains in the database but won't be included in classification workflows.

Usage:
    python disable_job.py <refnr> [reason]
    python disable_job.py 14092-234563-S
    python disable_job.py 14092-234563-S "Contains entire webpage instead of job description"
"""

import json
import sys
from pathlib import Path


def disable_job(
    refnr: str,
    reason: str = "Job description too large (likely scraped entire webpage)",
    database_path: str = "data/database/jobs.json",
) -> bool:
    """
    Disable a job by clearing its text and marking it as failed

    Args:
        refnr: The job reference number to disable
        reason: Reason for disabling (stored in error field)
        database_path: Path to the jobs database file

    Returns:
        True if job was disabled, False if not found
    """
    db_file = Path(database_path)

    if not db_file.exists():
        print(f"❌ Database not found: {database_path}")
        return False

    # Load database
    with open(db_file, encoding="utf-8") as f:
        data = json.load(f)

    jobs_dict = data.get("jobs", {})

    # Check if job exists
    if refnr not in jobs_dict:
        print(f"❌ Job [{refnr}] not found in database")
        print(f"   Total jobs in database: {len(jobs_dict)}")
        return False

    # Get job info
    job = jobs_dict[refnr]
    title = job.get("titel", "N/A")
    details = job.get("details", {})

    if not isinstance(details, dict):
        print(f"❌ Job [{refnr}] has no details field")
        return False

    original_text_len = len(details.get("text", ""))
    original_success = details.get("success", False)

    print(f"Disabling job [{refnr}]:")
    print(f"  Title: {title}")
    print(f"  Original text length: {original_text_len:,} chars")
    print(f"  Original success: {original_success}")
    print(f"  Reason: {reason}")
    print()

    # Disable the job
    details["text"] = reason
    details["success"] = False
    details["warning"] = "EXCESSIVE_CONTENT"
    details["error"] = reason
    details["text_length"] = len(reason)

    print(f"  New text: \"{details['text']}\"")
    print(f"  New success: {details['success']}")
    print(f"  New warning: {details['warning']}")

    # Save back to database
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print()
    print("✓ Job disabled successfully")
    print("  The job remains in the database but will be skipped during classification")
    print(f"  Total jobs in database: {len(jobs_dict)} (unchanged)")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python disable_job.py <refnr> [reason]")
        print()
        print("Examples:")
        print("  python disable_job.py 14092-234563-S")
        print('  python disable_job.py 14092-234563-S "Scraped entire webpage"')
        sys.exit(1)

    refnr = sys.argv[1]
    reason = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "Job description too large (likely scraped entire webpage)"
    )

    success = disable_job(refnr, reason)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
