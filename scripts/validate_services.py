"""Validate external service connectivity and credential format.

Checks reachability of: Supabase, n8n, OpenClaw, Resend.
Also validates .env completeness against .env.example.

Usage: python scripts/validate_services.py
"""

import os
import sys

import httpx
from dotenv import load_dotenv


# Load .env from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Categorize checks as CRITICAL or WARN-only
# CRITICAL failures cause exit code 1
# WARN failures are reported but don't block


def check_supabase() -> tuple[str, str, bool]:
    """Check Supabase reachability via REST API."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_SERVICE_KEY", "")

    if not url:
        return "Supabase", "FAIL -- SUPABASE_URL not set in .env", True

    try:
        r = httpx.get(
            f"{url}/rest/v1/",
            headers={"apikey": key} if key else {},
            timeout=10,
        )
        if r.status_code in (200, 401):
            return "Supabase", f"PASS -- reachable at {url} (HTTP {r.status_code})", True
        else:
            return "Supabase", f"FAIL -- unexpected status {r.status_code} at {url}", True
    except Exception as e:
        return "Supabase", f"FAIL -- {e}", True


def check_n8n() -> tuple[str, str, bool]:
    """Check n8n reachability via health endpoint."""
    url = os.getenv("N8N_BASE_URL", "")

    if not url:
        return "n8n", "WARN -- N8N_BASE_URL not set in .env", False

    try:
        r = httpx.get(f"{url}/healthz", timeout=10)
        if r.status_code == 200:
            return "n8n", f"PASS -- reachable at {url}", False
        else:
            return "n8n", f"WARN -- HTTP {r.status_code} at {url}/healthz", False
    except Exception as e:
        return "n8n", f"WARN -- {e}", False


def check_openclaw() -> tuple[str, str, bool]:
    """Check OpenClaw reachability (basic HTTP check only)."""
    url = os.getenv("OPENCLAW_API_URL", "")

    if not url:
        return "OpenClaw", "WARN -- OPENCLAW_API_URL not set in .env", False

    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        if r.status_code in (200, 302):
            return "OpenClaw", f"PASS -- reachable at {url} (HTTP {r.status_code})", False
        else:
            return "OpenClaw", f"WARN -- HTTP {r.status_code} at {url}", False
    except Exception as e:
        return "OpenClaw", f"WARN -- {e}", False


def check_resend_key() -> tuple[str, str, bool]:
    """Check Resend API key format (no API call -- avoids sending test emails)."""
    key = os.getenv("RESEND_API_KEY", "")

    if not key:
        return "Resend API Key", "FAIL -- RESEND_API_KEY not set in .env", False
    elif key.startswith("re_"):
        return "Resend API Key", "PASS -- key format valid (starts with re_)", False
    else:
        return "Resend API Key", "FAIL -- key does not start with 're_'", False


def check_twilio_creds() -> tuple[str, str, bool]:
    """Check Twilio credential format (no API call)."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")

    issues = []
    if not sid:
        issues.append("TWILIO_ACCOUNT_SID not set")
    elif not sid.startswith("AC"):
        issues.append(f"TWILIO_ACCOUNT_SID does not start with 'AC' (got '{sid[:4]}...')")

    if not token:
        issues.append("TWILIO_AUTH_TOKEN not set")

    if issues:
        return "Twilio Credentials", f"FAIL -- {'; '.join(issues)}", True
    else:
        return "Twilio Credentials", "PASS -- SID starts with AC, token present", True


def check_gcp_credentials_file() -> tuple[str, str, bool]:
    """Check GOOGLE_APPLICATION_CREDENTIALS file exists."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    if not creds_path:
        return "GCP Credentials File", "FAIL -- GOOGLE_APPLICATION_CREDENTIALS not set", True

    # Resolve relative path from project root
    if not os.path.isabs(creds_path):
        full_path = os.path.join(PROJECT_ROOT, creds_path)
    else:
        full_path = creds_path

    if os.path.isfile(full_path):
        return "GCP Credentials File", f"PASS -- file exists at {creds_path}", True
    else:
        return "GCP Credentials File", f"FAIL -- file not found at {full_path}", True


def check_gcp_project_id() -> tuple[str, str, bool]:
    """Check GCP_PROJECT_ID is set and not the old default."""
    project_id = os.getenv("GCP_PROJECT_ID", "")

    if not project_id:
        return "GCP Project ID", "FAIL -- GCP_PROJECT_ID not set", True
    elif project_id == "cloudboosta-agent":
        return "GCP Project ID", "FAIL -- still set to old default 'cloudboosta-agent' (should be 'vision-gridai')", True
    else:
        return "GCP Project ID", f"PASS -- set to '{project_id}'", True


def check_gemini_model() -> tuple[str, str, bool]:
    """Check GEMINI_MODEL is set and contains native-audio."""
    model = os.getenv("GEMINI_MODEL", "")

    if not model:
        return "Gemini Model", "FAIL -- GEMINI_MODEL not set", True
    elif "native-audio" in model:
        return "Gemini Model", f"PASS -- set to '{model}'", True
    else:
        return "Gemini Model", f"FAIL -- model '{model}' does not contain 'native-audio'", True


def check_env_completeness() -> list[str]:
    """Compare .env against .env.example and report missing vars."""
    env_example_path = os.path.join(PROJECT_ROOT, ".env.example")
    env_path = os.path.join(PROJECT_ROOT, ".env")

    if not os.path.isfile(env_example_path):
        return ["Cannot check: .env.example not found"]
    if not os.path.isfile(env_path):
        return ["Cannot check: .env not found"]

    # Parse var names from .env.example
    example_vars = set()
    with open(env_example_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=", 1)[0].strip()
                example_vars.add(var_name)

    # Parse var names from .env
    env_vars = set()
    with open(env_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=", 1)[0].strip()
                env_vars.add(var_name)

    missing = example_vars - env_vars
    return sorted(missing) if missing else []


def main() -> int:
    """Run all service checks and return exit code."""
    print("\n===== Service Reachability Validation =====\n")

    checks = [
        check_supabase,
        check_n8n,
        check_openclaw,
        check_resend_key,
        check_twilio_creds,
        check_gcp_credentials_file,
        check_gcp_project_id,
        check_gemini_model,
    ]

    results = []
    for check_fn in checks:
        name, message, is_critical = check_fn()
        results.append((name, message, is_critical))
        critical_label = " [CRITICAL]" if is_critical else ""
        print(f"  {name}{critical_label}: {message}")

    # Check .env completeness
    print("\n----- .env Completeness Check -----")
    missing_vars = check_env_completeness()
    if missing_vars:
        print(f"  Vars in .env.example but missing from .env ({len(missing_vars)}):")
        for var in missing_vars:
            print(f"    - {var}")
    else:
        print("  All .env.example vars are present in .env")

    # Summary
    print("\n===== Summary =====")
    pass_count = sum(1 for _, msg, _ in results if msg.startswith("PASS"))
    fail_count = sum(1 for _, msg, _ in results if msg.startswith("FAIL"))
    warn_count = sum(1 for _, msg, _ in results if msg.startswith("WARN"))
    critical_fails = sum(1 for _, msg, is_crit in results if msg.startswith("FAIL") and is_crit)

    print(f"  PASS: {pass_count}")
    print(f"  FAIL: {fail_count} ({critical_fails} critical)")
    print(f"  WARN: {warn_count}")

    # Exit 0 if all critical services pass
    if critical_fails > 0:
        print("\n  RESULT: CRITICAL checks failed. Fix the items above.")
        return 1
    else:
        print("\n  RESULT: All critical checks passed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
