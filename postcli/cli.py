import os
import time
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import click
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, UndefinedError
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from postcli.contacts import append_contacted, load_contacted_emails, load_contacts, write_contacts
from postcli.links import load_links

load_dotenv()

console = Console()


def _version():
    try:
        from importlib.metadata import version
        return version("postcli")
    except Exception:
        return "0.1.0"


def _get_smtp_config():
    required = ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "SMTP_SERVER", "SMTP_PORT")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        console.print(f"[red]✗ Missing env vars: {', '.join(missing)}. Add them to .env[/red]")
        raise SystemExit(1)
    return {
        "address": os.getenv("EMAIL_ADDRESS"),
        "password": os.getenv("EMAIL_PASSWORD"),
        "server": os.getenv("SMTP_SERVER"),
        "port": int(os.getenv("SMTP_PORT")),
    }


@click.group()
def cli():
    """postcli - Send handcrafted emails from your terminal."""
    pass


@cli.command()
@click.option("--template", required=True, help="Path to email template.")
@click.option("--contacts", required=True, help="Path to CSV contacts file.")
@click.option("--subject", default="Interested in {{ company }}", help="Email subject (use {{ name }}, {{ company }} for templating).")
@click.option("--from-name", default=None, help="Display name for sender (default: EMAIL_ADDRESS).")
@click.option("--delay", type=int, default=0, help="Seconds to wait between sends (default: 0).")
@click.option("--limit", type=int, default=0, help="Max contacts to send to (0 = all).")
@click.option("--skip-contacted", is_flag=True, help="Skip emails already in contacted.csv.")
@click.option("--mutate", is_flag=True, help="Append sent contacts to contacted.csv and remove them from contacts file (opt-in).")
@click.option("--dry-run", is_flag=True, help="Preview emails without sending.")
def send(template, contacts, subject, from_name, delay, limit, skip_contacted, mutate, dry_run):
    template_path = Path(template)
    contacts_path = Path(contacts)

    if not template_path.exists():
        console.print(f"[red]✗ Template not found: {template}[/red]")
        raise SystemExit(1)
    if not contacts_path.exists():
        console.print(f"[red]✗ Contacts file not found: {contacts}[/red]")
        raise SystemExit(1)

    try:
        rows = load_contacts(contacts_path)
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(1)

    if not rows:
        console.print("[yellow]✗ No contacts in CSV.[/yellow]")
        return

    already_contacted = load_contacted_emails(contacts_path) if skip_contacted else set()
    if already_contacted:
        rows = [r for r in rows if r["email"] not in already_contacted]
        if not rows:
            console.print("[yellow]✗ All contacts already in contacted.csv. Nothing to send.[/yellow]")
            return

    if limit > 0:
        rows = rows[:limit]

    # Header
    console.print(f"postcli {_version()}")
    console.print(Rule(style="dim"))
    if already_contacted:
        console.print(f"[dim]Skipped {len(already_contacted)} already contacted[/dim]")
    if limit > 0:
        console.print(f"[dim]Limited to {limit} contact(s)[/dim]")

    console.print(f"[green]✓[/green] Loaded {len(rows)} contact(s)")

    loader = FileSystemLoader(template_path.parent)
    env = Environment(loader=loader)
    subject_tmpl = Environment().from_string(subject)
    tmpl = env.get_template(template_path.name)
    console.print("[green]✓[/green] Template validated")

    links = load_links(contacts_path.parent)

    if not dry_run:
        cfg = _get_smtp_config()
        from_addr = f"{from_name} <{cfg['address']}>" if from_name else cfg["address"]
        try:
            with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as smtp:
                smtp.starttls()
                smtp.login(cfg["address"], cfg["password"])
            console.print("[green]✓[/green] SMTP connected")
        except smtplib.SMTPAuthenticationError:
            console.print("[red]✗ SMTP auth failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD (use Gmail App Password if 2FA).[/red]")
            raise SystemExit(1)
        except Exception as e:
            console.print(f"[red]✗ SMTP error: {e}[/red]")
            raise SystemExit(1)

        if delay == 0 and len(rows) > 1:
            console.print("[yellow]⚠ No delay set. Gmail may throttle high volume sends.[/yellow]")
    else:
        console.print(Rule(" DRY RUN ", style="yellow"))
        console.print("[yellow]~ Dry run mode — no emails sent[/yellow]\n")

    total = len(rows)
    sent: list[dict] = []

    for i, contact in enumerate(rows):
        ctx = {**links, **contact}
        try:
            rendered = tmpl.render(**ctx)
            rendered_subject = subject_tmpl.render(**ctx)
        except UndefinedError as e:
            console.print(f"[red]✗ Template error for {contact.get('email', '?')}: {e}[/red]")
            raise SystemExit(1)

        to_addr = contact.get("email", "").strip()
        if not to_addr:
            continue

        if dry_run:
            console.print(Panel(rendered, title=f"To: {to_addr} | Subject: {rendered_subject}", title_align="left", border_style="blue"))
            continue

        msg = MIMEText(rendered, "plain", "utf-8")
        msg["Subject"] = rendered_subject
        msg["From"] = from_addr
        msg["To"] = to_addr

        try:
            t0 = time.perf_counter()
            with smtplib.SMTP(cfg["server"], cfg["port"]) as smtp:
                smtp.starttls()
                smtp.login(cfg["address"], cfg["password"])
                smtp.sendmail(cfg["address"], to_addr, msg.as_string())
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            console.print(f"[green]✓[/green] [{i + 1}/{total}] Sent to {to_addr} ({elapsed_ms}ms)")
            sent.append(contact)
        except smtplib.SMTPAuthenticationError:
            console.print("[red]✗ SMTP auth failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD (use Gmail App Password if 2FA).[/red]")
            raise SystemExit(1)
        except Exception as e:
            console.print(f"[red]✗ [{i + 1}/{total}] Failed to send to {to_addr}: {e}[/red]")
            raise SystemExit(1)

        if delay > 0 and i < len(rows) - 1:
            time.sleep(delay)

    if not dry_run and sent and mutate:
        contacted_path = contacts_path.parent / "contacted.csv"
        append_contacted(contacted_path, sent)
        remaining = [c for c in rows if c["email"] not in {s["email"] for s in sent}]
        write_contacts(contacts_path, remaining)
        console.print(f"[green]✓[/green] Moved {len(sent)} contact(s) to {contacted_path}")


@cli.command()
@click.option("--template", default=None, help="Path to email template.")
@click.option("--contacts", default=None, help="Path to CSV contacts file.")
@click.option("--links", is_flag=True, help="Validate links.json.")
@click.option("--smtp", is_flag=True, help="Validate SMTP config (connect only, no send).")
def validate(template, contacts, links, smtp):
    """Validate template, CSV, links.json, and/or SMTP config."""
    cwd = Path.cwd()
    errors: list[str] = []
    ok: list[str] = []

    if template is None and contacts is None and not links and not smtp:
        # Default: validate all in cwd
        template = cwd / "template.txt"
        contacts = cwd / "contacts.csv"
        links = True
        smtp = True
        if not Path(template).exists():
            template = None
        if not Path(contacts).exists():
            contacts = None

    if template:
        p = Path(template)
        if not p.exists():
            errors.append(f"Template not found: {template}")
        else:
            try:
                loader = FileSystemLoader(p.parent)
                env = Environment(loader=loader)
                tmpl = env.get_template(p.name)
                # Dry render with dummy data
                tmpl.render(name="Test", company="Test Co", email="test@example.com", x="", linkedin="", github="", portfolio="", resume="", sender_name="Test")
                ok.append(f"Template OK: {template}")
            except TemplateNotFound as e:
                errors.append(f"Template error: {e}")
            except UndefinedError as e:
                errors.append(f"Template error: {e}")
            except Exception as e:
                errors.append(f"Template error: {e}")

    if contacts:
        p = Path(contacts)
        if not p.exists():
            errors.append(f"Contacts file not found: {contacts}")
        else:
            try:
                rows = load_contacts(p)
                ok.append(f"Contacts OK: {len(rows)} row(s) in {contacts}")
            except ValueError as e:
                errors.append(f"Contacts error: {e}")
            except Exception as e:
                errors.append(f"Contacts error: {e}")

    if links:
        lp = cwd / "links.json"
        if not lp.exists():
            console.print("[dim]links.json not found (optional)[/dim]")
        else:
            try:
                import json
                with open(lp) as f:
                    json.load(f)
                ok.append("links.json OK")
            except json.JSONDecodeError as e:
                errors.append(f"links.json invalid: {e}")

    if smtp:
        try:
            cfg = _get_smtp_config()
            with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as smtp_conn:
                smtp_conn.starttls()
                smtp_conn.login(cfg["address"], cfg["password"])
            ok.append("SMTP OK")
        except smtplib.SMTPAuthenticationError:
            errors.append("SMTP auth failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD.")
        except Exception as e:
            errors.append(f"SMTP error: {e}")

    for msg in ok:
        console.print(f"[green]✓ {msg}[/green]")
    for msg in errors:
        console.print(f"[red]✗ {msg}[/red]")

    if errors:
        raise SystemExit(1)


@cli.command("import")
@click.argument("json_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="contacts.csv", help="Output CSV path (default: contacts.csv).")
def import_cmd(json_file, output):
    """Convert JSON to contacts.csv. Supports YC founders format (company, founders[].name, companyEmails[]) or flat {name, company, email}."""
    import json

    path = Path(json_file)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    rows: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        # Email: companyEmails[0] (YC format) or email (flat)
        emails = item.get("companyEmails")
        if isinstance(emails, list) and emails:
            email = str(emails[0] or "").strip()
        else:
            email = str(item.get("email") or "").strip()
        if not email:
            continue

        # Name: founders[0].name (YC format) or name (flat)
        name = str(item.get("name") or "").strip()
        if not name:
            founders = item.get("founders")
            if isinstance(founders, list) and founders and isinstance(founders[0], dict):
                name = str(founders[0].get("name") or "").strip()

        # Company
        company = str(item.get("company") or item.get("company_name") or item.get("organization") or "").strip()

        rows.append({"name": name, "company": company, "email": email})

    if not rows:
        console.print("[red]✗ No records with email found in JSON.[/red]")
        raise SystemExit(1)

    out_path = Path(output)
    write_contacts(out_path, rows)
    console.print(f"[green]✓ Wrote {len(rows)} contact(s) to {out_path}[/green]")


@cli.command()
@click.option("--dir", "target_dir", default=".", type=click.Path(), help="Directory to init (default: current).")
def init(target_dir):
    """Create template.txt, contacts.csv, links.json, and .env.example in the target directory."""
    import shutil

    # Prefer bundled examples (postcli/examples), fallback to project root
    pkg_dir = Path(__file__).parent
    src = pkg_dir / "examples"
    if not src.exists():
        src = pkg_dir.parent / "examples"
    dst = Path(target_dir).resolve()
    dst.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        console.print("[red]✗ Examples folder not found.[/red]")
        raise SystemExit(1)

    files = ["template.txt", "contacts.csv", "links.json"]
    for f in files:
        sp = src / f
        dp = dst / f
        if dp.exists():
            console.print(f"[yellow]~ Skip {f} (exists)[/yellow]")
        else:
            shutil.copy(sp, dp)
            console.print(f"[green]✓ Created {dp}[/green]")

    env_src = src / ".env.example"
    env_dst = dst / ".env.example"
    if env_src.exists() and not env_dst.exists():
        shutil.copy(env_src, env_dst)
        console.print(f"[green]✓ Created {env_dst}[/green]")
    elif env_dst.exists():
        console.print(f"[yellow]~ Skip .env.example (exists)[/yellow]")
