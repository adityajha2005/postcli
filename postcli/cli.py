import os
import time
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import click
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, UndefinedError
from rich import print
from rich.panel import Panel

from postcli.contacts import append_contacted, load_contacted_emails, load_contacts, write_contacts
from postcli.links import load_links

load_dotenv()


def _get_smtp_config():
    required = ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "SMTP_SERVER", "SMTP_PORT")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[red]Missing env vars: {', '.join(missing)}. Add them to .env[/red]")
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
@click.option("--subject", default="Hello", help="Email subject (use {{ name }}, {{ company }} for templating).")
@click.option("--from-name", default=None, help="Display name for sender (default: EMAIL_ADDRESS).")
@click.option("--delay", type=int, default=0, help="Seconds to wait between sends (default: 0).")
@click.option("--limit", type=int, default=0, help="Max contacts to send to (0 = all).")
@click.option("--skip-contacted", is_flag=True, help="Skip emails already in contacted.csv.")
@click.option("--dry-run", is_flag=True, help="Preview emails without sending.")
def send(template, contacts, subject, from_name, delay, limit, skip_contacted, dry_run):
    template_path = Path(template)
    contacts_path = Path(contacts)

    if not template_path.exists():
        print(f"[red]Template not found: {template}[/red]")
        raise SystemExit(1)
    if not contacts_path.exists():
        print(f"[red]Contacts file not found: {contacts}[/red]")
        raise SystemExit(1)

    try:
        rows = load_contacts(contacts_path)
    except ValueError as e:
        print(f"[red]{e}[/red]")
        raise SystemExit(1)

    if not rows:
        print("[yellow]No contacts in CSV.[/yellow]")
        return

    already_contacted = load_contacted_emails(contacts_path) if skip_contacted else set()
    if already_contacted:
        rows = [r for r in rows if r["email"] not in already_contacted]
        if not rows:
            print("[yellow]All contacts already in contacted.csv. Nothing to send.[/yellow]")
            return
        print(f"[dim]Skipped {len(already_contacted)} already contacted[/dim]")

    if limit > 0:
        rows = rows[:limit]
        print(f"[dim]Limited to {limit} contact(s)[/dim]")

    print(f"[bold green]postcli[/bold green] – {len(rows)} contact(s)")
    if dry_run:
        print("[dim]Dry run – preview only, no emails sent[/dim]\n")

    loader = FileSystemLoader(template_path.parent)
    env = Environment(loader=loader)
    subject_tmpl = Environment().from_string(subject)
    tmpl = env.get_template(template_path.name)

    links = load_links(contacts_path.parent)

    if not dry_run:
        cfg = _get_smtp_config()
        from_addr = f"{from_name} <{cfg['address']}>" if from_name else cfg["address"]

    sent: list[dict] = []

    for i, contact in enumerate(rows):
        ctx = {**links, **contact}
        try:
            rendered = tmpl.render(**ctx)
            rendered_subject = subject_tmpl.render(**ctx)
        except UndefinedError as e:
            print(f"[red]Template error for {contact.get('email', '?')}: {e}[/red]")
            raise SystemExit(1)

        to_addr = contact.get("email", "").strip()
        if not to_addr:
            continue

        if dry_run:
            print(Panel(rendered, title=f"To: {to_addr} | Subject: {rendered_subject}", title_align="left", border_style="blue"))
            continue

        msg = MIMEText(rendered, "plain", "utf-8")
        msg["Subject"] = rendered_subject
        msg["From"] = from_addr
        msg["To"] = to_addr

        try:
            with smtplib.SMTP(cfg["server"], cfg["port"]) as smtp:
                smtp.starttls()
                smtp.login(cfg["address"], cfg["password"])
                smtp.sendmail(cfg["address"], to_addr, msg.as_string())
            print(f"[green]Sent to {to_addr}[/green]")
            sent.append(contact)
        except smtplib.SMTPAuthenticationError:
            print("[red]SMTP auth failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD (use Gmail App Password if 2FA).[/red]")
            raise SystemExit(1)
        except Exception as e:
            print(f"[red]Failed to send to {to_addr}: {e}[/red]")
            raise SystemExit(1)

        if delay > 0 and i < len(rows) - 1:
            time.sleep(delay)

    if not dry_run and sent:
        contacted_path = contacts_path.parent / "contacted.csv"
        append_contacted(contacted_path, sent)
        remaining = [c for c in rows if c["email"] not in {s["email"] for s in sent}]
        write_contacts(contacts_path, remaining)
        print(f"[dim]Moved {len(sent)} contact(s) to {contacted_path}[/dim]")


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
            print("[dim]links.json not found (optional)[/dim]")
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
        print(f"[green]{msg}[/green]")
    for msg in errors:
        print(f"[red]{msg}[/red]")

    if errors:
        raise SystemExit(1)


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
        print("[red]Examples folder not found.[/red]")
        raise SystemExit(1)

    files = ["template.txt", "contacts.csv", "links.json"]
    for f in files:
        sp = src / f
        dp = dst / f
        if dp.exists():
            print(f"[yellow]Skip {f} (exists)[/yellow]")
        else:
            shutil.copy(sp, dp)
            print(f"[green]Created {dp}[/green]")

    env_src = src / ".env.example"
    env_dst = dst / ".env.example"
    if env_src.exists() and not env_dst.exists():
        shutil.copy(env_src, env_dst)
        print(f"[green]Created {env_dst}[/green]")
    elif env_dst.exists():
        print(f"[yellow]Skip .env.example (exists)[/yellow]")
