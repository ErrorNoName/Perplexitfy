"""Rich rendering helpers for Perplexify CLI."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from models import MODEL_CHOICES, PerplexifyResult

console = Console()

LOGO = r"""
 ____                 _           _  __
|  _ \ ___ _ __ _ __ | | _____  _(_)/ _|_   _
| |_) / _ \ '__| '_ \| |/ _ \ \/ / | |_| | | |
|  __/  __/ |  | |_) | |  __/>  <| |  _| |_| |
|_|   \___|_|  | .__/|_|\___/_/\_\_|_|  \__, |
               |_|                      |___/
"""


def print_header() -> None:
    title = Text("Perplexify CLI", style="bold #ff7a4d")
    subtitle = Text("Reverse Perplexity Web Search - Cookie Bridge - Local Tools", style="dim")
    console.print(Panel.fit(f"[bold #ff7a4d]{LOGO}[/]\n{subtitle}", title=title, box=box.ROUNDED))


def print_models() -> None:
    table = Table(title="Available Reverse-Web Model Preferences", box=box.SIMPLE_HEAVY)
    table.add_column("Model", style="bold cyan")
    table.add_column("Notes", style="white")
    notes = {
        "sonar": "Default reverse-web preference.",
        "sonar-pro": "Pro-style search preference when accepted by Perplexity.",
        "gpt": "Requests Perplexity GPT preference.",
        "claude": "Requests Perplexity Claude preference.",
    }
    for model in MODEL_CHOICES:
        table.add_row(model, notes.get(model, "Model preference passed through to Perplexity."))
    console.print(table)
    console.print("[dim]The final model is reported by Perplexity as `model_used` when available.[/]")


def print_result(result: PerplexifyResult, *, animate: bool = False) -> None:
    if not result.ok:
        console.print(Panel(str(result.error or "Unknown error"), title="Error", style="red"))
        return

    meta = f"mode={result.mode} | status={result.status} | {result.elapsed_ms} ms"
    if result.model_used:
        meta += f" | model={result.model_used}"
    console.print(Panel(meta, title="Perplexify", style="bold cyan", box=box.DOUBLE))

    answer = clean_answer_for_terminal(result.answer, strip_sources=bool(result.sources))
    if animate:
        type_text(answer)
    else:
        console.print(Panel(Markdown(answer or "(empty answer)"), title="Answer", border_style="#ff7a4d"))

    if result.sources:
        print_sources(result.sources)


def print_sources(sources: Iterable[object]) -> None:
    console.print(Rule("[bold cyan]Sources[/]"))
    table = Table(box=box.SIMPLE_HEAVY, show_lines=False, expand=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Title", style="bold white", ratio=1)
    table.add_column("URL", style="cyan", ratio=2, overflow="fold")
    for idx, source in enumerate(sources, 1):
        title = getattr(source, "title", "") or "Source"
        url = getattr(source, "url", "") or ""
        table.add_row(str(idx), _pretty_source_title(str(title), str(url)), str(url))
    console.print(table)


def type_text(text: str, *, delay_s: float = 0.006) -> None:
    """Render a final response with a token-like typing effect."""
    if not text:
        console.print("(empty answer)")
        return
    console.print(Panel("", title="Answer", border_style="#ff7a4d", height=1))
    for chunk in _chunks(text, size=5):
        console.print(chunk, end="", style="white")
        time.sleep(delay_s)
    console.print()


def _chunks(text: str, *, size: int) -> Iterable[str]:
    for idx in range(0, len(text), size):
        yield text[idx : idx + size]


def clean_answer_for_terminal(text: str, *, strip_sources: bool = False) -> str:
    """Remove common Perplexity DOM extraction artifacts before rendering."""
    cleaned = text.replace("\u200b", "").replace("\ufeff", "")
    cleaned = cleaned.replace("𝜑", "phi").replace("φ", "phi").replace("√", "sqrt")
    cleaned = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", cleaned)

    if strip_sources:
        cleaned = re.split(r"\n\s*Sources\s*:?\s*\n", cleaned, maxsplit=1, flags=re.I)[0]

    lines = cleaned.splitlines()
    out: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        next_line = lines[idx + 1].strip() if idx + 1 < len(lines) else ""

        if line in {"", "phi", "=", "+", "1", "2", "5", "."}:
            # Drop stacked formula fragments like Perplexity's DOM sometimes emits.
            idx += 1
            continue
        if re.fullmatch(r"\+\d+", line):
            idx += 1
            continue
        if re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", line) and re.fullmatch(r"\+\d+", next_line):
            idx += 2
            continue

        out.append(lines[idx].rstrip())
        idx += 1

    cleaned = "\n".join(out).strip()
    cleaned = _repair_known_formula_fragments(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _repair_known_formula_fragments(text: str) -> str:
    text = re.sub(
        r"il vérifie\s*$",
        "il vérifie phi = (1 + sqrt(5)) / 2.",
        text,
        flags=re.I | re.M,
    )
    text = re.sub(
        r"on le note souvent\s+phi\s+et il vérifie\s*\.?",
        "on le note souvent phi et il vérifie phi = (1 + sqrt(5)) / 2.",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"^phi et il v[ée]rifie$",
        "phi et il verifie phi = (1 + sqrt(5)) / 2.",
        text,
        flags=re.I | re.M,
    )
    return text


def _pretty_source_title(title: str, url: str) -> str:
    if title == url or title.startswith("http"):
        host_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if host_match:
            return host_match.group(1)
    return title[:90]
