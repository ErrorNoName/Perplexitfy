"""Perplexify smoke tests.

The live mode intentionally uses the cookie already configured in
``betbrain-core/.env`` or the private Perplexify store. It never prints the
cookie value.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys

from scraping_lab.perplexity_lab.perplexify.config import (
    REPO_ROOT,
    ensure_import_paths,
    load_cookie,
)
from scraping_lab.perplexity_lab.perplexify.engine import run_query

SEARCH_TEST_QUERY = (
    "Find current Arsenal FC injury news. Answer briefly, then list exactly "
    "three raw source URLs under a Sources heading."
)
CHAT_TEST_QUERY = (
    "In one short paragraph, explain what you just found about Arsenal injuries "
    "and include at least one raw source URL."
)


def main(argv: list[str] | None = None) -> int:
    ensure_import_paths()
    parser = argparse.ArgumentParser(description="Smoke-test Perplexify CLI.")
    parser.add_argument("--live", action="store_true", help="Run live Perplexity search/chat checks.")
    args = parser.parse_args(argv)

    failures: list[str] = []
    _check_cli_commands(failures)

    if args.live:
        live_ok = asyncio.run(_check_live_queries(failures))
        if not live_ok:
            failures.append("live queries did not complete successfully")
    else:
        print("[SKIP] Live query checks skipped. Use --live to test cookie/search/chat.")

    if failures:
        print("\n[FAIL] Perplexify smoke test failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\n[OK] Perplexify smoke test passed.")
    return 0


def _check_cli_commands(failures: list[str]) -> None:
    print("[TEST] Python module help")
    _run_command(
        [sys.executable, "-m", "scraping_lab.perplexity_lab.perplexify", "--help"],
        failures,
        "module help failed",
    )

    print("[TEST] Python module models")
    _run_command(
        [sys.executable, "-m", "scraping_lab.perplexity_lab.perplexify", "models"],
        failures,
        "module models failed",
    )

    wrapper = REPO_ROOT / "scraping_lab" / "perplexity_lab" / "perplexify_cli.py"
    print("[TEST] Wrapper script models")
    _run_command(
        [sys.executable, str(wrapper), "models"],
        failures,
        "wrapper models failed",
    )

    print("[TEST] JSON blank-query contract")
    proc = _run_command(
        [
            sys.executable,
            "-m",
            "scraping_lab.perplexity_lab.perplexify",
            "json",
            "--mode",
            "search",
            "--query",
            " ",
        ],
        failures,
        "json blank-query command failed unexpectedly",
        accepted_exit_codes={1},
    )
    if proc and proc.stdout:
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            failures.append("json blank-query output was not valid JSON")
        else:
            if data.get("error") != "Query is empty":
                failures.append("json blank-query did not return the expected error")


async def _check_live_queries(failures: list[str]) -> bool:
    cookie = load_cookie()
    print(f"[TEST] Cookie configured: {'yes' if cookie.cookie else 'no'}")
    print(f"[TEST] Cookie source: {cookie.source}")
    if not cookie.cookie:
        failures.append("cookie missing; run perplexify_setup.bat or configure PPLX_COOKIE")
        return False

    from scraping_lab.perplexity_lab.perplexity_client import PerplexityClient

    client = PerplexityClient(cookie=cookie.cookie)
    session = client.validate_session()
    client.close()
    if "error" in session:
        failures.append(f"session validation failed: {session['error']}")
        return False

    user = session.get("user") or {}
    print(f"[OK] Session valid for: {user.get('email') or user.get('name') or 'unknown'}")

    print("[TEST] Live search with source extraction")
    search_result = await _run_with_source_retry(
        SEARCH_TEST_QUERY,
        mode="search",
        model="sonar",
        failures=failures,
        label="live search",
    )
    _print_result_summary("search", search_result)
    if not search_result.ok:
        failures.append(f"live search failed: {search_result.error}")
    if not _has_external_sources(search_result):
        failures.append("live search returned no external source URLs")

    print("[TEST] Live chat with source extraction")
    context = search_result.answer[:1200] if search_result.ok else ""
    if search_result.sources:
        source_lines = [
            f"- {source.title}: {source.url}"
            for source in search_result.sources[:5]
        ]
        context = f"{context}\n\nKnown source URLs:\n" + "\n".join(source_lines)
    chat_result = await _run_with_source_retry(
        CHAT_TEST_QUERY,
        mode="chat",
        model="sonar",
        context=context,
        failures=failures,
        label="live chat",
    )
    _print_result_summary("chat", chat_result)
    if not chat_result.ok:
        failures.append(f"live chat failed: {chat_result.error}")
    if not _has_external_sources(chat_result):
        failures.append("live chat returned no external source URLs")

    return search_result.ok and chat_result.ok


async def _run_with_source_retry(
    query: str,
    *,
    mode: str,
    model: str,
    failures: list[str],
    label: str,
    context: str = "",
):
    result = None
    retry_query = query
    for attempt in range(1, 4):
        result = await run_query(retry_query, mode=mode, model=model, context=context)
        if result.ok and _has_external_sources(result):
            if attempt > 1:
                print(f"[OK] {label} found sources after retry {attempt}")
            return result
        retry_query = (
            f"{query}\n\nImportant: return raw external URLs. Do not use citation labels only. "
            f"This is retry {attempt + 1}."
        )
    if result is None:
        failures.append(f"{label} did not run")
        return await run_query(query, mode=mode, model=model, context=context)
    return result


def _run_command(
    command: list[str],
    failures: list[str],
    failure_message: str,
    *,
    accepted_exit_codes: set[int] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    accepted = accepted_exit_codes or {0}
    try:
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            timeout=60,
        )
    except Exception as exc:
        failures.append(f"{failure_message}: {exc}")
        return None
    if proc.returncode not in accepted:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        failures.append(f"{failure_message}: exit {proc.returncode} {detail}")
    return proc


def _has_external_sources(result: object) -> bool:
    sources = getattr(result, "sources", [])
    for source in sources:
        url = getattr(source, "url", "")
        if url.startswith("http") and "perplexity.ai" not in url:
            return True
    return False


def _print_result_summary(label: str, result: object) -> None:
    sources = getattr(result, "sources", [])
    answer = getattr(result, "answer", "")
    print(
        f"[OK] {label}: ok={getattr(result, 'ok', False)} "
        f"answer_len={len(answer)} sources={len(sources)} "
        f"model={getattr(result, 'model_used', None)}"
    )
    for idx, source in enumerate(sources[:5], 1):
        print(f"  [{idx}] {getattr(source, 'title', 'source')}: {getattr(source, 'url', '')}")


if __name__ == "__main__":
    raise SystemExit(main())
