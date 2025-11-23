"""
Job description classifier using OpenRouter LLM API
Automatically categorizes job listings into predefined categories
"""

import json
import os
import re
from typing import TYPE_CHECKING, Optional

from .config import Config, config
from .exceptions import (
    EmptyJobContentError,
    LLMDataIntegrityError,
    LLMResponseError,
    TruncationError,
)
from .http_client import HttpClient, default_http_client
from .logging_config import get_module_logger

logger = get_module_logger("classifier")

if TYPE_CHECKING:
    from .session import SearchSession


def get_fallback_category(categories: list[str]) -> str:
    """
    Determine the appropriate fallback category based on the categories list.

    For CV/description matching workflow, returns "Poor Match" if available,
    otherwise falls back to the last category in the list.

    Args:
        categories: List of category names to classify into

    Returns:
        The fallback category name to use when no other categories match
    """
    if not categories:
        return "Poor Match"  # Default fallback

    # For matching workflow, use "Poor Match" as fallback
    if "Poor Match" in categories:
        return "Poor Match"
    else:
        # Use last category as fallback (convention)
        return categories[-1]


def build_category_guidance(
    categories: list[str], category_definitions: dict[str, str] | None = None
) -> str:
    """
    Build the category guidance section for classification prompts.

    Args:
        categories: List of category names to classify into
        category_definitions: Optional dict of category -> description mappings

    Returns:
        String with category-specific guidance, or empty string if no definitions
    """
    if not category_definitions:
        return ""

    guidance_parts = []
    for category in categories:
        if category in category_definitions:
            guidance_parts.append(f"IMPORTANT: {category_definitions[category]}")

    if not guidance_parts:
        return ""

    return "\n\n" + "\n\n".join(guidance_parts)


def classify_job_description(
    job_text: str,
    categories: list[str],
    api_key: str,
    model: str | None = None,
    category_definitions: dict[str, str] | None = None,
    http_client: HttpClient | None = None,
    config_obj: Config | None = None,
) -> list[str]:
    """
    Classify a single job description into one or more categories using OpenRouter

    Args:
        job_text: The job description text to classify
        categories: List of category names to classify into
        api_key: OpenRouter API key
        model: Model to use (defaults to value from llm_config.yaml)
        category_definitions: Optional dict of category -> description mappings
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        List of matching categories
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    if model is None:
        model = config_obj.get_required("llm.models.default")

    # Determine the appropriate fallback category for this workflow
    fallback_category = get_fallback_category(categories)

    # Create the prompt for classification
    categories_str = ", ".join(f'"{cat}"' for cat in categories)
    guidance = build_category_guidance(categories, category_definitions)

    max_chars = config_obj.get_required("processing.limits.job_text_single_job")

    prompt = f"""Analyze the following German job description and identify which of these categories apply:
{categories_str}
{guidance}
A job can belong to multiple categories. Return ONLY a JSON array of the matching categories.
If none of the specific categories apply, return ["{fallback_category}"].

Job Description:
{job_text[:max_chars]}

Return format example: ["Java", "Agile Projektentwicklung"]
"""

    try:
        # Import locally to avoid circular dependency
        from .llm.openrouter_client import OpenRouterClient

        # Use unified OpenRouter client
        client = OpenRouterClient(api_key=api_key, http_client=http_client, config_obj=config_obj)
        content, _full_response = client.complete(
            prompt=prompt,
            model=model,
            temperature=config_obj.get_required("llm.inference.temperature"),
            timeout=config_obj.get("api.timeouts.classification", 30),
            session=None,  # Single job classification doesn't use session
        )

        # Parse the JSON response - strict parsing, no silent fallbacks
        try:
            # Try to extract JSON array from the response
            # Some models might add explanation text, so we need to be flexible
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1

            if start_idx == -1 or end_idx <= start_idx:
                error_msg = (
                    f"LLM response missing JSON array brackets!\n"
                    f'Expected format: ["Category1", "Category2"]\n'
                    f"Got: {content[:200]}"
                )
                logger.error(error_msg)
                raise LLMResponseError(error_msg, raw_response=content)

            json_str = content[start_idx:end_idx]
            matched_categories = json.loads(json_str)

            # Validate that returned categories are in our list
            valid_categories = [cat for cat in matched_categories if cat in categories]
            invalid_categories = [cat for cat in matched_categories if cat not in categories]

            # Fail on invalid categories - no silent errors!
            if invalid_categories:
                error_msg = (
                    f"LLM returned invalid categories!\n"
                    f"Expected categories: {categories}\n"
                    f"LLM returned: {matched_categories}\n"
                    f"Invalid categories: {invalid_categories}\n"
                    f"This indicates the LLM failed to follow instructions."
                )
                logger.error(error_msg)
                raise LLMDataIntegrityError(
                    error_msg,
                    expected_count=len(categories),
                    actual_count=len(matched_categories),
                )

            return valid_categories

        except json.JSONDecodeError as e:
            error_msg = (
                f"Failed to parse LLM response as JSON!\n"
                f"JSON error: {e}\n"
                f"Attempted to parse: {json_str[:200]}\n"
                f"Full response: {content[:200]}"
            )
            logger.error(error_msg)
            raise LLMResponseError(error_msg, raw_response=content) from e

    except Exception as e:
        # Re-raise exceptions instead of masking with "Andere"
        logger.error(f"Error classifying job: {e}")
        raise


def classify_jobs(
    jobs: list[dict],
    categories: list[str],
    api_key: str | None = None,
    model: str | None = None,
    verbose: bool = True,
    category_definitions: dict[str, str] | None = None,
    http_client: HttpClient | None = None,
    config_obj: Config | None = None,
) -> list[dict]:
    """
    Classify multiple job descriptions

    Args:
        jobs: List of jobs with 'text' field
        categories: List of category names (uses config if None, falls back to defaults)
        api_key: OpenRouter API key (reads from OPENROUTER_API_KEY env var if None)
        model: Model to use for classification (defaults to value from llm_config.yaml)
        verbose: Print progress messages
        category_definitions: Optional dict of category -> description mappings
                             (loaded from categories.yaml if None)
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        List of jobs with added 'categories' field
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    if model is None:
        model = config_obj.get_required("llm.models.default")

    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenRouter API key not provided. "
                "Set OPENROUTER_API_KEY environment variable or pass api_key parameter."
            )

    classified_jobs = []
    max_chars = config_obj.get_required("processing.limits.job_text_single_job")

    for idx, job in enumerate(jobs, 1):
        logger.info(f"Classifying job {idx}/{len(jobs)}: {job.get('titel', 'N/A')}")

        job_text = job.get("text", "")
        original_len = len(job_text)
        was_truncated = original_len > max_chars

        # Fail on truncation - no silent errors!
        if was_truncated:
            job_id = job.get("refnr", "N/A")
            logger.error(
                f"      ❌ Job [{job_id}] text truncated: {original_len:,} → {max_chars:,} chars"
            )
            raise TruncationError(
                job_id=str(job_id), original_length=original_len, truncated_length=max_chars
            )

        if not job_text:
            job_id = job.get("refnr", "N/A")
            error_msg = (
                f"Job has no text content!\n"
                f"Job title: {job.get('titel', 'N/A')}\n"
                f"Job ID: {job_id}\n"
                f"This indicates a data quality issue (extraction failed or job has no description).\n"
                f"Cannot classify jobs without text content."
            )
            logger.error(error_msg)
            raise EmptyJobContentError(error_msg, job_id=str(job_id))

        matched_categories = classify_job_description(
            job_text=job_text,
            categories=categories,
            api_key=api_key,
            model=model,
            category_definitions=category_definitions,
            http_client=http_client,
            config_obj=config_obj,
        )

        logger.info(f"  ✓ Categories: {', '.join(matched_categories)}")

        job_copy = job.copy()
        job_copy["categories"] = matched_categories
        classified_jobs.append(job_copy)

    return classified_jobs


def classify_jobs_batch(
    jobs: list[dict],
    categories: list[str],
    api_key: str | None = None,
    model: str | None = None,
    batch_size: int = 5,
    verbose: bool = True,
    extra_api_params: dict | None = None,
    session: Optional["SearchSession"] = None,
    category_definitions: dict[str, str] | None = None,
    http_client: HttpClient | None = None,
    config_obj: Config | None = None,
) -> list[dict]:
    """
    Classify jobs in batches - sends multiple jobs per request

    Args:
        jobs: List of jobs with 'text' field
        categories: List of category names (uses config if None, falls back to defaults)
        api_key: OpenRouter API key
        model: Model to use (defaults to value from llm_config.yaml)
        batch_size: Number of jobs to classify per API call
        verbose: Print progress
        extra_api_params: Additional parameters (e.g., {"reasoning": {"effort": "high"}})
        session: SearchSession to save LLM requests/responses
        category_definitions: Optional dict of category -> description mappings
                             (loaded from categories.yaml if None)
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        List of jobs with added 'categories' field
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    if model is None:
        model = config_obj.get_required("llm.models.default")

    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key required")

    classified_jobs = []

    # Determine the appropriate fallback category for this workflow
    fallback_category = get_fallback_category(categories)

    # Calculate total batches for progress tracking
    num_batches = (len(jobs) + batch_size - 1) // batch_size

    # Process in batches
    for batch_start in range(0, len(jobs), batch_size):
        batch = jobs[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1

        logger.info(f"Processing batch {batch_num}/{num_batches} ({len(batch)} jobs)")

        # Build prompt with multiple jobs using ID-based markdown format
        categories_str = ", ".join(f'"{cat}"' for cat in categories)
        guidance = build_category_guidance(categories, category_definitions)

        max_chars_batch = config_obj.get_required("processing.limits.job_text_batch")
        jobs_text = ""

        for idx, job in enumerate(batch):
            job_id = f"JOB_{idx:03d}"
            text = job.get("text", "")
            original_len = len(text)

            # Fail on truncation - no silent errors!
            if original_len > max_chars_batch:
                ref_nr = job.get("refnr", "N/A")
                logger.error(
                    f"❌ Job [{ref_nr}] would be truncated: "
                    f"{original_len:,} → {max_chars_batch:,} chars"
                )
                raise TruncationError(
                    job_id=str(ref_nr),
                    original_length=original_len,
                    truncated_length=max_chars_batch,
                )

            jobs_text += f"\n[{job_id}] {job.get('titel', 'N/A')}\n"
            jobs_text += text + "\n"

        prompt = f"""Classify these German job descriptions into categories: {categories_str}
{guidance}
Jobs can belong to multiple categories. If none apply, use "{fallback_category}".

{jobs_text}

IMPORTANT: Return ONE LINE per job in this exact format:
[JOB_000] → Category1, Category2
[JOB_001] → Category1
[JOB_002] → {fallback_category}

Return ONLY the lines with job IDs and categories, nothing else.
"""

        try:
            # Import locally to avoid circular dependency
            from .llm.openrouter_client import OpenRouterClient

            # Use unified OpenRouter client
            client = OpenRouterClient(
                api_key=api_key, http_client=http_client, config_obj=config_obj
            )
            batch_info = f"Batch {batch_start // batch_size + 1} (Model: {model})"

            content, _full_response = client.complete(
                prompt=prompt,
                model=model,
                temperature=config_obj.get_required("llm.inference.temperature"),
                extra_params=extra_api_params,
                timeout=config_obj.get("api.timeouts.batch_classification", 60),
                session=session,
                interaction_label=batch_info,
            )

            # Parse markdown-based results line by line
            batch_results = {}
            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Match pattern: [JOB_XXX] → Category1, Category2
                match = re.match(r"\[JOB_(\d+)\]\s*(?:→|->)\s*(.+)", line)
                if match:
                    job_idx = int(match.group(1))
                    cats_str = match.group(2).strip()
                    cats = [c.strip() for c in cats_str.split(",")]
                    # Validate categories
                    valid_cats = [cat for cat in cats if cat in categories]
                    invalid_cats = [cat for cat in cats if cat not in categories]

                    # Fail on invalid categories - no silent errors!
                    if invalid_cats:
                        error_msg = (
                            f"CRITICAL ERROR: LLM returned invalid categories in batch!\n"
                            f"  Job index: JOB_{job_idx:03d}\n"
                            f"  Expected categories: {categories}\n"
                            f"  LLM returned: {cats}\n"
                            f"  Invalid categories: {invalid_cats}\n"
                            f"  This indicates the LLM failed to follow instructions.\n"
                            f"  NO SILENT FAILURES - aborting batch to prevent data corruption!"
                        )
                        logger.error(error_msg)
                        raise LLMDataIntegrityError(
                            error_msg,
                            expected_count=len(categories),
                            actual_count=len(cats),
                        )

                    batch_results[job_idx] = valid_cats

            # Check if we got results for all jobs
            missing_jobs = [i for i in range(len(batch)) if i not in batch_results]

            if missing_jobs:
                error_msg = (
                    f"CRITICAL ERROR: LLM returned incomplete results!\n"
                    f"  Expected {len(batch)} jobs, got {len(batch_results)} results.\n"
                    f"  Missing job indices: {missing_jobs}\n"
                    f"  This indicates either:\n"
                    f"    1. LLM failed to process some jobs (potential queue scrambling!)\n"
                    f"    2. Response parsing failed\n"
                    f"    3. Context window exceeded\n"
                    f"  NO SILENT FAILURES - aborting to prevent data corruption!"
                )
                logger.error(error_msg)
                raise LLMDataIntegrityError(
                    error_msg,
                    expected_count=len(batch),
                    actual_count=len(batch_results),
                    missing_indices=missing_jobs,
                )

            # Assign results to jobs
            for idx, job in enumerate(batch):
                job_copy = job.copy()
                # Direct access - should never fail due to missing_jobs check above
                if idx not in batch_results:
                    raise AssertionError(
                        f"FATAL: Job index {idx} missing from batch_results despite passing "
                        f"missing_jobs check! This should never happen."
                    )
                job_copy["categories"] = batch_results[idx]
                classified_jobs.append(job_copy)

            # Save checkpoint after each successful batch
            if session:
                session.save_partial_results(classified_jobs[-len(batch) :])

                # Calculate completed and pending refnrs
                # IMPORTANT: Include ALL completed jobs (previous runs + current run)
                all_completed_jobs = session.load_partial_results()
                completed_refnrs = [job.get("refnr", "") for job in all_completed_jobs]
                pending_jobs = jobs[batch_start + batch_size :]
                pending_refnrs = [job.get("refnr", "") for job in pending_jobs]

                session.save_checkpoint(
                    completed_refnrs=completed_refnrs,
                    pending_refnrs=pending_refnrs,
                    current_batch=batch_num,
                    total_batches=num_batches,
                )
                logger.info(
                    f"✓ Checkpoint saved ({len(classified_jobs)}/{len(jobs)} jobs complete)"
                )

        except Exception as e:
            # Re-raise exception instead of masking with "Andere"
            logger.error(f"  Error in batch: {e}")
            raise

    # Delete checkpoint after successful completion
    if session:
        session.delete_checkpoint()
        logger.info("✓ Classification complete - checkpoint cleaned up")

    return classified_jobs


def classify_jobs_mega_batch(
    jobs: list[dict],
    categories: list[str],
    api_key: str | None = None,
    model: str | None = None,
    verbose: bool = True,
    extra_api_params: dict | None = None,
    session: Optional["SearchSession"] = None,
    category_definitions: dict[str, str] | None = None,
    http_client: HttpClient | None = None,
    config_obj: Config | None = None,
) -> list[dict]:
    """
    Classify ALL jobs in ONE request (uses large context models)

    This is the most efficient approach for 100+ jobs:
    - Single API call regardless of job count
    - Lowest cost per job
    - Fastest total time

    Args:
        jobs: List of jobs with 'text' field
        categories: List of category names (uses config if None, falls back to defaults)
        api_key: OpenRouter API key
        model: Model to use (defaults to value from llm_config.yaml)
        verbose: Print progress
        extra_api_params: Additional parameters for the API request (e.g., {"reasoning": {"effort": "high"}})
        session: SearchSession to save LLM requests/responses
        category_definitions: Optional dict of category -> description mappings
                             (loaded from categories.yaml if None)
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        List of jobs with added 'categories' field
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    if model is None:
        model = config_obj.get_required("llm.models.default")

    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key required")

    # Check if we need to split into multiple mega-batches to avoid context overflow
    max_jobs_per_batch = config_obj.get_required("processing.limits.max_jobs_per_mega_batch")

    if len(jobs) > max_jobs_per_batch:
        # Split into multiple mega-batches
        num_batches = (len(jobs) + max_jobs_per_batch - 1) // max_jobs_per_batch

        logger.info(f"Splitting {len(jobs)} jobs into {num_batches} mega-batches...")
        logger.info(f"  (~{max_jobs_per_batch} jobs per batch for safe context usage)")

        classified_jobs = []
        for i in range(0, len(jobs), max_jobs_per_batch):
            batch = jobs[i : i + max_jobs_per_batch]
            batch_num = (i // max_jobs_per_batch) + 1

            logger.info(f"{'=' * 60}")
            logger.info(f"Mega-batch {batch_num}/{num_batches}: {len(batch)} jobs")
            logger.info(f"{'=' * 60}")

            # Recursively call for each sub-batch (will not recurse again since batch <= max)
            batch_classified = classify_jobs_mega_batch(
                jobs=batch,
                categories=categories,
                api_key=api_key,
                model=model,
                verbose=verbose,
                extra_api_params=extra_api_params,
                session=session,
                category_definitions=category_definitions,
                http_client=http_client,
                config_obj=config_obj,
            )
            classified_jobs.extend(batch_classified)

            # Save checkpoint after each successful mega-batch
            if session:
                session.save_partial_results(batch_classified)

                # Calculate completed and pending refnrs
                # IMPORTANT: Include ALL completed jobs (previous runs + current run)
                all_completed_jobs = session.load_partial_results()
                completed_refnrs = [job.get("refnr", "") for job in all_completed_jobs]
                pending_jobs = jobs[(i + max_jobs_per_batch) :]
                pending_refnrs = [job.get("refnr", "") for job in pending_jobs]

                session.save_checkpoint(
                    completed_refnrs=completed_refnrs,
                    pending_refnrs=pending_refnrs,
                    current_batch=batch_num,
                    total_batches=num_batches,
                )
                logger.info(
                    f"✓ Checkpoint saved ({len(classified_jobs)}/{len(jobs)} jobs complete)"
                )

        logger.info(f"{'=' * 60}")
        logger.info(
            f"✓ Completed all {num_batches} mega-batches ({len(classified_jobs)} jobs total)"
        )
        logger.info(f"{'=' * 60}")

        # Delete checkpoint after successful completion
        if session:
            session.delete_checkpoint()
            logger.info("✓ Classification complete - checkpoint cleaned up")

        return classified_jobs

    # Single mega-batch (jobs <= max_jobs_per_batch)
    logger.info(f"Classifying {len(jobs)} jobs in ONE mega-batch request...")

    # Determine the appropriate fallback category for this workflow
    fallback_category = get_fallback_category(categories)

    categories_str = ", ".join(f'"{cat}"' for cat in categories)
    guidance = build_category_guidance(categories, category_definitions)

    max_chars_mega = config_obj.get_required("processing.limits.job_text_mega_batch")

    # Build mega-batch prompt with ALL jobs using ID-based markdown format
    jobs_text = ""

    for idx, job in enumerate(jobs):
        job_id = f"JOB_{idx:03d}"
        title = job.get("titel", "N/A")
        text = job.get("text", "")
        original_len = len(text)

        # Fail on truncation - no silent errors!
        if original_len > max_chars_mega:
            ref_nr = job.get("refnr", "N/A")
            logger.error(
                f"❌ Job [{ref_nr}] would be truncated: {original_len:,} → {max_chars_mega:,} chars"
            )
            raise TruncationError(
                job_id=str(ref_nr), original_length=original_len, truncated_length=max_chars_mega
            )

        jobs_text += f"\n[{job_id}] {title}\n{text}\n"

    prompt = f"""Classify these {len(jobs)} German job descriptions into categories.

Categories: {categories_str}
{guidance}
Jobs can belong to multiple categories. If none of the specific categories apply, use "{fallback_category}".

{jobs_text}

IMPORTANT: Return ONE LINE per job in this exact format:
[JOB_000] → Category1, Category2
[JOB_001] → Category1
[JOB_002] → {fallback_category}

Return ONLY the lines with job IDs and categories, nothing else.
"""

    try:
        # Import locally to avoid circular dependency
        from .llm.openrouter_client import OpenRouterClient

        # Use unified OpenRouter client
        client = OpenRouterClient(api_key=api_key, http_client=http_client, config_obj=config_obj)
        batch_info = f"MEGA-BATCH ({len(jobs)} jobs, Model: {model})"

        content, full_response = client.complete(
            prompt=prompt,
            model=model,
            temperature=config_obj.get_required("llm.inference.temperature"),
            extra_params=extra_api_params,
            timeout=config_obj.get("api.timeouts.mega_batch_classification", 120),
            session=session,
            interaction_label=batch_info,
        )

        # Parse markdown-based results line by line
        batch_results = {}
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Match pattern: [JOB_XXX] → Category1, Category2
            match = re.match(r"\[JOB_(\d+)\]\s*(?:→|->)\s*(.+)", line)
            if match:
                job_idx = int(match.group(1))
                cats_str = match.group(2).strip()
                cats = [c.strip() for c in cats_str.split(",")]
                # Validate categories
                valid_cats = [cat for cat in cats if cat in categories]
                invalid_cats = [cat for cat in cats if cat not in categories]

                # Fail on invalid categories - no silent errors!
                if invalid_cats:
                    error_msg = (
                        f"CRITICAL ERROR: LLM returned invalid categories in MEGA-BATCH!\n"
                        f"  Job index: JOB_{job_idx:03d}\n"
                        f"  Expected categories: {categories}\n"
                        f"  LLM returned: {cats}\n"
                        f"  Invalid categories: {invalid_cats}\n"
                        f"  This indicates the LLM failed to follow instructions.\n"
                        f"  NO SILENT FAILURES - aborting mega-batch to prevent data corruption!"
                    )
                    logger.error(error_msg)
                    raise LLMDataIntegrityError(
                        error_msg,
                        expected_count=len(categories),
                        actual_count=len(cats),
                    )

                batch_results[job_idx] = valid_cats

        # Check if we got results for all jobs
        missing_jobs = [i for i in range(len(jobs)) if i not in batch_results]

        if missing_jobs:
            error_msg = (
                f"CRITICAL ERROR: MEGA-BATCH returned incomplete results!\n"
                f"  Expected {len(jobs)} jobs, got {len(batch_results)} results.\n"
                f"  Missing job indices: {missing_jobs}\n"
                f"  This is a CATASTROPHIC failure - jobs may be misaligned!\n"
                f"  Possible causes:\n"
                f"    1. Context window exceeded (reduce max_jobs_per_mega_batch)\n"
                f"    2. LLM failed to process some jobs\n"
                f"    3. Response parsing error\n"
                f"  NO SILENT FAILURES - aborting to prevent data corruption!"
            )
            logger.error(error_msg)
            raise LLMDataIntegrityError(
                error_msg,
                expected_count=len(jobs),
                actual_count=len(batch_results),
                missing_indices=missing_jobs,
            )

        # Assign results to jobs
        classified_jobs = []
        for idx, job in enumerate(jobs):
            job_copy = job.copy()
            # Direct access - should never fail due to missing_jobs check above
            if idx not in batch_results:
                raise AssertionError(
                    f"FATAL: Job index {idx} missing from batch_results despite passing "
                    f"missing_jobs check! This should never happen."
                )
            job_copy["categories"] = batch_results[idx]
            classified_jobs.append(job_copy)

        # Print usage stats from full response
        usage = full_response.get("usage", {})
        tokens = usage.get("completion_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        total_tokens = prompt_tokens + tokens

        logger.info(f"  ✓ Classified {len(jobs)} jobs (got {len(batch_results)} valid results)")
        logger.info(
            f"  ✓ Token usage: {prompt_tokens:,} prompt + {tokens:,} completion = {total_tokens:,} total"
        )
        logger.info("  [i] View actual costs at: https://openrouter.ai/activity")

        return classified_jobs

    except Exception as e:
        # Re-raise exception instead of masking with "Andere"
        logger.error(f"Error during classification: {e}")
        raise
