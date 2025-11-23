#!/usr/bin/env python3
"""
OpenRouter API Diagnostic Tool

This script tests connectivity, authentication, and model availability
for OpenRouter API. Useful for debugging communication issues.

Usage:
    python diagnose_openrouter.py
    python diagnose_openrouter.py --verbose
    python diagnose_openrouter.py --timeout 30
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import requests


class Colors:
    """ANSI color codes for terminal output"""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{char * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{char * 70}{Colors.RESET}")


def print_success(text: str) -> None:
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print info message"""
    print(f"{Colors.BLUE}[INFO] {text}{Colors.RESET}")


def get_api_key() -> str | None:
    """Get API key from environment variable"""
    return os.environ.get("OPENROUTER_API_KEY")


def test_connectivity(timeout: int = 10) -> bool:
    """Test basic connectivity to OpenRouter"""
    print_header("Test 1: Basic Connectivity")
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=timeout)
        print_success(f"Can reach OpenRouter API (Status: {response.status_code})")
        return True
    except requests.exceptions.Timeout:
        print_error("Connection timeout - OpenRouter may be slow or unreachable")
        return False
    except requests.exceptions.ConnectionError as e:
        print_error(f"Connection error: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        return False


def test_authentication(api_key: str, timeout: int = 10) -> dict[str, Any] | None:
    """Test API key authentication and get account info"""
    print_header("Test 2: API Key Authentication")

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(
            "https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=timeout
        )

        if response.status_code == 200:
            data: dict[str, Any] = response.json().get("data", {})
            print_success("API Key is valid")

            # Display account info
            limit = data.get("limit", 0)
            remaining = data.get("limit_remaining", 0)
            usage = data.get("usage", 0)
            usage_daily = data.get("usage_daily", 0)
            usage_weekly = data.get("usage_weekly", 0)
            usage_monthly = data.get("usage_monthly", 0)

            print(f"  {Colors.BOLD}Account Info:{Colors.RESET}")
            print(f"    Credit limit:      ${limit:.2f}")
            print(f"    Credit remaining:  ${remaining:.2f} ({remaining / limit * 100:.1f}%)")
            print(f"    Total usage:       ${usage:.2f}")
            print(f"    Daily usage:       ${usage_daily:.2f}")
            print(f"    Weekly usage:      ${usage_weekly:.2f}")
            print(f"    Monthly usage:     ${usage_monthly:.2f}")

            if remaining < 1.0:
                print_warning(f"Low credit remaining: ${remaining:.2f}")

            return data
        elif response.status_code == 401:
            print_error("Invalid API key")
            return None
        else:
            print_error(f"Authentication failed (Status: {response.status_code})")
            print(f"  Response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print_error("Request timeout")
        return None
    except Exception as e:
        print_error(f"Error: {type(e).__name__}: {e}")
        return None


def test_model(
    api_key: str, model: str, timeout: int = 15, verbose: bool = False
) -> tuple[str, float | None, str | None]:
    """
    Test a specific model

    Returns:
        tuple of (status, duration, error_message)
        status: 'success', 'timeout', 'error'
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "(test)",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say 'OK' in one word"}],
        "max_tokens": 10,
        "temperature": 0.2,
    }

    try:
        start = time.time()
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        duration = time.time() - start

        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if verbose:
                usage = result.get("usage", {})
                print(f"    Response: {content}")
                print(f"    Tokens: {usage.get('total_tokens', 'N/A')}")

            return ("success", duration, None)
        else:
            error_data = response.json().get("error", {})
            error_msg = error_data.get("message", "Unknown error")
            return ("error", duration, f"{response.status_code}: {error_msg}")

    except requests.exceptions.Timeout:
        return ("timeout", None, "Request timeout")
    except Exception as e:
        return ("error", None, f"{type(e).__name__}: {e}")


def test_models(api_key: str, timeout: int = 15, verbose: bool = False) -> dict[str, list]:
    """Test multiple models across different providers"""
    print_header("Test 3: Model Availability")

    # Models to test, organized by provider
    test_cases = [
        # Anthropic models
        ("anthropic/claude-3-haiku", "Anthropic Claude 3 Haiku", "cheap"),
        ("anthropic/claude-3-5-sonnet", "Anthropic Claude 3.5 Sonnet", "capable"),
        # Google models (commonly used)
        ("google/gemini-2.5-flash", "Google Gemini 2.5 Flash (your default)", "config"),
        ("google/gemini-2.5-pro", "Google Gemini 2.5 Pro", "capable"),
        ("google/gemini-flash-1.5", "Google Gemini Flash 1.5", "fast"),
        # OpenAI models
        ("openai/gpt-3.5-turbo", "OpenAI GPT-3.5 Turbo", "cheap"),
        ("openai/gpt-4o-mini", "OpenAI GPT-4o Mini", "capable"),
        # xAI models
        ("x-ai/grok-4.1-fast", "xAI Grok 4.1 Fast (supports reasoning)", "fast"),
        # Meta models
        ("meta-llama/llama-3.1-8b-instruct", "Meta Llama 3.1 8B", "cheap"),
    ]

    results: dict[str, list] = {"success": [], "timeout": [], "error": []}

    print(f"\n{Colors.BOLD}Testing {len(test_cases)} models...{Colors.RESET}\n")

    for model, description, _ in test_cases:
        status, duration, error = test_model(api_key, model, timeout, verbose)

        # Format model name with fixed width
        model_display = f"{description[:45]:45}"

        if status == "success":
            assert duration is not None
            print_success(f"{model_display} | {duration:.2f}s")
            results["success"].append((model, description, duration))
        elif status == "timeout":
            print_warning(f"{model_display} | TIMEOUT")
            results["timeout"].append((model, description))
        else:
            print_error(f"{model_display} | {error}")
            results["error"].append((model, description, error))

        # Small delay between requests to avoid rate limiting
        time.sleep(0.3)

    return results


def print_summary(results: dict[str, list]) -> None:
    """Print summary of test results"""
    print_header("Summary", "=")

    total = len(results["success"]) + len(results["timeout"]) + len(results["error"])
    success_count = len(results["success"])
    timeout_count = len(results["timeout"])
    error_count = len(results["error"])

    print(f"\n{Colors.BOLD}Overall Results:{Colors.RESET}")
    print(f"  Total models tested: {total}")
    print(f"  {Colors.GREEN}✅ Working:         {success_count}{Colors.RESET}")
    print(f"  {Colors.YELLOW}⏱️  Timeouts:        {timeout_count}{Colors.RESET}")
    print(f"  {Colors.RED}❌ Errors:          {error_count}{Colors.RESET}")

    # Show working models
    if results["success"]:
        print(f"\n{Colors.BOLD}{Colors.GREEN}Working Models:{Colors.RESET}")
        # Sort by response time
        sorted_success = sorted(results["success"], key=lambda x: x[2])
        for model, description, duration in sorted_success:
            print(f"  • {description[:50]:50} ({duration:.2f}s)")
            print(f"    {Colors.CYAN}{model}{Colors.RESET}")

    # Show timeout models
    if results["timeout"]:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Models With Timeouts:{Colors.RESET}")
        for model, description in results["timeout"]:
            print(f"  • {description}")
            print(f"    {Colors.CYAN}{model}{Colors.RESET}")

    # Show error models
    if results["error"]:
        print(f"\n{Colors.BOLD}{Colors.RED}Models With Errors:{Colors.RESET}")
        for model, description, error in results["error"]:
            print(f"  • {description}")
            print(f"    {Colors.CYAN}{model}{Colors.RESET}")
            print(f"    Error: {error}")


def print_recommendations(results: dict[str, list]) -> None:
    """Print recommendations based on test results"""
    print_header("Recommendations", "=")

    # Check if configured model (gemini-2.5-flash) is working
    gemini_flash_working = any("gemini-2.5-flash" in model for model, _, _ in results["success"])
    gemini_flash_timeout = any("gemini-2.5-flash" in model for model, _ in results["timeout"])

    if gemini_flash_working:
        print_success("Your configured model (google/gemini-2.5-flash) is working fine!")
    elif gemini_flash_timeout:
        print_warning("Your configured model (google/gemini-2.5-flash) is timing out!")
        print("\n{Colors.BOLD}Suggested actions:{Colors.RESET}")
        print("  1. This is a SERVICE-SIDE issue with OpenRouter's Google endpoints")
        print("  2. Switch to a working model temporarily")
        print("  3. Check OpenRouter status page: https://status.openrouter.ai")

        if results["success"]:
            fastest_model, fastest_desc, fastest_time = min(results["success"], key=lambda x: x[2])
            print(f"\n{Colors.BOLD}Recommended temporary alternative:{Colors.RESET}")
            print(f"  Model: {Colors.CYAN}{fastest_model}{Colors.RESET}")
            print(f"  Description: {fastest_desc}")
            print(f"  Response time: {fastest_time:.2f}s")
            print(f"\n{Colors.BOLD}To use this model:{Colors.RESET}")
            print("  Update config/llm_config.yaml:")
            print(f"    {Colors.CYAN}models:")
            print(f'      default: "{fastest_model}"{Colors.RESET}')

    # General recommendations
    if len(results["timeout"]) > len(results["success"]):
        print_warning("\nMost models are timing out - this suggests:")
        print("  • OpenRouter service issues")
        print("  • Network connectivity problems")
        print("  • High load on OpenRouter infrastructure")

    if not results["success"]:
        print_error("\nNo models are working!")
        print("  This is definitely a service-side issue.")
        print("  Wait and try again later, or contact OpenRouter support.")


def save_report(
    results: dict[str, list],
    auth_data: dict | None,
    output_file: str = "openrouter_diagnostic_report.json",
) -> None:
    """Save diagnostic report to JSON file"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "auth": {
            "valid": auth_data is not None,
            "credit_remaining": auth_data.get("limit_remaining") if auth_data else None,
            "credit_limit": auth_data.get("limit") if auth_data else None,
        },
        "results": {
            "success": [
                {"model": m, "description": d, "duration": dur} for m, d, dur in results["success"]
            ],
            "timeout": [{"model": m, "description": d} for m, d in results["timeout"]],
            "error": [{"model": m, "description": d, "error": e} for m, d, e in results["error"]],
        },
        "summary": {
            "total_tested": len(results["success"])
            + len(results["timeout"])
            + len(results["error"]),
            "success_count": len(results["success"]),
            "timeout_count": len(results["timeout"]),
            "error_count": len(results["error"]),
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n{Colors.BOLD}Report saved to: {Colors.CYAN}{output_file}{Colors.RESET}")


def main():
    """Main diagnostic routine"""
    parser = argparse.ArgumentParser(
        description="Diagnose OpenRouter API connectivity and model availability"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout for model tests in seconds (default: 15)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save diagnostic report to JSON file",
    )
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'=' * 70}")
    print("OpenRouter API Diagnostic Tool")
    print(f"{'=' * 70}{Colors.RESET}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print_error("\nOPENROUTER_API_KEY environment variable not set!")
        print(f"\n{Colors.BOLD}Set it with:{Colors.RESET}")
        print('  export OPENROUTER_API_KEY="your-key-here"')
        sys.exit(1)

    print_info(f"Using API key: {api_key[:15]}...{api_key[-4:]}")
    print_info(f"Timeout setting: {args.timeout}s")

    # Run tests
    connectivity_ok = test_connectivity(timeout=10)

    if not connectivity_ok:
        print_warning("\nBasic connectivity failed, but continuing with other tests...")

    auth_data = test_authentication(api_key, timeout=10)

    if auth_data is None:
        print_error("\nAuthentication failed! Cannot proceed with model tests.")
        sys.exit(1)

    results = test_models(api_key, timeout=args.timeout, verbose=args.verbose)

    # Print results
    print_summary(results)
    print_recommendations(results)

    # Save report if requested
    if args.save_report:
        save_report(results, auth_data)

    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'=' * 70}")
    print("Diagnostic Complete")
    print(f"{'=' * 70}{Colors.RESET}\n")

    # Exit with appropriate code
    if len(results["success"]) == 0:
        sys.exit(1)  # No models working
    elif len(results["timeout"]) > 0 or len(results["error"]) > 0:
        sys.exit(2)  # Some models not working
    else:
        sys.exit(0)  # All good


if __name__ == "__main__":
    main()
