"""Run the public Docling Graph pipeline and retain its native outputs."""

import json
import logging
import os
import threading
import time
from dataclasses import asdict

import httpx

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

from docling_graph.exceptions import ClientError
from docling_graph.llm_clients.litellm import LiteLLMClient
from docling_graph.pipeline import PipelineOrchestrator, PipelineStage


def projection_status(native, stage):
    """Count native projection separately from the complete extracted object list."""
    field, entity = {
        "A": ("observations", "Observation"),
        "B": ("relations", "RelationProposal"),
        "C": ("findings", "FindingProposal"),
    }.get(stage, (None, None))
    if not native or not field:
        return None
    source_count = sum(len(model.get(field, [])) for model in native.get("extracted", []))
    graph = native.get("graph")
    projected = (
        sum(n.get("__class__") == entity for n in graph.get("nodes", []))
        if graph is not None
        else None
    )
    return dict(
        source_objects=source_count,
        projected_objects=projected,
        incomplete=projected is not None and projected < source_count,
        object_list_authoritative=True,
    )


class _StreamIdleTimeoutError(TimeoutError):
    """Raised when an active LLM stream stops delivering content/reasoning chunks."""


def _is_mock_callable(fn) -> bool:
    return bool(
        hasattr(fn, "_mock_name")
        or type(fn).__module__.startswith("unittest.mock")
    )


def _classify_llm_exception(exc: BaseException, *, is_structured: bool, elapsed_s: float, timeout_s: float) -> dict:
    """Translate raw SDK/network exceptions into secret-free status codes and messages."""
    status_code = getattr(exc, "status_code", None)
    cause = getattr(exc, "cause", None) or getattr(exc, "__cause__", None)
    if status_code is None and cause is not None:
        status_code = getattr(cause, "status_code", None)
    try:
        status_code = int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        status_code = None

    cls_name = type(exc).__name__
    raw_msg = f"{cls_name}: {exc}"
    if cause is not None:
        raw_msg += f" | {type(cause).__name__}: {cause}"
    lower = raw_msg.lower()
    fmt = "json_schema" if is_structured else "json_object"

    if isinstance(exc, _StreamIdleTimeoutError):
        return dict(
            reason="stream_idle_timeout",
            http_status=status_code,
            retryable=(not is_structured) and (elapsed_s < 120.0),
            detail=f"Stream-Leerlauf nach {elapsed_s:.1f}s ohne Token-Fortschritt ({fmt})",
        )
    if (
        isinstance(exc, (TimeoutError, httpx.TimeoutException))
        or "timeout" in cls_name.lower()
        or "timed out" in lower
    ):
        return dict(
            reason="request_timeout",
            http_status=status_code,
            retryable=(not is_structured) and (elapsed_s < 120.0),
            detail=f"Zeitüberschreitung nach {elapsed_s:.1f}s (Limit {timeout_s:.0f}s) bei {fmt}",
        )
    if (
        "cannot connect to host" in lower
        or "hosted_vllmexception" in lower
        or "connection refused" in lower
        or "apiconnectionerror" in lower
        or isinstance(exc, httpx.ConnectError)
    ):
        code = status_code or 502
        return dict(
            reason="provider_backend_unavailable",
            http_status=code,
            retryable=not is_structured,
            detail=f"Upstream-Modellserver nicht erreichbar (HTTP {code})",
        )
    if status_code == 429 or "ratelimit" in lower:
        return dict(
            reason="rate_limited",
            http_status=429,
            retryable=True,
            detail="API-Ratenlimit erreicht (HTTP 429)",
        )
    if status_code in (401, 403) or "authentication" in lower or "unauthorized" in lower:
        code = status_code or 401
        return dict(
            reason="auth_failed",
            http_status=code,
            retryable=False,
            detail=f"API-Authentifizierung fehlgeschlagen (HTTP {code})",
        )
    if status_code == 400 and is_structured:
        return dict(
            reason="structured_schema_rejected",
            http_status=400,
            retryable=False,
            detail="Anbieter lehnt json_schema ab (HTTP 400)",
        )
    if status_code and status_code >= 500:
        return dict(
            reason="provider_server_error",
            http_status=status_code,
            retryable=not is_structured,
            detail=f"Anbieter-Serverfehler (HTTP {status_code}) bei {fmt}",
        )
    http_part = f", HTTP {status_code}" if status_code else ""
    return dict(
        reason=cls_name,
        http_status=status_code,
        retryable=False,
        detail=f"Modellaufruf fehlgeschlagen ({cls_name}{http_part})",
    )


class DiagnosticClient(LiteLLMClient):
    """Attach LiteLLM's synchronous observer, strict timeouts, and live console hooks."""

    def _emit_progress(self, payload: dict) -> None:
        cb = getattr(self, "progress", None)
        if not callable(cb):
            return
        try:
            cb(payload)
        except TypeError:
            cb(str(payload.get("phase") or "model_request"))

    def _timeout_budgets(self) -> tuple[float, float, float]:
        wall_s = max(1.0, float(getattr(self, "timeout", 180) or 180))
        explicit = bool(getattr(self, "explicit_timeout", False))
        idle_s = min(wall_s, max(15.0, min(75.0, wall_s * 0.6))) if wall_s >= 25.0 else wall_s
        active_wall_s = (
            wall_s
            if explicit or not getattr(self, "provider_output", False)
            else max(wall_s, 540.0)
        )
        return wall_s, idle_s, active_wall_s

    def _build_request(self, *args, **kwargs):
        request = super()._build_request(*args, **kwargs)
        if getattr(self, "provider_output", False):
            # OpenAI-compatible FAU accepts an omitted limit and budgets the
            # completion on the server against its combined context window.
            request.pop("max_tokens", None)

        wall_s, idle_s, _ = self._timeout_budgets()
        configured_retries = max(
            0, int(getattr(self._reliability, "max_retries", 1) if self._reliability else 1)
        )
        # Prevent silent SDK retry multiplication (LiteLLM x OpenAI client);
        # retries are executed explicitly with live diagnostics in _call_api.
        request["num_retries"] = 0
        request["max_retries"] = 0
        request["timeout"] = httpx.Timeout(
            connect=min(15.0, wall_s),
            write=min(30.0, wall_s),
            read=idle_s,
            pool=min(15.0, wall_s),
        )

        appendix = getattr(self, "system_appendix", None)
        if isinstance(appendix, str) and appendix.strip():
            msgs = list(request.get("messages") or [])
            injected = False
            for idx, m in enumerate(msgs):
                if m.get("role") == "system" and isinstance(m.get("content"), str):
                    msgs[idx] = dict(m, content=f"{m['content'].rstrip()}\n\n{appendix.strip()}")
                    injected = True
                    break
            if not injected:
                msgs.insert(0, {"role": "system", "content": appendix.strip()})
            request["messages"] = msgs

        record = {
            k: request[k]
            for k in (
                "model",
                "max_tokens",
                "temperature",
                "top_p",
                "top_k",
                "num_retries",
            )
            if k in request
        }
        record["timeout"] = wall_s
        record["read_timeout_s"] = round(idle_s, 1)
        record["configured_retries"] = configured_retries
        record["response_format"] = (request.get("response_format") or {}).get("type")
        record["output_policy"] = (
            "provider" if getattr(self, "provider_output", False) else "native_client"
        )
        if getattr(self, "request_diagnostics", None) is not None:
            lock = getattr(self, "_diag_lock", None)
            record["messages"] = [
                {"role": message["role"], "text": message["content"]}
                for message in request.get("messages", [])
                if isinstance(message.get("content"), str)
            ]
            if lock is not None:
                with lock:
                    self.request_diagnostics.append(record)
            else:
                self.request_diagnostics.append(record)
            request["logger_fn"] = lambda event: observe_request(record, event, lock)
        request["_ux_diag_record"] = record
        return request

    def _run_monitored_attempt(
        self,
        req_kwargs: dict,
        *,
        wall_s: float,
        idle_s: float,
        active_wall_s: float,
        record: dict | None,
        lock,
    ) -> tuple[str, dict]:
        import litellm

        use_stream = not _is_mock_callable(litellm.completion) and not getattr(
            self, "disable_stream_monitor", False
        )
        call_kwargs = dict(req_kwargs)
        if use_stream:
            call_kwargs["stream"] = True
            call_kwargs["stream_options"] = {"include_usage": True}

        started = time.monotonic()
        state = {
            "last_progress": started,
            "chunks": 0,
            "content_parts": [],
            "reasoning_seen": False,
            "finish_reason": None,
            "usage": None,
            "model_used": None,
            "non_stream_response": None,
            "error": None,
            "stream_obj": None,
        }
        done = threading.Event()

        def _consume_stream(stream_resp):
            state["stream_obj"] = stream_resp
            for chunk in stream_resp:
                is_dict = isinstance(chunk, dict)
                c_usage = chunk.get("usage") if is_dict else getattr(chunk, "usage", None)
                if c_usage:
                    if hasattr(c_usage, "model_dump"):
                        c_usage = c_usage.model_dump()
                    elif not isinstance(c_usage, dict):
                        c_usage = dict(c_usage)
                    state["usage"] = c_usage
                    state["last_progress"] = time.monotonic()

                c_model = chunk.get("model") if is_dict else getattr(chunk, "model", None)
                if c_model:
                    state["model_used"] = c_model

                choices = chunk.get("choices") if is_dict else getattr(chunk, "choices", None)
                if choices:
                    ch0 = choices[0]
                    ch_dict = isinstance(ch0, dict)
                    fin = ch0.get("finish_reason") if ch_dict else getattr(ch0, "finish_reason", None)
                    if fin:
                        state["finish_reason"] = fin
                    delta = ch0.get("delta") if ch_dict else getattr(ch0, "delta", None)
                    if delta is not None:
                        d_dict = isinstance(delta, dict)
                        piece = delta.get("content") if d_dict else getattr(delta, "content", None)
                        rc = (
                            (delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking"))
                            if d_dict
                            else (
                                getattr(delta, "reasoning_content", None)
                                or getattr(delta, "reasoning", None)
                                or getattr(delta, "thinking", None)
                            )
                        )
                        if piece:
                            state["content_parts"].append(str(piece))
                            state["chunks"] += 1
                            state["last_progress"] = time.monotonic()
                        elif rc:
                            state["reasoning_seen"] = True
                            state["chunks"] += 1
                            state["last_progress"] = time.monotonic()

        def _worker():
            try:
                try:
                    raw = litellm.completion(**call_kwargs)
                except Exception as first_exc:
                    if use_stream and "stream" in str(first_exc).lower() and getattr(first_exc, "status_code", None) == 400:
                        fallback_kw = {k: v for k, v in call_kwargs.items() if k not in ("stream", "stream_options")}
                        raw = litellm.completion(**fallback_kw)
                    else:
                        raise
                is_non_stream = isinstance(raw, dict) or (
                    hasattr(raw, "choices")
                    and getattr(raw, "object", None) != "chat.completion.chunk"
                    and not hasattr(raw, "__next__")
                )
                if is_non_stream:
                    state["non_stream_response"] = raw
                    state["last_progress"] = time.monotonic()
                else:
                    _consume_stream(raw)
            except BaseException as exc:
                state["error"] = exc
            finally:
                done.set()

        t = threading.Thread(target=_worker, name="ux-maind-llm-call", daemon=True)
        t.start()

        last_heartbeat = started
        while not done.wait(timeout=0.25):
            now_m = time.monotonic()
            elapsed = now_m - started
            idle = now_m - state["last_progress"]
            eff_wall = active_wall_s if state["chunks"] > 0 else wall_s
            if idle >= idle_s or elapsed >= eff_wall:
                stream_ref = state.get("stream_obj")
                close_fn = getattr(stream_ref, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass
                if state["chunks"] > 0 and idle >= idle_s and elapsed < eff_wall:
                    raise _StreamIdleTimeoutError(f"Idle for {idle:.1f}s after {state['chunks']} chunks")
                raise TimeoutError(f"LLM request exceeded deadline ({elapsed:.1f}s / {eff_wall:.0f}s)")
            if state["chunks"] > 0 and now_m - last_heartbeat >= 20.0:
                last_heartbeat = now_m
                self._emit_progress(
                    dict(
                        phase="model_streaming",
                        model=self.model,
                        duration_s=round(elapsed, 1),
                        chunks=state["chunks"],
                        detail=f"Stream aktiv ({round(elapsed)}s · {state['chunks']} Chunks empfangen)",
                    )
                )

        if state["error"] is not None:
            raise state["error"]

        elapsed_total = round(time.monotonic() - started, 2)
        if state["non_stream_response"] is not None:
            response = state["non_stream_response"]
            r_dict = isinstance(response, dict)
            choices = response.get("choices", []) if r_dict else (getattr(response, "choices", None) or [])
            if not choices:
                raise ClientError("LiteLLM returned no choices", details={"model": self.model})
            ch0 = choices[0]
            ch0_d = isinstance(ch0, dict)
            msg = (ch0.get("message") or {}) if ch0_d else (getattr(ch0, "message", None) or {})
            msg_d = isinstance(msg, dict)
            content = msg.get("content") if msg_d else getattr(msg, "content", None)
            if not content:
                raise ClientError("LiteLLM returned empty content", details={"model": self.model})
            fin_reason = ch0.get("finish_reason") if ch0_d else getattr(ch0, "finish_reason", None)
            usage = response.get("usage") if r_dict else getattr(response, "usage", None)
            if usage is not None and hasattr(usage, "model_dump"):
                usage = usage.model_dump()
            model_used = (response.get("model") if r_dict else getattr(response, "model", None)) or self.model
            reasoning_seen = bool(
                (msg.get("reasoning_content") or msg.get("reasoning"))
                if msg_d
                else (getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None))
            )
            content_str = str(content)
        else:
            content_str = "".join(state["content_parts"])
            if not content_str:
                raise ClientError("LiteLLM returned empty content", details={"model": self.model})
            fin_reason = state["finish_reason"]
            usage = state["usage"]
            model_used = state["model_used"] or self.model
            reasoning_seen = state["reasoning_seen"]

        if record is not None:
            details = _extract_usage_details(usage)
            def _update_ok():
                record["duration_s"] = elapsed_total
                record["finish_reason"] = fin_reason
                record["content"] = content_str
                if isinstance(usage, dict):
                    record["usage"] = usage
                if details:
                    record["usage_details"] = details
                record["reasoning_present"] = bool(
                    reasoning_seen or (details and details.get("reasoning_tokens"))
                )
            if lock is not None:
                with lock:
                    _update_ok()
            else:
                _update_ok()

        return content_str, {
            "finish_reason": fin_reason,
            "model": model_used,
            "usage": usage,
        }

    def _call_api(self, messages, **params):
        is_structured = bool(params.get("structured_output", True))
        fmt_label = "json_schema" if is_structured else "json_object"
        wall_s, idle_s, active_wall_s = self._timeout_budgets()
        configured_retries = max(
            0, int(getattr(self._reliability, "max_retries", 1) if self._reliability else 1)
        )
        max_attempts = 1 if is_structured else (1 + min(configured_retries, 2))

        last_exc = None
        for attempt in range(1, max_attempts + 1):
            attempt_start = time.monotonic()
            request = self._build_request(messages, **params)
            record = request.pop("_ux_diag_record", None)
            lock = getattr(self, "_diag_lock", None)
            if record is not None:
                record["attempt"] = attempt
                record["max_attempts"] = max_attempts

            self._emit_progress(
                dict(
                    phase="model_request",
                    model=self.model,
                    response_format=fmt_label,
                    timeout_s=round(wall_s, 1),
                    read_timeout_s=round(idle_s, 1),
                    attempt=attempt,
                    max_attempts=max_attempts,
                    detail=(
                        f"Modellaufruf ({fmt_label}, Timeout {round(wall_s)}s)"
                        if max_attempts == 1
                        else f"Modellaufruf ({fmt_label}, Versuch {attempt}/{max_attempts}, Timeout {round(wall_s)}s)"
                    ),
                )
            )
            try:
                return self._run_monitored_attempt(
                    request,
                    wall_s=wall_s,
                    idle_s=idle_s,
                    active_wall_s=active_wall_s,
                    record=record,
                    lock=lock,
                )
            except Exception as exc:
                last_exc = exc
                elapsed_s = round(time.monotonic() - attempt_start, 2)
                if isinstance(exc, ClientError):
                    if record is not None:
                        record["duration_s"] = elapsed_s
                        record["error_reason"] = "empty_response"
                    raise
                err_info = _classify_llm_exception(
                    exc, is_structured=is_structured, elapsed_s=elapsed_s, timeout_s=wall_s
                )
                if record is not None:
                    def _update_err():
                        record["duration_s"] = elapsed_s
                        record["error_reason"] = err_info["reason"]
                        record["http_status"] = err_info["http_status"]
                        record["error_detail"] = err_info["detail"]
                    if lock is not None:
                        with lock:
                            _update_err()
                    else:
                        _update_err()

                can_retry = (
                    attempt < max_attempts
                    and err_info["retryable"]
                    and err_info["reason"] != "provider_backend_unavailable"
                )
                if can_retry:
                    backoff_s = min(4.0, 1.5 * attempt)
                    self._emit_progress(
                        dict(
                            phase="model_retry",
                            status="WARN",
                            model=self.model,
                            response_format=fmt_label,
                            reason=err_info["reason"],
                            http_status=err_info["http_status"],
                            duration_s=elapsed_s,
                            timeout_s=round(wall_s, 1),
                            attempt=attempt,
                            max_attempts=max_attempts,
                            detail=f"{err_info['detail']} — neuer Versuch {attempt + 1}/{max_attempts} in {backoff_s:.1f}s",
                        )
                    )
                    time.sleep(backoff_s)
                    continue

                if is_structured:
                    self.last_call_diagnostics.update(
                        {
                            "structured_failed": True,
                            "fallback_error_class": type(exc).__name__,
                            "error_reason": err_info["reason"],
                            "http_status": err_info["http_status"],
                        }
                    )
                    phase_name = (
                        "stream_stalled"
                        if err_info["reason"] == "stream_idle_timeout"
                        else "model_timeout"
                        if err_info["reason"] == "request_timeout"
                        else "structured_fallback"
                    )
                    self._emit_progress(
                        dict(
                            phase=phase_name,
                            status="WARN",
                            model=self.model,
                            response_format=fmt_label,
                            reason=err_info["reason"],
                            http_status=err_info["http_status"],
                            duration_s=elapsed_s,
                            timeout_s=round(wall_s, 1),
                            attempt=attempt,
                            max_attempts=max_attempts,
                            detail=f"{err_info['detail']} — Fallback auf json_object",
                        )
                    )
                    raise ClientError(
                        "Structured output request failed. Disable structured output for this model "
                        "or use a model/provider that supports response_format json_schema.",
                        details={
                            "stage": "api_request",
                            "reason": err_info["reason"],
                            "http_status": err_info["http_status"],
                            "model": self.model,
                            "provider": self._config.provider_id,
                        },
                        cause=exc,
                    ) from exc

                err_phase = (
                    "stream_stalled"
                    if err_info["reason"] == "stream_idle_timeout"
                    else "model_timeout"
                    if err_info["reason"] == "request_timeout"
                    else "api_error"
                )
                self._emit_progress(
                    dict(
                        phase=err_phase,
                        status="ERROR",
                        model=self.model,
                        response_format=fmt_label,
                        reason=err_info["reason"],
                        error=err_info["reason"],
                        http_status=err_info["http_status"],
                        duration_s=elapsed_s,
                        timeout_s=round(wall_s, 1),
                        attempt=attempt,
                        max_attempts=max_attempts,
                        detail=err_info["detail"],
                    )
                )
                raise ClientError(
                    f"LiteLLM API call failed: {type(exc).__name__}",
                    details={
                        "stage": "api_request",
                        "reason": err_info["reason"],
                        "http_status": err_info["http_status"],
                        "model": self.model,
                    },
                    cause=exc,
                ) from exc
        raise ClientError("LLM request exhausted attempts", details={"model": self.model}, cause=last_exc)


def _extract_usage_details(usage):
    if not isinstance(usage, dict):
        return None
    comp_details = usage.get("completion_tokens_details") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    reasoning = comp_details.get("reasoning_tokens")
    if reasoning is None:
        reasoning = usage.get("reasoning_tokens")
    cached = prompt_details.get("cached_tokens")
    if cached is None:
        cached = usage.get("cache_read_input_tokens")
    out = {}
    if isinstance(reasoning, int) and reasoning >= 0:
        out["reasoning_tokens"] = reasoning
    if isinstance(cached, int) and cached >= 0:
        out["cached_tokens"] = cached
    return out or None


def observe_request(record, event, lock=None):
    payload = (event.get("additional_args") or {}).get("complete_input_dict")
    raw = event.get("original_response")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None

    def _apply():
        if isinstance(payload, dict):
            record["provider_parameters"] = {
                k: payload[k]
                for k in (
                    "max_tokens",
                    "max_completion_tokens",
                    "temperature",
                    "top_p",
                    "top_k",
                )
                if k in payload
            }
        if not isinstance(raw, dict):
            return
        usage = raw.get("usage")
        record["usage"] = usage
        details = _extract_usage_details(usage)
        if details:
            record["usage_details"] = details
        choices = raw.get("choices") or []
        if choices:
            choice = choices[0]
            message = choice.get("message") or {}
            record.update(
                finish_reason=choice.get("finish_reason"),
                content=message.get("content"),
                reasoning_present=bool(
                    message.get("reasoning_content")
                    or message.get("reasoning")
                    or (details and details.get("reasoning_tokens"))
                ),
            )
        elif "stop_reason" in raw:
            blocks = raw.get("content") or []
            record.update(
                finish_reason=raw["stop_reason"],
                content=[x.get("text") for x in blocks if x.get("type") == "text"],
                reasoning_present=any(x.get("type") == "thinking" for x in blocks),
            )

    if lock is not None:
        with lock:
            _apply()
    else:
        _apply()


class RetainContext(PipelineStage):
    """Keep the native debug context available when a later stage raises."""

    context = None

    def name(self):
        return "Workspace diagnostics"

    def execute(self, context):
        self.context = context
        return context


def run(path, template, client, options, progress=lambda stage: None, *, system_appendix=None):
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm
    from docling_graph import PipelineConfig
    from docling_graph.core.exporters.json_exporter import graph_to_dict
    from docling_graph.logging_utils import ensure_logging
    from pydantic_core import to_json

    # The native clients can log provider errors and document content at debug
    # level. Keep the run trace locally and never send it to logging sinks.
    litellm.disable_logging = True
    ensure_logging()
    logging.getLogger("docling_graph").setLevel(logging.CRITICAL)
    logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
    planning_client = client
    if (
        getattr(client, "provider_output", False)
        and getattr(client, "max_tokens", 0) <= 4096
        and (getattr(client, "context_limit", 0) or 0) >= 32768
    ):
        plan_budget = min(32768, max(8192, client.context_limit // 8))
        planning_client = DiagnosticClient(
            client.model_config.model_copy(
                update={
                    "max_output_tokens": plan_budget,
                    "generation": client.model_config.generation.model_copy(
                        update={"max_tokens": plan_budget}
                    ),
                }
            )
        )
        planning_client.provider_output = True
        planning_client.explicit_timeout = getattr(client, "explicit_timeout", False)
        planning_client.limit_origins = getattr(client, "limit_origins", {})
        planning_client.directory_limits = getattr(client, "directory_limits", False)
    extra_cfg = {}
    for opt_key in (
        "use_chunking",
        "chunk_max_tokens",
        "parallel_workers",
        "dense_dedupe",
        "dense_fill_context",
        "structured_sparse_check",
    ):
        if opt_key in options and options[opt_key] is not None:
            extra_cfg[opt_key] = options[opt_key]
    proc_mode = options.get("processing_mode", "many-to-one")
    if proc_mode == "one-to-one":
        try:
            from pathlib import Path as _P

            p_obj = _P(path) if isinstance(path, (str, os.PathLike)) else None
            if p_obj and p_obj.suffix.lower() == ".json" and p_obj.is_file():
                raw_doc = json.loads(p_obj.read_text(encoding="utf-8"))
                if isinstance(raw_doc, dict) and not raw_doc.get("pages"):
                    proc_mode = "many-to-one"
            elif hasattr(path, "pages") and not getattr(path, "pages", None):
                proc_mode = "many-to-one"
        except Exception:
            pass
    config = PipelineConfig(
        source=path,
        template=template,
        inference="remote",
        provider_override=planning_client.provider,
        model_override=planning_client.model,
        llm_client=planning_client,
        extraction_contract=options.get("extraction_contract", "auto"),
        processing_mode=proc_mode,
        llm_input_format=options.get("llm_input_format", "auto"),
        gleaning_enabled=options.get("gleaning_enabled", True),
        structured_output=options.get("structured_output", True),
        provenance="detailed",
        dump_to_disk=False,
        debug=True,
        **extra_cfg,
    )
    planning_client._diag_lock = threading.Lock()
    planning_client.system_appendix = system_appendix
    planning_client.last_call_diagnostics = {}
    planning_client.request_diagnostics = []
    planning_client.progress = progress
    capture = RetainContext()
    pipeline = PipelineOrchestrator(config)
    pipeline.stages.insert(0, capture)
    failure = None
    try:
        result = pipeline.run()
    except Exception as error:
        result = capture.context
        failure = dict(type=type(error).__name__, details=getattr(error, "details", {}))
        failure["causes"] = []
        seen = set()
        while error and id(error) not in seen:
            seen.add(id(error))
            failure["causes"].append(
                dict(
                    type=type(error).__name__,
                    status_code=getattr(error, "status_code", None),
                    details=getattr(error, "details", {}),
                )
            )
            error = getattr(error, "cause", None) or error.__cause__
    finally:
        planning_client.system_appendix = None
        client.last_call_diagnostics = planning_client.last_call_diagnostics
        client.request_diagnostics = planning_client.request_diagnostics

    trace_events = (
        [asdict(event) for event in result.trace_data.events]
        if result and result.trace_data
        else []
    )
    salvaged = bool(
        not failure
        and any(ev.get("event_type") == "validation_error_raw_data" for ev in trace_events)
    )
    receipt = dict(
        config={
            **config.model_dump(
                mode="json",
                exclude={
                    "template",
                    "source",
                    "docling_serve_api_key",
                    "docling_serve_headers",
                },
            ),
            "plan_max_output_tokens": planning_client.max_tokens,
        },
        template=template.model_json_schema(),
        trace=trace_events,
        provenance=result.provenance.model_dump(mode="json")
        if result and result.provenance is not None
        else None,
        last_response=planning_client.last_call_diagnostics,
        requests=planning_client.request_diagnostics,
        extracted=[
            model.model_dump(mode="json") for model in (result.extracted_models or [])
        ]
        if result
        else [],
        graph=graph_to_dict(result.knowledge_graph)
        if result and result.knowledge_graph is not None
        else None,
        salvaged=salvaged,
        error=failure,
    )
    serialized = to_json(receipt, serialize_unknown=True, fallback=str)
    key = client.model_config.connection.api_key
    if key and key.get_secret_value() not in ("local", "metadata-preview"):
        serialized = serialized.replace(key.get_secret_value().encode(), b"[REDACTED]")
    return json.loads(serialized)


def outcome(native):
    """Safe status from native failures and observed request stages."""
    failure = native["error"]
    events = native["trace"]
    stages = list(dict.fromkeys(e["stage"] for e in events))
    salvaged = bool(native.get("salvaged")) or (
        not failure and any(e.get("event_type") == "validation_error_raw_data" for e in events)
    )
    if not failure:
        return dict(stage="source_resolution", stages=stages, salvaged=salvaged)
    details = failure["details"]
    stage = details.get("stage") or "native_extraction"
    reason = details.get("reason") or failure["type"]
    calls = native["requests"]
    last = native["last_response"]
    cause = native["error"]["causes"][-1]
    http_status = cause.get("status_code")
    detail = None
    last_err_call = next((c for c in reversed(calls) if c.get("error_reason")), None)
    if stage == "Extraction":
        fallback_err = next(
            (
                str((e.get("payload") or {}).get("error_message") or "")
                for e in reversed(events)
                if e.get("event_type") == "structured_output_fallback_triggered"
            ),
            "",
        )
        if last_err_call:
            stage = "api_request"
            reason = last_err_call["error_reason"]
            http_status = http_status or last_err_call.get("http_status")
            detail = last_err_call.get("error_detail")
        elif "InternalServerError" in fallback_err or "Cannot connect to host" in fallback_err:
            stage = "api_request"
            reason = "provider_backend_unavailable"
            http_status = http_status or 500
            detail = f"Upstream-Modellserver nicht erreichbar (HTTP {http_status})"
        elif http_status or last.get("fallback_error_class"):
            stage = "api_request"
            if last.get("error_reason"):
                reason = last["error_reason"]
            http_status = http_status or last.get("http_status")
        if any(e["event_type"] == "validation_error_raw_data" for e in events):
            stage = "pydantic_validation"
        elif "parsed_json" not in last and last.get("raw_response"):
            stage = "response_parsing"
        elif any("finish_reason" in c and not c.get("content") for c in calls):
            stage = "api_response"
    out = dict(
        stage=stage,
        stages=stages,
        reason=reason,
        cause=cause["type"],
        http_status=http_status,
        salvaged=salvaged,
    )
    if detail:
        out["detail"] = detail
    return out
