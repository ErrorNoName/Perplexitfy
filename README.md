# Perplexify CLI

Perplexify CLI is a local terminal and HTTP wrapper around Footix's Perplexity
Reverse Web Search stack. It uses the existing cookie-based Browser Bridge first
and the reverse SSE client as fallback. It does not call the official
`api.perplexity.ai` endpoint.

## Install

Perplexify now carries its own quick scripts and local dependency file. From
this folder:

```powershell
cd scraping_lab\perplexity_lab\perplexify
.\perplexify_setup.bat
```

Manual install:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## First Run

Fast Windows setup from the Perplexify folder:

```powershell
.\perplexify_setup.bat
```

This installs Python dependencies, installs Playwright Chromium, then opens the
cookie setup flow.

Manual setup:

```powershell
python -m scraping_lab.perplexity_lab.perplexify setup
```

Paste the `__Secure-next-auth.session-token` cookie from a logged-in
Perplexity session. The CLI stores it in `cookie.private.json` and mirrors it to
the local Perplexify `.env` by default.

For GitHub/public sharing, commit `.env.example` and never commit `.env`.
Perplexify reads configuration in this order:

1. Process environment variable `PPLX_COOKIE`
2. Local `perplexify\.env`
3. Legacy Footix `betbrain-core\.env` fallback
4. Local `cookie.private.json`

Use `--no-env` if you only want the private CLI store:

```powershell
python -m scraping_lab.perplexity_lab.perplexify setup --no-env
```

## Commands

Quick launcher from the repository root:

```powershell
cd scraping_lab\perplexity_lab\perplexify
.\perplexify_launch.bat
.\perplexify_launch.bat search "Latest PSG injury news"
.\perplexify_launch.bat serve --host 127.0.0.1 --port 8787
```

With no arguments, `perplexify_launch.bat` opens chat mode.

Direct Python commands:

```powershell
python -m scraping_lab.perplexity_lab.perplexify status
python -m scraping_lab.perplexity_lab.perplexify models
python -m scraping_lab.perplexity_lab.perplexify ask "Explain Perplexity reverse SSE"
python -m scraping_lab.perplexity_lab.perplexify search "Latest PSG injury news"
python -m scraping_lab.perplexity_lab.perplexify chat --model sonar
```

Search mode prints a formatted answer followed by a `Sources` table when the
reverse stack extracts web URLs.

Chat mode keeps a small in-memory conversation context and animates the final
answer in the terminal.

## Modern Go Terminal App

Perplexify also ships a modern keyboard-driven terminal app in Go under
`go-tui/`. It uses the Python JSON backend for real Perplexity reverse-web
queries, but the interface is a native terminal app with menus, panels, loading
animations, and a dark coral theme.

Install Go first from `https://go.dev/dl/`, then run from this folder:

```powershell
.\perplexify_go_run.bat
```

Build a Windows executable:

```powershell
.\perplexify_go_build.bat
.\go-tui\dist\perplexify.exe
```

Launch the built executable when available, falling back to `go run`:

```powershell
.\perplexify_app.bat
```

Keyboard controls:

- `up/down` or `j/k`: move in menus
- `enter`: select, submit search, or send chat message
- `esc`: return home
- `q`: back/quit depending on screen
- `ctrl+c`: quit immediately
- `r`: refresh status screen

The Go app intentionally uses no green UI states. The palette is black,
coral/orange, white, grey, and small cyan accents for technical metadata.
The layout is responsive: wide terminals show side-by-side panels, while
smaller terminals switch to stacked panels and a compact logo so the interface
does not get crushed.

## Direct Script Wrapper

```powershell
python scraping_lab\perplexity_lab\perplexify_cli.py search "latest Arsenal injuries"
```

## JSON / Stdio Integration

Use this when another program wants to launch Perplexify as a subprocess:

```powershell
python -m scraping_lab.perplexity_lab.perplexify json --mode search --query "latest Ligue 1 injuries"
```

If `--query` is omitted, stdin is read:

```powershell
"latest Ligue 1 injuries" | python -m scraping_lab.perplexity_lab.perplexify json --mode search
```

Stable response shape:

```json
{
  "ok": true,
  "mode": "search",
  "query": "...",
  "answer": "...",
  "sources": [{"title": "...", "url": "...", "snippet": "", "host": ""}],
  "model_requested": "sonar",
  "model_used": "perplexity-pro-browser",
  "status": "bridge_ok",
  "elapsed_ms": 12000,
  "error": null
}
```

## Local HTTP Bridge

```powershell
python -m scraping_lab.perplexity_lab.perplexify serve --host 127.0.0.1 --port 8787
```

Endpoints:

- `GET /health`
- `GET /models`
- `POST /ask`
- `POST /search`
- `POST /chat`

Example body:

```json
{
  "query": "latest Real Madrid injury news",
  "model": "sonar",
  "context": ""
}
```

Keep the default `127.0.0.1` bind for local extension/software usage.

## Live Test

Run all launch paths plus live search/chat validation:

```powershell
cd scraping_lab\perplexity_lab\perplexify
.\perplexify_test.bat
```

The live test reads the cookie from the local `.env` first, validates the
session, runs one search query, runs one chat query, and fails if no external
source URLs are returned.
