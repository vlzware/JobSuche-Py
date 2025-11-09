"""
API client for the German Arbeitsagentur job search API
https://github.com/bundesAPI/jobsuche-api
"""

from typing import TYPE_CHECKING, Optional

import requests

from .config import Config, config
from .http_client import HttpClient, default_http_client
from .logging_config import get_module_logger

logger = get_module_logger("api_client")

if TYPE_CHECKING:
    from .session import SearchSession


def search_jobs(
    was: str,
    wo: str,
    size: int | None = None,
    max_pages: int | None = None,
    umkreis: int | None = None,
    arbeitszeit: str = "",
    zeitarbeit: bool = False,
    exclude_weiterbildung: bool = True,
    session: Optional["SearchSession"] = None,
    http_client: HttpClient | None = None,
    config_obj: Config | None = None,
) -> list[dict]:
    """
    Search for jobs on Arbeitsagentur

    Args:
        was: Job description/title (e.g., "Softwareentwickler")
        wo: Location (e.g., "Bergisch Gladbach")
        size: Number of results per page (max 100). Defaults to config value.
        max_pages: Maximum number of pages to fetch. Defaults to config value.
        umkreis: Radius in kilometers. Defaults to config value.
        arbeitszeit: Working time filter (vz=fulltime, tz=parttime, ho=homeoffice, snw=nightshift, or empty for all)
        zeitarbeit: Include temporary work agencies
        exclude_weiterbildung: Exclude jobs marked as Weiterbildung/Ausbildung (default: True)
        session: Optional SearchSession to save raw API responses for debugging
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        List of all job listings
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    # Load defaults from config if not provided
    if size is None:
        size = config_obj.get("search.defaults.page_size", 100)
    if max_pages is None:
        max_pages = config_obj.get("search.defaults.max_pages", 1)
    if umkreis is None:
        umkreis = config_obj.get("search.defaults.radius_km", 25)

    base_url = config_obj.get("api.arbeitsagentur.base_url")

    headers = {
        "User-Agent": config_obj.get("api.arbeitsagentur.headers.user_agent"),
        "Host": config_obj.get("api.arbeitsagentur.headers.host"),
        "X-API-Key": config_obj.get("api.arbeitsagentur.headers.api_key"),
        "Connection": "keep-alive",
    }

    all_jobs = []
    raw_responses = []  # Collect raw responses for debugging

    for page in range(1, max_pages + 1):
        params = [
            ("angebotsart", config_obj.get("api.arbeitsagentur.params.angebotsart")),
            ("page", page),
            ("pav", config_obj.get("api.arbeitsagentur.params.pav")),  # Personalvermittlung
            ("size", size),
            ("umkreis", umkreis),
            ("was", was),
            ("wo", wo),
            ("zeitarbeit", zeitarbeit),
        ]

        # Only add arbeitszeit if specified
        if arbeitszeit:
            params.append(("arbeitszeit", arbeitszeit))

        try:
            response = http_client.get(
                f"{base_url}/pc/v4/jobs",
                params=params,
                headers=headers,
                timeout=config_obj.get("api.timeouts.api_request", 30),
            )

            if response.status_code == 200:
                data = response.json()

                # Save raw response for debugging
                raw_responses.append({"page": page, "response": data})

                jobs = data.get("stellenangebote", [])

                if not jobs:
                    break  # No more results

                # Filter out Weiterbildung/Ausbildung jobs if requested
                if exclude_weiterbildung:
                    exclude_keywords = config_obj.get(
                        "search.filters.exclude_keywords", ["weiterbildung", "ausbildung"]
                    )
                    jobs = [
                        job
                        for job in jobs
                        if not any(
                            keyword in job.get("beruf", "").lower() for keyword in exclude_keywords
                        )
                    ]

                all_jobs.extend(jobs)

                # Check if we've fetched all available results
                total_results = int(data.get("maxErgebnisse", "0"))
                if len(all_jobs) >= total_results:
                    break

            else:
                logger.error(f"API request failed on page {page}: HTTP {response.status_code}")
                logger.error(
                    f"Returning partial results: {len(all_jobs)} jobs from {page - 1} page(s)"
                )
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching page {page}: {e}")
            logger.error(f"Returning partial results: {len(all_jobs)} jobs from {page - 1} page(s)")
            break

    # Save raw API responses if session is provided
    if session and raw_responses:
        session.save_raw_api_response(
            {
                "search_params": {
                    "was": was,
                    "wo": wo,
                    "umkreis": umkreis,
                    "size": size,
                    "max_pages": max_pages,
                    "arbeitszeit": arbeitszeit,
                    "zeitarbeit": zeitarbeit,
                    "exclude_weiterbildung": exclude_weiterbildung,
                },
                "pages": raw_responses,
                "total_jobs_found": len(all_jobs),
            }
        )

    return all_jobs


def simplify_job_data(jobs: list[dict]) -> list[dict]:
    """
    Extract only relevant fields from job data

    Args:
        jobs: List of job listings from API

    Returns:
        Simplified job data with titel, ort, arbeitgeber
    """
    simplified = []

    for job in jobs:
        # Extract location
        arbeitsort = job.get("arbeitsort", {})
        ort = arbeitsort.get("ort", "") if isinstance(arbeitsort, dict) else ""

        simplified.append(
            {
                "titel": job.get("beruf", ""),
                "ort": ort,
                "arbeitgeber": job.get("arbeitgeber", ""),
                "refnr": job.get("refnr"),
                "externeUrl": job.get("externeUrl"),
            }
        )

    return simplified
