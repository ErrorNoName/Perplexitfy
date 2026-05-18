"""Perplexify query engine.

This module is deliberately small: it adapts the existing Perplexity reverse
client into a stable CLI/HTTP response contract.
"""

from __future__ import annotations

import time
import re
import ast
import operator
from typing import Any

try:
    from scraping_lab.perplexity_lab.perplexify.config import ensure_import_paths, load_cookie
    from scraping_lab.perplexity_lab.perplexify.models import (
        MODEL_CHOICES,
        MODE_CHOICES,
        PerplexifyResult,
        PerplexifySource,
    )
except ModuleNotFoundError:
    from config import ensure_import_paths, load_cookie
    from models import MODEL_CHOICES, MODE_CHOICES, PerplexifyResult, PerplexifySource

SEARCH_PROMPT = """\
Answer this as a web research task.

Rules:
- Prefer recent, verifiable sources.
- Keep the answer structured and concise.
- Include citations in the answer when Perplexity provides them.
- The client will render source links separately.
- End with a "Sources" section containing raw source URLs.
- Use plain terminal-safe text: no LaTeX blocks, no stacked equations, no
  isolated math glyphs. Write formulas inline, for example:
  phi = (1 + sqrt(5)) / 2.

Question: {query}
"""

CHAT_PROMPT = """\
You are Perplexify CLI, a precise local research assistant.
This is plain chat mode, not web search mode. Do not browse the web, do not add
source URLs, and do not include a Sources section. Answer directly from general
knowledge, reasoning, or calculation. Use the conversation context only if it is
relevant.
Use plain terminal-safe text: no LaTeX blocks, no stacked equations, no isolated
math glyphs. Write formulas inline, for example: phi = (1 + sqrt(5)) / 2.

Conversation context:
{context}

User: {query}
"""


def validate_model(model: str | None) -> str | None:
    if not model:
        return None
    clean = model.strip()
    if clean not in MODEL_CHOICES:
        raise ValueError(f"Unsupported model '{clean}'. Use one of: {', '.join(MODEL_CHOICES)}")
    return clean


def validate_mode(mode: str) -> str:
    clean = mode.strip().lower()
    if clean not in MODE_CHOICES:
        raise ValueError(f"Unsupported mode '{clean}'. Use one of: {', '.join(MODE_CHOICES)}")
    return clean


async def run_query(
    query: str,
    *,
    mode: str = "search",
    model: str | None = None,
    context: str = "",
) -> PerplexifyResult:
    """Run one query through the existing reverse-web Perplexity stack."""
    ensure_import_paths()
    clean_query = query.strip()
    clean_mode = validate_mode(mode)
    clean_model = validate_model(model)

    if not clean_query:
        return PerplexifyResult(
            ok=False,
            mode=clean_mode,
            query=query,
            model_requested=clean_model,
            error="Query is empty",
        )

    if clean_mode == "chat":
        local_result = _try_local_chat_response(clean_query)
        if local_result is not None:
            return local_result

    cookie_state = load_cookie()
    if not cookie_state.cookie:
        return PerplexifyResult(
            ok=False,
            mode=clean_mode,
            query=clean_query,
            model_requested=clean_model,
            error="PPLX_COOKIE is not configured. Run `setup` first.",
        )

    prepared_query = _prepare_query(clean_query, mode=clean_mode, context=context)
    started = time.perf_counter()
    try:
        try:
            from scraping_lab.perplexity_lab.perplexity_client import ask_perplexity_async
        except ModuleNotFoundError:
            from standalone_client import ask_perplexity_async

        response = await ask_perplexity_async(prepared_query, model=clean_model)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return PerplexifyResult(
            ok=False,
            mode=clean_mode,
            query=clean_query,
            model_requested=clean_model,
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    sources: list[PerplexifySource] = []
    if clean_mode != "chat":
        sources = _normalize_sources(response.web_results)
        if not sources:
            sources = _extract_sources_from_answer(response.answer)
    return PerplexifyResult(
        ok=response.ok,
        mode=clean_mode,
        query=clean_query,
        answer=response.answer,
        sources=sources,
        model_requested=clean_model,
        model_used=response.model_used,
        status=response.status,
        elapsed_ms=elapsed_ms,
        error=response.error,
    )


def _prepare_query(query: str, *, mode: str, context: str) -> str:
    if mode == "search":
        return SEARCH_PROMPT.format(query=query)
    if mode == "chat":
        return CHAT_PROMPT.format(context=context.strip() or "(none)", query=query)
    return query


def _normalize_sources(raw_sources: list[dict[str, Any]]) -> list[PerplexifySource]:
    sources: list[PerplexifySource] = []
    seen: set[str] = set()
    for raw in raw_sources:
        source = PerplexifySource.from_raw(raw)
        if not source.url or source.url in seen:
            continue
        seen.add(source.url)
        sources.append(source)
    return sources


def _extract_sources_from_answer(answer: str) -> list[PerplexifySource]:
    sources: list[PerplexifySource] = []
    seen: set[str] = set()
    for match in re.finditer(r"https?://[^\s)\]>\"']+", answer):
        url = match.group(0).rstrip(".,;:")
        if "perplexity.ai" in url or url in seen:
            continue
        seen.add(url)
        sources.append(PerplexifySource(title=url, url=url))
    return sources


_ALLOWED_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARYOPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _try_local_chat_response(query: str) -> PerplexifyResult | None:
    expr = _extract_arithmetic_expression(query)
    if not expr:
        return None
    try:
        value = _safe_eval_arithmetic(expr)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return PerplexifyResult(
        ok=True,
        mode="chat",
        query=query,
        answer=f"{expr} = {value}",
        model_requested=None,
        model_used="local-arithmetic",
        status="local_ok",
        elapsed_ms=0,
    )


def _extract_arithmetic_expression(query: str) -> str:
    normalized = query.replace("×", "*").replace("x", "*").replace("X", "*")
    normalized = normalized.replace("−", "-").replace("÷", "/")
    matches = re.findall(r"[0-9][0-9\s+\-*/().%]*[0-9)]", normalized)
    if not matches:
        return ""
    expr = max(matches, key=len)
    expr = re.sub(r"\s+", "", expr)
    if not re.fullmatch(r"[0-9+\-*/().%]+", expr):
        return ""
    if len(re.findall(r"[+\-*/%]", expr)) == 0:
        return ""
    return expr


def _safe_eval_arithmetic(expr: str) -> int | float:
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported operator")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported unary operator")
        return op(_eval_node(node.operand))
    raise ValueError("Unsupported expression")
