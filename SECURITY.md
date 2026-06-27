# Security

## Reporting

If you find a security issue, open a private report via GitHub **Security → Advisories** on this repository (or contact the maintainer directly).

## Secrets policy

**Never commit:**

- API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)
- Private keys (`.pem`, `.key`, SSH keys)
- `.env` files
- Session telemetry with personal driving data (already gitignored under `ac_app/data/` and `exports/`)

Use [`.env.example`](.env.example) as a template. Copy to `.env` locally only.

## Automated scanning

- **Gitleaks** runs on every push/PR ([`.github/workflows/secrets.yml`](.github/workflows/secrets.yml))
- Release zips are checked to exclude `.env` and key files

## Audit result (2026-06)

Full git history (`a60007f` → `a971bb4`) was scanned for:

- GitHub, OpenAI, Anthropic, and AWS key patterns
- PEM / private key blocks
- Hardcoded bearer tokens

**No secrets were found in committed history.** No history rewrite was required.

If you previously committed secrets elsewhere, rotate those keys immediately — removing from git does not invalidate leaked credentials.

## LLM keys (optional features)

Coach LLM and narrative generation read keys from **environment variables only** — never from the repo. The in-game AC app does not require cloud API keys.
