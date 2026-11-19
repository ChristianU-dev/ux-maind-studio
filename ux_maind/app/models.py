"""Non-secret profiles and the native Docling Graph client configuration; no request engine."""

import os
import re
from urllib.parse import urlsplit

FAU = "https://hub.nhr.fau.de/api/llmgw/v1"
FAU_REFERENCE = {
    # Historical shared window of the deployment, used if discovery fails.
    "Qwen/Qwen3.6-35B-A3B-FP8": 262144,
}
PRESETS = {
    "nhr_fau": {"base_url": FAU, "key_env": "LLMAPI_KEY"},
    "ollama": {"base_url": "http://127.0.0.1:11434", "key_env": ""},
    "gemini": {"key_env": "GEMINI_TRIAL_KEY"},
    "openai": {"key_env": "OPENAI_API_KEY"},
    "anthropic": {"key_env": "ANTHROPIC_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY"},
    "mistral": {"key_env": "MistralAPI_Key"},
    "groq": {"key_env": "GROQ_API_KEY"},
    "nvidia_nim": {"key_env": "NvidiaAPI_Key"},
    "custom": {"base_url": "", "key_env": ""},
}
ENV_ALIASES = {
    "nhr_fau": ("LLMAPI_KEY", "FAU_API_KEY", "NHR_FAU_API_KEY"),
    "gemini": ("GEMINI_TRIAL_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GeminiAI_Key", "GeminiAPI_Key"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "mistral": ("MistralAPI_Key", "MISTRAL_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "nvidia_nim": ("NvidiaAPI_Key", "NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"),
}
PROVIDER_CATALOG_INFO = {
    "nhr_fau": {
        "label": "NHR@FAU Academic Gateway",
        "deployment": "OpenAI-kompatibles Hochschul-Gateway · Open-Weights",
        "privacy_tier": "Wissenschafts-Cluster · DSGVO-freundlich",
        "cost_tier": "Hochschulkontingent (0,00 $ API-Abrechnung)",
        "key_env": "LLMAPI_KEY",
        "recommended": True,
    },
    "ollama": {
        "label": "Ollama (Lokal / Offline)",
        "deployment": "100 % Lokale Inferenz auf eigener Hardware",
        "privacy_tier": "Maximaler Datenschutz · kein externer Netzwerkverkehr",
        "cost_tier": "Lokal (0,00 $ API-Abrechnung)",
        "key_env": "",
        "recommended": True,
    },
    "gemini": {
        "label": "Google Gemini API",
        "deployment": "Cloud API · Native Multimodal- & Langkontext-Modelle",
        "privacy_tier": "Externe Cloud-API (explizite Sendefreigabe pro Lauf)",
        "cost_tier": "Nutzungsbasiert / API-Guthaben",
        "key_env": "GEMINI_TRIAL_KEY",
        "recommended": False,
    },
    "openai": {
        "label": "OpenAI API",
        "deployment": "Cloud API · Strukturierte JSON-Schema-Modelle",
        "privacy_tier": "Externe Cloud-API (explizite Sendefreigabe pro Lauf)",
        "cost_tier": "Pay-per-Token",
        "key_env": "OPENAI_API_KEY",
        "recommended": False,
    },
    "anthropic": {
        "label": "Anthropic Claude API",
        "deployment": "Cloud API · Sprach- & Vision-Modelle",
        "privacy_tier": "Externe Cloud-API (explizite Sendefreigabe pro Lauf)",
        "cost_tier": "Pay-per-Token / Laborkontingent",
        "key_env": "ANTHROPIC_API_KEY",
        "recommended": False,
    },
    "openrouter": {
        "label": "OpenRouter Gateway",
        "deployment": "OpenAI-kompatibles Multi-Modell-Gateway",
        "privacy_tier": "Externe Cloud-API",
        "cost_tier": "Pay-per-Token / Free-Modelle",
        "key_env": "OPENROUTER_API_KEY",
        "recommended": False,
    },
    "mistral": {
        "label": "Mistral AI",
        "deployment": "EU-Cloud API · Open-Weights & Frontier",
        "privacy_tier": "EU-Cloud-Anbieter",
        "cost_tier": "Pay-per-Token",
        "key_env": "MistralAPI_Key",
        "recommended": False,
    },
    "groq": {
        "label": "Groq Cloud",
        "deployment": "Cloud API · Schnelle Open-Weights-Inferenz",
        "privacy_tier": "Externe Cloud-API",
        "cost_tier": "Free Tier / Pay-per-Token",
        "key_env": "GROQ_API_KEY",
        "recommended": False,
    },
    "nvidia_nim": {
        "label": "NVIDIA NIM",
        "deployment": "Cloud API oder Self-Hosted Container",
        "privacy_tier": "Cloud oder On-Prem Container",
        "cost_tier": "Credits / Enterprise",
        "key_env": "NvidiaAPI_Key",
        "recommended": False,
    },
    "custom": {
        "label": "Eigener OpenAI-Endpunkt (vLLM / LM Studio / LiteLLM)",
        "deployment": "Beliebiger lokaler oder selbstgehosteter /v1-Server",
        "privacy_tier": "Abhängig vom gewählten Zielserver",
        "cost_tier": "Selbstverwaltet",
        "key_env": "",
        "recommended": False,
    },
}


class ModelAccessError(ValueError):
    """A safe, user-actionable model setup failure."""


def detected_env_vars():
    """Return safe names (never values) of API-key-like environment variables present in the shell."""
    ignore_prefixes = ("VSCODE_", "ELECTRON_", "CHROME_", "WT_", "FPS_", "NPM_", "CONDA_", "UV_")
    found = []
    for name, val in os.environ.items():
        if not val or not val.strip():
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            continue
        if name.upper().startswith(ignore_prefixes):
            continue
        if re.search(r"(?:API_KEY|LLM.*KEY|TRIAL_KEY|AI_KEY|_TOKEN)$", name, re.IGNORECASE):
            found.append(name)
    return sorted(set(found))


def env_status():
    """Return safe boolean credential readiness per provider without exposing secret values."""
    out = {}
    for provider, preset in PRESETS.items():
        primary = preset.get("key_env", "")
        candidates = (primary, *ENV_ALIASES.get(provider, ())) if primary else ()
        matched_env = next((k for k in candidates if k and os.environ.get(k, "").strip()), "")
        is_local = provider == "ollama"
        configured = True if is_local else bool(matched_env)
        info = PROVIDER_CATALOG_INFO.get(provider, {})
        out[provider] = dict(
            key_env=primary,
            detected_env=matched_env or primary,
            default_base_url=preset.get("base_url", ""),
            configured=configured,
            local=is_local,
            label=info.get("label", provider),
            deployment=info.get("deployment", ""),
            privacy_tier=info.get("privacy_tier", ""),
            cost_tier=info.get("cost_tier", ""),
            recommended=bool(info.get("recommended")),
        )
    return out


def profile_options(raw):
    from docling_graph.llm_clients.config import (
        GenerationOverrides,
        ReliabilityOverrides,
    )
    from pydantic import ValidationError

    provider = str(raw.get("provider", "")).strip()
    model = str(raw.get("model", "")).strip()
    if not provider or not model:
        raise ValueError("Anbieter und freie Modellkennung erforderlich")
    base = str(
        raw.get("base_url") or PRESETS.get(provider, {}).get("base_url", "")
    ).rstrip("/")
    if base:
        url = urlsplit(base)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Basis-URL ohne Zugangsdaten, Query oder Fragment eingeben"
            )
    if provider == "custom" and not base:
        raise ValueError("OpenAI-kompatible Basis-URL erforderlich")
    if provider == "nhr_fau" and base != FAU:
        raise ValueError("FAU-Profil verwendet ausschließlich den festen FAU-Gateway")
    env = str(raw.get("key_env", PRESETS.get(provider, {}).get("key_env", ""))).strip()
    if env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env):
        raise ValueError("Name einer Umgebungsvariable eingeben, keinen Schlüsselwert")
    try:
        generation = GenerationOverrides.model_validate(
            raw.get("generation") or {}
        ).model_dump(exclude_none=True)
        reliability = ReliabilityOverrides.model_validate(
            raw.get("reliability") or {}
        ).model_dump(exclude_none=True)
        if reliability.get("timeout_s", 1) < 1 or reliability.get("max_retries", 0) < 0:
            raise ValueError()
        values = {
            name: int(raw[name])
            for name in ("context_limit", "max_output_tokens")
            if raw.get(name) not in (None, "")
        }
        if any(v <= 0 for v in values.values()):
            raise ValueError()
    except (ValidationError, ValueError, TypeError):
        raise ValueError("Ungültige native Modellparameter") from None
    if (
        generation.get("max_tokens")
        and values.get("max_output_tokens")
        and generation["max_tokens"] > values["max_output_tokens"]
    ):
        raise ValueError(
            "max_tokens übersteigt das gewählte Ausgabebudget max_output_tokens; beide Werte bewusst anpassen"
        )
    # Deliberately no credential value, arbitrary connection headers or unvalidated fields.
    if "structured_output" in raw and type(raw["structured_output"]) is not bool:
        raise ValueError("Native JSONschema-Option als booleschen Wert angeben")
    native = {}
    for name, values_allowed in (
        ("extraction_contract", ("auto", "direct", "dense")),
        ("processing_mode", ("many-to-one", "one-to-one")),
        ("llm_input_format", ("auto", "doclang", "doclang-geo", "markdown")),
        ("dense_dedupe", ("off", "standard", "aggressive")),
        ("dense_fill_context", ("scoped", "full")),
    ):
        if name in raw and raw[name] not in (None, ""):
            if raw[name] not in values_allowed:
                raise ValueError(f"Ungültige native Option: {name}")
            native[name] = raw[name]
    for bool_name in ("gleaning_enabled", "stage_gleaning", "use_chunking"):
        if bool_name in raw and raw[bool_name] is not None:
            if type(raw[bool_name]) is not bool:
                raise ValueError(f"Booleschen Wert angeben für {bool_name}")
            native[bool_name] = raw[bool_name]
    for int_name in ("chunk_max_tokens", "parallel_workers"):
        if raw.get(int_name) not in (None, ""):
            try:
                ival = int(raw[int_name])
                if ival <= 0:
                    raise ValueError()
                native[int_name] = ival
            except (ValueError, TypeError):
                raise ValueError(f"Positiven Ganzzahlwert angeben für {int_name}") from None
    return dict(
        provider=provider,
        model=model,
        base_url=base,
        key_env=env,
        generation=generation,
        **({"reliability": reliability} if reliability else {}),
        **(
            {"structured_output": raw["structured_output"]}
            if "structured_output" in raw
            else {}
        ),
        **values,
        **native,
    )


def runtime_key(options, manual=None):
    env = options.get("key_env", "")
    return (
        manual
        or (os.environ.get(env) if env else None)
        or next(
            (
                os.environ[n]
                for n in ENV_ALIASES.get(options["provider"], ())
                if os.environ.get(n)
            ),
            None,
        )
    )


def model_info(litellm_model):
    import litellm

    litellm.suppress_debug_info = True
    try:
        return litellm.get_model_info(litellm_model) or {}
    except Exception:
        return {}


def positive(value):
    return value if type(value) is int and value > 0 else None


def limits(clean, info, directory):
    """Translate published limits and profile values into native overrides."""
    reference = (
        FAU_REFERENCE.get(clean["model"]) if clean["provider"] == "nhr_fau" else None
    )
    shared = positive(directory.get("max_model_len")) or positive(
        directory.get("max_input_tokens")
    )
    output = positive(directory.get("max_output_tokens"))
    sdk_context = positive(info.get("max_input_tokens"))
    sdk_output = positive(info.get("max_output_tokens"))
    choices = (
        (
            "context_limit",
            (
                (clean.get("context_limit"), "Profil"),
                (shared, "FAU-Modellverzeichnis"),
                (sdk_context, "LiteLLM-Modellmetadaten"),
                (reference, "Dokumentierte FAU-Referenz"),
            ),
        ),
        (
            "max_output_tokens",
            (
                (clean.get("max_output_tokens"), "Profil"),
                (
                    output if shared and output and output < shared else None,
                    "FAU-Modellverzeichnis",
                ),
                (sdk_output, "LiteLLM-Modellmetadaten"),
                (
                    clean["generation"].get("max_tokens"),
                    "Profil · generation.max_tokens",
                ),
            ),
        ),
    )
    values, origins = {}, {}
    for name, candidates in choices:
        value, origin = next(
            ((v, o) for v, o in candidates if v),
            (None, "Bibliotheksfallback · Anbietergrenze unbekannt"),
        )
        if value:
            values[name] = value
        origins[name] = origin
    return values, origins


def vision_capability(clean, *, directory=()):
    if clean["provider"] == "nhr_fau" and clean["model"] in FAU_REFERENCE:
        return True
    if clean["provider"] == "nhr_fau":
        entry = next((m for m in directory if m["id"] == clean["model"]), {})
        value = entry.get("supports_vision")
        if type(value) is bool:
            return value
        if entry.get("mode") in ("embedding", "rerank"):
            return False
    detected = _infer_open_multimodal(clean["model"], item_meta=None)
    if type(detected) is bool and (
        not clean["base_url"] or clean["provider"] in ("nhr_fau", "ollama", "openrouter", "custom")
    ):
        return detected
    if clean["base_url"] and clean["base_url"] != vision_endpoint(clean["provider"]):
        return None  # SDK metadata cannot confirm a different deployment.
    value = model_info(f"{clean['provider']}/{clean['model']}").get("supports_vision")
    return value if type(value) is bool else None


def vision_endpoint(provider):
    if provider == "anthropic":
        return ""
    if provider == "gemini":
        return DIRECTORIES[provider] + "/openai"
    return DIRECTORIES.get(provider, "")


def vision_options(options):
    clean = profile_options(options)
    return {
        **clean,
        "base_url": clean["base_url"] or vision_endpoint(clean["provider"]),
    }


def connect(options, *, preview=False, discover_limits=False):
    from docling_graph.llm_clients.config import resolve_effective_model_config
    from .native_graph import DiagnosticClient

    clean = profile_options(options)
    provider = clean["provider"]
    routing = "openai" if provider in ("nhr_fau", "openrouter", "custom") else provider
    key = "metadata-preview" if preview else runtime_key(clean, options.get("key"))
    local = urlsplit(clean["base_url"]).hostname in ("127.0.0.1", "localhost", "::1")
    if not preview and not key and provider not in ("ollama", "custom") and not local:
        raise ModelAccessError("Schlüsselvariable fehlt. Profil oder Umgebung prüfen.")
    explicit_rel = clean.get("reliability") or {}
    explicit_timeout = "timeout_s" in explicit_rel
    overrides = {
        "connection": {"api_key": key or "local"},
        "generation": clean["generation"],
        "reliability": {
            "timeout_s": int(explicit_rel.get("timeout_s") or 180),
            "max_retries": int(explicit_rel["max_retries"]) if "max_retries" in explicit_rel else 1,
        },
    }
    if clean["base_url"]:
        overrides["connection"]["base_url"] = clean["base_url"]
    prefix = ("ollama_chat" if provider == "ollama" else routing) + "/"
    route = prefix + clean["model"].removeprefix(prefix)
    info = model_info(route) if not clean["base_url"] else {}
    entry = {}
    if (
        provider == "nhr_fau"
        and (not preview or discover_limits and runtime_key(clean))
        and ("context_limit" not in clean or "max_output_tokens" not in clean)
    ):
        try:
            entry = next(
                (m for m in fau_entries(options) if m["id"] == clean["model"]), {}
            )
        except ValueError:
            pass  # A directory outage does not prevent a direct model request.
    resolved, origins = limits(clean, info, entry)
    overrides.update(resolved)
    reference = FAU_REFERENCE.get(clean["model"]) if provider == "nhr_fau" else None
    shared = (
        positive(entry.get("max_model_len"))
        or positive(entry.get("max_input_tokens"))
        or reference
    )
    request_budget = clean["generation"].get("max_tokens") or resolved.get(
        "max_output_tokens"
    )
    if shared and request_budget and request_budget >= shared:
        raise ModelAccessError(
            "Ausgabebudget belegt bereits das gemeinsame FAU-Kontextfenster"
        )
    config = resolve_effective_model_config(routing, clean["model"], overrides)
    client = DiagnosticClient(
        config.model_copy(
            update={
                "provider_id": provider,
                "litellm_model": route,
            }
        )
    )
    client.limit_origins = origins
    client.directory_limits = bool(entry)
    client.explicit_timeout = explicit_timeout
    client.provider_output = (
        provider == "nhr_fau"
        and not clean["generation"].get("max_tokens")
        and "max_output_tokens" not in clean
        and origins["max_output_tokens"] != "FAU-Modellverzeichnis"
    )
    return client


def describe(raw, *, client=None, discover_vision=False, discover_limits=False):
    """Preview the client and optionally query the authenticated FAU directory."""
    import litellm

    clean = profile_options(raw)
    is_preview = client is None
    client = client or connect(clean, preview=True, discover_limits=discover_limits)
    vision = vision_capability(clean)
    vision_url = clean["base_url"] or vision_endpoint(clean["provider"])
    host = urlsplit(vision_url).hostname
    local = host in ("127.0.0.1", "localhost", "::1")
    key_available = bool(runtime_key(clean))
    vision_ready = bool(host and (key_available or local))
    if (
        discover_vision
        and clean["provider"] == "nhr_fau"
        and vision_ready
        and vision is None
    ):
        try:
            vision = vision_capability(clean, directory=fau_entries(raw))
        except ValueError:
            pass
    try:
        supported = litellm.get_supported_openai_params(
            model=client.model_config.litellm_model
        )
    except Exception:
        supported = None
    sources = dict(client.limit_origins)
    sources["generation"] = {
        name: "Manueller Profilwert"
        if name in clean["generation"]
        else "Benutzerbudget max_output_tokens"
        if name == "max_tokens" and "max_output_tokens" in clean
        else "Native Bibliotheks-/Modellvorgabe"
        for name in client.generation.model_dump(exclude_none=True)
    }
    sources["reliability"] = {
        name: "Manueller Profilwert"
        if name in clean.get("reliability", {})
        else "Native Bibliotheks-/Modellvorgabe"
        for name in client.reliability.model_dump()
    }
    provider_limits = {
        name: None
        if origin.startswith("Bibliotheksfallback") or origin.startswith("Profil")
        else client.context_limit
        if name == "context_limit"
        else client.model_config.max_output_tokens
        for name, origin in client.limit_origins.items()
    }
    plan_max_output_tokens = (
        min(32768, max(8192, (client.context_limit or 0) // 8))
        if (
            client.provider_output
            and client.model_config.max_output_tokens <= 4096
            and (client.context_limit or 0) >= 32768
        )
        else client.model_config.max_output_tokens
    )
    return dict(
        options=clean,
        context_limit=client.context_limit,
        max_output_tokens=client.model_config.max_output_tokens,
        plan_max_output_tokens=plan_max_output_tokens,
        wire_max_tokens=None if client.provider_output else client.max_tokens,
        output_policy="provider" if client.provider_output else "native_client",
        reliability=client.reliability.model_dump(),
        generation=client.generation.model_dump(exclude_none=True),
        sources=sources,
        provider_limits=provider_limits,
        limits_discovery=(
            "Verzeichniseintrag verwendet"
            if client.directory_limits
            else "Kein Verzeichniseintrag verfügbar"
            if discover_limits or not is_preview
            else "Lokale Vorschau ohne Verzeichnisabfrage"
        )
        if clean["provider"] == "nhr_fau"
        else None,
        thinking="Docling Graph 1.9.2 bietet in diesem Client keinen öffentlichen Reasoning-Parameter. Temperatur steuert die Generierung.",
        vision=vision,
        vision_ready=vision_ready,
        key_available=key_available,
        vision_endpoint=bool(host),
        vision_url=vision_url,
        local_endpoint=local,
        endpoint=clean["base_url"] or f"Nativer LiteLLM-Anbieter: {clean['provider']}",
        parameter_status="LiteLLM und der native Client können Parameter anhand von Modellmetadaten verwerfen (drop_params). Die Vorschau zeigt die Konfiguration. Die Serverannahme ist anbieterabhängig.",
        parameter_support={
            name: "Anbieterautomatik · Parameter ausgelassen"
            if name == "max_tokens" and client.provider_output
            else "Vom nativen Client nicht weitergereicht"
            if name in {"min_tokens", "repetition_penalty", "decoding_method"}
            else "Vom nativen Metadatenfilter entfernt"
            if supported and name not in supported
            else "SDK-Eingang laut Metadaten; Serverannahme ungeprüft"
            if supported
            else "SDK-Filterauskunft unbekannt; Serverannahme ungeprüft"
            for name in client.generation.model_dump(exclude_none=True)
        },
    )


def fau_models(raw):
    return [model["id"] for model in fau_entries(raw)]


DIRECTORIES = {
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


_QUANT_SUFFIX_RE = re.compile(
    r"-(?:fp8(?:-dynamic|-block)?|int4|int8|awq|gptq|gguf|bnb-4bit)$",
    re.IGNORECASE,
)


def _infer_open_multimodal(model_id: str, item_meta: dict | None = None) -> bool | None:
    """Detect multimodal (Text + Vision / 'Mischmodell') capability from endpoint metadata or open model family."""
    low = str(model_id or "").lower()
    if any(k in low for k in ("embed", "rerank", "bge-", "whisper", "tts", "moderation")):
        return False
    if isinstance(item_meta, dict):
        if isinstance(item_meta.get("supports_vision"), bool):
            return item_meta["supports_vision"]
        if item_meta.get("multimodal") is True:
            return True
        caps = item_meta.get("capabilities")
        if isinstance(caps, dict) and isinstance(caps.get("vision"), bool):
            return caps["vision"]
        arch = item_meta.get("architecture")
        if isinstance(arch, dict):
            mod_str = str(arch.get("modality") or "") + " " + " ".join(
                str(x) for x in (arch.get("input_modalities") or [])
            )
            if "image" in mod_str.lower() or "vision" in mod_str.lower():
                return True
        mods = item_meta.get("modalities") or item_meta.get("input_modalities")
        if isinstance(mods, list) and any("image" in str(m).lower() for m in mods):
            return True
    if "-text" in low:
        return False
    multimodal_markers = (
        "qwen3.5",
        "qwen3.6",
        "qwen2-vl",
        "qwen2.5-vl",
        "qwen3-vl",
        "-vl",
        "vision",
        "pixtral",
        "mistral-small-3.1",
        "mistral-small-3.2",
        "mistral-medium-3",
        "gemma-3-",
        "gemma-4",
        "gemma3",
        "gemma4",
        "kimi-k2.5",
        "kimi-k2.6",
        "llama-4",
        "llava",
        "minicpm-v",
        "internvl",
        "lightonocr",
        "omni",
        "gpt-4o",
        "gpt-4.1",
        "gpt-5",
        "claude-3",
        "claude-sonnet-4",
        "claude-opus-4",
        "claude-haiku-4",
    )
    if any(m in low for m in multimodal_markers):
        return True
    if "gemma-3" in low and "1b" not in low:
        return True
    return None


def catalog_meta(provider, model_id):
    """Resolve non-hardcoded metadata from LiteLLM's local model registry when available."""
    import litellm

    litellm.suppress_debug_info = True
    cost_table = getattr(litellm, "model_cost", None) or {}
    tail = model_id.split("/")[-1] if "/" in model_id else model_id
    stripped_tail = _QUANT_SUFFIX_RE.sub("", tail)
    exact_candidates = [
        f"{provider}/{model_id}",
        model_id,
        tail if "/" in model_id else None,
    ]
    family_candidates = [
        stripped_tail if stripped_tail != tail else None,
        f"openai/{stripped_tail}" if stripped_tail != tail else None,
        f"openrouter/{model_id}",
    ]
    # Exact match required for billing prices (`US-56`: never guess or extrapolate tariffs!)
    exact_entry = None
    for cand in exact_candidates:
        if cand and isinstance(cost_table.get(cand), dict):
            exact_entry = cost_table[cand]
            break
    meta_entry = exact_entry
    if meta_entry is None:
        for cand in family_candidates:
            if cand and isinstance(cost_table.get(cand), dict):
                meta_entry = cost_table[cand]
                break
    if isinstance(meta_entry, dict):
        in_cost = exact_entry.get("input_cost_per_token") if exact_entry else None
        out_cost = exact_entry.get("output_cost_per_token") if exact_entry else None
        cache_cost = exact_entry.get("cache_read_input_token_cost") if exact_entry else None
        return dict(
            context_limit=positive(
                meta_entry.get("max_input_tokens") or meta_entry.get("max_tokens")
            ),
            max_output_tokens=positive(
                meta_entry.get("max_output_tokens") or meta_entry.get("max_tokens")
            ),
            supports_vision=meta_entry.get("supports_vision")
            if isinstance(meta_entry.get("supports_vision"), bool)
            else None,
            supports_reasoning=bool(meta_entry.get("supports_reasoning")),
            supports_schema=bool(meta_entry.get("supports_response_schema")),
            input_cost_per_1m=round(float(in_cost) * 1_000_000, 4)
            if isinstance(in_cost, (int, float))
            else None,
            output_cost_per_1m=round(float(out_cost) * 1_000_000, 4)
            if isinstance(out_cost, (int, float))
            else None,
            cache_read_cost_per_1m=round(float(cache_cost) * 1_000_000, 4)
            if isinstance(cache_cost, (int, float))
            else None,
            pricing_verified=bool(
                isinstance(in_cost, (int, float)) or isinstance(out_cost, (int, float))
            ),
            mode=meta_entry.get("mode") or "chat",
        )
    return {}


_litellm_catalog_meta = catalog_meta


def _classify_modality_kind(mode: str, supports_vision: bool | None, model_id: str) -> str:
    low = str(model_id or "").lower()
    if mode in ("embedding", "rerank"):
        return "embedding"
    if "ocr" in low:
        return "vision_ocr"
    if supports_vision is True:
        return "multimodal"
    return "text"


def discover_catalog(raw, *, verified_vision: dict | None = None):
    """Query the live provider endpoint and return rich, non-hardcoded model capability entries."""
    provider = str(raw.get("provider") or "").strip()
    clean = profile_options(dict(raw, model=raw.get("model") or "directory"))
    key = runtime_key(clean, raw.get("key"))
    base = clean["base_url"] or DIRECTORIES.get(provider, "")
    zero_billed = provider in ("nhr_fau", "ollama")
    verified_map = verified_vision if isinstance(verified_vision, dict) else {}

    entries = []
    if provider == "nhr_fau":
        raw_items = fau_entries(raw)
        for item in raw_items:
            mid = item["id"]
            lm = _litellm_catalog_meta("openai", mid)
            ctx = (
                positive(item.get("max_model_len"))
                or positive(item.get("max_input_tokens"))
                or lm.get("context_limit")
                or FAU_REFERENCE.get(mid)
            )
            out_tok = positive(item.get("max_output_tokens"))
            if ctx and out_tok and out_tok >= ctx:
                out_tok = lm.get("max_output_tokens")
            mode = item.get("mode") or lm.get("mode") or "chat"
            if any(k in mid.lower() for k in ("embed", "rerank", "bge-", "whisper")):
                mode = "embedding"
            v_key = f"{provider}:{mid}"
            if v_key in verified_map and isinstance(verified_map[v_key], bool):
                vis = verified_map[v_key]
            elif mid in FAU_REFERENCE:
                vis = True
            else:
                vis = _infer_open_multimodal(mid, item_meta=item)
                if vis is None:
                    vis = lm.get("supports_vision")
            entries.append(
                dict(
                    id=mid,
                    label=item.get("name") or mid,
                    context_limit=ctx,
                    max_output_tokens=out_tok,
                    supports_vision=vis,
                    modality_kind=_classify_modality_kind(mode, vis, mid),
                    supports_reasoning=bool(
                        item.get("supports_reasoning")
                        or lm.get("supports_reasoning")
                        or any(k in mid.lower() for k in ("qwen3", "r1", "magistral", "deepseek-v4", "kimi-k2"))
                    ),
                    billing_mode="free_academic",
                    pricing_verified=True,
                    input_cost_per_1m=0.0,
                    output_cost_per_1m=0.0,
                    reference_input_cost_per_1m=lm.get("input_cost_per_1m"),
                    reference_output_cost_per_1m=lm.get("output_cost_per_1m"),
                    mode=mode,
                    source="endpoint",
                )
            )
    elif provider == "ollama":
        if not base:
            raise ValueError("Lokale Ollama-Basis-URL fehlt.")
        root_url = base.removesuffix("/v1").rstrip("/")
        page = directory_page(root_url + "/api/tags", {}, "Ollama")
        for item in page.get("models") or []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            mid = item["name"]
            details = item.get("details") or {}
            lm = _litellm_catalog_meta("ollama", mid)
            families = [str(f).lower() for f in (details.get("families") or [])]
            v_key = f"{provider}:{mid}"
            if v_key in verified_map and isinstance(verified_map[v_key], bool):
                vis = verified_map[v_key]
            else:
                vis = (
                    "clip" in families
                    or "mllama" in families
                    or bool(_infer_open_multimodal(mid, item_meta=item))
                )
            param_size = details.get("parameter_size") or ""
            quant = details.get("quantization_level") or ""
            badge = " · ".join(p for p in (param_size, quant) if p)
            mode = "embedding" if "embed" in mid.lower() else "chat"
            entries.append(
                dict(
                    id=mid,
                    label=f"{mid} ({badge})" if badge else mid,
                    context_limit=lm.get("context_limit"),
                    max_output_tokens=lm.get("max_output_tokens"),
                    supports_vision=vis,
                    modality_kind=_classify_modality_kind(mode, vis, mid),
                    supports_reasoning=bool(
                        lm.get("supports_reasoning")
                        or "qwen3" in mid.lower()
                        or "deepseek-r1" in mid.lower()
                    ),
                    billing_mode="free_local",
                    pricing_verified=True,
                    input_cost_per_1m=0.0,
                    output_cost_per_1m=0.0,
                    mode=mode,
                    source="ollama_local",
                )
            )
    elif provider == "gemini":
        if not key:
            raise ValueError("Gemini-Schlüsselvariable fehlt in der Umgebung.")
        from urllib.parse import urlencode

        headers = {"x-goog-api-key": key}
        query, seen = {}, set()
        while True:
            url = (base or DIRECTORIES["gemini"]) + "/models" + ("?" + urlencode(query) if query else "")
            page = directory_page(url, headers, "Gemini")
            for item in page.get("models") or []:
                if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                    continue
                methods = item.get("supportedGenerationMethods") or []
                if methods and "generateContent" not in methods:
                    continue
                mid = item["name"].removeprefix("models/")
                lm = _litellm_catalog_meta("gemini", mid)
                ctx = positive(item.get("inputTokenLimit")) or lm.get("context_limit")
                out_tok = positive(item.get("outputTokenLimit")) or lm.get("max_output_tokens")
                vis = True if "gemini" in mid.lower() else _infer_open_multimodal(mid, item_meta=item)
                if vis is None:
                    vis = lm.get("supports_vision")
                entries.append(
                    dict(
                        id=mid,
                        label=item.get("displayName") or mid,
                        description=item.get("description") or "",
                        context_limit=ctx,
                        max_output_tokens=out_tok,
                        supports_vision=vis,
                        modality_kind=_classify_modality_kind("chat", vis, mid),
                        supports_reasoning=bool(
                            item.get("thinking")
                            or lm.get("supports_reasoning")
                            or "2.5" in mid
                            or "3" in mid
                        ),
                        billing_mode="metered_api",
                        pricing_verified=bool(lm.get("pricing_verified")),
                        input_cost_per_1m=lm.get("input_cost_per_1m"),
                        output_cost_per_1m=lm.get("output_cost_per_1m"),
                        mode="chat",
                        source="gemini_api",
                    )
                )
            query = directory_cursor("gemini", page)
            if not query:
                break
            cur = next(iter(query.values()))
            if not cur or cur in seen:
                break
            seen.add(cur)
    else:
        if not base:
            raise ValueError("Für diesen Anbieter ist eine Basis-URL erforderlich.")
        if clean["key_env"] and not key:
            raise ValueError(f"Umgebungsvariable {clean['key_env']} nicht gesetzt.")
        if (
            key
            and urlsplit(base).scheme != "https"
            and urlsplit(base).hostname not in ("localhost", "127.0.0.1", "::1")
        ):
            raise ValueError("Das Modellverzeichnis benötigt HTTPS für den Schlüssel.")
        headers = {"Authorization": "Bearer " + key} if key else {}
        if provider == "anthropic":
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"} if key else {"anthropic-version": "2023-06-01"}
        page = directory_page(base.rstrip("/") + "/models", headers, provider)
        for item in page.get("data") or []:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            mid = item["id"]
            lm = _litellm_catalog_meta(provider, mid)
            ctx = (
                positive(item.get("context_length"))
                or positive(item.get("context_window"))
                or positive(item.get("max_model_len"))
                or lm.get("context_limit")
            )
            out_tok = (
                positive((item.get("top_provider") or {}).get("max_completion_tokens") if isinstance(item.get("top_provider"), dict) else None)
                or positive(item.get("max_output_tokens"))
                or lm.get("max_output_tokens")
            )
            pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
            in_cost = lm.get("input_cost_per_1m")
            out_cost = lm.get("output_cost_per_1m")
            pricing_verified = bool(lm.get("pricing_verified"))
            try:
                if pricing.get("prompt") is not None:
                    in_cost = round(float(pricing["prompt"]) * 1_000_000, 4)
                    pricing_verified = True
                if pricing.get("completion") is not None:
                    out_cost = round(float(pricing["completion"]) * 1_000_000, 4)
                    pricing_verified = True
            except (ValueError, TypeError):
                pass
            v_key = f"{provider}:{mid}"
            if v_key in verified_map and isinstance(verified_map[v_key], bool):
                vis = verified_map[v_key]
            else:
                vis = _infer_open_multimodal(mid, item_meta=item)
                if vis is None:
                    vis = lm.get("supports_vision")
            mode = "embedding" if any(k in mid.lower() for k in ("embed", "rerank", "whisper", "tts", "moderation")) else (lm.get("mode") or "chat")
            is_local_custom = urlsplit(base).hostname in ("127.0.0.1", "localhost", "::1")
            entries.append(
                dict(
                    id=mid,
                    label=item.get("display_name") or item.get("name") or mid,
                    context_limit=ctx,
                    max_output_tokens=out_tok,
                    supports_vision=vis,
                    modality_kind=_classify_modality_kind(mode, vis, mid),
                    supports_reasoning=bool(
                        lm.get("supports_reasoning")
                        or any(k in mid.lower() for k in ("qwen3", "r1", "o3", "o4", "gpt-5", "magistral"))
                    ),
                    billing_mode="free_local" if is_local_custom else "metered_api",
                    pricing_verified=True if is_local_custom else pricing_verified,
                    input_cost_per_1m=0.0 if is_local_custom else in_cost,
                    output_cost_per_1m=0.0 if is_local_custom else out_cost,
                    mode=mode,
                    source="endpoint",
                )
            )

    # Deduplicate while ranking chat/vision models ahead of pure embedding/utility models
    dedup = {}
    for e in entries:
        dedup.setdefault(e["id"], e)
    ordered = sorted(
        dedup.values(),
        key=lambda x: (0 if x.get("mode") == "chat" else 1, x["id"].lower()),
    )
    return dict(
        provider=provider,
        endpoint=base,
        configured=True,
        count=len(ordered),
        models=ordered,
    )


def offered_models(raw):
    """Read the selected endpoint's real catalogue."""
    provider = raw.get("provider")
    if provider == "nhr_fau":
        return fau_models(raw)
    clean = profile_options(dict(raw, model=raw.get("model") or "directory"))
    key = runtime_key(clean)
    base = clean["base_url"] or DIRECTORIES.get(provider)
    if not base:
        raise ValueError(
            "Für diesen Anbieter ist hier kein Modellverzeichnis verbunden."
        )
    if clean["key_env"] and not key:
        raise ValueError("Die konfigurierte Schlüsselvariable fehlt.")
    if (
        key
        and urlsplit(base).scheme != "https"
        and urlsplit(base).hostname not in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError("Das Modellverzeichnis benötigt HTTPS für den Schlüssel.")
    headers = {"Authorization": "Bearer " + key} if key else {}
    if provider == "ollama":
        base = base.removesuffix("/v1").rstrip("/")
        page = directory_page(base + "/api/tags", headers, "Ollama")
        return model_ids(page, "models", "name")
    if provider == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
    if provider == "gemini":
        headers = {"x-goog-api-key": key} if key else {}
    return directory_models(base + "/models", headers, provider)


def model_ids(page, field, identifier):
    if not isinstance(page.get(field), list):
        raise ValueError("Das Modellverzeichnis lieferte keine lesbare Modellliste.")
    return [
        entry[identifier]
        for entry in page[field]
        if isinstance(entry, dict) and isinstance(entry.get(identifier), str)
    ]


def directory_models(url, headers, provider):
    from urllib.parse import urlencode

    result, seen, query = [], set(), {}
    while True:
        page = directory_page(
            url + ("?" + urlencode(query) if query else ""), headers, provider
        )
        if provider == "gemini":
            result.extend(
                m.removeprefix("models/") for m in model_ids(page, "models", "name")
            )
        else:
            result.extend(model_ids(page, "data", "id"))
        query = directory_cursor(provider, page)
        if not query:
            return list(dict.fromkeys(result))
        cursor = next(iter(query.values()))
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise ValueError(
                "Das Modellverzeichnis lieferte einen ungültigen Seitencursor."
            )
        seen.add(cursor)


def directory_cursor(provider, page):
    if provider == "anthropic" and page.get("has_more"):
        return {"after_id": page.get("last_id")}
    if provider == "gemini" and page.get("nextPageToken"):
        return {"pageToken": page["nextPageToken"]}
    return {}


def directory_page(url, headers, provider):
    import json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    request = Request(url)
    for name, value in headers.items():
        request.add_unredirected_header(name, value)
    try:
        with urlopen(request, timeout=30) as response:
            value = json.load(response)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except HTTPError as exc:
        raise ValueError(f"{provider}-Modellverzeichnis: HTTP {exc.code}") from None
    except (URLError, OSError, ValueError):
        raise ValueError(
            f"{provider}-Modellverzeichnis derzeit nicht erreichbar."
        ) from None


def fau_entries(raw):
    clean = profile_options(dict(raw, model=raw.get("model") or "directory"))
    if clean["provider"] != "nhr_fau":
        raise ValueError("Diese Vorschlagsabfrage gehört zum FAU-Profil")
    key = runtime_key(clean, raw.get("key"))
    if not key:
        raise ValueError("FAU-Schlüsselvariable fehlt")
    page = directory_page(FAU + "/models", {"Authorization": "Bearer " + key}, "FAU")
    return [
        m
        for m in page.get("data", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    ]


def check_access(options):
    """Check one synthetic text response using the same client and profile with a bounded probe timeout."""
    import json
    import logging
    import litellm

    litellm.disable_logging = True
    logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
    probe_opts = dict(options)
    rel = dict(probe_opts.get("reliability") or {})
    rel["timeout_s"] = min(int(rel.get("timeout_s") or 25), 45)
    rel["max_retries"] = 0
    probe_opts["reliability"] = rel
    client = connect(probe_opts)
    result = client.get_json_response(
        'Return the JSON object {"ok": true}.',
        json.dumps(
            {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            }
        ),
        structured_output=options.get("structured_output", True),
    )
    return dict(
        status="responded"
        if isinstance(result, dict) and result.get("ok") is True
        else "unexpected_response"
    )


_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def probe_vision_access(options):
    """Live 1x1 PNG probe to verify whether an API model genuinely accepts multimodal image inputs (`US-55`)."""
    import json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    v_opts = vision_options(options)
    base = v_opts["base_url"]
    key = runtime_key(v_opts, options.get("key"))
    if not base:
        return dict(supports_vision=False, status="unsupported_endpoint")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": v_opts["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Reply OK."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_TINY_PNG_B64}"},
                    },
                ],
            }
        ],
        "max_tokens": 32,
    }
    req = Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            body = json.load(resp)
        ok = bool(body.get("choices"))
        return dict(supports_vision=ok, status="responded" if ok else "unexpected_response")
    except HTTPError as exc:
        return dict(supports_vision=False, status="http_error", http_status=exc.code)
    except (URLError, OSError, ValueError):
        return dict(supports_vision=False, status="unreachable")
