# GAM New Sender Monitor

A small defensive-security utility that uses **GAMADV-XTD3** to identify email
`From` addresses that have not previously been observed in a Google Workspace
environment.

The project intentionally stores **sender email addresses only**. It does not
persist message bodies, subjects, recipients, attachments, message IDs, or
other Gmail content.


## What it does

1. Runs a GAM Gmail message query.
2. Requests the `From` header.
3. Parses and normalizes the email address.
4. Compares the current sender set with a private local baseline.
5. Prints and saves only previously unseen addresses.
6. Updates the private baseline for the next run.

The resulting new addresses can then be reviewed manually with tools such as
VirusTotal.

## Privacy / repository safety

Do **not** commit real Workspace sender information to GitHub.

The repository `.gitignore` excludes:

- `data/known_senders.txt`
- everything under `output/`
- common GAM/OAuth/service-account credential files

Before every commit, run:

```powershell
git status
```

and verify that no Workspace-derived data or credentials are staged.

## Requirements

- Python 3.10+
- GAMADV-XTD3 installed and already authorized for the Gmail data you intend
  to query
- Appropriate authorization from your organization for this monitoring use

No third-party Python packages are required.

## Test with one mailbox first

From PowerShell:

```powershell
python .\monitor.py --user your-test-user@yourdomain.org --query "newer_than:1d"
```

If `gam` is not in `PATH`, specify it:

```powershell
python .\monitor.py --gam "C:\GAMADV-XTD3\gam.exe" --user your-test-user@yourdomain.org --query "newer_than:1d"
```

## Create the initial baseline

The first run should normally be a baseline rather than treating every sender
as new.

For one test mailbox:

```powershell
python .\monitor.py --user your-test-user@yourdomain.org --query "newer_than:30d" --initialize
```

After validating the output, you can baseline the intended Workspace scope:

```powershell
python .\monitor.py --query "newer_than:30d" --initialize
```

This creates the private local file:

```text
data/known_senders.txt
```

It is ignored by Git.

## Daily run

After the baseline exists:

```powershell
python .\monitor.py --query "newer_than:1d"
```

If new senders are seen, the program outputs only addresses such as:

```text
billing@example.net
security-alerts@example.org
```

and creates a timestamped private file under `output/`.

## Suggested rollout

Do not start with all Workspace users until you have validated the query and
volume against a single test mailbox or small authorized scope.

A sensible sequence is:

1. One mailbox, last 1 day
2. One mailbox, last 30 days, baseline mode
3. Small authorized user scope
4. Full intended Workspace scope
5. Scheduled execution after you are satisfied with API volume and results

## Notes about `From` versus `Sender`

This project tracks the RFC `From` header. That identifies the apparent message
author and is generally the most useful field for this particular new-sender
workflow.

The SMTP `Sender` header is a different field and can identify an agent that
sent on behalf of the author. GAM can work with sender matching separately,
but this MVP intentionally stays focused on `From`.

## Limitations

A previously unseen sender is **not automatically malicious**.

Likewise, a previously known sender is not automatically safe. Display-name
spoofing, compromised accounts, lookalike domains, reply-to manipulation, and
other techniques require additional analysis.

This tool is a discovery aid, not a malware verdict or reputation engine.
