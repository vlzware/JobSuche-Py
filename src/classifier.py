"""
Job description classifier using OpenRouter LLM API
Automatically categorizes job listings into predefined categories
"""

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional, TypedDict

from .config import Config, config
from .exceptions import (
    EmptyJobContentError,
    LLMDataIntegrityError,
    LLMResponseError,
    OpenRouterAPIError,
)
from .http_client import HttpClient, default_http_client
from .logging_config import get_module_logger

logger = get_module_logger("classifier")

if TYPE_CHECKING:
    from .session import SearchSession


class TruncationInfo(TypedDict):
    """Information about a truncated job"""

    index: int
    job_id: str
    title: str
    original_length: int
    truncated_length: int
    loss: int


class TruncationStats(TypedDict):
    """Statistics about job truncations"""

    jobs_truncated: int
    total_jobs: int
    truncated_jobs: list[TruncationInfo]


try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


DEFAULT_CATEGORIES = [
    "Projektleitung",
    "Agile Projektentwicklung",
    "Java",
    "Python",
    "TypeScript",
    "C#/.NET",
    "Industrie",
    "Andere",
]


def load_category_config(config_path: str | None = None) -> tuple[list[str] | None, dict[str, str]]:
    """
    Load category configuration from YAML config file.

    Args:
        config_path: Path to the categories config file (defaults to value from paths_config.yaml)

    Returns:
        Tuple of (categories_list, definitions_dict):
        - categories_list: List of category names from config (None if not found/available)
        - definitions_dict: Dictionary mapping category names to descriptions
    """
    if not YAML_AVAILABLE:
        return (None, {})

    if config_path is None:
        config_path = config.get("paths.files.categories", "categories.yaml")

    config_file = Path(config_path)
    if not config_file.exists():
        return (None, {})

    try:
        with open(config_file, encoding="utf-8") as f:
            categories_config = yaml.safe_load(f)

        if not categories_config or "categories" not in categories_config:
            return (None, {})

        categories_list = []
        definitions = {}

        # Extract categories and their optional descriptions
        for cat_item in categories_config["categories"]:
            if isinstance(cat_item, dict) and "name" in cat_item:
                cat_name = cat_item["name"]
                categories_list.append(cat_name)

                # Extract description if present
                if cat_item.get("description"):
                    definitions[cat_name] = cat_item["description"].strip()

        return (categories_list if categories_list else None, definitions)
    except Exception as e:
        logger.warning(f"Could not load category config from {config_path}: {e}")
        return (None, {})


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
        model = config_obj.get("llm.models.default", "google/gemini-2.5-flash")

    # Create the prompt for classification
    categories_str = ", ".join(f'"{cat}"' for cat in categories)
    guidance = build_category_guidance(categories, category_definitions)

    max_chars = config_obj.get("processing.limits.job_text_single_job", 3000)

    prompt = f"""Analyze the following German job description and identify which of these categories apply:
{categories_str}
{guidance}
A job can belong to multiple categories. Return ONLY a JSON array of the matching categories.
If none of the specific categories apply, return ["Andere"].

Job Description:
{job_text[:max_chars]}

Return format example: ["Java", "Agile Projektentwicklung"]
"""

    try:
        response = http_client.post(
            url=config_obj.get("api.openrouter.endpoint"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": config_obj.get("llm.inference.temperature", 0.1),
            },
            timeout=config_obj.get("api.timeouts.classification", 30),
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]

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

                # If no valid categories, return "Andere" (legitimate case)
                if not valid_categories:
                    logger.warning(
                        f"LLM returned categories not in our list: {matched_categories}. "
                        f"Using 'Andere' as fallback."
                    )
                    return ["Andere"]

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
        else:
            # API error - raise exception instead of masking with "Andere"
            error_msg = f"OpenRouter API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise OpenRouterAPIError(
                error_msg, status_code=response.status_code, response_text=response.text
            )

    except Exception as e:
        # Re-raise exceptions instead of masking with "Andere"
        logger.error(f"Error classifying job: {e}")
        raise


def classify_jobs(
    jobs: list[dict],
    categories: list[str] | None = None,
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
        model = config_obj.get("llm.models.default", "google/gemini-2.5-flash")

    # Load category config (both list and definitions)
    config_categories, config_definitions = load_category_config()

    # Use provided categories, or config categories, or default categories
    if categories is None:
        categories = config_categories if config_categories else DEFAULT_CATEGORIES

    # Use provided definitions, or config definitions
    if category_definitions is None:
        category_definitions = config_definitions

    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenRouter API key not provided. "
                "Set OPENROUTER_API_KEY environment variable or pass api_key parameter."
            )

    classified_jobs = []
    max_chars = config_obj.get("processing.limits.job_text_single_job", 3000)

    for idx, job in enumerate(jobs, 1):
        logger.info(f"Classifying job {idx}/{len(jobs)}: {job.get('titel', 'N/A')}")

        job_text = job.get("text", "")
        original_len = len(job_text)
        was_truncated = original_len > max_chars

        # Warn about truncation
        if was_truncated:
            logger.warning(f"      ⚠️  Truncated: {original_len:,} → {max_chars:,} chars")

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

        # Add truncation metadata
        if was_truncated:
            job_copy["was_truncated"] = True
            job_copy["original_length"] = original_len
            job_copy["truncated_to"] = max_chars
        else:
            job_copy["was_truncated"] = False

        classified_jobs.append(job_copy)

    return classified_jobs


def classify_jobs_batch(
    jobs: list[dict],
    categories: list[str] | None = None,
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
        model = config_obj.get("llm.models.default", "google/gemini-2.5-flash")

    # Load category config (both list and definitions)
    config_categories, config_definitions = load_category_config()

    # Use provided categories, or config categories, or default categories
    if categories is None:
        categories = config_categories if config_categories else DEFAULT_CATEGORIES

    # Use provided definitions, or config definitions
    if category_definitions is None:
        category_definitions = config_definitions

    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key required")

    classified_jobs = []

    # Process in batches
    for batch_start in range(0, len(jobs), batch_size):
        batch = jobs[batch_start : batch_start + batch_size]

        logger.info(f"Processing batch {batch_start // batch_size + 1} ({len(batch)} jobs)")

        # Build prompt with multiple jobs using ID-based markdown format
        categories_str = ", ".join(f'"{cat}"' for cat in categories)
        guidance = build_category_guidance(categories, category_definitions)

        max_chars_batch = config_obj.get("processing.limits.job_text_batch", 1000)
        jobs_text = ""
        truncated_jobs = []

        for idx, job in enumerate(batch):
            job_id = f"JOB_{idx:03d}"
            text = job.get("text", "")
            original_len = len(text)

            # Track truncation
            if original_len > max_chars_batch:
                truncated_jobs.append(
                    {
                        "id": job_id,
                        "title": job.get("titel", "N/A"),
                        "original_len": original_len,
                        "truncated_to": max_chars_batch,
                    }
                )

            jobs_text += f"\n[{job_id}] {job.get('titel', 'N/A')}\n"
            jobs_text += text[:max_chars_batch] + "\n"

        # Warn about truncated jobs
        if truncated_jobs:
            logger.warning(f"  ⚠️  WARNING: {len(truncated_jobs)}/{len(batch)} jobs truncated:")
            for t in truncated_jobs[:3]:  # Show first 3
                logger.warning(
                    f"      • {t['title']}: {t['original_len']:,} → {t['truncated_to']:,} chars"
                )
            if len(truncated_jobs) > 3:
                logger.warning(f"      ... and {len(truncated_jobs) - 3} more")

        prompt = f"""Classify these German job descriptions into categories: {categories_str}
{guidance}
Jobs can belong to multiple categories. If none apply, use "Andere".

{jobs_text}

IMPORTANT: Return ONE LINE per job in this exact format:
[JOB_000] → Category1, Category2
[JOB_001] → Category1
[JOB_002] → Andere

Return ONLY the lines with job IDs and categories, nothing else.
"""

        try:
            # Build request payload
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": config_obj.get("llm.inference.temperature", 0.1),
            }

            # Merge any extra API parameters
            if extra_api_params:
                payload.update(extra_api_params)

            response = http_client.post(
                url=config_obj.get("api.openrouter.endpoint"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=config_obj.get("api.timeouts.batch_classification", 60),
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Save LLM interaction to session
                if session:
                    batch_info = f"Batch {batch_start // batch_size + 1} (Model: {model})"
                    session.append_llm_interaction(prompt, content, batch_info)

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

                        if not valid_cats:
                            logger.warning(
                                f"JOB_{job_idx:03d}: LLM returned invalid categories: {cats}. "
                                f"Using 'Andere' as fallback."
                            )
                            batch_results[job_idx] = ["Andere"]
                        else:
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

                # Create truncation lookup
                truncation_lookup = {t["id"]: t for t in truncated_jobs}

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

                    # Add truncation metadata
                    job_id = f"JOB_{idx:03d}"
                    if job_id in truncation_lookup:
                        t = truncation_lookup[job_id]
                        job_copy["was_truncated"] = True
                        job_copy["original_length"] = t["original_len"]
                        job_copy["truncated_to"] = t["truncated_to"]
                    else:
                        job_copy["was_truncated"] = False

                    classified_jobs.append(job_copy)

            else:
                # API error - raise exception instead of masking with "Andere"
                error_msg = f"API error: {response.status_code} - {response.text[:200]}"
                logger.error(f"  ✗ {error_msg}")
                raise OpenRouterAPIError(
                    error_msg, status_code=response.status_code, response_text=response.text
                )

        except Exception as e:
            # Re-raise exception instead of masking with "Andere"
            logger.error(f"  Error in batch: {e}")
            raise

    return classified_jobs


def classify_jobs_mega_batch(
    jobs: list[dict],
    categories: list[str] | None = None,
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
        model = config_obj.get("llm.models.default", "google/gemini-2.5-flash")

    # Load category config (both list and definitions)
    config_categories, config_definitions = load_category_config()

    # Use provided categories, or config categories, or default categories
    if categories is None:
        categories = config_categories if config_categories else DEFAULT_CATEGORIES

    # Use provided definitions, or config definitions
    if category_definitions is None:
        category_definitions = config_definitions

    if api_key is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key required")

    # Check if we need to split into multiple mega-batches to avoid context overflow
    max_jobs_per_batch = config_obj.get("processing.limits.max_jobs_per_mega_batch", 100)

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

        logger.info(f"{'=' * 60}")
        logger.info(
            f"✓ Completed all {num_batches} mega-batches ({len(classified_jobs)} jobs total)"
        )
        logger.info(f"{'=' * 60}")

        return classified_jobs

    # Single mega-batch (jobs <= max_jobs_per_batch)
    logger.info(f"Classifying {len(jobs)} jobs in ONE mega-batch request...")

    categories_str = ", ".join(f'"{cat}"' for cat in categories)
    guidance = build_category_guidance(categories, category_definitions)

    max_chars_mega = config_obj.get("processing.limits.job_text_mega_batch", 25000)

    # Truncation tracking
    truncation_stats: TruncationStats = {
        "jobs_truncated": 0,
        "total_jobs": len(jobs),
        "truncated_jobs": [],  # List of {index, title, original_len, truncated_len, loss}
    }

    # Build mega-batch prompt with ALL jobs using ID-based markdown format
    jobs_text = ""

    for idx, job in enumerate(jobs):
        job_id = f"JOB_{idx:03d}"
        title = job.get("titel", "N/A")
        text = job.get("text", "")
        original_len = len(text)

        # Track truncation
        if original_len > max_chars_mega:
            loss = original_len - max_chars_mega

            # Record truncation
            truncation_stats["jobs_truncated"] += 1
            truncation_stats["truncated_jobs"].append(
                {
                    "index": idx,
                    "job_id": job_id,
                    "title": title,
                    "original_length": original_len,
                    "truncated_length": max_chars_mega,
                    "loss": loss,
                }
            )

            # LOG WARNING
            logger.warning(
                f"🚨 TRUNCATION: Job {idx} '{title}' "
                f"truncated from {original_len:,} to {max_chars_mega:,} chars "
                f"(LOSS: {loss:,} chars) - classification may be unreliable!"
            )

        jobs_text += f"\n[{job_id}] {title}\n{text[:max_chars_mega]}\n"

    # DISPLAY TRUNCATION SUMMARY (if any)
    if truncation_stats["jobs_truncated"] > 0:
        logger.error("=" * 70)
        logger.error("⚠️  TRUNCATION WARNING ⚠️")
        logger.error(f"{truncation_stats['jobs_truncated']}/{len(jobs)} jobs had text truncated!")
        logger.error("These classifications may be UNRELIABLE due to incomplete data.")
        logger.error("=" * 70)

        for trunc_info in truncation_stats["truncated_jobs"][:5]:  # Show first 5
            logger.error(
                f"  - '{trunc_info['title']}': "
                f"{trunc_info['original_length']:,} → {trunc_info['truncated_length']:,} chars "
                f"(loss: {trunc_info['loss']:,})"
            )

        if truncation_stats["jobs_truncated"] > 5:
            logger.error(f"  ... and {truncation_stats['jobs_truncated'] - 5} more")

        logger.error("=" * 70)

    prompt = f"""Classify these {len(jobs)} German job descriptions into categories.

Categories: {categories_str}
{guidance}
Jobs can belong to multiple categories. If none of the specific categories apply, use "Andere".

{jobs_text}

IMPORTANT: Return ONE LINE per job in this exact format:
[JOB_000] → Category1, Category2
[JOB_001] → Category1
[JOB_002] → Andere

Return ONLY the lines with job IDs and categories, nothing else.
"""

    try:
        # Build request payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config_obj.get("llm.inference.temperature", 0.1),
        }

        # Merge any extra API parameters
        if extra_api_params:
            payload.update(extra_api_params)

        response = http_client.post(
            url=config_obj.get("api.openrouter.endpoint"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=config_obj.get("api.timeouts.mega_batch_classification", 120),
        )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Save LLM interaction to session
            if session:
                batch_info = f"MEGA-BATCH ({len(jobs)} jobs, Model: {model})"
                session.append_llm_interaction(prompt, content, batch_info)

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

                    if not valid_cats:
                        logger.warning(
                            f"JOB_{job_idx:03d}: LLM returned invalid categories: {cats}. "
                            f"Using 'Andere' as fallback."
                        )
                        batch_results[job_idx] = ["Andere"]
                    else:
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

            # Create truncation lookup
            truncation_lookup = {t["job_id"]: t for t in truncation_stats["truncated_jobs"]}

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

                # Add truncation metadata (standardized naming)
                job_id = f"JOB_{idx:03d}"
                if job_id in truncation_lookup:
                    t = truncation_lookup[job_id]
                    job_copy["_truncated"] = True
                    job_copy["_original_text_length"] = t["original_length"]
                    job_copy["_truncation_loss"] = t["loss"]
                    job_copy["_warning"] = "TRUNCATED"
                else:
                    job_copy["was_truncated"] = False

                classified_jobs.append(job_copy)

            # Print usage stats
            usage = result.get("usage", {})
            tokens = usage.get("completion_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens", 0)
            total_tokens = prompt_tokens + tokens

            logger.info(f"  ✓ Classified {len(jobs)} jobs (got {len(batch_results)} valid results)")
            logger.info(
                f"  ✓ Token usage: {prompt_tokens:,} prompt + {tokens:,} completion = {total_tokens:,} total"
            )
            logger.info("  [i] View actual costs at: https://openrouter.ai/activity")

            # Save truncation stats to session
            if session and truncation_stats["jobs_truncated"] > 0:
                truncation_file = session.debug_dir / "truncation_report.json"
                with open(truncation_file, "w", encoding="utf-8") as f:
                    json.dump(truncation_stats, f, ensure_ascii=False, indent=2)
                logger.info(f"Truncation report saved to {truncation_file}")

            return classified_jobs
        else:
            # API error - raise exception instead of masking with "Andere"
            error_msg = f"API error: {response.status_code} - {response.text[:200]}"
            logger.error(error_msg)
            raise OpenRouterAPIError(
                error_msg, status_code=response.status_code, response_text=response.text
            )

    except Exception as e:
        # Re-raise exception instead of masking with "Andere"
        logger.error(f"Error during classification: {e}")
        raise
