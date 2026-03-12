"""Twilio credential validation and phone verification helper.

Validates Twilio account credentials, lists owned numbers and verified
caller IDs, and optionally places a test call.

Usage:
    python scripts/validate_twilio.py                       # Sections 1-3 + 5
    python scripts/validate_twilio.py --test-call +1234567890  # Also section 4

Exit codes:
    0 = Sections 1-2 pass (credentials valid, at least 1 owned number)
    1 = Credentials invalid or no owned numbers
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def section_1_credentials() -> tuple[bool, str]:
    """Section 1: Validate Twilio credentials and account status."""
    print("\n--- Section 1: Credential Validation ---")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")

    if not account_sid or not auth_token:
        print("  ERROR: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set in .env")
        print("  FAIL")
        return False, ""

    if not account_sid.startswith("AC"):
        print(f"  ERROR: TWILIO_ACCOUNT_SID should start with 'AC', got: {account_sid[:4]}...")
        print("  FAIL")
        return False, ""

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()

        print(f"  Account Name:   {account.friendly_name}")
        print(f"  Account Status: {account.status}")
        print(f"  Account Type:   {account.type}")
        print(f"  Account SID:    {account_sid[:8]}...{account_sid[-4:]}")

        if account.status == "active":
            account_type = "Trial" if account.type == "Trial" else "Full"
            print(f"  PASS (Active {account_type} account)")
            return True, account_type
        else:
            print(f"  FAIL (Account status: {account.status})")
            return False, ""

    except Exception as e:
        error_msg = str(e)
        print(f"  ERROR: {error_msg}")

        if "authenticate" in error_msg.lower() or "401" in error_msg:
            print("\n  Your Twilio credentials are invalid.")
            print("  Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in your .env file.")
            print("  Find them at: https://www.twilio.com/console")

        if "rate limit" in error_msg.lower() or "429" in error_msg:
            print("\n  Rate limited by Twilio. Wait a few seconds and try again.")

        print("  FAIL")
        return False, ""


def section_2_owned_numbers() -> bool:
    """Section 2: List owned/purchased phone numbers."""
    print("\n--- Section 2: Owned Phone Numbers ---")

    try:
        from twilio.rest import Client

        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )

        numbers = client.incoming_phone_numbers.list()

        if not numbers:
            print("  No owned phone numbers found.")
            print("  You need at least 1 Twilio number for outbound calling.")
            print("  Purchase one at: https://www.twilio.com/console/phone-numbers/search")
            print("  FAIL")
            return False

        print(f"  Owned numbers: {len(numbers)}")
        for number in numbers:
            capabilities = []
            if number.capabilities.get("voice"):
                capabilities.append("Voice")
            if number.capabilities.get("sms"):
                capabilities.append("SMS")
            if number.capabilities.get("mms"):
                capabilities.append("MMS")
            cap_str = ", ".join(capabilities) if capabilities else "None"
            print(f"    {number.phone_number} ({number.friendly_name}) [{cap_str}]")

        print(f"  PASS ({len(numbers)} number(s) found)")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        print("  FAIL")
        return False


def section_3_verified_callers() -> int:
    """Section 3: List verified outgoing caller IDs."""
    print("\n--- Section 3: Verified Caller IDs ---")

    try:
        from twilio.rest import Client

        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )

        outgoing = client.outgoing_caller_ids.list()
        count = len(outgoing)

        print(f"  Verified caller IDs: {count}")
        for caller_id in outgoing:
            friendly = caller_id.friendly_name or "No name"
            print(f"    {caller_id.phone_number} ({friendly})")

        if count >= 10:
            print(f"  PASS ({count} verified -- meets 10-number requirement)")
        elif count > 0:
            print(f"  WARN ({count}/10 verified -- need {10 - count} more for all test leads)")
        else:
            print(f"  WARN (0 verified caller IDs -- need 10 for test leads)")

        return count

    except Exception as e:
        print(f"  ERROR: {e}")
        print("  FAIL")
        return -1


def section_4_test_call(to_number: str) -> bool:
    """Section 4: Place a test call to verify Twilio calling works."""
    print(f"\n--- Section 4: Test Call to {to_number} ---")

    try:
        from twilio.rest import Client

        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )

        from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
        if not from_number:
            print("  ERROR: TWILIO_PHONE_NUMBER not set in .env")
            print("  FAIL")
            return False

        twiml = (
            '<Response>'
            '<Say voice="alice">'
            'This is a Cloudboosta test call. '
            'If you hear this, Twilio integration is working correctly. '
            'Goodbye.'
            '</Say>'
            '</Response>'
        )

        print(f"  Calling {to_number} from {from_number}...")
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=twiml,
        )

        print(f"  Call SID:    {call.sid}")
        print(f"  Call Status: {call.status}")

        if call.status in ("queued", "initiated", "ringing", "in-progress"):
            print(f"  PASS (Call {call.status})")
            return True
        else:
            print(f"  WARN (Unexpected status: {call.status})")
            return True  # Still created

    except Exception as e:
        error_msg = str(e)
        print(f"  ERROR: {error_msg}")

        if "not verified" in error_msg.lower() or "21219" in error_msg:
            print(f"\n  The number {to_number} is not verified on your Twilio trial account.")
            print(f"  Verify it at: https://www.twilio.com/console/phone-numbers/verified")

        if "geographic" in error_msg.lower() or "21215" in error_msg:
            print(f"\n  Geographic permissions may block calls to this region.")
            print(f"  Enable at: https://www.twilio.com/console/voice/settings/geo-permissions")
            print(f"  Ensure the country for {to_number} is enabled.")

        if "rate limit" in error_msg.lower() or "429" in error_msg:
            print(f"\n  Rate limited. Wait and try again.")

        print("  FAIL")
        return False


def section_5_verification_instructions(verified_count: int):
    """Section 5: Print instructions for verifying remaining numbers."""
    if verified_count >= 10:
        return

    print("\n--- Section 5: Phone Verification Instructions ---")
    print(f"\n  You have {verified_count}/10 verified numbers.")
    print(f"  You need to verify {10 - verified_count} more test lead phone numbers.")
    print()
    print("  Step-by-step:")
    print("  1. Go to https://www.twilio.com/console/phone-numbers/verified")
    print("  2. Click 'Add a new Caller ID'")
    print("  3. Enter the phone number with country code")
    print("     (e.g., +234XXXXXXXXXX for Nigeria, +44XXXXXXXXXX for UK)")
    print("  4. Choose 'Call this number' or 'Text this number' for verification")
    print("  5. Enter the OTP code received on the phone")
    print("  6. Repeat for each of the 10 test lead numbers")
    print()
    print("  IMPORTANT: Geographic permissions")
    print("  Check: https://www.twilio.com/console/voice/settings/geo-permissions")
    print("  Ensure Nigeria (+234) and any other lead countries are enabled.")
    print("  Without geographic permissions, calls to those regions will fail.")
    print()
    print("  NOTE: On a Twilio trial account, every outbound call will be")
    print("  prefixed with a Twilio trial message. This is normal and expected.")
    print("  Inform your test leads they'll hear this message before Sarah speaks.")


def main():
    parser = argparse.ArgumentParser(description="Validate Twilio setup for Cloudboosta AI Sales Agent")
    parser.add_argument(
        "--test-call",
        metavar="+NUMBER",
        help="Place a test call to this number (e.g., --test-call +1234567890)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Twilio Validation for Cloudboosta AI Sales Agent")
    print("=" * 60)

    # Section 1: Credentials
    creds_ok, account_type = section_1_credentials()
    if not creds_ok:
        print("\n" + "=" * 60)
        print("OVERALL: FAIL (credentials invalid)")
        print("=" * 60)
        sys.exit(1)

    # Section 2: Owned numbers
    numbers_ok = section_2_owned_numbers()

    # Section 3: Verified caller IDs
    verified_count = section_3_verified_callers()

    # Section 4: Test call (optional)
    test_call_ok = None
    if args.test_call:
        test_call_ok = section_4_test_call(args.test_call)

    # Section 5: Verification instructions (if needed)
    if verified_count >= 0:
        section_5_verification_instructions(verified_count)

    # Summary
    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)
    print(f"  Credentials:         {'PASS' if creds_ok else 'FAIL'} ({account_type})")
    print(f"  Owned numbers:       {'PASS' if numbers_ok else 'FAIL'}")

    if verified_count >= 10:
        verified_status = f"PASS ({verified_count} verified)"
    elif verified_count >= 0:
        verified_status = f"WARN ({verified_count}/10 verified)"
    else:
        verified_status = "FAIL"
    print(f"  Verified caller IDs: {verified_status}")

    if test_call_ok is not None:
        print(f"  Test call:           {'PASS' if test_call_ok else 'FAIL'}")

    # Overall result
    if creds_ok and numbers_ok:
        print(f"\nOVERALL: PASS")
        sys.exit(0)
    else:
        print(f"\nOVERALL: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
