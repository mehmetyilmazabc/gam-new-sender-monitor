#!/usr/bin/env python3
"""
GAM New Sender Monitor

Runs GAMADV-XTD3, reads only the CSV output in memory, extracts email addresses
from the Gmail From header, compares them with previously known senders, and
writes only newly observed sender addresses to disk.

No message body, subject, attachment, recipient, or message ID is persisted.
"""


from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

DEFAULT_KNOWN = Path("data/known_senders.txt")
DEFAULT_OUTPUT_DIR = Path("output")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_address(value: str) -> str | None:
    """Extract and normalize an email address from an RFC-style From header."""
    if not value:
        return None

    _display_name, address = parseaddr(value)
    address = address.strip().lower()

    if not EMAIL_RE.match(address):
        return None

    return address


def load_known_senders(path: Path) -> set[str]:
    if not path.exists():
        return set()

    result = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        address = normalize_address(line)
        if address:
            result.add(address)
    return result


def save_addresses(path: Path, addresses: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(sorted(addresses))
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def run_gam(gam_path: str, user_selector: list[str], query: str) -> str:
    """
    Run GAM and return CSV stdout.

    Example command:
      gam all users print messages query "newer_than:1d" headers from

    We intentionally do NOT request showbody, showhtml, attachments, subject,
    recipients, or other message content.
    """
    command = [
        gam_path,
        *user_selector,
        "print",
        "messages",
        "query",
        query,
        "headers",
        "from",
    ]

    print("Running GAM query...", file=sys.stderr)

    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.returncode != 0:
        print(completed.stderr, file=sys.stderr)
        raise RuntimeError(
            f"GAM exited with status {completed.returncode}. "
            "Run the GAM command manually to verify authentication and syntax."
        )

    return completed.stdout


def find_from_column(fieldnames: list[str] | None) -> str:
    if not fieldnames:
        raise RuntimeError("GAM returned no CSV header.")

    # GAM output can vary slightly by version/casing.
    candidates = {"from", "fromaddress", "from.address"}
    for field in fieldnames:
        if field and field.strip().lower() in candidates:
            return field

    # Fall back to any column that ends with "from".
    for field in fieldnames:
        if field and field.strip().lower().endswith("from"):
            return field

    raise RuntimeError(
        "Could not find the From column in GAM CSV output. "
        f"Columns returned: {fieldnames}"
    )


def extract_senders(csv_text: str) -> set[str]:
    reader = csv.DictReader(io.StringIO(csv_text))
    from_column = find_from_column(reader.fieldnames)

    senders: set[str] = set()
    for row in reader:
        address = normalize_address(row.get(from_column, ""))
        if address:
            senders.add(address)

    return senders


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find previously unseen Gmail From addresses using GAM."
    )
    parser.add_argument(
        "--gam",
        default="gam",
        help="Path to GAM executable. Default: gam",
    )
    parser.add_argument(
        "--query",
        default="newer_than:1d",
        help='Gmail search query. Default: "newer_than:1d"',
    )
    parser.add_argument(
        "--known",
        type=Path,
        default=DEFAULT_KNOWN,
        help="Private local known-senders file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Private local output directory.",
    )
    parser.add_argument(
        "--user",
        help=(
            "Optional single Workspace user to test with first. "
            "If omitted, GAM selector 'all users' is used."
        ),
    )
    parser.add_argument(
        "--initialize",
        action="store_true",
        help=(
            "Baseline mode: add current senders to known_senders.txt "
            "without reporting them as alerts."
        ),
    )

    args = parser.parse_args()

    user_selector = ["user", args.user] if args.user else ["all", "users"]

    csv_text = run_gam(args.gam, user_selector, args.query)
    current_senders = extract_senders(csv_text)
    known_senders = load_known_senders(args.known)

    if args.initialize:
        combined = known_senders | current_senders
        save_addresses(args.known, combined)
        print(
            f"Baseline updated: {len(current_senders)} sender(s) observed; "
            f"{len(combined)} total known sender(s)."
        )
        return 0

    new_senders = current_senders - known_senders

    # Update baseline after calculating what's new.
    save_addresses(args.known, known_senders | current_senders)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_file = args.output_dir / f"new_senders_{timestamp}.txt"
    save_addresses(output_file, new_senders)

    print(f"Observed unique senders : {len(current_senders)}")
    print(f"Previously known        : {len(known_senders)}")
    print(f"New senders             : {len(new_senders)}")

    if new_senders:
        print("\nNew sender addresses:")
        for address in sorted(new_senders):
            print(address)
        print(f"\nSaved to: {output_file}")
    else:
        # Avoid accumulating empty files.
        output_file.unlink(missing_ok=True)
        print("\nNo new senders found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
