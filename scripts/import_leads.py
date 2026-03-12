"""Import leads from CSV into Supabase.

Reads a CSV file with columns: name, phone, email
and inserts them into the sales_agent.leads table with status='new'.

Usage: python scripts/import_leads.py leads.csv

Phone numbers must start with '+' and be valid E.164 format.
Duplicate phone numbers are safely skipped on re-import.
"""

import csv
import os
import sys

import httpx
import phonenumbers
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def validate_phone(phone_str: str) -> str | None:
    """Validate and normalize a phone number to E.164 format.

    Returns the E.164 string (e.g. '+2348012345678') or None if invalid.
    Rejects numbers without a '+' prefix before parsing.
    """
    phone_str = phone_str.strip()
    if not phone_str.startswith("+"):
        return None
    try:
        parsed = phonenumbers.parse(phone_str, None)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
    except phonenumbers.NumberParseException:
        return None


def _check_duplicate(client: httpx.Client, phone: str) -> bool:
    """Check if a lead with this phone already exists in sales_agent.leads."""
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/leads",
        params={"phone": f"eq.{phone}", "select": "id"},
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Accept-Profile": "sales_agent",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return len(resp.json()) > 0


def _insert_lead(client: httpx.Client, name: str, phone: str, email: str | None) -> bool:
    """Insert a single lead into sales_agent.leads. Returns True on success."""
    payload = {
        "name": name,
        "phone": phone,
        "email": email,
        "status": "new",
        "priority": 3,
    }
    resp = client.post(
        f"{SUPABASE_URL}/rest/v1/leads",
        json=payload,
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Content-Profile": "sales_agent",
            "Prefer": "return=minimal",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return True


def import_leads(csv_path: str) -> None:
    """Import leads from a CSV file into Supabase sales_agent.leads.

    CSV must have columns: name, phone, email
    - Phone numbers must start with '+' and be valid E.164 format
    - Duplicate phone numbers are skipped
    - Prints per-row status and a final summary
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("[ERROR] SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment")
        sys.exit(1)

    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)

    imported = 0
    invalid_phone = 0
    duplicates = 0
    errors = 0

    with httpx.Client() as client:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                phone_raw = row.get("phone", "").strip()
                email = row.get("email", "").strip() or None

                if not name:
                    print(f"  [ERROR] Missing name in row: {row}")
                    errors += 1
                    continue

                # Validate phone number
                phone = validate_phone(phone_raw)
                if phone is None:
                    print(f"  [SKIP]  {name} ({phone_raw}) -- invalid phone number")
                    invalid_phone += 1
                    continue

                # Check for duplicate
                try:
                    if _check_duplicate(client, phone):
                        print(f"  [SKIP]  {name} ({phone}) -- duplicate")
                        duplicates += 1
                        continue
                except Exception as e:
                    print(f"  [ERROR] {name} ({phone}) -- duplicate check failed: {e}")
                    errors += 1
                    continue

                # Insert lead
                try:
                    _insert_lead(client, name, phone, email)
                    print(f"  [OK]    {name} ({phone})")
                    imported += 1
                except Exception as e:
                    print(f"  [ERROR] {name} ({phone}) -- insert failed: {e}")
                    errors += 1

    skipped = invalid_phone + duplicates
    print()
    print(f"Imported {imported}, skipped {skipped} ({invalid_phone} invalid phone, {duplicates} duplicates)")
    if errors:
        print(f"Errors: {errors}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_leads.py <csv_file>")
        sys.exit(1)
    import_leads(sys.argv[1])
