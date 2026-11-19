import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Eye,
  Play,
  RefreshCw,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";
import { api } from "../lib/api.js";
import { InfoPopover, Modal, Select, StatusBadge, StatusDot, Switch } from "../components/ui.jsx";
import { isOpenEvidence } from "../components/EvidenceCard.jsx";
import { PipelineFlowConsole } from "../components/PipelineFlowConsole.jsx";

const shortHash = (h) => (h ? h.slice(0, 10) : "—");

export function PipelineView({
  scopeIds,
  workspace,
  loadingWorkspace,
  workflowSettings,
  profiles,
  jobStatus,
  evidenceRuns,
  onChangeEvidenceRun,
  onOpenDocumentById,
  onNavigate,
  onJobStarted,
  onOpenJumpToOpenEvidence,
  workflowModalRequest,
  onClearWorkflowModalRequest,
}) {
  const { t } = usePrefs();
  const [basisSearch, setBasisSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);

  // Full workflow preview/consent modal
  const [wfPlan, setWfPlan] = useState(null);
  const [wfMeta, setWfMeta] = useState(null); // { resume, review }
  const [wfTextConsent, setWfTextConsent] = useState(false);
  const [wfPixelConsent, setWfPixelConsent] = useState(false);
  const [wfReuse, setWfReuse] = useState(false);
  const [wfRefresh, setWfRefresh] = useState(false);
  const [wfSubmitting, setWfSubmitting] = useState(false);

  // Single-stage LLM consent modal
  const [singleStagePending, setSingleStagePending] = useState(null); // { kind: "enrich"|"A"|"B"|"C", label, model, pixels }
  const [singleConsent, setSingleConsent] = useState(false);
  const [singleFocus, setSingleFocus] = useState("");
  const [singleBusy, setSingleBusy] = useState(false);

  const busy = Boolean(jobStatus?.busy);

  const resolveRoleModel = (stage) => {
    const profName = workflowSettings?.profiles?.[stage] || "";
    const found = profiles.find((p) => p.name === profName);
    if (found) return found.options;
    if ((stage === "B" || stage === "C") && workflowSettings?.profiles?.A) {
      const fallback = profiles.find((p) => p.name === workflowSettings.profiles.A);
      return fallback?.options || null;
    }
    return null;
  };

  const reusableBasis = useMemo(() => {
    if (!workspace?.result?.documents?.length) return null;
    const docs = workspace.result.documents;
    if (docs.some((d) => !d.selected_run)) return null;
    return Object.fromEntries(docs.map((d) => [d.document, d.selected_run]));
  }, [workspace]);

  const openWorkflowModal = async (resume = null, review = null) => {
    if (!resume && !scopeIds.length) {
      toast.error(t("Bitte zuerst Dokumente im Korpus auswählen.", "Select documents in Corpus first."));
      return;
    }
    try {
      const plan = await api("workflow-preview", {
        documents: scopeIds,
        resume,
        reuse_basis: resume ? null : reusableBasis,
      });
      setWfPlan(plan);
      setWfMeta({ resume, review });
      setWfTextConsent(false);
      setWfPixelConsent(false);
      setWfReuse(false);
      setWfRefresh(false);
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Allow RunMonitor resume button to trigger the modal
  React.useEffect(() => {
    if (workflowModalRequest) {
      openWorkflowModal(workflowModalRequest.resume, workflowModalRequest);
      onClearWorkflowModalRequest?.();
    }
  }, [workflowModalRequest]);

  const startFullWorkflow = async () => {
    if (!wfPlan || !wfTextConsent) return;
    setWfSubmitting(true);
    try {
      await api("workflow-start", {
        documents: scopeIds,
        resume: wfMeta?.resume || null,
        configuration: wfPlan.configuration,
        send: wfTextConsent,
        send_pixels: wfPixelConsent,
        refresh: !wfReuse && wfRefresh,
        reuse_basis: wfReuse ? wfPlan.reuse_basis : null,
        allow_partial: allowPartial,
      });
      setWfPlan(null);
      toast.success(t("Gesamtanalyse gestartet", "End-to-end pipeline started"));
      onJobStarted?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setWfSubmitting(false);
    }
  };

  const runLocalConversion = async () => {
    if (!scopeIds.length) return;
    try {
      await api("convert", { documents: scopeIds });
      toast.success(t("Lokale Docling-Konvertierung gestartet", "Local Docling conversion started"));
      onJobStarted?.();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const triggerSingleStage = (kind) => {
    if (!scopeIds.length) {
      toast.error(t("Bitte zuerst Dokumente auswählen.", "Select documents first."));
      return;
    }
    if (kind === "enrich") {
      const vis = workflowSettings?.vision || {};
      const prof = resolveRoleModel("vision");
      const isLocalOnly = (!vis.description && !vis.chart) || (vis.mode === "inline" && !vis.description);
      if (isLocalOnly) {
        api("enrich", { documents: scopeIds, vision: { ...vis, profile: prof } })
          .then(() => {
            toast.success(t("Lokale Bildanalyse gestartet", "Local visual analysis started"));
            onJobStarted?.();
          })
          .catch((e) => toast.error(e.message));
        return;
      }
      if (!prof) {
        toast.error(t("Kein Vision-Profil in Einstellungen zugeordnet.", "No Vision profile assigned in Settings."));
        return;
      }
      setSingleConsent(false);
      setSingleStagePending({
        kind: "enrich",
        label: t("Visuelle Analyse (Bildanreicherung)", "Visual Analysis (Picture Enrichment)"),
        model: `${prof.provider} · ${prof.model}`,
        pixels: true,
      });
      return;
    }

    const prof = resolveRoleModel(kind);
    if (!prof?.model) {
      toast.error(
        t(
          `Kein Modellprofil für Stufe ${kind} zugeordnet. Bitte unter Einstellungen wählen.`,
          `No model profile assigned for Stage ${kind}. Configure it in Settings.`
        )
      );
      return;
    }
    setSingleConsent(false);
    setSingleStagePending({
      kind,
      label:
        kind === "A"
          ? t("Stufe A · Quellengebundene Beobachtungen", "Stage A · Source-Bound Observations")
          : kind === "B"
          ? t("Stufe B · Dokumentübergreifende Beziehungen", "Stage B · Cross-Document Relations")
          : t("Stufe C · UX-Finding-Kandidaten", "Stage C · UX Finding Candidates"),
      model: `${prof.provider} · ${prof.model}`,
      pixels: false,
    });
  };

  const executeSingleStage = async () => {
    if (!singleStagePending || !singleConsent) return;
    setSingleBusy(true);
    try {
      const { kind } = singleStagePending;
      if (kind === "enrich") {
        const prof = resolveRoleModel("vision");
        await api("enrich", {
          documents: scopeIds,
          vision: { ...(workflowSettings?.vision || {}), profile: prof, send: true },
        });
      } else if (kind === "A") {
        const prof = resolveRoleModel("A");
        const versions = {};
        for (const f of workspace?.files || []) {
          const v = f.summary?.preferred_version || f.summary?.version;
          if (v) versions[f.file.id] = v;
        }
        await api("extract", {
          documents: scopeIds,
          options: prof,
          versions,
          send: true,
        });
      } else if (kind === "B") {
        const prof = resolveRoleModel("B");
        await api("ux-relations", {
          documents: scopeIds,
          basis: workspace?.basis || {},
          options: prof,
          focus: singleFocus.trim(),
          allow_partial: allowPartial,
          send: true,
        });
      } else if (kind === "C") {
        const prof = resolveRoleModel("C");
        await api("ux-findings", {
          documents: scopeIds,
          basis: workspace?.basis || {},
          b_run: workspace?.runs?.B || null,
          options: prof,
          focus: singleFocus.trim(),
          allow_partial: allowPartial,
          send: true,
        });
      }
      setSingleStagePending(null);
      toast.success(t("Stufenauftrag gestartet", "Stage job started"));
      onJobStarted?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSingleBusy(false);
    }
  };

  const docs = workspace?.result?.documents || [];
  const filteredDocs = useMemo(() => {
    const q = basisSearch.trim().toLowerCase();
    if (!q) return docs.map((d, idx) => ({ d, idx }));
    return docs
      .map((d, idx) => ({ d, idx }))
      .filter(({ d }) => d.name.toLowerCase().includes(q));
  }, [docs, basisSearch]);

  const modelA = resolveRoleModel("A");
  const modelB = resolveRoleModel("B");
  const modelC = resolveRoleModel("C");
  const modelVision = resolveRoleModel("vision");

  return (
    <div className="lx-page">
      <header className="lx-page-header">
        <div className="min-w-0">
          <h1 className="lx-page-title">{t("Analyse-Pipeline", "Analysis Pipeline")}</h1>
          <p className="lx-page-subtitle">
            {t(
              "Mehrstufige Erschließung von der lokalen Docling-Struktur über Evidenz A und Relationen B bis zu Findings C.",
              "Multi-stage synthesis from local Docling structure through Evidence A and Relations B to Findings C."
            )}
          </p>
        </div>
        <div className="lx-btn-row">
          <button type="button" className="lx-btn" onClick={() => onNavigate("settings")}>
            <Settings size={14} />
            <span>{t("Modellrollen", "Model Roles")}</span>
          </button>
          <button
            type="button"
            id="workflow-open"
            className="lx-btn lx-btn-primary"
            disabled={!scopeIds.length || busy}
            onClick={() => openWorkflowModal()}
          >
            <Play size={14} />
            <span>{t("Gesamtanalyse starten", "Run Full Pipeline")}</span>
          </button>
        </div>
      </header>

      {scopeIds.length === 0 ? (
        <div className="lx-empty-state">
          <Sparkles size={28} strokeWidth={1.5} className="lx-icon-muted" />
          <h2>{t("Keine Studiendokumente ausgewählt", "No Study Documents Selected")}</h2>
          <p>
            {t(
              "Wähle im Studienkorpus alle zusammengehörigen Dateien einer Usability-Studie aus, um dokumentübergreifende Evidenz und Triangulation zu berechnen.",
              "Select all related files of a usability study in the Corpus view to enable cross-document triangulation."
            )}
          </p>
          <button type="button" className="lx-btn lx-btn-primary" onClick={() => onNavigate("documents")}>
            <span>{t("Dokumente im Korpus wählen", "Select Documents in Corpus")}</span>
            <ArrowRight size={14} />
          </button>
        </div>
      ) : (
        <>
          {/* Fluid 5-Stage Visual Pipeline + Live Safe Console */}
          <PipelineFlowConsole
            jobStatus={jobStatus}
            workspace={workspace}
            onOpenTerminal={() => onNavigate("terminal")}
            stages={[
              {
                step: "01",
                key: "convert",
                wfKey: "conversion",
                title: t("Docling-Struktur", "Docling Structure"),
                sub: t("Lokal · Layout, Tabellen, Seiten", "Local · Layout, tables, pages"),
                infoBody: t(
                  "Konvertiert alle ausgewählten Dokumente lokal auf deinem Rechner in adressierbare DoclingDocument-Strukturen mit Koordinaten und Tabellenrastern.",
                  "Locally parses all selected documents into addressable DoclingDocument structures with coordinates and table grids."
                ),
                actionLabel: t("Konvertieren", "Convert"),
                onRun: runLocalConversion,
              },
              {
                step: "02",
                key: "enrich",
                wfKey: "vision",
                title: t("Visuelle Analyse", "Visual Analysis"),
                sub: workflowSettings?.vision?.description
                  ? modelVision?.model || t("Vision-Profil fehlt", "No Vision profile")
                  : t("Lokal / Optional", "Local / Optional"),
                infoBody: t(
                  "Klassifiziert Abbildungen lokal, liest Diagrammtabellen aus und erzeugt optional Bildbeschreibungen über das zugeordnete Vision-Modell.",
                  "Classifies figures locally, extracts chart data tables, and optionally generates VLM descriptions."
                ),
                actionLabel: t("Anreichern", "Enrich"),
                onRun: () => triggerSingleStage("enrich"),
              },
              {
                step: "03",
                key: "A",
                wfKey: "A",
                title: t("Stufe A · Evidenz", "Stage A · Evidence"),
                sub: modelA?.model || t("Profil wählen", "Assign profile"),
                infoBody: t(
                  "Extrahiert pro Dokument wörtlich verankerte UX-Beobachtungen, Messwerte und Zitate und prüft jede Fundstelle gegen das Original.",
                  "Extracts verbatim-grounded UX observations and metrics per document and verifies every anchor against the source."
                ),
                actionLabel: t("A starten", "Run A"),
                onRun: () => triggerSingleStage("A"),
              },
              {
                step: "04",
                key: "B",
                wfKey: "B",
                title: t("Stufe B · Relationen", "Stage B · Relations"),
                sub: modelB?.model || t("Wie Stufe A", "Same as A"),
                infoBody: t(
                  "Verknüpft bestätigte/zitierbare Beobachtungen über Dokumentgrenzen hinweg (Stützung, Widerspruch, Spezifikation).",
                  "Connects citation-ready observations across documents (support, contradiction, qualification)."
                ),
                actionLabel: t("B starten", "Run B"),
                onRun: () => triggerSingleStage("B"),
              },
              {
                step: "05",
                key: "C",
                wfKey: "C",
                title: t("Stufe C · Findings", "Stage C · Findings"),
                sub: modelC?.model || t("Wie Stufe A", "Same as A"),
                infoBody: t(
                  "Verdichtet Beobachtungen (A) und Relationen (B) zu nachprüfbaren UX-Findings inklusive Valenz, Unsicherheit und Gegenbelegen.",
                  "Synthesizes Observations (A) and Relations (B) into auditable UX Findings with valence, uncertainty, and counterevidence."
                ),
                actionLabel: t("C starten", "Run C"),
                onRun: () => triggerSingleStage("C"),
              },
            ]}
          />

          {/* Partial basis switch bar */}
          <div className="lx-toolbar-card">
            <div className="lx-row-gap min-w-0">
              <ShieldCheck size={15} className="lx-icon-muted" />
              <span className="lx-text-sm truncate">
                {t(
                  `Aktiver Umfang: ${scopeIds.length} Dokumente`,
                  `Active Scope: ${scopeIds.length} documents`
                )}
              </span>
              {workspace?.runs?.C && (
                <StatusBadge
                  label={`${t("Aktueller Stand", "Latest C")} #${workspace.runs.C}`}
                  tone="success"
                />
              )}
            </div>
            <div className="lx-toolbar-right">
              <label className="lx-inline-switch">
                <Switch checked={allowPartial} onCheckedChange={setAllowPartial} />
                <span>
                  {t(
                    "Teilbasis für Einzelstufen B/C erlauben",
                    "Allow partial A-basis for single B/C runs"
                  )}
                </span>
              </label>
              <button
                type="button"
                className="lx-btn lx-btn-sm"
                onClick={() => onNavigate("results")}
              >
                <span>{t("Zu den Ergebnissen", "View Synthesis")}</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>

          {/* Saved Stage A Basis Table */}
          <section className="lx-table-card">
            <header className="lx-card-header">
              <div className="min-w-0">
                <h2 className="lx-card-title">
                  {t("Gespeicherte A-Basis & Quellenverankerung", "Saved Stage A Basis & Source Grounding")}
                </h2>
                <p className="lx-card-sub">
                  {t(
                    "Jedes Dokument speichert revisionssichere A-Läufe. Wähle pro Datei die gewünschte Evidenzbasis für B und C.",
                    "Each document retains immutable Stage A runs. Choose the evidence basis per document for B and C."
                  )}
                </p>
              </div>
              <input
                type="search"
                className="lx-input lx-input-sm"
                style={{ width: 220 }}
                value={basisSearch}
                onChange={(e) => setBasisSearch(e.target.value)}
                placeholder={t("Basis filtern …", "Filter basis…")}
              />
            </header>

            <div className="lx-table-scroll">
              <table className="lx-table">
                <thead>
                  <tr>
                    <th>{t("Dokument", "Document")}</th>
                    <th style={{ width: 280 }}>{t("Gewählter A-Lauf", "Selected Stage A Run")}</th>
                    <th>{t("Verankerung & Übergabe an B/C", "Grounding & Handoff to B/C")}</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingWorkspace && !docs.length ? (
                    <tr>
                      <td colSpan={3} className="lx-table-empty">
                        {t("Lade gespeicherte Läufe …", "Loading saved runs…")}
                      </td>
                    </tr>
                  ) : (
                    filteredDocs.map(({ d, idx }) => {
                      const fileBundle = workspace?.files?.[idx];
                      const candidateRuns = (fileBundle?.runs || []).filter(
                        (r) => !r.historical && r.result?.observations?.length
                      );
                      const options = candidateRuns.length
                        ? candidateRuns.map((r) => [
                            String(r.id),
                            `A #${r.id} · Docling ${shortHash(r.result?.document_version)} (${r.result?.observations?.length || 0})`,
                          ])
                        : [["none", t("Kein A-Lauf vorhanden", "No Stage A run")]];

                      const openObs = (workspace?.result?.observations || []).filter(
                        (e) => e.ref.document === d.document && isOpenEvidence(e)
                      );
                      const tech = d.technical || {};
                      const handoff = d.handoff || null;

                      return (
                        <tr key={d.document}>
                          <td>
                            <div className="lx-doc-cell min-w-0">
                              <button
                                type="button"
                                className="lx-doc-link truncate"
                                onClick={() => onOpenDocumentById(d.document)}
                              >
                                {d.name}
                              </button>
                              <span className="lx-doc-path tabular">
                                Docling{" "}
                                {shortHash(
                                  fileBundle?.summary?.preferred_version || fileBundle?.summary?.version
                                )}
                              </span>
                            </div>
                          </td>
                          <td>
                            <Select
                              size="sm"
                              disabled={!candidateRuns.length}
                              value={String(d.selected_run ?? "none")}
                              onValueChange={(v) => {
                                if (v !== "none") onChangeEvidenceRun(d.document, Number(v));
                              }}
                              options={options}
                            />
                          </td>
                          <td>
                            <div className="lx-basis-meta">
                              <div className="lx-row-wrap">
                                {tech.human_reconciled && (
                                  <StatusBadge
                                    label={t("Menschlich geklärt (Freigegeben)", "Human Reconciled")}
                                    tone="success"
                                  />
                                )}
                                {tech.salvaged && (
                                  <StatusBadge
                                    label={t("Schema-Salvage", "Schema Salvaged")}
                                    tone="warning"
                                  />
                                )}
                                {handoff ? (
                                  <>
                                    <span className="lx-tag tabular">
                                      <StatusDot
                                        tone={handoff.citation_ready > 0 ? "success" : "neutral"}
                                      />
                                      <span>
                                        {handoff.citation_ready}/{handoff.total}{" "}
                                        {t("zitierbar", "citation-ready")}
                                      </span>
                                    </span>
                                    {handoff.excluded > 0 && (
                                      <span className="lx-tag tabular lx-row-gap" style={{ gap: 4 }}>
                                        <span>
                                          {handoff.excluded} {t("ausgeschlossen", "excluded")}
                                        </span>
                                        {(d.exclusion_reasons || []).length > 0 && (
                                          <InfoPopover
                                            title={t(
                                              `Warum wurden ${handoff.excluded} Einträge ausgeschlossen?`,
                                              `Why were ${handoff.excluded} items excluded?`
                                            )}
                                          >
                                            <p className="lx-text-xs lx-muted">
                                              {t(
                                                "Nicht eindeutig verankerte oder verworfene Beobachtungen werden zum Schutz vor Halluzinationen nicht als Fakten an B/C übergeben:",
                                                "Unanchored or rejected observations are excluded from B/C to prevent hallucination propagation:"
                                              )}
                                            </p>
                                            <div className="lx-exclusion-list">
                                              {d.exclusion_reasons.map((ex, eIdx) => (
                                                <div key={eIdx} className="lx-exclusion-item">
                                                  <div className="lx-between">
                                                    <strong>{ex.observation}</strong>
                                                    <span className="lx-mono-tag">{ex.status}</span>
                                                  </div>
                                                  <div>{ex.reason}</div>
                                                  {ex.quote && (
                                                    <div className="lx-muted truncate">
                                                      „{ex.quote}“
                                                    </div>
                                                  )}
                                                  {ex.candidates_count > 0 && (
                                                    <div style={{ color: "var(--brand)", fontWeight: 600 }}>
                                                      {t(
                                                        `→ ${ex.candidates_count} Kandidaten per 1-Klick wählbar`,
                                                        `-> ${ex.candidates_count} candidates selectable in 1 click`
                                                      )}
                                                    </div>
                                                  )}
                                                </div>
                                              ))}
                                            </div>
                                          </InfoPopover>
                                        )}
                                      </span>
                                    )}
                                  </>
                                ) : (
                                  <span className="lx-muted lx-text-xs">
                                    {t("Noch keine extrahierte Basis", "No extracted basis yet")}
                                  </span>
                                )}
                                {tech.measurement_open > 0 && (
                                  <span className="lx-tag tabular">
                                    {tech.measurement_open}{" "}
                                    {t("sekundäre Messstellen offen", "secondary metrics open")}
                                  </span>
                                )}
                                {openObs.length > 0 && (
                                  <button
                                    type="button"
                                    className="lx-btn lx-btn-xs lx-btn-primary"
                                    onClick={() => onOpenJumpToOpenEvidence?.(openObs[0].ref)}
                                  >
                                    <Eye size={12} />
                                    <span>
                                      {openObs.length} {t("offene prüfen & heilen", "inspect & heal open")}
                                    </span>
                                  </button>
                                )}
                                {candidateRuns.length > 1 && d.selected_run && (
                                  <button
                                    type="button"
                                    className="lx-btn lx-btn-xs lx-btn-ghost"
                                    title={t(
                                      "Überträgt bestätigte Entscheidungen identischer Textstellen aus früheren A-Läufen auf diesen Lauf",
                                      "Carry forward human decisions for identical anchored quotes from prior A-runs"
                                    )}
                                    onClick={async () => {
                                      try {
                                        const res = await api("carry-forward-decisions", {
                                          document: d.document,
                                          run: d.selected_run,
                                        });
                                        toast.success(
                                          t(
                                            `${res.carried_forward} bestätigte Entscheidungen übernommen`,
                                            `Carried forward ${res.carried_forward} decisions`
                                          )
                                        );
                                        onJobStarted?.();
                                      } catch (err) {
                                        toast.error(err.message);
                                      }
                                    }}
                                  >
                                    <RefreshCw size={11} />
                                    <span>{t("Vorlauf-Review übernehmen", "Carry Review")}</span>
                                  </button>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* Full Workflow Plan & Conscious Consent Modal */}
      <Modal
        open={Boolean(wfPlan)}
        onOpenChange={(v) => !v && setWfPlan(null)}
        title={
          wfMeta?.resume
            ? t("Gesamtauftrag fortsetzen", "Resume Pipeline Run")
            : t("Gesamtanalyse prüfen & freigeben", "Review & Authorize Full Pipeline")
        }
        subtitle={t(
          "Externe Modellübermittlung erfolgt ausschließlich nach deiner expliziten Freigabe.",
          "External LLM transmission occurs strictly upon your explicit authorization."
        )}
        width={600}
      >
        {wfPlan && (
          <div className="lx-form-stack">
            <div className="lx-card lx-card-subtle lx-form-stack">
              <div className="lx-text-xs lx-muted">
                {t("Ausgewählte Dokumente", "Selected Documents")} ({wfPlan.documents?.length || 0})
              </div>
              <p className="lx-text-sm" style={{ lineHeight: 1.5 }}>
                {(wfPlan.documents || []).join(" · ")}
              </p>
              <div className="lx-divider" />
              <div className="lx-grid-2">
                {Object.entries(wfPlan.models || {}).map(([st, mdl]) => (
                  <div key={st} className="lx-kv-item min-w-0">
                    <span className="lx-muted lx-text-xs">Stufe {st}</span>
                    <strong className="lx-text-xs truncate" title={mdl}>
                      {mdl}
                    </strong>
                  </div>
                ))}
                <div className="lx-kv-item min-w-0">
                  <span className="lx-muted lx-text-xs">{t("Bildanalyse", "Visual Analysis")}</span>
                  <strong className="lx-text-xs truncate">
                    {wfPlan.vision_enabled
                      ? wfPlan.vision_model || t("Aktiv", "Enabled")
                      : t("Deaktiviert", "Disabled")}
                  </strong>
                </div>
              </div>
            </div>

            {wfPlan.reuse_basis && !wfMeta?.resume && (
              <label className="lx-inline-switch">
                <Switch checked={wfReuse} onCheckedChange={setWfReuse} />
                <span>
                  {t(
                    "Vorhandene gewählte A-Basis wiederverwenden (überspringt Konvertierung, Vision & A)",
                    "Reuse selected Stage A basis (skips Conversion, Vision & Stage A)"
                  )}
                </span>
              </label>
            )}

            {!wfReuse && !wfMeta?.resume && (
              <label className="lx-inline-switch">
                <Switch checked={wfRefresh} onCheckedChange={setWfRefresh} />
                <span>
                  {t(
                    "Bereits abgeschlossene Teilschritte frisch neu berechnen",
                    "Force recomputation of already completed steps"
                  )}
                </span>
              </label>
            )}

            <div className="lx-consent-box">
              <label className="lx-check-label">
                <input
                  type="checkbox"
                  className="lx-checkbox"
                  checked={wfTextConsent}
                  onChange={(e) => setWfTextConsent(e.target.checked)}
                />
                <span>
                  {t(
                    "Ich gebe die Übermittlung der strukturierten Dokumenttexte an die oben genannten Modellendpunkte frei.",
                    "I authorize sending structured document text to the configured model endpoints above."
                  )}
                </span>
              </label>

              {wfPlan.vision_pixels && !wfReuse && (
                <label className="lx-check-label">
                  <input
                    type="checkbox"
                    className="lx-checkbox"
                    checked={wfPixelConsent}
                    onChange={(e) => setWfPixelConsent(e.target.checked)}
                  />
                  <span>
                    {t(
                      "Zusätzlich Bildpixel (eingebettete Grafiken / Folienkontext) an das Vision-Modell senden.",
                      "Also transmit image pixels (embedded figures / slide renders) to the Vision model."
                    )}
                  </span>
                </label>
              )}
            </div>

            <div className="lx-modal-actions">
              <button type="button" className="lx-btn" onClick={() => setWfPlan(null)}>
                {t("Abbrechen", "Cancel")}
              </button>
              <button
                type="button"
                disabled={!wfTextConsent || wfSubmitting}
                className="lx-btn lx-btn-primary"
                onClick={startFullWorkflow}
              >
                <Play size={14} />
                <span>
                  {wfSubmitting
                    ? t("Startet …", "Starting…")
                    : t("Pipeline jetzt starten", "Start Pipeline Now")}
                </span>
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Single-Stage Conscious Consent Modal */}
      <Modal
        open={Boolean(singleStagePending)}
        onOpenChange={(v) => !v && setSingleStagePending(null)}
        title={singleStagePending?.label || ""}
        subtitle={t("Einzelstufen-Ausführung bestätigen", "Authorize Single-Stage Execution")}
      >
        {singleStagePending && (
          <div className="lx-form-stack">
            <div className="lx-card lx-card-subtle">
              <div className="lx-between">
                <span className="lx-muted lx-text-xs">{t("Zielmodell", "Target Model")}</span>
                <code className="lx-mono-tag">{singleStagePending.model}</code>
              </div>
              <div className="lx-between" style={{ marginTop: 6 }}>
                <span className="lx-muted lx-text-xs">{t("Dokumente", "Documents")}</span>
                <strong className="tabular lx-text-xs">{scopeIds.length}</strong>
              </div>
            </div>
            {(singleStagePending.kind === "B" || singleStagePending.kind === "C") && (
              <label className="lx-field">
                <span className="lx-field-label">
                  {t(
                    "Optionaler Forschungsfokus / Fragestellung für diesen Lauf",
                    "Optional Research Focus / Question for this Run"
                  )}
                </span>
                <input
                  type="text"
                  className="lx-input lx-input-sm"
                  value={singleFocus}
                  onChange={(e) => setSingleFocus(e.target.value)}
                  placeholder={t(
                    "z. B. Fokus auf Checkout-Abbrüche oder Vergleich Aufgabe 1 vs. 2 …",
                    "e.g. Focus on checkout friction or Task 1 vs Task 2…"
                  )}
                />
              </label>
            )}
            <div className="lx-consent-box">
              <label className="lx-check-label">
                <input
                  type="checkbox"
                  className="lx-checkbox"
                  checked={singleConsent}
                  onChange={(e) => setSingleConsent(e.target.checked)}
                />
                <span>
                  {singleStagePending.pixels
                    ? t(
                        "Bildpixel für diesen Einzellauf bewusst an das konfigurierte Vision-Modell übermitteln.",
                        "Consciously transmit image pixels to the configured Vision endpoint."
                      )
                    : t(
                        "Strukturierte Studiendaten für diese Stufe an das gewählte Modell senden.",
                        "Transmit structured study inputs for this stage to the selected model."
                      )}
                </span>
              </label>
            </div>
            <div className="lx-modal-actions">
              <button type="button" className="lx-btn" onClick={() => setSingleStagePending(null)}>
                {t("Abbrechen", "Cancel")}
              </button>
              <button
                type="button"
                disabled={!singleConsent || singleBusy}
                className="lx-btn lx-btn-primary"
                onClick={executeSingleStage}
              >
                <Play size={13} />
                <span>{t("Stufe ausführen", "Execute Stage")}</span>
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
