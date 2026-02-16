"""Load, normalize, and manage contact CSVs."""

import csv
from pathlib import Path
from typing import Any

# Column header aliases (normalized: lowercase, no spaces/underscores/hyphens)
NAME_ALIASES = frozenset({"name", "fullname", "full_name", "contactname", "contact_name", "recipient", "firstname", "first_name"})
EMAIL_ALIASES = frozenset({"email", "e-mail", "mail", "emailaddress", "email_address", "workemail", "work_email"})
COMPANY_ALIASES = frozenset({"company", "companyname", "company_name", "organization", "org"})


def _normalize_header(header: str) -> str:
    """Normalize header for matching."""
    return header.lower().replace(" ", "").replace("_", "").replace("-", "").strip()


def _detect_column(headers: list[str]) -> dict[str, str]:
    """
    Detect name, company, email columns from CSV headers.
    Returns mapping: canonical_name -> original_header.
    Raises if email column not found.
    """
    mapping: dict[str, str] = {}
    for h in headers:
        norm = _normalize_header(h)
        if norm in EMAIL_ALIASES and "email" not in mapping:
            mapping["email"] = h
        elif norm in NAME_ALIASES and "name" not in mapping:
            mapping["name"] = h
        elif norm in COMPANY_ALIASES and "company" not in mapping:
            mapping["company"] = h

    if "email" not in mapping:
        raise ValueError(
            f"Could not find email column. Expected one of: {', '.join(EMAIL_ALIASES)}. "
            f"Found headers: {headers}"
        )
    return mapping


def load_contacted_emails(contacts_path: Path) -> set[str]:
    """Load emails from contacted.csv (same folder as contacts file). Returns empty set if file missing."""
    path = Path(contacts_path).parent / "contacted.csv"
    if not path.exists():
        return set()
    emails: set[str] = set()
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = (row.get("email") or "").strip()
                if email:
                    emails.add(email)
    except Exception:
        pass
    return emails


def load_contacts(path: Path) -> list[dict[str, str]]:
    """
    Load CSV and normalize to canonical format {name, company, email}.
    Auto-detects columns from headers.
    Raises ValueError with row number if a row has missing email.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    if not headers:
        raise ValueError("CSV has no headers")

    col_map = _detect_column(headers)

    normalized: list[dict[str, str]] = []
    for i, row in enumerate(rows, start=2):  # row 1 = header
        email = (row.get(col_map["email"]) or "").strip()
        if not email:
            raise ValueError(f"Row {i}: missing email")

        n: dict[str, str] = {
            "name": (row.get(col_map.get("name", "")) or "").strip(),
            "company": (row.get(col_map.get("company", "")) or "").strip(),
            "email": email,
        }
        normalized.append(n)

    return normalized


def write_contacts(path: Path, rows: list[dict[str, Any]], create_parent: bool = True) -> None:
    """Write contacts in canonical format (name, company, email)."""
    path = Path(path)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "company", "email"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_contacted(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append contacts to contacted file. Creates file with headers if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "company", "email"], extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
