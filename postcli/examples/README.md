# postcli examples

Use these starter files to send your first emails.

## Quick start

1. Copy the example files:
   ```bash
   cp examples/template.txt examples/contacts.csv examples/links.json .
   ```

2. Edit `template.txt` with your message. The default is a cold mail format (TLDR, pitch, value prop list, links, CTA). Replace `[placeholders]` with your own content.

3. Edit `links.json` with your X, LinkedIn, GitHub, portfolio, resume, and sender name. These are available in templates as `{{ x }}`, `{{ linkedin }}`, `{{ github }}`, `{{ portfolio }}`, `{{ resume }}`, `{{ sender_name }}`.

4. Edit `contacts.csv` with your contacts. Column names are auto-detected:
   - **Email** – `email`, `e-mail`, `mail`, `work_email`, etc.
   - **Name** – `name`, `full_name`, `contact_name`, etc.
   - **Company** – `company`, `organization`, `org`, etc.

5. Add your SMTP credentials to `.env`. For Gmail: use an [App Password](https://myaccount.google.com/apppasswords), not your regular password — enable 2-Step Verification first, then generate an App Password.

6. Preview and send:
   ```bash
   postcli send --template template.txt --contacts contacts.csv --subject "Hello" --dry-run
   postcli send --template template.txt --contacts contacts.csv --subject "Hello"
   ```

## Tracking sent contacts

After each successful send:
- Sent contacts are appended to `contacted.csv` (same folder as your contacts file)
- Sent contacts are removed from your main contacts file
