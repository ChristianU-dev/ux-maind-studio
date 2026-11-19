import React, { useCallback, useEffect, useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  BookOpen,
  Cpu,
  Eye,
  FileCode2,
  FileScan,
  FolderOpen,
  Image as ImageIcon,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../lib/i18n.jsx";
import { api } from "../lib/api.js";
import { InfoPopover, Select, StatusBadge, StatusDot, Switch } from "../components/ui.jsx";
import { DoclingSettingsTab } from "../components/DoclingSettingsTab.jsx";
import { ManualLimitsSettingsTab } from "./settings/ManualLimitsSettingsTab.jsx";
import { PromptsSettingsTab } from "./settings/PromptsSettingsTab.jsx";
import {
  ParameterTransparencyCard,
  StageRolesCard,
} from "./settings/StageRolesAndPreview.jsx";
import { VisionSettingsTab, WorkspacePathsTab } from "./settings/VisionPathsSettingsTabs.jsx";

const PROVIDER_META = {
  nhr_fau: {
    de: "FAU NHR LLM-Gateway",
    en: "FAU NHR LLM Gateway",
    descDe: "Akademisches OpenAI-kompatibles Hochschul-Cluster",
    descEn: "Academic OpenAI-compatible university cluster",
  },
  ollama: {
    de: "Ollama (Lokal / On-Prem)",
    en: "Ollama (Local / On-Prem)",
    descDe: "Lokale Modelle auf diesem Rechner ohne Datenabfluss",
    descEn: "Local models on this machine with zero external transfer",
  },
  gemini: {
    de: "Google Gemini API",
    en: "Google Gemini API",
    descDe: "Google AI Studio / Gemini Modelle via API-Key",
    descEn: "Google AI Studio / Gemini models via API key",
  },
  openrouter: {
    de: "OpenRouter",
    en: "OpenRouter",
    descDe: "Einheitlicher Katalog für hunderte Open- & Frontier-Modelle",
    descEn: "Unified gateway for hundreds of open & frontier models",
  },
  openai: {
    de: "OpenAI API",
    en: "OpenAI API",
    descDe: "Direkter OpenAI-Endpunkt",
    descEn: "Direct OpenAI endpoint",
  },
  anthropic: {
    de: "Anthropic API",
    en: "Anthropic API",
    descDe: "Claude-Modelle über offiziellen Anthropic-Endpunkt",
    descEn: "Claude models via official Anthropic endpoint",
  },
  mistral: {
    de: "Mistral AI",
    en: "Mistral AI",
    descDe: "Europäische Mistral- & Pixtral-Modelle",
    descEn: "European Mistral & Pixtral models",
  },
  groq: {
    de: "Groq Cloud",
    en: "Groq Cloud",
    descDe: "Schnelle LPU-Inferenz für Open-Weight-Modelle",
    descEn: "Fast LPU inference for open-weight models",
  },
  nvidia_nim: {
    de: "NVIDIA NIM",
    en: "NVIDIA NIM",
    descDe: "NVIDIA-gehostete oder selbstbetriebene NIM-Container",
    descEn: "NVIDIA-hosted or self-hosted NIM endpoints",
  },
  custom: {
    de: "Eigener OpenAI-Endpunkt",
    en: "Custom OpenAI Endpoint",
    descDe: "Beliebiger vLLM-, LiteLLM-, LM-Studio- oder Unternehmens-Server",
    descEn: "Any vLLM, LiteLLM, LM Studio, or enterprise OpenAI-compatible server",
  },
};

function formatTokenCompact(n) {
  if (!n || !Number.isFinite(Number(n))) return null;
  const v = Number(n);
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(v % 1_000_000 === 0 ? 0 : 1)}M`;
  if (v >= 1000) return `${Math.round(v / 1024)}k`;
  return String(v);
}

function translateBackendPreview(text, lang) {
  if (!text || lang !== "en") return text || "";
  return String(text)
    .replace("Dokumentierte FAU-Referenz", "Documented FAU Reference")
    .replace("Lokale Vorschau ohne Verzeichnisabfrage", "Local preview without endpoint probe")
    .replace("Manueller Profilwert", "Manual profile override")
    .replace("Anbieterverzeichnis", "Provider endpoint metadata")
    .replace("Standard", "Default");
}

const emptyDraft = (provider = "nhr_fau", preset = {}) => ({
  provider,
  model: "",
  base_url: preset.base_url || "",
  key_env: preset.key_env || "",
  extraction_contract: "direct",
  processing_mode: "many-to-one",
  llm_input_format: "doclang-geo",
  structured_output: true,
  gleaning_enabled: false,
  stage_gleaning: false,
  use_chunking: true,
  chunk_max_tokens: "",
  parallel_workers: "",
  dense_dedupe: "standard",
  dense_fill_context: "scoped",
  context_limit: "",
  max_output_tokens: "",
  temperature: "",
  top_p: "",
  top_k: "",
  max_tokens: "",
  timeout_s: "",
  max_retries: "",
});

function draftFromOptions(opt = {}) {
  return {
    provider: opt.provider || "nhr_fau",
    model: opt.model || "",
    base_url: opt.base_url || "",
    key_env: opt.key_env || "",
    extraction_contract: opt.extraction_contract || "auto",
    processing_mode: opt.processing_mode || "many-to-one",
    llm_input_format: opt.llm_input_format || "auto",
    structured_output: opt.structured_output !== false,
    gleaning_enabled: Boolean(opt.gleaning_enabled),
    stage_gleaning: Boolean(opt.stage_gleaning),
    use_chunking: opt.use_chunking !== false,
    chunk_max_tokens: opt.chunk_max_tokens ?? "",
    parallel_workers: opt.parallel_workers ?? "",
    dense_dedupe: opt.dense_dedupe || "standard",
    dense_fill_context: opt.dense_fill_context || "scoped",
    context_limit: opt.context_limit ?? "",
    max_output_tokens: opt.max_output_tokens ?? "",
    temperature: opt.generation?.temperature ?? "",
    top_p: opt.generation?.top_p ?? "",
    top_k: opt.generation?.top_k ?? "",
    max_tokens: opt.generation?.max_tokens ?? "",
    timeout_s: opt.reliability?.timeout_s ?? "",
    max_retries: opt.reliability?.max_retries ?? "",
  };
}

function optionsFromDraft(d) {
  const out = {
    provider: d.provider.trim(),
    model: d.model.trim(),
    base_url: d.base_url.trim(),
    key_env: d.key_env.trim(),
    extraction_contract: d.extraction_contract,
    processing_mode: d.processing_mode,
    llm_input_format: d.llm_input_format,
    structured_output: Boolean(d.structured_output),
    gleaning_enabled: Boolean(d.gleaning_enabled),
    stage_gleaning: Boolean(d.stage_gleaning),
    use_chunking: Boolean(d.use_chunking),
    generation: {},
    reliability: {},
  };
  if (d.extraction_contract === "dense") {
    out.dense_dedupe = d.dense_dedupe || "standard";
    out.dense_fill_context = d.dense_fill_context || "scoped";
  }
  if (d.chunk_max_tokens !== "") out.chunk_max_tokens = Number(d.chunk_max_tokens);
  if (d.parallel_workers !== "") out.parallel_workers = Number(d.parallel_workers);
  if (d.context_limit !== "") out.context_limit = Number(d.context_limit);
  if (d.max_output_tokens !== "") out.max_output_tokens = Number(d.max_output_tokens);
  for (const k of ["temperature", "top_p", "top_k", "max_tokens"]) {
    if (d[k] !== "") out.generation[k] = Number(d[k]);
  }
  for (const k of ["timeout_s", "max_retries"]) {
    if (d[k] !== "") out.reliability[k] = Number(d[k]);
  }
  return out;
}

export function SettingsView({
  profilesData,
  workflowSettings,
  onReloadSettings,
  requestedTab,
  onClearRequestedTab,
}) {
  const { lang, t } = usePrefs();
  const [tab, setTab] = useState(requestedTab || "models");

  useEffect(() => {
    if (requestedTab) {
      setTab(requestedTab);
      onClearRequestedTab?.();
    }
  }, [requestedTab, onClearRequestedTab]);

  const profiles = profilesData?.profiles || [];
  const presets = profilesData?.presets || {};
  const envStatus = profilesData?.env_status || {};
  const detectedEnvVars = profilesData?.detected_env_vars || [];

  const [selectedProfileName, setSelectedProfileName] = useState("");
  const [profileName, setProfileName] = useState("");
  const [draft, setDraft] = useState(() => emptyDraft("nhr_fau", presets.nhr_fau));

  const [preview, setPreview] = useState(null);
  const [catalog, setCatalog] = useState(null); // { models: [], error, configured }
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogFilter, setCatalogFilter] = useState("all"); // all | vision
  const [checkingModel, setCheckingModel] = useState(false);

  // Initialize editor with first saved profile or first connected provider
  useEffect(() => {
    if (!selectedProfileName && profiles.length > 0 && !draft.model) {
      const first = profiles[0];
      setSelectedProfileName(first.name);
      setProfileName(first.name);
      setDraft(draftFromOptions(first.options));
      return;
    }
    if (!profiles.length && !draft.model) {
      const connectedKey = Object.keys(envStatus).find(
        (k) => envStatus[k]?.configured && !envStatus[k]?.local
      );
      if (connectedKey) {
        const st = envStatus[connectedKey];
        setDraft(
          emptyDraft(connectedKey, {
            base_url: st.default_base_url || presets[connectedKey]?.base_url || "",
            key_env: st.detected_env || st.key_env || "",
          })
        );
      }
    }
  }, [profiles, envStatus]);

  // Fetch live model catalog dynamically from the selected API provider
  const fetchCatalog = useCallback(
    async (providerOverride, baseUrlOverride, keyEnvOverride, silent = false) => {
      const prov = providerOverride ?? draft.provider;
      const bUrl = baseUrlOverride ?? draft.base_url;
      const kEnv = keyEnvOverride ?? draft.key_env;
      if (!prov) return;
      setLoadingCatalog(true);
      try {
        const res = await api("model-catalog", {
          provider: prov,
          base_url: bUrl,
          key_env: kEnv,
        });
        setCatalog(res);
        if (!silent) {
          if (res.models?.length) {
            toast.success(
              t(
                `${res.models.length} Modelle live von der API geladen`,
                `Loaded ${res.models.length} models live from API`
              )
            );
          } else if (res.error) {
            toast.warning(res.error);
          }
        }
      } catch (err) {
        if (!silent) toast.error(err.message);
        setCatalog({ models: [], error: err.message });
      } finally {
        setLoadingCatalog(false);
      }
    },
    [draft.provider, draft.base_url, draft.key_env, t]
  );

  // Auto-load catalog whenever provider changes and has credentials / is local
  useEffect(() => {
    const st = envStatus[draft.provider];
    const hasCustomEnv = draft.key_env && detectedEnvVars.includes(draft.key_env);
    if (st?.configured || st?.local || hasCustomEnv) {
      fetchCatalog(draft.provider, draft.base_url, draft.key_env, true);
    } else {
      setCatalog(null);
    }
  }, [draft.provider, envStatus, detectedEnvVars]);

  // Live wire parameter preview
  useEffect(() => {
    if (!draft.provider || !draft.model) {
      setPreview(null);
      return;
    }
    const timer = setTimeout(() => {
      api("model-preview", { ...optionsFromDraft(draft), discover_limits: false })
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 180);
    return () => clearTimeout(timer);
  }, [draft]);

  const orderedProviders = useMemo(() => {
    const allKeys = new Set([
      ...Object.keys(PROVIDER_META),
      ...Object.keys(presets),
      ...Object.keys(envStatus),
    ]);
    return [...allKeys].sort((a, b) => {
      const sa = envStatus[a];
      const sb = envStatus[b];
      const score = (s) => (s?.configured && !s?.local ? 2 : s?.local ? 1 : 0);
      return score(sb) - score(sa);
    });
  }, [presets, envStatus]);

  const providerChoices = useMemo(
    () =>
      orderedProviders.map((k) => {
        const meta = PROVIDER_META[k];
        const lbl = meta ? (lang === "en" ? meta.en : meta.de) : k;
        return [k, lbl];
      }),
    [orderedProviders, lang]
  );

  const selectProviderCard = (provKey) => {
    const st = envStatus[provKey] || {};
    const pr = presets[provKey] || {};
    const nextBase = st.default_base_url || pr.base_url || "";
    const nextEnv = st.detected_env || st.key_env || pr.key_env || "";
    setSelectedProfileName("");
    setProfileName("");
    setDraft((prev) => ({
      ...emptyDraft(provKey, pr),
      base_url: nextBase,
      key_env: nextEnv,
      extraction_contract: prev.extraction_contract || "direct",
      llm_input_format: prev.llm_input_format || "doclang-geo",
    }));
    setCatalogSearch("");
  };

  const selectSavedProfile = (name) => {
    setSelectedProfileName(name);
    const found = profiles.find((p) => p.name === name);
    if (found) {
      setProfileName(found.name);
      setDraft(draftFromOptions(found.options));
    } else {
      setProfileName("");
      setDraft(emptyDraft(draft.provider, presets[draft.provider]));
    }
  };

  const pickCatalogModel = (m) => {
    const shortModel = m.id.includes("/") ? m.id.split("/").pop() : m.id;
    const provLabel = (PROVIDER_META[draft.provider]?.[lang === "en" ? "en" : "de"] || draft.provider)
      .split(" ")[0];
    setDraft((d) => ({
      ...d,
      model: m.id,
    }));
    if (!selectedProfileName) {
      setProfileName(`${provLabel} · ${shortModel}`);
    }
  };

  const filteredCatalogModels = useMemo(() => {
    const list = catalog?.models || [];
    const q = catalogSearch.trim().toLowerCase();
    return list.filter((m) => {
      if (catalogFilter === "vision" && !m.supports_vision) return false;
      if (!q) return true;
      return m.id.toLowerCase().includes(q);
    });
  }, [catalog, catalogSearch, catalogFilter]);

  const activeCatalogModelMeta = useMemo(
    () => (catalog?.models || []).find((m) => m.id === draft.model) || null,
    [catalog, draft.model]
  );

  const saveProfile = async (assignAll = false) => {
    const opts = optionsFromDraft(draft);
    if (!opts.provider || !opts.model) {
      toast.error(t("Anbieter und Modellkennung auswählen.", "Select provider and model ID."));
      return;
    }
    const name = profileName.trim() || `${opts.provider} · ${opts.model}`;
    try {
      await api("profile-save", { name, options: opts });
      if (assignAll && workflowSettings) {
        const nextProfiles = {
          ...workflowSettings.profiles,
          A: name,
          B: name,
          C: name,
        };
        if (activeCatalogModelMeta?.supports_vision) {
          nextProfiles.vision = name;
        }
        await api("workflow-settings", {
          profiles: nextProfiles,
          vision: workflowSettings.vision,
          conversion: workflowSettings.conversion,
          stage_prompts: workflowSettings.stage_prompts,
          output_language: workflowSettings.output_language || "auto",
        });
      }
      await onReloadSettings?.();
      setSelectedProfileName(name);
      setProfileName(name);
      toast.success(
        assignAll
          ? t(`Profil „${name}“ gespeichert & A/B/C zugeordnet`, `Saved "${name}" & assigned to stages`)
          : t(`Profil „${name}“ gespeichert`, `Profile "${name}" saved`)
      );
    } catch (err) {
      toast.error(err.message);
    }
  };

  const deleteProfile = async () => {
    if (!profileName.trim()) return;
    try {
      await api("profile-delete", { name: profileName.trim() });
      await onReloadSettings?.();
      selectSavedProfile("");
      toast.success(t("Profil gelöscht", "Profile deleted"));
    } catch (err) {
      toast.error(err.message);
    }
  };

  const runSyntheticCheck = async () => {
    if (!draft.model) {
      toast.error(t("Modellkennung auswählen.", "Select a model identifier first."));
      return;
    }
    setCheckingModel(true);
    try {
      const res = await api("model-check", optionsFromDraft(draft));
      if (res.status === "responded") {
        toast.success(t("Verbindungstest erfolgreich (Modell antwortet)", "Connection check succeeded"));
      } else {
        toast.error(res.error || t("Unerwartete Modellantwort", "Unexpected model response"));
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setCheckingModel(false);
    }
  };

  const runVisionProbe = async () => {
    if (!draft.model.trim()) {
      toast.error(t("Bitte zuerst ein Modell wählen", "Select a model first"));
      return;
    }
    setCheckingModel(true);
    try {
      const res = await api("vision-probe", optionsFromDraft(draft));
      if (res.supports_vision) {
        toast.success(
          t(
            `Multimodal bestätigt: ${draft.model} verarbeitet Text + Bilder (Mischmodell)!`,
            `Multimodal verified: ${draft.model} accepts Text + Vision!`
          )
        );
      } else {
        toast.info(
          t(
            `${draft.model} antwortete nicht auf Bild-Inputs (${res.status || "nur Text"}).`,
            `${draft.model} rejected image input (${res.status || "text-only"}).`
          )
        );
      }
      await fetchCatalog();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setCheckingModel(false);
    }
  };

  const discoverLimits = async () => {
    try {
      const p = await api("model-preview", { ...optionsFromDraft(draft), discover_limits: true });
      setPreview(p);
      toast.success(t("Endpunkt-Metadaten aktualisiert", "Endpoint limits refreshed"));
    } catch (err) {
      toast.error(err.message);
    }
  };

  const updateWorkflowConfig = async (patch) => {
    if (!workflowSettings) return;
    try {
      await api("workflow-settings", {
        profiles: { ...workflowSettings.profiles, ...(patch.profiles || {}) },
        vision: { ...workflowSettings.vision, ...(patch.vision || {}) },
        conversion: { ...(workflowSettings.conversion || {}), ...(patch.conversion || {}) },
        stage_prompts: { ...(workflowSettings.stage_prompts || {}), ...(patch.stage_prompts || {}) },
        base_prompts: { ...(workflowSettings.base_prompts || {}), ...(patch.base_prompts || {}) },
        output_language: patch.output_language ?? workflowSettings.output_language ?? "auto",
      });
      await onReloadSettings?.();
      toast.success(t("Einstellung übernommen", "Setting updated"));
    } catch (err) {
      toast.error(err.message);
    }
  };

  const detectedCtx =
    activeCatalogModelMeta?.context_limit || preview?.context_limit || null;
  const detectedOut =
    activeCatalogModelMeta?.max_output_tokens || preview?.max_output_tokens || null;

  return (
    <div className="lx-page">
      <header className="lx-page-header">
        <div className="min-w-0">
          <div className="lx-row-gap">
            <h1 className="lx-page-title">
              {t("Einstellungen & Dynamische Modellanbindung", "Settings & Dynamic Model Discovery")}
            </h1>
            <InfoPopover
              title={t("Wie funktioniert die API-Anbindung?", "How does API discovery work?")}
            >
              <p>
                {t(
                  "UX-mAInd erkennt gesetzte API-Umgebungsvariablen automatisch auf jedem System und lädt verfügbare Modelle sowie deren Kontextfenster live vom jeweiligen Anbieter.",
                  "UX-mAInd automatically detects API environment variables on any machine and queries live model catalogs and context windows directly from connected providers."
                )}
              </p>
              <p>
                {t(
                  "Geheime API-Schlüssel werden niemals in Profilen oder Datenbanken gespeichert — es wird ausschließlich der Name der Umgebungsvariable referenziert.",
                  "Secret API keys are never stored in profiles or databases — only the environment variable name is referenced."
                )}
              </p>
            </InfoPopover>
          </div>
          <p className="lx-page-subtitle">
            {t(
              "Verbundene Schnittstellen automatisch erkennen, Live-Modellkataloge abrufen, Kontextfenster anpassen und Stufenrollen (A · B · C · Vision) zuordnen.",
              "Auto-detect connected APIs, browse live model catalogs, tune context budgets, and assign stage roles (A · B · C · Vision)."
            )}
          </p>
        </div>
      </header>

      <Tabs.Root value={tab} onValueChange={setTab} className="lx-tabs-stack">
        <Tabs.List className="lx-tabs-list">
          <Tabs.Trigger value="models" className="lx-tab-trigger">
            <Cpu size={13} />
            <span>{t("API-Anbieter, Katalog & Rollen", "Providers, Live Catalog & Roles")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="prompts" className="lx-tab-trigger">
            <FileCode2 size={13} />
            <span>{t("Stufen-Prompts & Schema", "Stage Prompts & Schema")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="docling" className="lx-tab-trigger">
            <FileScan size={13} />
            <span>{t("Docling-Engine (Lokal)", "Docling Engine (Local)")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="vision" className="lx-tab-trigger">
            <ImageIcon size={13} />
            <span>{t("Visuelle Analyse (Vision)", "Visual Analysis (Vision)")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="paths" className="lx-tab-trigger">
            <FolderOpen size={13} />
            <span>{t("Arbeitsbereich & Pfade", "Workspace & Paths")}</span>
          </Tabs.Trigger>
          <Tabs.Trigger value="manual" className="lx-tab-trigger">
            <BookOpen size={13} />
            <span>{t("Handbuch & Systemgrenzen", "Manual & System Limits")}</span>
          </Tabs.Trigger>
        </Tabs.List>

        {/* TAB 1: DYNAMIC PROVIDERS, LIVE CATALOG & ROLES */}
        <Tabs.Content value="models" className="lx-tab-panel">
          {/* Dynamic Provider Discovery Grid */}
          <section className="lx-card lx-form-stack">
            <div className="lx-between">
              <div>
                <div className="lx-row-gap">
                  <h2 className="lx-card-title">
                    {t("1. Erkannte Schnittstellen & Anbieter wählen", "1. Detected APIs & Provider Selection")}
                  </h2>
                  <InfoPopover
                    title={t("Umgebungsvariablen & Portabilität", "Environment Variables & Portability")}
                  >
                    <p>
                      {t(
                        "Grün markierte Anbieter haben auf diesem System bereits eine gesetzte Umgebungsvariable (oder laufen lokal wie Ollama). Klicke auf eine Karte, um sofort alle dort aktuell verfügbaren Modelle abzurufen.",
                        "Green providers already have an active environment variable on this system (or run locally like Ollama). Click any card to fetch its live model catalog."
                      )}
                    </p>
                  </InfoPopover>
                </div>
                <p className="lx-card-sub">
                  {t(
                    "Dynamische Erkennung aus System-Umgebungsvariablen — ohne fest einprogrammierte Modellnamen.",
                    "Dynamically detected from system environment variables — zero hardcoded model lists."
                  )}
                </p>
              </div>
              {detectedEnvVars.length > 0 && (
                <StatusBadge
                  label={`${detectedEnvVars.length} ${t("API-Variablen im System erkannt", "env keys detected")}`}
                  tone="success"
                />
              )}
            </div>

            <div className="lx-provider-grid">
              {orderedProviders.map((provKey) => {
                const st = envStatus[provKey] || {};
                const meta = PROVIDER_META[provKey] || {
                  de: provKey,
                  en: provKey,
                  descDe: "",
                  descEn: "",
                };
                const isSelected = draft.provider === provKey;
                const isReady = Boolean(st.configured);
                const envBadge =
                  provKey === "custom"
                    ? t("Frei konfigurierbar (URL + Key)", "Custom URL & Env Var")
                    : st.local
                    ? t("Lokal ohne API-Key", "Local · No key needed")
                    : st.configured
                    ? `${st.detected_env || st.key_env} ${t("aktiv", "detected")}`
                    : `${st.key_env || "API_KEY"} ${t("nicht gesetzt", "not set")}`;

                return (
                  <button
                    key={provKey}
                    type="button"
                    className={`lx-provider-card${isSelected ? " is-selected" : ""}`}
                    onClick={() => selectProviderCard(provKey)}
                  >
                    <div className="lx-between" style={{ width: "100%" }}>
                      <strong className="lx-preset-title truncate">
                        {lang === "en" ? meta.en : meta.de}
                      </strong>
                      <StatusDot
                        tone={isReady && !st.local ? "success" : st.local ? "active" : "neutral"}
                      />
                    </div>
                    <span className="lx-muted lx-text-xs truncate" style={{ width: "100%" }}>
                      {lang === "en" ? meta.descEn : meta.descDe}
                    </span>
                    <span className="lx-preset-env tabular truncate">{envBadge}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* 2-Column Bento: Live Catalog + Profile Parameters (Left) & Stage Roles (Right) */}
          <div className="lx-bento-2">
            {/* Left: Profile Editor + Dynamic Live API Catalog */}
            <section className="lx-card lx-form-stack">
              <div className="lx-between">
                <div className="lx-row-gap">
                  <h2 className="lx-card-title">
                    {t("2. Live-Modellkatalog & Profil-Parameter", "2. Live Model Catalog & Profile Parameters")}
                  </h2>
                </div>
                <div className="lx-row-gap">
                  <div style={{ width: 215 }}>
                    <Select
                      size="sm"
                      value={selectedProfileName}
                      onValueChange={selectSavedProfile}
                      options={[
                        ["", t("Neues Profil erstellen …", "Create new profile…")],
                        ...profiles.map((p) => [p.name, p.name]),
                      ]}
                    />
                  </div>
                  {selectedProfileName && (
                    <button
                      type="button"
                      className="lx-btn lx-btn-xs lx-btn-ghost"
                      onClick={() => selectSavedProfile("")}
                      title={t("Frisches Profil anlegen", "Start a new profile")}
                    >
                      <Plus size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* Connection coordinates */}
              <div className="lx-grid-2">
                <label className="lx-field">
                  <span className="lx-field-label">{t("Anbieter / Gateway", "Provider / Gateway")}</span>
                  <Select
                    value={draft.provider}
                    onValueChange={(v) => {
                      const st = envStatus[v] || {};
                      const p = presets[v] || {};
                      setDraft((d) => ({
                        ...d,
                        provider: v,
                        base_url: st.default_base_url || p.base_url || "",
                        key_env: st.detected_env || st.key_env || p.key_env || "",
                      }));
                    }}
                    options={providerChoices}
                  />
                </label>

                <div className="lx-field">
                  <div className="lx-between">
                    <span className="lx-field-label">
                      {t("Umgebungsvariable (API-Key)", "API Key Env Variable")}
                    </span>
                    <InfoPopover title={t("Umgebungsvariable für API-Schlüssel", "API Key Environment Variable")}>
                      <p>
                        {t(
                          "Name der System-Umgebungsvariable (z. B. OPENAI_API_KEY, GEMINI_API_KEY, LLMAPI_KEY). Wähle rechts eine bereits erkannte Variable oder tippe einen eigenen Namen ein.",
                          "Name of your OS environment variable (e.g. OPENAI_API_KEY, GEMINI_API_KEY). Pick a detected variable or enter a custom name."
                        )}
                      </p>
                    </InfoPopover>
                  </div>
                  <div className="lx-row-gap">
                    <input
                      type="text"
                      className="lx-input tabular"
                      value={draft.key_env}
                      onChange={(e) => setDraft((d) => ({ ...d, key_env: e.target.value }))}
                      placeholder={
                        draft.provider === "ollama"
                          ? t("Lokal (kein Key nötig)", "Local (none required)")
                          : "OPENAI_API_KEY"
                      }
                    />
                    {detectedEnvVars.length > 0 && (
                      <div style={{ width: 145, flexShrink: 0 }}>
                        <Select
                          size="md"
                          value={detectedEnvVars.includes(draft.key_env) ? draft.key_env : ""}
                          placeholder={t("Erkannte …", "Detected…")}
                          onValueChange={(v) => {
                            if (v) setDraft((d) => ({ ...d, key_env: v }));
                          }}
                          options={detectedEnvVars.map((ev) => [ev, ev])}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="lx-grid-2">
                <label className="lx-field">
                  <span className="lx-field-label">{t("Basis-URL (optional)", "Base URL (optional)")}</span>
                  <input
                    type="text"
                    className="lx-input"
                    value={draft.base_url}
                    onChange={(e) => setDraft((d) => ({ ...d, base_url: e.target.value }))}
                    placeholder={
                      presets[draft.provider]?.base_url ||
                      t("Standard-Endpunkt des Anbieters", "Provider default endpoint")
                    }
                  />
                </label>

                <label className="lx-field">
                  <span className="lx-field-label">
                    {t("Anzeigename des Profils", "Saved Profile Name")}
                  </span>
                  <input
                    type="text"
                    className="lx-input"
                    value={profileName}
                    onChange={(e) => setProfileName(e.target.value)}
                    placeholder={
                      draft.model ? `${draft.provider} · ${draft.model}` : t("Automatisch aus Modellname", "Auto from model")
                    }
                  />
                </label>
              </div>

              {/* Dynamic Live API Model Browser */}
              <div className="lx-catalog-box">
                <div className="lx-catalog-head">
                  <div className="lx-row-gap">
                    <strong className="lx-text-xs">
                      {t("Verfügbare Modelle dieser API", "Available Models on Connected API")}
                    </strong>
                    {catalog?.models?.length > 0 && (
                      <span className="lx-mono-tag tabular">{filteredCatalogModels.length}</span>
                    )}
                    <InfoPopover title={t("Live-Modellkatalog", "Live API Model Catalog")}>
                      <p>
                        {t(
                          "Fragt den /models-Endpunkt des gewählten Anbieters live ab und ergänzt Kontextfenster, Ausgabelimits, Vision-Fähigkeit und Referenzpreise aus den Modellmetadaten.",
                          "Queries the provider's live /models endpoint and enriches each entry with context window, max output tokens, Vision support, and pricing metadata."
                        )}
                      </p>
                    </InfoPopover>
                  </div>

                  <div className="lx-row-gap">
                    <div className="lx-segmented">
                      <button
                        type="button"
                        className={`lx-seg-btn${catalogFilter === "all" ? " is-active" : ""}`}
                        onClick={() => setCatalogFilter("all")}
                      >
                        {t("Alle", "All")}
                      </button>
                      <button
                        type="button"
                        className={`lx-seg-btn${catalogFilter === "vision" ? " is-active" : ""}`}
                        onClick={() => setCatalogFilter("vision")}
                      >
                        Vision
                      </button>
                    </div>
                    <button
                      type="button"
                      className="lx-btn lx-btn-xs"
                      disabled={loadingCatalog}
                      onClick={() => fetchCatalog()}
                    >
                      <RefreshCw size={11} />
                      <span>
                        {loadingCatalog
                          ? t("Lädt …", "Loading…")
                          : t("Live abrufen", "Fetch Live")}
                      </span>
                    </button>
                  </div>
                </div>

                {catalog?.models?.length > 5 && (
                  <div style={{ padding: "6px 8px", borderBottom: "1px solid var(--border)" }}>
                    <div className="lx-search-wrap">
                      <Search size={12} className="lx-search-icon" />
                      <input
                        type="search"
                        className="lx-input lx-input-sm lx-search-input"
                        value={catalogSearch}
                        onChange={(e) => setCatalogSearch(e.target.value)}
                        placeholder={t("Modell im Live-Katalog filtern …", "Filter live models…")}
                      />
                    </div>
                  </div>
                )}

                <div className="lx-catalog-list">
                  {loadingCatalog ? (
                    <div className="lx-muted lx-text-xs" style={{ padding: "12px 10px" }}>
                      {t("Frage verbundene API nach aktuellen Modellen ab …", "Querying provider endpoint for live models…")}
                    </div>
                  ) : filteredCatalogModels.length > 0 ? (
                    filteredCatalogModels.map((m) => {
                      const active = draft.model === m.id;
                      const ctxTxt = formatTokenCompact(m.context_limit);
                      const outTxt = formatTokenCompact(m.max_output_tokens);
                      return (
                        <button
                          key={m.id}
                          type="button"
                          className={`lx-catalog-row${active ? " is-active" : ""}`}
                          onClick={() => pickCatalogModel(m)}
                        >
                          <div className="min-w-0" style={{ flex: 1 }}>
                            <div className="lx-text-xs truncate" style={{ fontWeight: 600 }}>
                              {m.id}
                            </div>
                          </div>
                          <div className="lx-row-gap" style={{ flexShrink: 0 }}>
                            {ctxTxt && (
                              <span className="lx-cap-pill tabular" title={t("Kontextfenster", "Context Window")}>
                                Ctx {ctxTxt}
                              </span>
                            )}
                            {outTxt && (
                              <span className="lx-cap-pill tabular" title={t("Max. Output", "Max Output")}>
                                Out {outTxt}
                              </span>
                            )}
                            {m.modality_kind === "multimodal" || m.supports_vision ? (
                              <span
                                className="lx-cap-pill is-vision"
                                title={t(
                                  "Mischmodell: Verarbeitet sowohl Text als auch Bilder/Folien",
                                  "Multimodal: Accepts both Text and Vision inputs"
                                )}
                              >
                                {t("Multimodal (Text+Vision)", "Multimodal")}
                              </span>
                            ) : m.modality_kind === "embedding" ? (
                              <span className="lx-cap-pill">Embedding</span>
                            ) : null}
                            {m.supports_reasoning && (
                              <span className="lx-cap-pill">Reasoning</span>
                            )}
                            {m.billing_mode === "free_academic" || m.billing_mode === "free_local" ? (
                              <span
                                className="lx-cap-pill tabular"
                                title={t(
                                  "0,00 € reale Abrechnung über lokalen / Hochschul-Endpunkt",
                                  "0.00 EUR real billed cost on local / academic endpoint"
                                )}
                              >
                                0,00 €
                              </span>
                            ) : m.pricing_verified && m.input_cost_per_1m != null ? (
                              <span
                                className="lx-cap-pill tabular"
                                title={`Input $${m.input_cost_per_1m}/1M · Output $${m.output_cost_per_1m ?? "—"}/1M`}
                              >
                                ${m.input_cost_per_1m}/${m.output_cost_per_1m ?? "—"}/1M
                              </span>
                            ) : (
                              <span
                                className="lx-cap-pill"
                                title={t(
                                  "Kein Listenpreis in der Tarifdatenbank hinterlegt (keine Schätzwerte)",
                                  "No verified tariff listed (no guessed prices)"
                                )}
                              >
                                {t("Kein Tarif", "Unlisted")}
                              </span>
                            )}
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="lx-muted lx-text-xs" style={{ padding: "10px" }}>
                      {catalog?.error
                        ? `${t("Hinweis", "Note")}: ${catalog.error}`
                        : t(
                            "Klicke auf ‚Live abrufen‘ (oder trage unten direkt eine beliebige Modell-ID ein).",
                            "Click 'Fetch Live' (or enter any model identifier directly below)."
                          )}
                    </div>
                  )}
                </div>
              </div>

              {/* Explicit Model Identifier Input (supports brand-new / unlisted models anytime) */}
              <label className="lx-field">
                <div className="lx-between">
                  <span className="lx-field-label">
                    {t("Gewählte Modellkennung (frei editierbar)", "Selected Model ID (freely editable)")}
                  </span>
                  {detectedCtx && (
                    <span className="lx-muted lx-text-xs tabular">
                      {t("Erkanntes Fenster", "Detected window")}: {detectedCtx.toLocaleString()} Tokens
                    </span>
                  )}
                </div>
                <input
                  type="text"
                  className="lx-input tabular"
                  value={draft.model}
                  onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}
                  placeholder={t("Modell oben anklicken oder Modell-ID eingeben …", "Click a model above or type any model ID…")}
                />
              </label>

              {/* First-Class Context Window & Extraction Controls (Always Visible with Explanations!) */}
              <div className="lx-card lx-card-subtle lx-form-stack">
                <div className="lx-between">
                  <span className="lx-eyebrow">
                    {t("Kontextfenster, Budget & Extraktionsmodus", "Context Window, Budget & Extraction Mode")}
                  </span>
                  <InfoPopover
                    title={t("Kontextfenster & Ausgabebudget erklärt", "Context Window & Output Budget Explained")}
                  >
                    <p>
                      <strong>{t("Kontextlimit", "Context Limit")}:</strong>{" "}
                      {t(
                        "Bestimmt, wie groß Dokumentabschnitte vor der Zerlegung geplant werden. Leer = nutzt automatisch das vom Anbieter gemeldete Modellfenster.",
                        "Controls how document chunks are sized during planning. Leave empty ('Auto') to automatically use the model's reported context window."
                      )}
                    </p>
                    <p>
                      <strong>{t("Max. Ausgabe-Tokens", "Max Output Tokens")}:</strong>{" "}
                      {t(
                        "Maximale Antwortlänge pro Aufruf. Bei Modellen mit gemeinsamem Kontextfenster bleibt der Wire-Parameter automatisch frei, sofern du hier keinen festen Wert erzwingst.",
                        "Maximum completion budget. On shared-window endpoints, wire max_tokens is safely omitted unless explicitly overridden here."
                      )}
                    </p>
                    <p>
                      <strong>{t("Extraktionsvertrag", "Extraction Contract")}:</strong>{" "}
                      {t(
                        "‚Direct‘ sendet das strukturierte JSON-Schema in einem präzisen Durchgang (empfohlen). ‚Dense‘ nutzt Docling-Graphs mehrstufiges Skeleton+Fill-Verfahren für besonders dichte/kleinere Modelle.",
                        "'Direct' executes structured JSON extraction in a single pass (recommended). 'Dense' uses Docling-Graph's multi-pass Skeleton+Fill mode."
                      )}
                    </p>
                  </InfoPopover>
                </div>

                <div className="lx-grid-2">
                  <label className="lx-field">
                    <span className="lx-field-label">
                      {t("Kontextfenster (Tokens)", "Context Window (Tokens)")}
                    </span>
                    <input
                      type="number"
                      className="lx-input lx-input-sm tabular"
                      value={draft.context_limit}
                      onChange={(e) => setDraft((d) => ({ ...d, context_limit: e.target.value }))}
                      placeholder={
                        detectedCtx
                          ? `Auto (${detectedCtx.toLocaleString()})`
                          : t("Auto (Anbieterwert)", "Auto (provider limit)")
                      }
                    />
                  </label>

                  <label className="lx-field">
                    <span className="lx-field-label">
                      {t("Max. Ausgabe-Tokens", "Max Output Tokens")}
                    </span>
                    <input
                      type="number"
                      className="lx-input lx-input-sm tabular"
                      value={draft.max_output_tokens}
                      onChange={(e) => setDraft((d) => ({ ...d, max_output_tokens: e.target.value }))}
                      placeholder={
                        detectedOut
                          ? `Auto (${detectedOut.toLocaleString()})`
                          : t("Auto (Anbieterautomatik)", "Auto (provider budget)")
                      }
                    />
                  </label>

                  <label className="lx-field">
                    <span className="lx-field-label">
                      {t("Extraktionsvertrag (Docling-Graph)", "Extraction Contract")}
                    </span>
                    <Select
                      size="sm"
                      value={draft.extraction_contract}
                      onValueChange={(v) => setDraft((d) => ({ ...d, extraction_contract: v }))}
                      options={[
                        ["direct", t("Direct · Einzeldurchlauf (Empfohlen)", "Direct · Single-Pass Schema")],
                        ["dense", t("Dense · Mehrstufiges Skeleton + Fill", "Dense · Skeleton + Fill")],
                        ["auto", "Auto (Docling-Graph)"],
                      ]}
                    />
                  </label>

                  <label className="lx-field">
                    <span className="lx-field-label">
                      {t("Dokument-Eingabeformat", "Document Input Format")}
                    </span>
                    <Select
                      size="sm"
                      value={draft.llm_input_format}
                      onValueChange={(v) => setDraft((d) => ({ ...d, llm_input_format: v }))}
                      options={[
                        ["doclang-geo", t("DocLang + Geometrie (Empfohlen)", "DocLang + Geometry")],
                        ["doclang", "DocLang (ohne Geometrie)"],
                        ["markdown", "Markdown"],
                        ["auto", "Auto"],
                      ]}
                    />
                  </label>

                  <label className="lx-field">
                    <span className="lx-field-label">
                      {t("Verarbeitungsmodus (Stufe A)", "Processing Mode (Stage A)")}
                    </span>
                    <Select
                      size="sm"
                      value={draft.processing_mode}
                      onValueChange={(v) => setDraft((d) => ({ ...d, processing_mode: v }))}
                      options={[
                        ["many-to-one", t("Many-to-One · Dokumentzusammenführung", "Many-to-One · Document merge")],
                        ["one-to-one", t("One-to-One · Seiten-/Chunkweise getrennt", "One-to-One · Per page/chunk")],
                      ]}
                    />
                  </label>

                  <label className="lx-field">
                    <span className="lx-field-label">{t("Temperatur", "Temperature")}</span>
                    <input
                      type="number"
                      step="0.1"
                      className="lx-input lx-input-sm tabular"
                      value={draft.temperature}
                      onChange={(e) => setDraft((d) => ({ ...d, temperature: e.target.value }))}
                      placeholder="Auto (0.0)"
                    />
                  </label>
                </div>

                <div className="lx-between">
                  <label className="lx-inline-switch lx-text-xs">
                    <Switch
                      checked={draft.gleaning_enabled}
                      onCheckedChange={(v) => setDraft((d) => ({ ...d, gleaning_enabled: v }))}
                    />
                    <span>
                      {t(
                        "Gleaning in Stufe A (zweiter Prüfdurchlauf für übersehene Dokumentbelege)",
                        "Gleaning in Stage A (second pass for missed document evidence)"
                      )}
                    </span>
                  </label>
                  <InfoPopover title={t("Was bewirkt Gleaning?", "What does Gleaning do?")} align="end">
                    <p>
                      {t(
                        "Nach der ersten Extraktion prüft Docling-Graph in einem zweiten Durchlauf gezielt, ob im Dokumentabschnitt wörtliche UX-Aussagen oder Messwerte übersehen wurden. Erhöht die Abdeckung bei langen Interviews deutlich (kostet ~1.6× Tokens).",
                        "Runs a targeted second pass over each chunk to recover any missed verbatim UX statements or metrics. Substantially boosts recall on dense transcripts (~1.6x tokens)."
                      )}
                    </p>
                  </InfoPopover>
                </div>

                <div className="lx-between">
                  <label className="lx-inline-switch lx-text-xs">
                    <Switch
                      checked={draft.stage_gleaning}
                      onCheckedChange={(v) => setDraft((d) => ({ ...d, stage_gleaning: v }))}
                    />
                    <span>
                      {t(
                        "Gleaning in Stufe B/C (zweiter Prüfdurchlauf in der Synthese)",
                        "Gleaning in Stage B/C (second pass during synthesis)"
                      )}
                    </span>
                  </label>
                  <InfoPopover title={t("Synthese-Gleaning (B/C)", "Synthesis Gleaning (B/C)")} align="end">
                    <p>
                      {t(
                        "Optionaler zweiter Durchlauf bei großen Studien (>10 Dokumente), um zusätzliche dokumentübergreifende Relationen oder Gegenbelege zu ergänzen.",
                        "Optional second pass on large studies (>10 files) to surface additional cross-document links or counterevidence."
                      )}
                    </p>
                  </InfoPopover>
                </div>

                <div className="lx-between">
                  <label className="lx-inline-switch lx-text-xs">
                    <Switch
                      checked={draft.structured_output}
                      onCheckedChange={(v) => setDraft((d) => ({ ...d, structured_output: v }))}
                    />
                    <span>
                      {t(
                        "Striktes JSON-Schema erzwingen (Structured Output)",
                        "Enforce strict JSON Schema (Structured Output)"
                      )}
                    </span>
                  </label>
                  <InfoPopover title={t("Structured Output", "Structured Output")} align="end">
                    <p>
                      {t(
                        "Übergibt das exakte Pydantic-JSON-Schema an den Anbieter, sodass Antworten garantiert syntaktisch valide sind. Nur abschalten, wenn ein älterer lokaler Server response_format=json_schema ablehnt.",
                        "Passes the exact Pydantic JSON schema to guarantee valid structured responses. Only disable if an older local server rejects response_format=json_schema."
                      )}
                    </p>
                  </InfoPopover>
                </div>

                <details className="lx-details">
                  <summary>
                    {t(
                      "Feinsteuerung: Chunking, Parallelisierung, Retries & Dense-Optionen",
                      "Fine-Tuning: Chunking, Concurrency, Retries & Dense Options"
                    )}
                  </summary>
                  <div className="lx-details-body lx-form-stack">
                    <label className="lx-inline-switch lx-text-xs">
                      <Switch
                        checked={draft.use_chunking}
                        onCheckedChange={(v) => setDraft((d) => ({ ...d, use_chunking: v }))}
                      />
                      <span>
                        {t(
                          "Natives Docling-Graph-Chunking aktivieren (bei sehr langen Dokumenten)",
                          "Enable native Docling-Graph chunking"
                        )}
                      </span>
                    </label>
                    <div className="lx-grid-2">
                      <label className="lx-field">
                        <span className="lx-field-label">
                          {t("Max. Tokens pro Chunk", "Chunk Max Tokens")}
                        </span>
                        <input
                          type="number"
                          className="lx-input lx-input-sm tabular"
                          value={draft.chunk_max_tokens}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, chunk_max_tokens: e.target.value }))
                          }
                          placeholder={t("Auto (aus Kontextfenster)", "Auto (from context)")}
                        />
                      </label>
                      <label className="lx-field">
                        <span className="lx-field-label">
                          {t("Parallele Chunk-Worker", "Parallel Workers")}
                        </span>
                        <input
                          type="number"
                          className="lx-input lx-input-sm tabular"
                          value={draft.parallel_workers}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, parallel_workers: e.target.value }))
                          }
                          placeholder="Auto (4)"
                        />
                      </label>
                      <label className="lx-field">
                        <span className="lx-field-label">
                          {t("Antwortfrist / Timeout (s)", "Timeout (s)")}
                        </span>
                        <input
                          type="number"
                          className="lx-input lx-input-sm tabular"
                          value={draft.timeout_s}
                          onChange={(e) => setDraft((d) => ({ ...d, timeout_s: e.target.value }))}
                          placeholder="Auto"
                        />
                      </label>
                      <label className="lx-field">
                        <span className="lx-field-label">
                          {t("Max. Wiederholungen (Retries)", "Max Retries")}
                        </span>
                        <input
                          type="number"
                          className="lx-input lx-input-sm tabular"
                          value={draft.max_retries}
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, max_retries: e.target.value }))
                          }
                          placeholder="Auto"
                        />
                      </label>
                      <label className="lx-field">
                        <span className="lx-field-label">Top-P</span>
                        <input
                          type="number"
                          step="0.05"
                          className="lx-input lx-input-sm tabular"
                          value={draft.top_p}
                          onChange={(e) => setDraft((d) => ({ ...d, top_p: e.target.value }))}
                          placeholder="Auto"
                        />
                      </label>
                      {draft.extraction_contract === "dense" && (
                        <label className="lx-field">
                          <span className="lx-field-label">
                            {t("Dense-Deduplizierung", "Dense Deduplication")}
                          </span>
                          <Select
                            size="sm"
                            value={draft.dense_dedupe}
                            onValueChange={(v) => setDraft((d) => ({ ...d, dense_dedupe: v }))}
                            options={[
                              ["standard", "Standard"],
                              ["aggressive", "Aggressive"],
                              ["off", "Off"],
                            ]}
                          />
                        </label>
                      )}
                    </div>
                  </div>
                </details>
              </div>

              <div className="lx-btn-row" style={{ marginTop: 2 }}>
                <button
                  type="button"
                  className="lx-btn lx-btn-primary"
                  onClick={() => saveProfile(true)}
                >
                  <Save size={13} />
                  <span>{t("Speichern & für A/B/C aktivieren", "Save & Assign to A/B/C")}</span>
                </button>
                <button type="button" className="lx-btn" onClick={() => saveProfile(false)}>
                  <span>{t("Nur Profil speichern", "Save Profile Only")}</span>
                </button>
                <button
                  type="button"
                  className="lx-btn lx-btn-ghost"
                  disabled={checkingModel}
                  onClick={runSyntheticCheck}
                >
                  <Zap size={13} />
                  <span>{t("Text testen", "Test Text")}</span>
                </button>
                <button
                  type="button"
                  className="lx-btn lx-btn-ghost"
                  disabled={checkingModel}
                  onClick={runVisionProbe}
                  title={t(
                    "Prüft per echtem 1x1-Testbild, ob dieses Modell ein Mischmodell (Text + Vision) ist",
                    "Sends a 1x1 test image to verify if this model supports Vision"
                  )}
                >
                  <Eye size={13} />
                  <span>{t("Vision testen", "Test Vision")}</span>
                </button>
                {selectedProfileName && (
                  <button
                    type="button"
                    className="lx-icon-btn"
                    onClick={deleteProfile}
                    title={t("Profil löschen", "Delete profile")}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </section>

            {/* Right: Stage Role Assignment */}
            <StageRolesCard
              workflowSettings={workflowSettings}
              profiles={profiles}
              onUpdateWorkflowConfig={updateWorkflowConfig}
            />
          </div>

          {/* Bottom: Parameter Transparency Matrix (Rule 10) */}
          <ParameterTransparencyCard preview={preview} onProbeLimits={discoverLimits} />
        </Tabs.Content>

        {/* TAB 2: TRANSPARENT & CUSTOMIZABLE STAGE PROMPTS */}
        <Tabs.Content value="prompts" className="lx-tab-panel">
          <PromptsSettingsTab
            workflowSettings={workflowSettings}
            onSavePrompts={(patch) => updateWorkflowConfig(patch)}
          />
        </Tabs.Content>

        {/* TAB 3: NATIVE DOCLING CONVERSION ENGINE */}
        <Tabs.Content value="docling" className="lx-tab-panel">
          <DoclingSettingsTab
            conversion={workflowSettings?.conversion}
            onUpdateConversion={(patch) => updateWorkflowConfig({ conversion: patch })}
          />
        </Tabs.Content>

        {/* TAB 4: VISUAL ANALYSIS */}
        <Tabs.Content value="vision" className="lx-tab-panel">
          <VisionSettingsTab
            workflowSettings={workflowSettings}
            profiles={profiles}
            onUpdateWorkflowConfig={updateWorkflowConfig}
            onOpenPromptsTab={() => setTab("prompts")}
          />
        </Tabs.Content>

        {/* TAB 5: WORKSPACE & PATHS */}
        <Tabs.Content value="paths" className="lx-tab-panel">
          <WorkspacePathsTab />
        </Tabs.Content>

        {/* TAB 6: USER MANUAL, METADATA GLOSSARY & SYSTEM LIMITS */}
        <Tabs.Content value="manual" className="lx-tab-panel">
          <ManualLimitsSettingsTab />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
