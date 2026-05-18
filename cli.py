"""Command line interface for Perplexify."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import deque
from getpass import getpass
from typing import Any

from rich import box
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from scraping_lab.perplexity_lab.perplexify.config import (
    ENV_PATH,
    PRIVATE_COOKIE_PATH,
    ensure_import_paths,
    load_cookie,
    save_cookie,
)
from scraping_lab.perplexity_lab.perplexify.engine import run_query, validate_model
from scraping_lab.perplexity_lab.perplexify.models import MODEL_CHOICES
from scraping_lab.perplexity_lab.perplexify.render import (
    console,
    print_header,
    print_models,
    print_result,
)


def main(argv: list[str] | None = None) -> int:
    ensure_import_paths()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        print_header()
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/]")
        return 130
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="perplexify",
        description="Perplexify CLI: local reverse Perplexity web search.",
    )
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="Save and validate a Perplexity session cookie.")
    p_setup.add_argument("--no-env", action="store_true", help="Do not mirror the cookie into betbrain-core/.env.")
    p_setup.set_defaults(func=cmd_setup)

    p_status = sub.add_parser("status", help="Validate session and show rate limits.")
    p_status.set_defaults(func=cmd_status)

    p_status_json = sub.add_parser("status-json", help="Validate session and print machine-readable JSON.")
    p_status_json.set_defaults(func=cmd_status_json)

    p_models = sub.add_parser("models", help="Show supported model preferences.")
    p_models.set_defaults(func=cmd_models)

    for name, help_text in (
        ("ask", "Ask one question."),
        ("search", "Run a web research query and print sources."),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("query", nargs="*", help="Question to send.")
        p.add_argument("--model", choices=MODEL_CHOICES, default=None)
        p.add_argument("--animate", action="store_true", help="Animate the final answer.")
        p.set_defaults(func=cmd_query)

    p_chat = sub.add_parser("chat", help="Open an interactive chat loop.")
    p_chat.add_argument("--model", choices=MODEL_CHOICES, default=None)
    p_chat.set_defaults(func=cmd_chat)

    p_json = sub.add_parser("json", help="Machine-readable JSON/stdio mode.")
    p_json.add_argument("--mode", choices=("ask", "search", "chat"), default="search")
    p_json.add_argument("--query", default=None, help="Query text. If omitted, stdin is read.")
    p_json.add_argument("--model", choices=MODEL_CHOICES, default=None)
    p_json.add_argument("--context", default="", help="Optional chat context.")
    p_json.set_defaults(func=cmd_json)

    p_serve = sub.add_parser("serve", help="Run the local HTTP bridge.")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8787)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def cmd_setup(args: argparse.Namespace) -> int:
    print_header()
    console.print(
        Panel(
            "Paste the value of `__Secure-next-auth.session-token` from perplexity.ai cookies.\n"
            "The value is hidden while typing and will never be printed back.",
            title="Cookie Setup",
            box=box.ROUNDED,
        )
    )
    cookie = getpass("Perplexity cookie: ").strip()
    state = save_cookie(cookie, mirror_env=not args.no_env)
    console.print(f"[bold #ff7a4d]Saved private cookie:[/] {PRIVATE_COOKIE_PATH}")
    if not args.no_env:
        console.print(f"[bold #ff7a4d]Mirrored PPLX_COOKIE into:[/] {ENV_PATH}")
    console.print(f"[dim]Loaded cookie: {state.masked}[/]")
    if Confirm.ask("Validate the session now?", default=True):
        return cmd_status(argparse.Namespace())
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print_header()
    state = load_cookie()
    table = Table(title="Perplexify Status", box=box.SIMPLE_HEAVY)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Cookie source", state.source)
    table.add_row("Cookie", state.masked)

    if not state.cookie:
        console.print(table)
        console.print("[red]Cookie missing. Run `perplexify setup`.[/]")
        return 1

    from scraping_lab.perplexity_lab.perplexity_client import PerplexityClient

    client = PerplexityClient(cookie=state.cookie)
    session = client.validate_session()
    limits = client.get_rate_limits()
    client.close()

    if "error" in session:
        table.add_row("Session", f"ERROR: {session['error']}")
        console.print(table)
        return 1

    user = session.get("user") or {}
    table.add_row("Session", "OK")
    table.add_row("User", str(user.get("email") or user.get("name") or "unknown"))
    table.add_row("Subscription", str(user.get("subscriptionStatus") or "unknown"))
    table.add_row("Rate limits", json.dumps(limits, ensure_ascii=False)[:240])
    console.print(table)
    return 0


def cmd_status_json(_: argparse.Namespace) -> int:
    state = load_cookie()
    payload: dict[str, Any] = {
        "ok": False,
        "cookie_configured": bool(state.cookie),
        "cookie_source": state.source,
        "cookie": state.masked,
        "session": "missing",
        "user": "",
        "subscription": "",
        "remaining_pro": None,
        "remaining_research": None,
        "remaining_labs": None,
        "error": None,
    }
    if not state.cookie:
        payload["error"] = "Cookie missing. Run setup first."
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 1

    from scraping_lab.perplexity_lab.perplexity_client import PerplexityClient

    client = PerplexityClient(cookie=state.cookie)
    session = client.validate_session()
    limits = client.get_rate_limits()
    client.close()

    if "error" in session:
        payload["session"] = "error"
        payload["error"] = session["error"]
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 1

    user = session.get("user") or {}
    payload["ok"] = True
    payload["session"] = "OK"
    payload["user"] = str(user.get("email") or user.get("name") or "unknown")
    payload["subscription"] = str(user.get("subscriptionStatus") or "unknown")
    if isinstance(limits, dict):
        payload["remaining_pro"] = limits.get("remaining_pro")
        payload["remaining_research"] = limits.get("remaining_research")
        payload["remaining_labs"] = limits.get("remaining_labs")
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def cmd_models(_: argparse.Namespace) -> int:
    print_header()
    print_models()
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    query = " ".join(args.query).strip() or Prompt.ask("Query").strip()
    mode = "search" if args.command == "search" else "ask"
    validate_model(args.model)
    print_header()
    with console.status(
        "[bold #ff7a4d]Perplexify explores the web...[/]",
        spinner="bouncingBar",
        spinner_style="cyan",
    ):
        result = asyncio.run(run_query(query, mode=mode, model=args.model))
    print_result(result, animate=bool(args.animate))
    return 0 if result.ok else 1


def cmd_chat(args: argparse.Namespace) -> int:
    validate_model(args.model)
    print_header()
    console.print("[dim]Type /exit to leave, /models to list models, /status to check auth.[/]")
    history: deque[tuple[str, str]] = deque(maxlen=6)
    while True:
        query = Prompt.ask("[bold #ff7a4d]you[/]").strip()
        if not query:
            continue
        if query.lower() in {"/exit", "exit", "quit", "/quit"}:
            console.print("[dim]Bye.[/]")
            return 0
        if query.lower() == "/models":
            print_models()
            continue
        if query.lower() == "/status":
            cmd_status(argparse.Namespace())
            continue

        context = _history_context(history)
        with console.status(
            "[bold #ff7a4d]Perplexify composes the answer...[/]",
            spinner="bouncingBar",
            spinner_style="cyan",
        ):
            result = asyncio.run(run_query(query, mode="chat", model=args.model, context=context))
        print_result(result, animate=True)
        if result.ok:
            history.append(("user", query))
            history.append(("assistant", result.answer[:1600]))


def cmd_json(args: argparse.Namespace) -> int:
    if args.query is None:
        query = sys.stdin.read().strip()
    else:
        query = args.query.strip()
    result = asyncio.run(
        run_query(query, mode=args.mode, model=args.model, context=args.context)
    )
    print(json.dumps(result.to_dict(), ensure_ascii=True, indent=2))
    return 0 if result.ok else 1


def cmd_serve(args: argparse.Namespace) -> int:
    from scraping_lab.perplexity_lab.perplexify.server import run_server

    run_server(host=args.host, port=args.port, reload=args.reload)
    return 0


def _history_context(history: deque[tuple[str, str]]) -> str:
    if not history:
        return ""
    lines = []
    for role, text in history:
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
