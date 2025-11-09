"""
Web scraper for fetching detailed job descriptions
Handles both internal Arbeitsagentur pages and external job listings
"""

import json
import re
import time
from typing import TYPE_CHECKING, Any, Optional, TypedDict
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .config import Config, config
from .http_client import HttpClient, default_http_client
from .logging_config import get_module_logger

logger = get_module_logger("scraper")

if TYPE_CHECKING:
    from .session import SearchSession


class FailedJobInfo(TypedDict):
    """Information about a failed job fetch"""

    index: int
    title: str
    url: str
    domain: str
    error: str
    warning: str


class ErrorStats(TypedDict):
    """Statistics about errors during job fetching"""

    total_jobs: int
    successful: int
    failed: int
    by_warning: dict[str, int]
    by_domain: dict[str, int]
    failed_jobs: list[FailedJobInfo]


class SourceStats(TypedDict):
    """Statistics for a specific source"""

    total: int
    successful: int
    failed: int
    avg_text_length: int


class DomainData(TypedDict):
    """Internal structure for domain data collection"""

    total: int
    successful: int
    failed: int
    text_lengths: list[int]
    warnings: dict[str, int]
    methods: dict[str, int]


class DomainSummary(TypedDict):
    """Summary statistics for a domain"""

    total: int
    successful: int
    failed: int
    success_rate: float
    avg_text_length: int
    min_text_length: int
    max_text_length: int
    primary_warning: str | None
    primary_method: str | None


class ProblemDomainInfo(TypedDict):
    """Information about a problem domain"""

    domain: str
    total: int
    success_rate: float
    primary_warning: str | None


class SuccessfulDomainInfo(TypedDict):
    """Information about a successful domain"""

    domain: str
    total: int
    success_rate: float
    primary_method: str | None


class ExtractionStats(TypedDict):
    """Comprehensive extraction statistics"""

    total_jobs: int
    by_source: dict[str, SourceStats]
    by_domain: dict[str, DomainSummary]
    by_extraction_method: dict[str, int]
    by_warning: dict[str, int]
    problem_domains: list[ProblemDomainInfo]
    successful_domains: list[SuccessfulDomainInfo]


# Minimum valid text length for job descriptions
MIN_VALID_TEXT_LENGTH = 1000


def clean_text(text: str | None) -> str:
    """Clean and normalize extracted text"""
    if not text:
        return ""

    # Remove extra whitespace and normalize line breaks
    text = re.sub(r"\s+", " ", text.strip())
    # Remove multiple consecutive line breaks
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text


def extract_json_ld(soup: BeautifulSoup) -> str | None:
    """
    Extract job description from JSON-LD structured data

    Many job sites include Schema.org JobPosting structured data which
    provides clean, reliable job descriptions.

    Args:
        soup: BeautifulSoup object of the page

    Returns:
        Job description text if found, None otherwise
    """
    try:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            if not script.string:
                continue

            data = json.loads(script.string)

            # Handle both single objects and arrays
            data_items = data if isinstance(data, list) else [data]

            # Look for JobPosting schema
            for item in data_items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    description = item.get("description", "")
                    if description and len(description) >= MIN_VALID_TEXT_LENGTH:
                        return clean_text(description)

        return None
    except (json.JSONDecodeError, AttributeError, KeyError):
        return None


def is_js_required(text: str) -> bool:
    """
    Detect if page requires JavaScript to render content

    Uses flexible heuristic: short text + mentions "JavaScript"
    This works across languages and phrasing variations:
    - "Sie müssen JavaScript aktivieren"
    - "JavaScript erforderlich"
    - "You need to enable JavaScript"
    - etc.

    Args:
        text: Extracted page text

    Returns:
        True if page likely requires JavaScript
    """
    if not text:
        return False

    # Short text (< 500 chars) + contains "javascript" = likely SPA placeholder
    return len(text) < 500 and "javascript" in text.lower()


def extract_from_paragraphs(soup: BeautifulSoup) -> str:
    """
    Fallback: Aggregate all paragraph tags for content extraction

    When semantic HTML fails, gathering all <p> tags often captures
    the job description scattered across the page.

    Args:
        soup: BeautifulSoup object of the page

    Returns:
        Concatenated text from all paragraphs
    """
    paragraphs = soup.find_all("p")
    text_parts = []

    for p in paragraphs:
        text = p.get_text(separator=" ", strip=True)
        if text and len(text) > 20:  # Skip trivial paragraphs
            text_parts.append(text)

    return " ".join(text_parts)


def find_content_heavy_div(soup: BeautifulSoup) -> str | None:
    """
    Find the div with the most text content

    Often the main job description is in the div with the most text,
    even if it lacks semantic markers.

    Args:
        soup: BeautifulSoup object of the page

    Returns:
        Text from the most content-heavy div, or None
    """
    divs = soup.find_all("div")

    if not divs:
        return None

    # Find div with most text
    max_text = ""
    max_length = 0

    for div in divs:
        text = div.get_text(separator="\n", strip=True)
        if len(text) > max_length:
            max_length = len(text)
            max_text = text

    if max_length >= MIN_VALID_TEXT_LENGTH:
        return max_text

    return None


def extract_domain(url: str) -> str:
    """Extract domain from URL for statistics tracking"""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return "unknown"


def parse_arbeitsagentur_page(html: str | None, url: str, config_obj: Config | None = None) -> dict:
    """
    Parse Arbeitsagentur job page HTML (pure function for testability).

    Args:
        html: HTML content of the page
        url: URL of the page (for metadata)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        Dictionary with success status, text content, and metadata
    """
    if config_obj is None:
        config_obj = config

    if not html:
        return {
            "success": False,
            "text": "",
            "url": url,
            "domain": "www.arbeitsagentur.de",
            "error": "No HTML content provided",
            "source": "arbeitsagentur",
            "text_length": 0,
            "warning": "EXCEPTION",
        }

    domain = "www.arbeitsagentur.de"

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        remove_tags = config_obj.get(
            "scraper.html_cleanup.remove_tags", ["script", "style", "nav", "header", "footer"]
        )
        for element in soup(remove_tags):
            element.decompose()

        # Try to find main content area
        content_selector = config_obj.get(
            "scraper.arbeitsagentur.content_selector", "jb-steadetail-beschreibung"
        )
        main_content = soup.find(content_selector)

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
            text = clean_text(text)
            return {
                "success": True,
                "text": text,
                "url": url,
                "source": "arbeitsagentur",
                "extraction_method": "css_selector",
                "text_length": len(text),
                "domain": domain,
                "warning": None,
            }

        # Fallback if selector doesn't match
        return {
            "success": False,
            "error": "Content selector not found",
            "url": url,
            "source": "arbeitsagentur",
            "domain": domain,
            "text_length": 0,
            "warning": "NO_CONTENT",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url,
            "source": "arbeitsagentur",
            "domain": domain,
            "text_length": 0,
            "warning": "EXCEPTION",
        }


def fetch_arbeitsagentur_details(
    refnr: str, http_client: HttpClient | None = None, config_obj: Config | None = None
) -> dict:
    """
    Fetch job details from Arbeitsagentur internal page

    Args:
        refnr: Reference number of the job listing
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        Dictionary with success status, text content, and metadata
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
    domain = "www.arbeitsagentur.de"

    headers = {"User-Agent": config_obj.get("scraper.headers.user_agent")}

    try:
        timeout = config_obj.get("api.timeouts.arbeitsagentur_details", 10)
        response = http_client.get(url, headers=headers, timeout=timeout)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "url": url,
                "source": "arbeitsagentur",
                "domain": domain,
                "text_length": 0,
            }

        # Use the parsing function (separated for testability)
        return parse_arbeitsagentur_page(response.text, url, config_obj)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url,
            "source": "arbeitsagentur",
            "domain": domain,
            "text_length": 0,
            "warning": "EXCEPTION",
        }


def parse_external_page(html: str, url: str, config_obj: Config | None = None) -> dict:
    """
    Parse external job page HTML (pure function for testability).

    Extraction priority:
    1. JSON-LD structured data (most reliable)
    2. Standard CSS selectors (main, article, etc.)
    3. Content-heavy div detection
    4. Paragraph aggregation

    Args:
        html: HTML content of the page
        url: URL of the page (for metadata)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        Dictionary with success status, text content, and metadata
    """
    if config_obj is None:
        config_obj = config

    domain = extract_domain(url)

    try:
        soup = BeautifulSoup(html, "html.parser")

        # TIER 1: Try JSON-LD extraction first (before removing script tags!)
        json_ld_text = extract_json_ld(soup)
        if json_ld_text:
            return {
                "success": True,
                "text": json_ld_text,
                "url": url,
                "source": "external",
                "extraction_method": "json_ld",
                "text_length": len(json_ld_text),
                "domain": domain,
                "warning": None,
            }

        # Remove unwanted elements for HTML-based extraction
        remove_tags = config_obj.get(
            "scraper.html_cleanup.remove_tags",
            ["script", "style", "nav", "header", "footer", "aside", "iframe"],
        )
        for element in soup(remove_tags):
            element.decompose()

        # Remove common navigation/menu classes
        remove_classes_pattern = config_obj.get(
            "scraper.html_cleanup.remove_classes", "(nav|menu|sidebar|breadcrumb|cookie|popup)"
        )
        for element in soup.find_all(class_=re.compile(remove_classes_pattern, re.I)):
            element.decompose()

        # TIER 2: Try standard CSS selectors
        primary_selector = config_obj.get("scraper.external.content_selectors.primary", "main")
        secondary_selector = config_obj.get(
            "scraper.external.content_selectors.secondary", "article"
        )
        content_pattern = config_obj.get(
            "scraper.external.content_selectors.content_pattern", "(content|job|detail|description)"
        )
        id_pattern = config_obj.get(
            "scraper.external.content_selectors.id_pattern", "(content|job|detail|main)"
        )

        main_content = (
            soup.find(primary_selector)
            or soup.find(secondary_selector)
            or soup.find("div", class_=re.compile(content_pattern, re.I))
            or soup.find("div", id=re.compile(id_pattern, re.I))
        )

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
            text = clean_text(text)
            text_length = len(text)

            # Validate text quality
            if text_length >= MIN_VALID_TEXT_LENGTH:
                return {
                    "success": True,
                    "text": text,
                    "url": url,
                    "source": "external",
                    "extraction_method": "css_selector",
                    "text_length": text_length,
                    "domain": domain,
                    "warning": None,
                }

            # Check if it's a JS-required page
            if is_js_required(text):
                return {
                    "success": False,
                    "error": "JavaScript required",
                    "text": text,  # Keep for debugging
                    "url": url,
                    "source": "external",
                    "extraction_method": "css_selector",
                    "text_length": text_length,
                    "domain": domain,
                    "warning": "JS_REQUIRED",
                }

            # Text too short but not JS issue
            if text_length < MIN_VALID_TEXT_LENGTH:
                # Continue to fallback strategies
                pass

        # TIER 3: Try content-heavy div detection
        heavy_div_text = find_content_heavy_div(soup)
        if heavy_div_text:
            text = clean_text(heavy_div_text)
            return {
                "success": True,
                "text": text,
                "url": url,
                "source": "external",
                "extraction_method": "content_heavy_div",
                "text_length": len(text),
                "domain": domain,
                "warning": None,
            }

        # TIER 4: Try paragraph aggregation as last resort
        paragraph_text = extract_from_paragraphs(soup)
        if paragraph_text:
            text = clean_text(paragraph_text)
            text_length = len(text)

            if text_length >= MIN_VALID_TEXT_LENGTH:
                return {
                    "success": True,
                    "text": text,
                    "url": url,
                    "source": "external",
                    "extraction_method": "paragraph_aggregation",
                    "text_length": text_length,
                    "domain": domain,
                    "warning": None,
                }

        # All strategies failed - return whatever we got with warning
        fallback_text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""
        fallback_text = clean_text(fallback_text)
        text_length = len(fallback_text)

        # Determine warning type
        if is_js_required(fallback_text):
            warning = "JS_REQUIRED"
        elif text_length < MIN_VALID_TEXT_LENGTH:
            warning = "SHORT_CONTENT"
        else:
            warning = "LOW_QUALITY"

        return {
            "success": False,
            "error": f"Insufficient content ({text_length} chars)",
            "text": fallback_text,  # Keep for debugging
            "url": url,
            "source": "external",
            "extraction_method": "fallback",
            "text_length": text_length,
            "domain": domain,
            "warning": warning,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url,
            "source": "external",
            "domain": domain,
            "text_length": 0,
            "warning": "EXCEPTION",
        }


def fetch_external_details(
    external_url: str, http_client: HttpClient | None = None, config_obj: Config | None = None
) -> dict:
    """
    Fetch job details from external website using multi-tier extraction strategy

    Extraction priority:
    1. JSON-LD structured data (most reliable)
    2. Standard CSS selectors (main, article, etc.)
    3. Content-heavy div detection
    4. Paragraph aggregation

    Args:
        external_url: URL of the external job listing
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        Dictionary with success status, text content, and metadata including:
        - extraction_method: Which method successfully extracted content
        - warning: Any issues detected (JS_REQUIRED, SHORT_CONTENT, etc.)
        - text_length: Length of extracted text
        - domain: Domain of the URL
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    headers = {
        "User-Agent": config_obj.get("scraper.headers.user_agent"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    domain = extract_domain(external_url)

    try:
        timeout = config_obj.get("api.timeouts.external_url", 15)
        response = http_client.get(external_url, headers=headers, timeout=timeout)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "url": external_url,
                "source": "external",
                "domain": domain,
                "text_length": 0,
            }

        # Use the parsing function (separated for testability)
        return parse_external_page(response.text, external_url, config_obj)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": external_url,
            "source": "external",
            "domain": domain,
            "text_length": 0,
            "warning": "EXCEPTION",
        }


def fetch_detailed_listings(
    jobs: list[dict],
    delay: float | None = None,
    verbose: bool = True,
    session: Optional["SearchSession"] = None,
    http_client: HttpClient | None = None,
    config_obj: Config | None = None,
) -> list[dict]:
    """
    Fetch detailed information for all job listings

    Args:
        jobs: List of job listings from search_jobs()
        delay: Delay between requests in seconds (defaults to config value)
        verbose: Print progress messages
        session: Optional SearchSession to save scraped data for debugging
        http_client: HTTP client for making requests (optional)
        config_obj: Config object (optional, uses global config if None)

    Returns:
        List of jobs with detailed information added
    """
    if http_client is None:
        http_client = default_http_client
    if config_obj is None:
        config_obj = config

    if delay is None:
        delay = config_obj.get("api.delays.scraping", 1.0)

    detailed_jobs = []

    # ERROR TRACKING
    error_stats: ErrorStats = {
        "total_jobs": len(jobs),
        "successful": 0,
        "failed": 0,
        "by_warning": {},  # JS_REQUIRED, TIMEOUT, etc.
        "by_domain": {},  # Errors per domain
        "failed_jobs": [],  # List of failed job details
    }

    for idx, job in enumerate(jobs, 1):
        logger.info(f"Fetching details for job {idx}/{len(jobs)}: {job.get('beruf', 'N/A')}")

        # Create a copy of the original job data
        detailed_job = job.copy()

        refnr = job.get("refnr")
        external_url = job.get("externeUrl")

        if external_url and external_url.strip():
            # External website
            logger.info(f"  Fetching from external URL: {external_url}")
            details = fetch_external_details(external_url, http_client, config_obj)
        elif refnr:
            # Internal Arbeitsagentur page
            logger.info(f"  Fetching from Arbeitsagentur: {refnr}")
            details = fetch_arbeitsagentur_details(refnr, http_client, config_obj)
        else:
            logger.warning("  No detail URL available")
            details = {
                "success": False,
                "error": "No refnr or external URL available",
                "source": "none",
            }

        # Add the details to the job
        detailed_job["details"] = details

        # TRACK SUCCESS/FAILURE
        if details["success"]:
            error_stats["successful"] += 1
            text_len = details.get("text_length", len(details.get("text", "")))
            method = details.get("extraction_method", "unknown")
            logger.info(f"  ✓ Job {idx} fetched successfully: {text_len} chars via {method}")
        else:
            error_stats["failed"] += 1

            # Track by warning type
            warning = details.get("warning", "UNKNOWN")
            error_stats["by_warning"][warning] = error_stats["by_warning"].get(warning, 0) + 1

            # Track by domain
            domain = details.get("domain", "unknown")
            error_stats["by_domain"][domain] = error_stats["by_domain"].get(domain, 0) + 1

            # Record failed job
            error_stats["failed_jobs"].append(
                {
                    "index": idx,
                    "title": job.get("beruf", "N/A"),
                    "url": details.get("url", external_url or f"refnr:{refnr}"),
                    "domain": domain,
                    "error": details.get("error", "Unknown"),
                    "warning": warning,
                }
            )

            error = details.get("error", "Unknown error")
            text_len = details.get("text_length", 0)
            if warning and warning != "UNKNOWN":
                logger.warning(
                    f"  ⚠ Job {idx} warning ({warning}): {error} "
                    f"(domain: {domain}, extracted: {text_len} chars)"
                )
            else:
                logger.warning(f"  ✗ Job {idx} failed: {error} (domain: {domain})")

        detailed_jobs.append(detailed_job)

        # Add delay to be respectful to servers
        if idx < len(jobs):
            time.sleep(delay)

    # PRINT ERROR SUMMARY
    if error_stats["failed"] > 0:
        logger.error("=" * 70)
        logger.error("SCRAPING ERROR SUMMARY")
        logger.error("=" * 70)
        logger.error(
            f"Total failures: {error_stats['failed']}/{error_stats['total_jobs']} jobs ({error_stats['failed'] / error_stats['total_jobs'] * 100:.1f}%)"
        )

        logger.error("\nBy error type:")
        for warning, count in sorted(
            error_stats["by_warning"].items(), key=lambda x: x[1], reverse=True
        ):
            logger.error(f"  {warning}: {count} jobs")

        logger.error("\nBy domain:")
        for domain, count in sorted(
            error_stats["by_domain"].items(), key=lambda x: x[1], reverse=True
        )[:10]:
            logger.error(f"  {domain}: {count} failures")

        logger.error("=" * 70)

    # Save error stats to session
    if session and error_stats["failed"] > 0:
        error_file = session.debug_dir / "scraping_errors.json"
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(error_stats, f, ensure_ascii=False, indent=2)
        logger.info(f"Error report saved to {error_file}")

    # Save scraped jobs to session
    if session:
        session.save_scraped_jobs(detailed_jobs)

    # Generate and print extraction statistics
    if verbose and len(detailed_jobs) > 0:
        stats = generate_extraction_statistics(detailed_jobs)
        print_extraction_statistics(stats)

    return detailed_jobs


def extract_descriptions(detailed_jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Extract job descriptions, separating successful and failed scrapes

    Args:
        detailed_jobs: List of jobs with detailed information

    Returns:
        Tuple of (successful_jobs, failed_jobs):
        - successful_jobs: List with titel, ort, arbeitgeber, text, url, refnr
        - failed_jobs: List with titel, ort, arbeitgeber, url, error_type
    """
    successful = []
    failed = []

    for job in detailed_jobs:
        details = job.get("details", {})

        # Extract common fields
        arbeitsort = job.get("arbeitsort", {})
        ort = arbeitsort.get("ort", "") if isinstance(arbeitsort, dict) else ""

        titel = job.get("beruf", "")
        arbeitgeber = job.get("arbeitgeber", "")

        if details.get("success", False):
            # Successful scrape
            job_url = details.get("url", "")
            refnr = job.get("refnr", "")

            successful.append(
                {
                    "titel": titel,
                    "ort": ort,
                    "arbeitgeber": arbeitgeber,
                    "text": details["text"],
                    "url": job_url,
                    "refnr": refnr,
                }
            )
        else:
            # Failed scrape - extract minimal info for tracking
            job_url = details.get("url", job.get("externeUrl", ""))
            if not job_url and job.get("refnr"):
                job_url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{job.get('refnr')}"

            # Determine error type
            warning = details.get("warning", "UNKNOWN")
            error = details.get("error", "Unknown error")

            # Map warnings to short error types
            error_type_map = {
                "JS_REQUIRED": "JS_REQUIRED",
                "SHORT_CONTENT": "SHORT_CONTENT",
                "NO_CONTENT": "NO_CONTENT",
                "TIMEOUT": "TIMEOUT",
                "EXCEPTION": "EXCEPTION",
                "UNKNOWN": "ERROR",
            }
            error_type = error_type_map.get(warning, "ERROR")

            failed.append(
                {
                    "titel": titel,
                    "ort": ort,
                    "arbeitgeber": arbeitgeber,
                    "url": job_url,
                    "error_type": error_type,
                    "error_details": error,  # Keep for debugging
                }
            )

    return successful, failed


def generate_extraction_statistics(detailed_jobs: list[dict]) -> ExtractionStats:
    """
    Generate comprehensive extraction quality statistics

    Provides detailed breakdown by:
    - Source (internal vs external)
    - Domain (for external sources)
    - Extraction method
    - Success/failure rates
    - Warning types

    Args:
        detailed_jobs: List of jobs with detailed information

    Returns:
        Dictionary with comprehensive statistics
    """
    stats: ExtractionStats = {
        "total_jobs": len(detailed_jobs),
        "by_source": {},
        "by_domain": {},
        "by_extraction_method": {},
        "by_warning": {},
        "problem_domains": [],
        "successful_domains": [],
    }

    # Separate by source (use dict[str, Any] during construction)
    by_source_temp: dict[str, Any] = {}
    for job in detailed_jobs:
        details = job.get("details", {})
        source = details.get("source", "unknown")

        if source not in by_source_temp:
            by_source_temp[source] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "avg_text_length": 0,
                "total_text_length": 0,
            }

        by_source_temp[source]["total"] += 1

        if details.get("success"):
            by_source_temp[source]["successful"] += 1
        else:
            by_source_temp[source]["failed"] += 1

        text_length = details.get("text_length", len(details.get("text", "")))
        by_source_temp[source]["total_text_length"] += text_length

    # Calculate averages and convert to final structure
    for source_stats in by_source_temp.values():
        if source_stats["total"] > 0:
            source_stats["avg_text_length"] = (
                source_stats["total_text_length"] // source_stats["total"]
            )
        del source_stats["total_text_length"]

    stats["by_source"] = by_source_temp

    # Analyze external sites by domain
    domain_data: dict[str, DomainData] = {}
    for job in detailed_jobs:
        details = job.get("details", {})

        if details.get("source") != "external":
            continue

        domain = details.get("domain", "unknown")
        if domain not in domain_data:
            domain_data[domain] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "text_lengths": [],
                "warnings": {},
                "methods": {},
            }

        domain_data[domain]["total"] += 1

        if details.get("success"):
            domain_data[domain]["successful"] += 1
        else:
            domain_data[domain]["failed"] += 1

        text_length = details.get("text_length", 0)
        domain_data[domain]["text_lengths"].append(text_length)

        # Track warnings
        warning = details.get("warning")
        if warning:
            domain_data[domain]["warnings"][warning] = (
                domain_data[domain]["warnings"].get(warning, 0) + 1
            )

        # Track extraction methods
        method = details.get("extraction_method", "unknown")
        domain_data[domain]["methods"][method] = domain_data[domain]["methods"].get(method, 0) + 1

    # Process domain statistics
    for domain, data in domain_data.items():
        text_lengths = data["text_lengths"]
        avg_length = sum(text_lengths) // len(text_lengths) if text_lengths else 0
        min_length = min(text_lengths) if text_lengths else 0
        max_length = max(text_lengths) if text_lengths else 0

        success_rate = (data["successful"] / data["total"] * 100) if data["total"] > 0 else 0

        domain_summary: DomainSummary = {
            "total": data["total"],
            "successful": data["successful"],
            "failed": data["failed"],
            "success_rate": round(success_rate, 1),
            "avg_text_length": avg_length,
            "min_text_length": min_length,
            "max_text_length": max_length,
            "primary_warning": max(data["warnings"].items(), key=lambda x: x[1])[0]
            if data["warnings"]
            else None,
            "primary_method": max(data["methods"].items(), key=lambda x: x[1])[0]
            if data["methods"]
            else None,
        }

        stats["by_domain"][domain] = domain_summary

        # Categorize as problem or successful domain
        if success_rate < 50 and data["total"] >= 3:
            problem_info: ProblemDomainInfo = {
                "domain": domain,
                "total": data["total"],
                "success_rate": round(success_rate, 1),
                "primary_warning": domain_summary["primary_warning"],
            }
            stats["problem_domains"].append(problem_info)
        elif success_rate >= 80 and data["total"] >= 3:
            success_info: SuccessfulDomainInfo = {
                "domain": domain,
                "total": data["total"],
                "success_rate": round(success_rate, 1),
                "primary_method": domain_summary["primary_method"],
            }
            stats["successful_domains"].append(success_info)

    # Sort problem and successful domains by total jobs
    stats["problem_domains"].sort(key=lambda x: x["total"], reverse=True)
    stats["successful_domains"].sort(key=lambda x: x["total"], reverse=True)

    # Track extraction methods overall
    for job in detailed_jobs:
        details = job.get("details", {})
        method = details.get("extraction_method", "unknown")

        if method and method != "unknown":
            if method not in stats["by_extraction_method"]:
                stats["by_extraction_method"][method] = 0
            stats["by_extraction_method"][method] += 1

    # Track warnings overall
    for job in detailed_jobs:
        details = job.get("details", {})
        warning = details.get("warning")

        if warning:
            if warning not in stats["by_warning"]:
                stats["by_warning"][warning] = 0
            stats["by_warning"][warning] += 1

    return stats


def print_extraction_statistics(stats: ExtractionStats) -> None:
    """
    Print extraction statistics in a human-readable format

    Args:
        stats: Statistics dictionary from generate_extraction_statistics()
    """
    logger.info("=" * 70)
    logger.info("EXTRACTION QUALITY REPORT")
    logger.info("=" * 70)

    # Overall summary
    logger.info(f"Total jobs: {stats['total_jobs']}")

    # By source
    logger.info("--- By Source ---")
    for source, data in stats["by_source"].items():
        success_rate = (data["successful"] / data["total"] * 100) if data["total"] > 0 else 0
        logger.info(
            f"  {source}: {data['successful']}/{data['total']} successful ({success_rate:.1f}%)"
        )
        logger.info(f"    Avg text length: {data['avg_text_length']:,} chars")

    # Extraction methods
    if stats["by_extraction_method"]:
        logger.info("--- Extraction Methods ---")
        total_extracted = sum(stats["by_extraction_method"].values())
        for method, count in sorted(
            stats["by_extraction_method"].items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / total_extracted * 100) if total_extracted > 0 else 0
            logger.info(f"  {method}: {count} ({percentage:.1f}%)")

    # Warnings
    if stats["by_warning"]:
        logger.info("--- Warnings ---")
        for warning, count in sorted(stats["by_warning"].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {warning}: {count} jobs")

    # Problem domains
    if stats["problem_domains"]:
        logger.info("--- Top Problem Domains ---")
        for domain_info in stats["problem_domains"][:5]:
            logger.info(
                f"  {domain_info['domain']}: {domain_info['success_rate']}% success ({domain_info['total']} jobs)"
            )
            if domain_info["primary_warning"]:
                logger.info(f"    Primary issue: {domain_info['primary_warning']}")

    logger.info("=" * 70)
