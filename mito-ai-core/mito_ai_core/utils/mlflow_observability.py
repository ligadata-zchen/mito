# Copyright (c) Saga Inc.
# Distributed under the terms of the GNU Affero General Public License v3.0 License.

"""
Optional MLflow tracing layer for Mito AI completions.

Patterned after the alphaiterations agentic-ai-usecases observability module
(https://github.com/alphaiterations/agentic-ai-usecases/tree/main/advanced/genai-observability).

Design goals:
 - **Opt-in**: disabled unless `MITO_MLFLOW_ENABLED=true`. mlflow is treated as
   an optional dependency — ImportError is swallowed.
 - **Fail-open**: any mlflow error (init, span creation, attribute setting) is
   swallowed. User-facing LLM requests must never fail because of telemetry.
 - **Side-by-side**: this module is parallel to the existing Mixpanel/CSV
   telemetry in telemetry_utils.py. Both run; neither replaces the other.

Usage in provider_manager:

    from mito_ai_core.utils import mlflow_observability as mlobs

    with mlobs.llm_span(
        name=f"completion.{message_type.value}",
        model=resolved_model,
        message_type=message_type.value,
    ) as span:
        span.set_input_tokens(estimated_input_tokens)
        completion = await provider.request_completions(...)
        span.set_completion(completion)

Environment variables:
 - MITO_MLFLOW_ENABLED   "true" to enable; default false
 - MLFLOW_TRACKING_URI   forwarded to mlflow.set_tracking_uri (e.g. "http://localhost:5000")
 - MLFLOW_EXPERIMENT     experiment name; defaults to "mito-ai"
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# Tri-state cache: None = not yet checked, True/False = decision cached.
_ENABLED: Optional[bool] = None
_INITIALIZED = False
_INIT_FAILED = False


def is_enabled() -> bool:
    """True when MITO_MLFLOW_ENABLED is set truthy. Cached after first read."""
    global _ENABLED
    if _ENABLED is None:
        _ENABLED = os.environ.get("MITO_MLFLOW_ENABLED", "false").strip().lower() in (
            "1", "true", "yes", "on"
        )
    return _ENABLED


def _init_once() -> None:
    """Configure tracking URI + experiment exactly once. Idempotent and fail-open."""
    global _INITIALIZED, _INIT_FAILED
    if _INITIALIZED or _INIT_FAILED or not is_enabled():
        return
    try:
        import mlflow  # type: ignore[import-not-found]
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT", "mito-ai"))
        _INITIALIZED = True
    except Exception as e:  # pragma: no cover - depends on mlflow install
        logger.debug("MLflow observability init failed; disabling: %s", e)
        _INIT_FAILED = True


# ---------------------------------------------------------------------------
# Token and cost estimation
# ---------------------------------------------------------------------------

# Per-1M-tokens public list pricing in USD. Conservative defaults are used for
# unknown models so cost.usd is at least populated. These are list prices; users
# with negotiated contracts should override via the MITO_MODEL_PRICING_OVERRIDES
# env var (JSON dict) if needed — out of scope for this initial cut.
_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-4.1":   {"input": 2.50,  "output": 10.00},
    "gpt-5":     {"input": 5.00,  "output": 15.00},
    "gpt-5.2":   {"input": 5.00,  "output": 15.00},
    # Anthropic
    "claude-haiku-4-5-20251001":  {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-6":            {"input": 15.00, "output": 75.00},
    # Google
    "gemini-3-flash-preview":     {"input": 0.10, "output": 0.40},
    "gemini-3.1-pro-preview":     {"input": 1.25, "output": 5.00},
}

_DEFAULT_PRICING = {"input": 0.15, "output": 0.60}


def estimate_tokens(text: Optional[str]) -> int:
    """Rough English token count: 4 chars ≈ 1 token. Mirrors alphaiterations."""
    if not text:
        return 0
    return len(text) // 4


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost based on per-1M-tokens list pricing. Falls back to a generic rate
    so unknown models still get a non-zero cost.usd attribute."""
    pricing = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# Span handle
# ---------------------------------------------------------------------------


class SpanHandle:
    """No-op-friendly handle returned by llm_span().

    Stays inert when MLflow is disabled — callers can unconditionally invoke
    set_completion / set_input_tokens without worrying about gating.
    """

    __slots__ = ("_span", "completion", "input_tokens", "extra_attrs")

    def __init__(self) -> None:
        self._span: Any = None
        self.completion: Optional[str] = None
        self.input_tokens: Optional[int] = None
        self.extra_attrs: Dict[str, Any] = {}

    def set_completion(self, completion: Optional[str]) -> None:
        self.completion = completion

    def set_input_tokens(self, count: Optional[int]) -> None:
        self.input_tokens = count

    def set_attribute(self, key: str, value: Any) -> None:
        """Stage an attribute. Applied on span exit so the caller doesn't have
        to know whether MLflow is enabled."""
        self.extra_attrs[key] = value


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def record_completion(
    name: str,
    model: str,
    message_type: str,
    *,
    completion: Optional[str] = None,
    input_tokens: Optional[int] = None,
    duration_ms: Optional[int] = None,
    success: bool = True,
    error: Optional[BaseException] = None,
    span_type: str = "LLM",
    **attrs: Any,
) -> None:
    """Post-hoc span emission for a completed (or failed) LLM call.

    Designed for call sites where the existing try/except/retry structure makes
    a `with` block awkward: just compute completion as usual, then call this
    once at the success or error point. Each invocation creates its own span,
    so retries get one span per attempt.

    Fail-open. Returns None even on internal errors.
    """
    if not is_enabled() or _INIT_FAILED:
        return
    _init_once()
    if _INIT_FAILED:
        return
    try:
        import mlflow  # type: ignore[import-not-found]
    except ImportError:
        return

    try:
        with mlflow.start_span(name=name, span_type=span_type) as span:
            try:
                span.set_attribute("model", model)
                span.set_attribute("message_type", message_type)
                span.set_attribute("status", "ok" if success else "error")
                for k, v in attrs.items():
                    span.set_attribute(k, v)
                if duration_ms is not None:
                    span.set_attribute("duration_ms", duration_ms)
                if completion is not None:
                    output_tokens = estimate_tokens(completion)
                    span.set_attribute("tokens.output", output_tokens)
                    span.set_attribute("bytes.output", len(completion))
                    if input_tokens is not None:
                        span.set_attribute("tokens.input", input_tokens)
                        span.set_attribute(
                            "cost.usd",
                            calculate_cost(model, input_tokens, output_tokens),
                        )
                elif input_tokens is not None:
                    span.set_attribute("tokens.input", input_tokens)
                if error is not None:
                    span.set_attribute("error.type", type(error).__name__)
                    span.set_attribute("error.message", str(error)[:1000])
            except Exception:
                pass
    except Exception as e:
        logger.debug("MLflow record_completion failed; ignoring: %s", e)


@contextlib.contextmanager
def llm_span(
    name: str,
    model: str,
    message_type: str,
    span_type: str = "LLM",
    **attrs: Any,
) -> Iterator[SpanHandle]:
    """Wrap an LLM request with an MLflow span if observability is enabled.

    Yields a SpanHandle even when MLflow is disabled or unavailable, so call
    sites can be uniform. Attributes recorded on success:
        model, message_type, span_type
        duration_ms
        tokens.input  (if set_input_tokens was called)
        tokens.output (estimated from completion)
        cost.usd      (if input tokens are known)
        bytes.output  (length of completion)
        plus any **attrs and any handle.set_attribute(...) calls.
    Errors set:
        error.type, error.message, status="error"
    """
    handle = SpanHandle()

    # Fast path: not enabled, or mlflow not importable, or init previously failed.
    if not is_enabled() or _INIT_FAILED:
        yield handle
        return

    _init_once()
    if _INIT_FAILED:
        yield handle
        return

    try:
        import mlflow  # type: ignore[import-not-found]
    except ImportError:
        # Treat missing optional dep as "disabled" without spamming logs.
        yield handle
        return

    start_ts = time.monotonic()
    span_cm: Any = None
    try:
        span_cm = mlflow.start_span(name=name, span_type=span_type)
        span = span_cm.__enter__()
        handle._span = span
    except Exception as e:
        logger.debug("MLflow start_span failed; continuing without trace: %s", e)
        yield handle
        return

    error_to_record: Optional[BaseException] = None
    try:
        try:
            span.set_attribute("model", model)
            span.set_attribute("message_type", message_type)
            for k, v in attrs.items():
                span.set_attribute(k, v)
        except Exception:
            pass
        try:
            yield handle
        except BaseException as e:
            error_to_record = e
            raise
    finally:
        try:
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            try:
                span.set_attribute("duration_ms", duration_ms)
            except Exception:
                pass

            for k, v in handle.extra_attrs.items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass

            if handle.completion is not None:
                try:
                    output_tokens = estimate_tokens(handle.completion)
                    span.set_attribute("tokens.output", output_tokens)
                    span.set_attribute("bytes.output", len(handle.completion))
                    if handle.input_tokens is not None:
                        span.set_attribute("tokens.input", handle.input_tokens)
                        span.set_attribute(
                            "cost.usd",
                            calculate_cost(model, handle.input_tokens, output_tokens),
                        )
                except Exception:
                    pass

            if error_to_record is not None:
                try:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(error_to_record).__name__)
                    span.set_attribute("error.message", str(error_to_record)[:1000])
                except Exception:
                    pass
        finally:
            try:
                span_cm.__exit__(
                    type(error_to_record) if error_to_record else None,
                    error_to_record,
                    error_to_record.__traceback__ if error_to_record else None,
                )
            except Exception:
                # Last line of defense: never let mlflow tear down a request.
                pass
