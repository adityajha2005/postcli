# postcli

Send handcrafted emails from your terminal. Template your messages with Jinja2, keep contacts in CSV, and send via SMTP.

## Install

```bash
pip install postcli
```

Or from source:

```bash
git clone https://github.com/adityajha2005/postcli.git
cd postcli
pip install -e .
```

## Setup

1. Initialize a project (creates template.txt, contacts.csv, links.json, .env.example):
   ```bash
   postcli init
   ```

2. Copy and edit `.env` with your SMTP credentials:
   ```
   cp .env.example .env
   ```
   Edit `.env`:
   ```
   EMAIL_ADDRESS=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```

   **Gmail – EMAIL_PASSWORD is not your regular password.** Gmail blocks third-party apps from using your normal login password. You must use an **App Password** instead:

   1. Go to [Google Account → Security](https://myaccount.google.com/security)
   2. Turn on **2-Step Verification** (required before App Passwords appear)
   3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
   4. Create one: select "Mail" and "Other", name it e.g. `postcli`
   5. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`) and paste it into `.env` as `EMAIL_PASSWORD` — remove spaces: `abcdefghijklmnop`

3. Edit `template.txt`, `contacts.csv`, and `links.json` with your content.

## Demo

From a directory where you've run `postcli init` (or use `postcli/examples/` paths when in the repo):

```bash
postcli send --template template.txt --contacts contacts.csv --subject "Hello {{ name }}" --dry-run
```

Send for real (default subject: "Interested in {{ company }}"):
```bash
postcli send --template template.txt --contacts contacts.csv
postcli send --template template.txt --contacts contacts.csv --subject "Quick question for {{ name }}"
```

### Commands

| Command | Description |
|---------|-------------|
| `postcli init` | Create template.txt, contacts.csv, links.json, .env.example |
| `postcli import data.json` | Convert JSON → contacts.csv |
| `postcli validate` | Validate template, CSV, links.json, SMTP config |
| `postcli send` | Send emails |

### Send options

| Option | Description |
|--------|-------------|
| `--template` | Path to Jinja2 email template (required) |
| `--contacts` | Path to CSV contacts file (required) |
| `--subject` | Subject line – default: `Interested in {{ company }}` (use `{{ name }}`, `{{ company }}`) |
| `--from-name` | Display name for sender |
| `--delay N` | Seconds to wait between sends (default: 0) |
| `--limit N` | Max contacts to send to (0 = all) |
| `--skip-contacted` | Skip emails already in contacted.csv |
| `--mutate` | **Opt-in file changes:** append sent to `contacted.csv`, remove from contacts file |
| `--dry-run` | Preview only, no emails sent |

### Template

Use Jinja2 placeholders in your template. CSV column names become variables:

```txt
Hi {{ name }},

I came across {{ company }} and wanted to reach out.

Best
```

### Contacts CSV

First row must be column headers. Column names are **auto-detected**—use any of these aliases:

| Canonical | Aliases |
|-----------|---------|
| `email` | email, e-mail, mail, work_email, email_address |
| `name` | name, full_name, contact_name, first_name |
| `company` | company, organization, org, company_name |

Example:

```csv
name,company,email
Jane Doe,Acme Inc,jane@example.com
John Smith,Tech Co,john@example.com
```

### Tracking sent contacts

> **postcli does not modify your files by default.**  
> Use `--mutate` to enable: appending sent contacts to `contacted.csv` and removing them from your main contacts file.

By default, postcli leaves your contacts file untouched. Pass `--mutate` if you want:
- Sent contacts appended to `contacted.csv` (same folder as your contacts file)
- Sent contacts removed from your main contacts file

### Validate

```bash
postcli validate
postcli validate --template template.txt --contacts contacts.csv --links --smtp
```

### Init

```bash
postcli init
postcli init --dir ./my-campaign
```

### Import JSON → contacts.csv

Drop a JSON file and run:

```bash
postcli import data.json
postcli import yc_founders.json -o contacts.csv
```

| Option | Description |
|--------|-------------|
| `JSON_FILE` | Path to JSON file (required) |
| `-o`, `--output` | Output CSV path (default: contacts.csv) |

**Supported formats:**
- **founders:** `{ "company": "...", "founders": [{ "name": "..." }], "companyEmails": ["..."] }`
- **Flat:** `{ "name": "...", "company": "...", "email": "..." }`

Skips records without `companyEmails` or `email`. Uses first founder's name when available.

## License

MIT
