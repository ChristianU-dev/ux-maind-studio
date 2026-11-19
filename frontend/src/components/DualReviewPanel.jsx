import React, { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  Edit3,
  EyeOff,
  FolderDown,
  Lock,
  Unlock,
  Upload,
  Users,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../lib/i18n.jsx";
import { api, apiUploadBinary } from "../lib/api.js";
import { Modal, Select, StatusDot } from "./ui.jsx";

const ACTION_LABELS = {
  confirmed: { de: "Bestätigt", en: "Confirmed", tone: "success" },
  corrected: { de: "Korrigiert", en: "Corrected", tone: "active" },
  rejected: { de: "Verworfen", en: "Rejected", tone: "danger" },
  open: { de: "Offen", en: "Open", tone: "warning" },
};

const EDITABLE_FIELDS = [
  "title",
  "valence",
  "finding_type",
  "usability_heuristic",
  "rationale",
  "observed_effect",
  "scope",
  "uncertainty",
  "improvement_hypothesis",
];

function FindingFieldsEditor({ draft, setDraft, t }) {
  return (
    <div className="lx-form-stack" style={{ marginTop: 8 }}>
      <div className="lx-grid-2">
        <label className="lx-field">
          <span className="lx-field-label">{t("Finding-Titel", "Finding Title")}</span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.title || ""}
            onChange={(e) => setDraft((f) => ({ ...f, title: e.target.value }))}
          />
        </label>
        <label className="lx-field">
          <span className="lx-field-label">{t("Valenz", "Valence")}</span>
          <Select
            size="sm"
            value={draft.valence || "neutral"}
            onValueChange={(v) => setDraft((f) => ({ ...f, valence: v }))}
            options={[
              ["problem", t("Nutzungsproblem (problem)", "Usability Problem")],
              ["strength", t("Stärke / Positiv (strength)", "Strength / Positive")],
              ["mixed", t("Ambivalent / Gemischt (mixed)", "Mixed / Ambivalent")],
              ["neutral", t("Neutral / Kontext (neutral)", "Neutral / Context")],
              ["unclear", t("Unklar / Polung offen (unclear)", "Unclear / Polarity Open")],
            ]}
          />
        </label>
      </div>
      <div className="lx-grid-2">
        <label className="lx-field">
          <span className="lx-field-label">
            {t("Usability-Kriterium (Nielsen / ISO / WCAG)", "UX Criterion")}
          </span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.usability_heuristic || ""}
            onChange={(e) => setDraft((f) => ({ ...f, usability_heuristic: e.target.value }))}
          />
        </label>
        <label className="lx-field">
          <span className="lx-field-label">{t("Befundtyp (finding_type)", "Finding Type")}</span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.finding_type || ""}
            onChange={(e) => setDraft((f) => ({ ...f, finding_type: e.target.value }))}
          />
        </label>
      </div>
      <label className="lx-field">
        <span className="lx-field-label">{t("Synthese & Begründung", "Rationale")}</span>
        <textarea
          rows={2}
          className="lx-textarea lx-text-xs"
          value={draft.rationale || ""}
          onChange={(e) => setDraft((f) => ({ ...f, rationale: e.target.value }))}
        />
      </label>
      <div className="lx-grid-2">
        <label className="lx-field">
          <span className="lx-field-label">{t("Beobachtete Wirkung", "Observed Effect")}</span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.observed_effect || ""}
            onChange={(e) => setDraft((f) => ({ ...f, observed_effect: e.target.value }))}
          />
        </label>
        <label className="lx-field">
          <span className="lx-field-label">{t("Geltungsbereich (Scope)", "Scope")}</span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.scope || ""}
            onChange={(e) => setDraft((f) => ({ ...f, scope: e.target.value }))}
          />
        </label>
      </div>
      <div className="lx-grid-2">
        <label className="lx-field">
          <span className="lx-field-label">{t("Unsicherheit", "Uncertainty")}</span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.uncertainty || ""}
            onChange={(e) => setDraft((f) => ({ ...f, uncertainty: e.target.value }))}
          />
        </label>
        <label className="lx-field">
          <span className="lx-field-label">{t("Gestaltungshypothese", "Design Hypothesis")}</span>
          <input
            type="text"
            className="lx-input lx-input-sm"
            value={draft.improvement_hypothesis || ""}
            onChange={(e) => setDraft((f) => ({ ...f, improvement_hypothesis: e.target.value }))}
          />
        </label>
      </div>
    </div>
  );
}

export function DualReviewStartModal({
  open,
  onOpenChange,
  workspace,
  researcherState,
  onSessionStarted,
}) {
  const { t } = usePrefs();
  const [mode, setMode] = useState("same_machine");
  const [revAName, setRevAName] = useState("");
  const [revACode, setRevACode] = useState("");
  const [revBName, setRevBName] = useState("");
  const [revBCode, setRevBCode] = useState("");
  const [selectedFindingIds, setSelectedFindingIds] = useState(() => new Set());
  const [busy, setBusy] = useState(false);

  const findingObjects = (workspace?.result?.objects || []).filter((o) => o.kind === "finding");

  useEffect(() => {
    if (!open) return;
    const profiles = researcherState?.profiles || [];
    const act = researcherState?.active || profiles[0];
    setRevAName(act?.display_name || "Prüfer 1");
    setRevACode(act?.short_code || "P1");
    const other = profiles.find((p) => p.id !== act?.id && p.id !== "default");
    setRevBName(other?.display_name || "Zweitprüfer 2");
    setRevBCode(other?.short_code || "P2");
    setSelectedFindingIds(new Set(findingObjects.map((f) => f.id)));
  }, [open]);

  const toggleFinding = (fid) => {
    setSelectedFindingIds((prev) => {
      const next = new Set(prev);
      if (next.has(fid)) next.delete(fid);
      else next.add(fid);
      return next;
    });
  };

  const handleStart = async () => {
    if (!revAName.trim() || !revBName.trim()) {
      toast.error(t("Bitte Anzeigename oder Kürzel für beide Prüfer angeben.", "Enter names or codes for both reviewers."));
      return;
    }
    if (!selectedFindingIds.size) {
      toast.error(t("Mindestens ein Finding auswählen.", "Select at least one Finding."));
      return;
    }
    setBusy(true);
    try {
      const res = await api("dual-review-start", {
        mode,
        documents: workspace?.documents || [],
        basis: workspace?.basis || {},
        result_runs: workspace?.runs || {},
        finding_ids: [...selectedFindingIds],
        reviewer_a: { display_name: revAName.trim(), short_code: revACode.trim() },
        reviewer_b: { display_name: revBName.trim(), short_code: revBCode.trim() },
      });
      toast.success(
        mode === "same_machine"
          ? t(
              "Zweitprüfung (Am selben Rechner) gestartet — Ausgangsstand eingefroren",
              "Dual review (Same Machine) started — baseline frozen"
            )
          : t(
              "Zweitprüfung (Auf zwei Rechnern) gestartet — Prüfpaket bereit zum Export",
              "Dual review (Two Machines) started — assignment package ready to export"
            )
      );
      onOpenChange(false);
      await onSessionStarted?.(res);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("Unabhängige Zweitprüfung starten", "Start Independent Dual Review")}
      subtitle={t(
        "Hält den aktuellen Ausgangsstand (Findings, Laufversionen & Originalbelege) fest. Bis beide abgegeben haben, ist nur die eigene Bewertung sichtbar; der Vergleich bleibt bis zur Freigabe verborgen.",
        "Captures the current baseline (Findings, run versions & verbatim anchors). Until both submit, only your assessment is visible; the comparison remains hidden until release."
      )}
    >
      <div className="lx-form-stack">
        <div className="lx-grid-2">
          <button
            type="button"
            data-testid="dual-mode-same"
            className={`lx-card ${mode === "same_machine" ? "lx-card-selected" : "lx-card-subtle"}`}
            style={{
              textAlign: "left",
              cursor: "pointer",
              borderColor: mode === "same_machine" ? "var(--accent)" : undefined,
            }}
            onClick={() => setMode("same_machine")}
          >
            <div className="lx-between">
              <strong className="lx-text-sm">{t("Am selben Rechner", "On the Same Machine")}</strong>
              <StatusDot tone={mode === "same_machine" ? "success" : "neutral"} />
            </div>
            <p className="lx-muted lx-text-xs" style={{ marginTop: 4 }}>
              {t(
                "Prüfer 1 und Prüfer 2 arbeiten nacheinander über den lokalen Profilwechsel im selben Arbeitsbereich.",
                "Reviewer 1 and Reviewer 2 evaluate sequentially via local profile switching."
              )}
            </p>
          </button>

          <button
            type="button"
            data-testid="dual-mode-two"
            className={`lx-card ${mode === "two_machines" ? "lx-card-selected" : "lx-card-subtle"}`}
            style={{
              textAlign: "left",
              cursor: "pointer",
              borderColor: mode === "two_machines" ? "var(--accent)" : undefined,
            }}
            onClick={() => setMode("two_machines")}
          >
            <div className="lx-between">
              <strong className="lx-text-sm">{t("Auf zwei Rechnern", "Across Two Machines")}</strong>
              <StatusDot tone={mode === "two_machines" ? "success" : "neutral"} />
            </div>
            <p className="lx-muted lx-text-xs" style={{ marginTop: 4 }}>
              {t(
                "Selbsttragendes Prüfpaket (.zip inkl. Originalbelegen) für Rechner 2; Rückgabe & Vergleich als lokale Datei (.json).",
                "Self-contained review package (.zip with originals) for Machine 2; return & comparison via local .json files."
              )}
            </p>
          </button>
        </div>

        <div className="lx-grid-2">
          <div className="lx-card lx-card-subtle lx-form-stack" style={{ gap: 8 }}>
            <strong className="lx-text-xs">{t("Prüfer 1 (Erstprüfer)", "Reviewer 1")}</strong>
            <input
              type="text"
              data-testid="dual-rev-a-name"
              className="lx-input lx-input-sm"
              placeholder={t("Anzeigename oder Kürzel …", "Display name or code…")}
              value={revAName}
              onChange={(e) => setRevAName(e.target.value)}
            />
            <input
              type="text"
              data-testid="dual-rev-a-code"
              className="lx-input lx-input-sm"
              placeholder={t("Kürzel (optional, z. B. CU)", "Short code (optional)")}
              value={revACode}
              onChange={(e) => setRevACode(e.target.value)}
            />
          </div>
          <div className="lx-card lx-card-subtle lx-form-stack" style={{ gap: 8 }}>
            <strong className="lx-text-xs">{t("Prüfer 2 (Zweitprüfer)", "Reviewer 2")}</strong>
            <input
              type="text"
              data-testid="dual-rev-b-name"
              className="lx-input lx-input-sm"
              placeholder={t("Anzeigename oder Kürzel …", "Display name or code…")}
              value={revBName}
              onChange={(e) => setRevBName(e.target.value)}
            />
            <input
              type="text"
              data-testid="dual-rev-b-code"
              className="lx-input lx-input-sm"
              placeholder={t("Kürzel (optional, z. B. ZP2)", "Short code (optional)")}
              value={revBCode}
              onChange={(e) => setRevBCode(e.target.value)}
            />
          </div>
        </div>

        <div className="lx-card lx-card-subtle lx-form-stack" style={{ gap: 6 }}>
          <div className="lx-between">
            <strong className="lx-text-xs">
              {t(
                `Ausgangsstand: Zu prüfende Findings auswählen (${selectedFindingIds.size} / ${findingObjects.length})`,
                `Baseline: Select Findings to include (${selectedFindingIds.size} / ${findingObjects.length})`
              )}
            </strong>
            <div className="lx-row-gap">
              <button
                type="button"
                className="lx-btn lx-btn-xs"
                onClick={() => setSelectedFindingIds(new Set(findingObjects.map((f) => f.id)))}
              >
                {t("Alle", "All")}
              </button>
              <button
                type="button"
                className="lx-btn lx-btn-xs lx-btn-ghost"
                onClick={() => setSelectedFindingIds(new Set())}
              >
                {t("Keine", "None")}
              </button>
            </div>
          </div>
          <div style={{ maxHeight: 180, overflowY: "auto" }} className="lx-form-stack">
            {findingObjects.map((f) => (
              <label key={f.id} className="lx-row-gap lx-text-xs" style={{ cursor: "pointer" }}>
                <input
                  type="checkbox"
                  className="lx-checkbox"
                  checked={selectedFindingIds.has(f.id)}
                  onChange={() => toggleFinding(f.id)}
                />
                <span className="lx-mono-tag">C #{f.id}</span>
                <span className="truncate">{f.effective?.title || f.proposal?.title}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="lx-between">
          <span className="lx-muted lx-text-xs">
            {t(
              "Kein Cloud-Konto nötig · Lokale Speicherung in SQLite",
              "No cloud account required · Local SQLite storage"
            )}
          </span>
          <button
            type="button"
            data-testid="dual-start-confirm"
            disabled={busy || !findingObjects.length}
            className="lx-btn lx-btn-sm lx-btn-primary"
            onClick={handleStart}
          >
            <Users size={13} />
            <span>
              {t("Ausgangsstand einfrieren & starten", "Freeze Baseline & Start")}
            </span>
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function DualReviewSessionBanner({
  session,
  onSwitchProfile,
  onRefreshAll,
  onImportPackageFile,
}) {
  const { t } = usePrefs();
  const fileInputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  if (!session) return null;

  const isTwo = session.mode === "two_machines";
  const isPeer = session.role_on_this_machine === "peer";
  const slot = session.viewer_slot;
  const ownSubmitted =
    slot === "reviewer_a"
      ? Boolean(session.submitted_a_at)
      : slot === "reviewer_b"
      ? Boolean(session.submitted_b_at)
      : false;
  const bothSubmitted = Boolean(session.submitted_a_at && session.submitted_b_at);
  const canVoteHere =
    !isTwo
      ? slot === "reviewer_a" || slot === "reviewer_b"
      : isPeer
      ? slot === "reviewer_b"
      : slot === "reviewer_a";

  const handleSubmitOwn = async () => {
    setBusy(true);
    try {
      await api("dual-review-submit", { session_id: session.session_id });
      toast.success(
        t(
          "Deine erste Bewertung ist abgegeben",
          "Your first assessment has been submitted"
        )
      );
      await onRefreshAll?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleRelease = async () => {
    setBusy(true);
    try {
      await api("dual-review-release", { session_id: session.session_id });
      toast.success(
        t(
          "Vergleich freigegeben — beide Bewertungen sind jetzt nebeneinander sichtbar",
          "Comparison released — both judgments are now visible side-by-side"
        )
      );
      await onRefreshAll?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const triggerFileImport = () => fileInputRef.current?.click();

  const savePackageToExports = async (kind, extraQuery = "") => {
    setBusy(true);
    try {
      const res = await api(
        `dual-review-export?session_id=${encodeURIComponent(
          session.session_id
        )}&kind=${encodeURIComponent(kind)}&save=1${extraQuery}`
      );
      toast.success(`${t("Gespeichert unter", "Saved to")}: ${res?.path || res?.filename}`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const onFilePicked = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      await onImportPackageFile?.(file);
    } finally {
      setBusy(false);
    }
  };

  const modeBadge = isTwo
    ? isPeer
      ? t("Auf zwei Rechnern · Rechner 2 (Zweitprüfer)", "Two Machines · Machine 2 (Peer)")
      : t("Auf zwei Rechnern · Rechner 1 (Ausgangsrechner)", "Two Machines · Machine 1 (Origin)")
    : t("Am selben Rechner", "Same Machine");

  return (
    <section
      className="lx-card lx-card-subtle"
      data-testid="dual-review-session-banner"
      style={{ margin: "0 0 10px 0", padding: "10px 14px", borderLeft: "3px solid var(--accent)" }}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".zip,.json"
        style={{ display: "none" }}
        onChange={onFilePicked}
      />
      <div className="lx-between" style={{ flexWrap: "wrap", gap: 8 }}>
        <div className="lx-row-gap" style={{ flexWrap: "wrap" }}>
          <Users size={14} className="lx-icon-muted" />
          <strong className="lx-text-xs">{t("Zweitprüfung aktiv", "Dual Review Active")}:</strong>
          <span className="lx-mono-tag">{modeBadge}</span>
          <span className="lx-mono-tag" title={`Baseline SHA-256: ${session.baseline_sha256}`}>
            ID {session.session_id.slice(0, 8)} · Hash {session.baseline_sha256.slice(0, 8)}
          </span>
          {!session.released ? (
            <span
              className="lx-pill lx-pill-warning"
              data-testid="dual-visibility-pill"
              style={{ fontSize: 11 }}
            >
              <EyeOff size={11} style={{ marginRight: 4 }} />
              {t("Nur eigene Bewertung sichtbar", "Only your assessment is visible")}
            </span>
          ) : (
            <span
              className="lx-pill lx-pill-success"
              data-testid="dual-visibility-pill"
              style={{ fontSize: 11 }}
            >
              <Unlock size={11} style={{ marginRight: 4 }} />
              {t("Vergleich freigegeben", "Comparison released")}
            </span>
          )}
        </div>

        <div className="lx-row-gap" style={{ flexWrap: "wrap" }}>
          <span className="lx-text-xs">
            <StatusDot tone={session.submitted_a_at ? "success" : "warning"} />{" "}
            <strong>1: {session.reviewer_a?.display_name}</strong>{" "}
            <span className="lx-muted">
              ({session.submitted_a_at ? t("abgegeben", "submitted") : t("offen", "pending")})
            </span>
          </span>
          <span className="lx-muted">·</span>
          <span className="lx-text-xs">
            <StatusDot tone={session.submitted_b_at ? "success" : "warning"} />{" "}
            <strong>2: {session.reviewer_b?.display_name}</strong>{" "}
            <span className="lx-muted">
              ({session.submitted_b_at ? t("abgegeben", "submitted") : t("offen", "pending")})
            </span>
          </span>
        </div>
      </div>

      <div className="lx-between" style={{ marginTop: 8, flexWrap: "wrap", gap: 8 }}>
        <div className="lx-muted lx-text-xs">
          {!session.released ? (
            canVoteHere && !ownSubmitted ? (
              <span>
                {t("Eigener Fortschritt", "Own progress")}:{" "}
                <strong className="tabular">
                  {session.own_decided_count} / {session.total_findings}
                </strong>{" "}
                Findings
              </span>
            ) : ownSubmitted ? (
              <span data-testid="dual-banner-submitted-note">
                {t(
                  "Deine erste Bewertung ist abgegeben. Der Vergleich bleibt bis zur Freigabe verborgen.",
                  "Your first assessment has been submitted. The comparison remains hidden until release."
                )}
              </span>
            ) : (
              <span>
                {t(
                  "Wechsle zum vorgesehenen Prüfer-Profil oder importiere die Rückgabedatei.",
                  "Switch to the designated reviewer profile or import the return file."
                )}
              </span>
            )
          ) : (
            <span>
              {t(
                "Schritt 3 & 4 aktiv: Urteile vergleichen, optional Folgebewertung ergänzen und Studienstand je Finding übernehmen.",
                "Step 3 & 4 active: Compare judgments, optionally add a revision, and adopt each Finding into the study state."
              )}
            </span>
          )}
        </div>

        <div className="lx-btn-row" style={{ flexWrap: "wrap" }}>
          {!session.released && canVoteHere && !ownSubmitted && (
            <button
              type="button"
              data-testid="dual-submit-own"
              disabled={busy}
              className="lx-btn lx-btn-xs lx-btn-primary"
              onClick={handleSubmitOwn}
            >
              <Lock size={12} />
              <span>{t("Ersturteil verbindlich abgeben", "Submit Initial Judgment")}</span>
            </button>
          )}

          {!isTwo && (
            <>
              {slot !== "reviewer_a" && (
                <button
                  type="button"
                  data-testid="dual-switch-rev-a"
                  disabled={busy}
                  className="lx-btn lx-btn-xs"
                  onClick={() => onSwitchProfile?.(session.reviewer_a.id)}
                >
                  <span>
                    {t("Zu Prüfer 1 wechseln", "Switch to Reviewer 1")} ({session.reviewer_a.display_name})
                  </span>
                </button>
              )}
              {slot !== "reviewer_b" && (
                <button
                  type="button"
                  data-testid="dual-switch-rev-b"
                  disabled={busy}
                  className="lx-btn lx-btn-xs"
                  onClick={() => onSwitchProfile?.(session.reviewer_b.id)}
                >
                  <span>
                    {t("Zu Prüfer 2 wechseln", "Switch to Reviewer 2")} ({session.reviewer_b.display_name})
                  </span>
                </button>
              )}
            </>
          )}

          {isTwo && !isPeer && (
            <>
              <a
                data-testid="dual-export-assignment"
                className="lx-btn lx-btn-xs"
                href={`/api/dual-review-export?session_id=${encodeURIComponent(
                  session.session_id
                )}&kind=assignment`}
              >
                <Download size={12} />
                <span>{t("Prüfpaket (.zip)", "Review Package (.zip)")}</span>
              </a>
              <button
                type="button"
                data-testid="dual-save-assignment-to-exports"
                disabled={busy}
                className="lx-btn lx-btn-xs lx-btn-ghost"
                title={t("Prüfpaket im Ausgabeordner ablegen", "Save package in output folder")}
                onClick={() => savePackageToExports("assignment")}
              >
                <FolderDown size={12} />
                <span>{t("Paket ablegen", "Save .zip")}</span>
              </button>
            </>
          )}

          {isTwo && isPeer && session.submitted_b_at && (
            <>
              <a
                data-testid="dual-export-submission"
                className="lx-btn lx-btn-xs lx-btn-primary"
                href={`/api/dual-review-export?session_id=${encodeURIComponent(
                  session.session_id
                )}&kind=submission&slot=reviewer_b`}
              >
                <Download size={12} />
                <span>
                  {session.released
                    ? t("Bewertung / Überarbeitung (.json) exportieren", "Export Return / Revision (.json)")
                    : t("Bewertungs-Rückgabe (.json) exportieren", "Export Submission (.json)")}
                </span>
              </a>
              <button
                type="button"
                data-testid="dual-save-submission-to-exports"
                disabled={busy}
                className="lx-btn lx-btn-xs"
                onClick={() => savePackageToExports("submission", "&slot=reviewer_b")}
              >
                <FolderDown size={12} />
                <span>{t("Rückgabe ablegen", "Save .json")}</span>
              </button>
            </>
          )}

          {isTwo && (
            <button
              type="button"
              data-testid="dual-import-file-btn"
              disabled={busy}
              className="lx-btn lx-btn-xs"
              onClick={triggerFileImport}
            >
              <Upload size={12} />
              <span>
                {isPeer
                  ? t("Freigegebenen Vergleich (.json) importieren", "Import Released Comparison (.json)")
                  : t("Abgabe / Überarbeitung (.json) importieren", "Import Submission / Revision (.json)")}
              </span>
            </button>
          )}

          {!session.released && (!isTwo || !isPeer) && (
            <button
              type="button"
              data-testid="dual-release-btn"
              disabled={busy || !bothSubmitted}
              title={
                bothSubmitted
                  ? t("Vergleich jetzt freigeben", "Release comparison now")
                  : t("Beide Ersturteile müssen vorliegen", "Both initial submissions required")
              }
              className={`lx-btn lx-btn-xs ${bothSubmitted ? "lx-btn-primary" : ""}`}
              onClick={handleRelease}
            >
              <Unlock size={12} />
              <span>{t("Vergleich freigeben", "Release Comparison")}</span>
            </button>
          )}

          {isTwo && !isPeer && session.released && (
            <>
              <a
                data-testid="dual-export-comparison"
                className="lx-btn lx-btn-xs lx-btn-primary"
                href={`/api/dual-review-export?session_id=${encodeURIComponent(
                  session.session_id
                )}&kind=comparison`}
              >
                <Download size={12} />
                <span>{t("Vergleich für Rechner 2 (.json)", "Comparison for Machine 2 (.json)")}</span>
              </a>
              <button
                type="button"
                data-testid="dual-save-comparison-to-exports"
                disabled={busy}
                className="lx-btn lx-btn-xs"
                onClick={() => savePackageToExports("comparison")}
              >
                <FolderDown size={12} />
                <span>{t("Vergleich ablegen", "Save .json")}</span>
              </button>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function ReviewerColumnCard({ label, profile, slotData, baseline, lang, t }) {
  const init = slotData?.initial;
  const revs = slotData?.revisions || [];

  const renderDiffs = (entry) => {
    const interp = entry?.interpretation || {};
    const changedKeys = Object.keys(interp).filter(
      (k) => (interp[k] || null) !== (baseline?.[k] || null)
    );
    if (!changedKeys.length) return null;
    return (
      <div className="lx-form-stack" style={{ gap: 3, marginTop: 6 }}>
        {changedKeys.map((k) => (
          <div key={k} className="lx-text-xs" style={{ wordBreak: "break-word" }}>
            <span className="lx-mono-tag">{k}:</span>{" "}
            <strong>{String(interp[k] ?? "—")}</strong>
          </div>
        ))}
      </div>
    );
  };

  const actBadge = (act) => {
    const m = ACTION_LABELS[act] || { de: act, en: act, tone: "neutral" };
    return (
      <span className="lx-row-gap lx-text-xs">
        <StatusDot tone={m.tone} />
        <strong>{lang === "en" ? m.en : m.de}</strong>
      </span>
    );
  };

  return (
    <div className="lx-card lx-card-subtle lx-form-stack" style={{ gap: 6 }}>
      <div className="lx-between">
        <strong className="lx-text-xs">
          {label}: {profile?.display_name}{" "}
          {profile?.short_code ? `(${profile.short_code})` : ""}
        </strong>
      </div>

      {!init ? (
        <span className="lx-muted lx-text-xs">{t("Kein Ersturteil", "No initial judgment")}</span>
      ) : (
        <div
          style={{
            padding: "6px 8px",
            borderRadius: 6,
            background: "var(--surface-1)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div className="lx-between">
            <span className="lx-text-xs lx-muted">{t("Ersturteil (eingefroren)", "Initial Judgment")}</span>
            {actBadge(init.action)}
          </div>
          {init.reason && (
            <p className="lx-text-xs" style={{ marginTop: 4, fontStyle: "italic" }}>
              „{init.reason}“
            </p>
          )}
          {renderDiffs(init)}
        </div>
      )}

      {revs.map((rv, idx) => (
        <div
          key={rv.decision_uid || idx}
          style={{
            padding: "6px 8px",
            borderRadius: 6,
            background: "var(--surface-2)",
            borderLeft: "3px solid var(--accent)",
          }}
        >
          <div className="lx-between">
            <span className="lx-text-xs">
              <strong>{t(`Spätere Änderung #${idx + 1}`, `Post-Release Revision #${idx + 1}`)}</strong>
            </span>
            {actBadge(rv.action)}
          </div>
          {rv.reason && (
            <p className="lx-text-xs" style={{ marginTop: 4, fontStyle: "italic" }}>
              „{rv.reason}“
            </p>
          )}
          {renderDiffs(rv)}
        </div>
      ))}
    </div>
  );
}

export function DualReviewFindingWorkbench({ finding, onSaved }) {
  const { lang, t } = usePrefs();
  const dr = finding?.dual_review;
  const eff = finding?.effective || {};

  const [reason, setReason] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [consensusOpen, setConsensusOpen] = useState(false);
  const [adoptNote, setAdoptNote] = useState("");
  const [draftFields, setDraftFields] = useState({});
  const [consensusFields, setConsensusFields] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ownInit = dr?.own_initial;
    setReason(!dr?.released && ownInit?.reason ? ownInit.reason : "");
    setEditOpen(false);
    setRevisionOpen(false);
    setConsensusOpen(false);
    const seed = {};
    for (const k of EDITABLE_FIELDS) seed[k] = eff[k] || "";
    setDraftFields(seed);
    setConsensusFields(seed);
  }, [finding?.id, dr?.released, dr?.viewer_slot, dr?.own_initial?.decision_uid]);

  if (!dr) return null;

  const isTwo = dr.mode === "two_machines";
  const isPeer = dr.role_on_this_machine === "peer";
  const canVoteHere =
    !isTwo
      ? dr.viewer_slot === "reviewer_a" || dr.viewer_slot === "reviewer_b"
      : isPeer
      ? dr.viewer_slot === "reviewer_b"
      : dr.viewer_slot === "reviewer_a";

  const saveDecision = async (action, withFields = false) => {
    setBusy(true);
    try {
      const interpretation = {};
      if (withFields) {
        for (const k of EDITABLE_FIELDS) {
          if (draftFields[k] !== undefined) {
            const v = String(draftFields[k]).trim();
            if (v !== "" || k === "usability_heuristic" || k === "improvement_hypothesis") {
              interpretation[k] = v || null;
            }
          }
        }
      }
      await api("dual-review-decide", {
        session_id: dr.session_id,
        finding_id: finding.id,
        action,
        reason: reason.trim(),
        interpretation: Object.keys(interpretation).length ? interpretation : undefined,
      });
      setEditOpen(false);
      setRevisionOpen(false);
      toast.success(
        dr.released
          ? t("Folgebewertung gespeichert (Ersturteil bleibt erhalten)", "Revision saved (initial judgment preserved)")
          : t("Bewertung für dieses Finding gespeichert", "Judgment saved for this Finding")
      );
      await onSaved?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleAdopt = async (adoptFrom, extra = {}) => {
    setBusy(true);
    try {
      await api("dual-review-adopt", {
        session_id: dr.session_id,
        finding_id: finding.id,
        adopt_from: adoptFrom,
        reason: adoptNote.trim(),
        ...extra,
      });
      setConsensusOpen(false);
      toast.success(
        adoptFrom === "open_disagreement"
          ? t("Als offene Abweichung markiert", "Marked as Open Disagreement")
          : t("Ausgewählte Fassung in den Studienstand übernommen", "Adopted selected version into study state")
      );
      await onSaved?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  // ---------------- PHASE 2: BLINDED INITIAL EVALUATION ----------------
  if (!dr.released) {
    const own = dr.own_initial;
    const ownMeta = own ? ACTION_LABELS[own.action] : null;
    return (
      <div className="lx-review-stack" data-testid={`dual-finding-blinded-${finding.id}`}>
        <div className="lx-review-callout lx-callout-neutral">
          <div className="lx-review-callout-head">
            <span className="lx-review-callout-title">
              <EyeOff size={13} />
              <strong data-testid="dual-detail-heading">
                {dr.own_submitted
                  ? t(
                      "Deine erste Bewertung ist abgegeben",
                      "Your first assessment has been submitted"
                    )
                  : t(
                      "Unabhängige Erstbewertung",
                      "Independent first assessment"
                    )}
              </strong>
            </span>
            {own && (
              <span className="lx-row-gap lx-text-xs">
                <StatusDot tone={ownMeta?.tone || "neutral"} />
                <strong>{lang === "en" ? ownMeta?.en : ownMeta?.de}</strong>
              </span>
            )}
          </div>
          <p className="lx-text-xs lx-muted" data-testid="dual-detail-subtext">
            {dr.own_submitted
              ? t(
                  "Unabhängige Erstbewertung gespeichert. Der Vergleich bleibt bis zur Freigabe verborgen.",
                  "Independent first assessment saved. The comparison remains hidden until release."
                )
              : t(
                  "Nur eigene Bewertung sichtbar — du siehst den gemeinsamen Ausgangsvorschlag und deine eigene Bewertung. Der Vergleich bleibt bis zur Freigabe verborgen.",
                  "Only your assessment is visible — you see the shared baseline proposal and your own assessment. The comparison remains hidden until release."
                )}
          </p>
          {own?.reason && <p className="lx-review-note-quote">„{own.reason}“</p>}
        </div>

        {canVoteHere && !dr.own_submitted && (
          <>
            <div className="lx-decision-bar">
              <input
                type="text"
                data-testid="dual-reason-input"
                className="lx-input lx-decision-input"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t("Eigene Begründung / Prüfnotiz …", "Your rationale / review note…")}
              />
              <div className="lx-decision-actions">
                <button
                  type="button"
                  data-testid="dual-btn-confirm"
                  disabled={busy}
                  className="lx-btn lx-btn-sm lx-btn-confirm"
                  onClick={() => saveDecision("confirmed", false)}
                >
                  <CheckCircle2 size={13} />
                  <span>{t("Bestätigen", "Confirm")}</span>
                </button>
                <button
                  type="button"
                  data-testid="dual-btn-correct-toggle"
                  disabled={busy}
                  className="lx-btn lx-btn-sm"
                  onClick={() => setEditOpen((v) => !v)}
                >
                  <Edit3 size={13} />
                  <span>{t("Korrigieren", "Correct")}</span>
                </button>
                <button
                  type="button"
                  data-testid="dual-btn-reject"
                  disabled={busy}
                  className="lx-btn lx-btn-sm"
                  onClick={() => saveDecision("rejected", false)}
                >
                  <XCircle size={13} />
                  <span>{t("Verwerfen", "Reject")}</span>
                </button>
                <button
                  type="button"
                  data-testid="dual-btn-open"
                  disabled={busy}
                  className="lx-btn lx-btn-sm lx-btn-ghost"
                  onClick={() => saveDecision("open", false)}
                >
                  <Clock size={13} />
                  <span>{t("Offen", "Open")}</span>
                </button>
              </div>
            </div>

            {editOpen && (
              <div className="lx-correction-editor">
                <strong className="lx-text-xs">
                  {t(
                    "Eigener Korrekturvorschlag am Finding (für die andere Person vor Freigabe unsichtbar)",
                    "Your proposed Finding edits (invisible to the other reviewer prior to release)"
                  )}
                </strong>
                <FindingFieldsEditor draft={draftFields} setDraft={setDraftFields} t={t} />
                <div className="lx-between" style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs lx-btn-ghost"
                    onClick={() => setEditOpen(false)}
                  >
                    {t("Abbrechen", "Cancel")}
                  </button>
                  <button
                    type="button"
                    data-testid="dual-save-correction"
                    disabled={busy}
                    className="lx-btn lx-btn-sm lx-btn-primary"
                    onClick={() => saveDecision("corrected", true)}
                  >
                    {t("Korrekturvorschlag speichern", "Save Proposed Correction")}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  // ---------------- PHASE 3 & 4: RELEASED COMPARISON, REVISION & ADOPTION ----------------
  const agreed = Boolean(dr.agreement?.latest_agreed);
  const resState = dr.resolution_state;
  const diffs = (dr.agreement?.differing_fields || []).join(", ");

  return (
    <div className="lx-review-stack" data-testid={`dual-finding-released-${finding.id}`}>
      <div
        className={`lx-review-callout ${
          resState === "OPEN_DISAGREEMENT"
            ? "lx-callout-warning"
            : resState === "ADOPTED"
            ? "lx-callout-success"
            : "lx-callout-active"
        }`}
      >
        <div className="lx-review-callout-head">
          <span className="lx-review-callout-title">
            {resState === "OPEN_DISAGREEMENT" ? (
              <AlertTriangle size={14} />
            ) : (
              <CheckCircle2 size={14} />
            )}
            <strong>
              {resState === "OPEN_DISAGREEMENT"
                ? t("Offene Abweichung in der Zweitprüfung", "Open Disagreement in Dual Review")
                : resState === "ADOPTED"
                ? `${t("In Studienstand übernommen", "Adopted into Study State")} (${
                    dr.resolution?.adopted_from || ""
                  })`
                : t("Vergleich freigegeben — Übernahme ausstehend", "Comparison Released — Pending Adoption")}
            </strong>
          </span>
          <span className="lx-mono-tag">
            {agreed
              ? t("Übereinstimmung", "Agreement")
              : `${t("Abweichung", "Divergence")}: ${diffs}`}
          </span>
        </div>
        {dr.resolution?.reason && (
          <p className="lx-text-xs" style={{ marginTop: 4 }}>
            {dr.resolution.reason}
          </p>
        )}
      </div>

      <div className="lx-grid-2">
        <ReviewerColumnCard
          label={t("Prüfer 1", "Reviewer 1")}
          profile={dr.reviewer_a_profile}
          slotData={dr.reviewer_a}
          baseline={dr.baseline_effective}
          lang={lang}
          t={t}
        />
        <ReviewerColumnCard
          label={t("Prüfer 2", "Reviewer 2")}
          profile={dr.reviewer_b_profile}
          slotData={dr.reviewer_b}
          baseline={dr.baseline_effective}
          lang={lang}
          t={t}
        />
      </div>

      {/* Optional Step 3b: Post-Release Revision */}
      {canVoteHere && (
        <div>
          <button
            type="button"
            data-testid="dual-open-revision"
            className="lx-btn lx-btn-xs"
            onClick={() => setRevisionOpen((v) => !v)}
          >
            <Edit3 size={12} />
            <span>
              {t(
                "Nach Vergleich eigene Folgebewertung abgeben (Ersturteil bleibt erhalten)",
                "Submit Post-Release Revision (Initial Judgment Preserved)"
              )}
            </span>
          </button>
          {revisionOpen && (
            <div className="lx-correction-editor" style={{ marginTop: 8 }}>
              <input
                type="text"
                data-testid="dual-revision-reason"
                className="lx-input lx-input-sm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t(
                  "Begründung der späteren Änderung nach Einsicht des Vergleichs …",
                  "Rationale for post-comparison revision…"
                )}
              />
              <FindingFieldsEditor draft={draftFields} setDraft={setDraftFields} t={t} />
              <div className="lx-btn-row" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  data-testid="dual-revision-confirm"
                  disabled={busy}
                  className="lx-btn lx-btn-xs lx-btn-confirm"
                  onClick={() => saveDecision("confirmed", false)}
                >
                  {t("Als ‚Bestätigt‘ revidieren", "Revise to Confirmed")}
                </button>
                <button
                  type="button"
                  data-testid="dual-revision-corrected"
                  disabled={busy}
                  className="lx-btn lx-btn-xs lx-btn-primary"
                  onClick={() => saveDecision("corrected", true)}
                >
                  {t("Geänderten Korrekturvorschlag speichern", "Save Revised Correction")}
                </button>
                <button
                  type="button"
                  data-testid="dual-revision-reject"
                  disabled={busy}
                  className="lx-btn lx-btn-xs"
                  onClick={() => saveDecision("rejected", false)}
                >
                  {t("Als ‚Verworfen‘ revidieren", "Revise to Rejected")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Explicit Study State Adoption (on Origin / Single Machine) */}
      {(!isTwo || !isPeer) && (
        <div className="lx-card lx-card-subtle lx-form-stack" style={{ gap: 8 }}>
          <strong className="lx-text-xs">
            {t(
              "Schritt 4: Ergebnis ausdrücklich in den Studienstand übernehmen",
              "Step 4: Explicitly Adopt Result into Study State"
            )}
          </strong>
          <input
            type="text"
            data-testid="dual-adopt-note"
            className="lx-input lx-input-sm"
            value={adoptNote}
            onChange={(e) => setAdoptNote(e.target.value)}
            placeholder={t(
              "Optionale Entscheidungsnotiz für Bericht & JSON …",
              "Optional resolution note for report & JSON…"
            )}
          />
          <div className="lx-btn-row" style={{ flexWrap: "wrap" }}>
            <button
              type="button"
              data-testid="dual-adopt-a"
              disabled={busy}
              className="lx-btn lx-btn-xs lx-btn-primary"
              onClick={() => handleAdopt("reviewer_a")}
            >
              {t("Fassung Prüfer 1 übernehmen", "Adopt Reviewer 1")}
            </button>
            <button
              type="button"
              data-testid="dual-adopt-b"
              disabled={busy}
              className="lx-btn lx-btn-xs lx-btn-primary"
              onClick={() => handleAdopt("reviewer_b")}
            >
              {t("Fassung Prüfer 2 übernehmen", "Adopt Reviewer 2")}
            </button>
            <button
              type="button"
              data-testid="dual-adopt-baseline"
              disabled={busy}
              className="lx-btn lx-btn-xs"
              onClick={() => handleAdopt("baseline")}
            >
              {t("Ausgangsvorschlag übernehmen", "Adopt Baseline")}
            </button>
            <button
              type="button"
              data-testid="dual-adopt-consensus-toggle"
              disabled={busy}
              className="lx-btn lx-btn-xs"
              onClick={() => setConsensusOpen((v) => !v)}
            >
              {t("Konsensfassung bearbeiten …", "Edit Consensus Version…")}
            </button>
            <button
              type="button"
              data-testid="dual-adopt-open-disagreement"
              disabled={busy}
              className="lx-btn lx-btn-xs lx-btn-ghost"
              onClick={() => handleAdopt("open_disagreement")}
            >
              {t("Als offene Abweichung belassen", "Keep as Open Disagreement")}
            </button>
          </div>

          {consensusOpen && (
            <div className="lx-correction-editor">
              <FindingFieldsEditor draft={consensusFields} setDraft={setConsensusFields} t={t} />
              <div className="lx-between" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="lx-btn lx-btn-xs lx-btn-ghost"
                  onClick={() => setConsensusOpen(false)}
                >
                  {t("Abbrechen", "Cancel")}
                </button>
                <button
                  type="button"
                  data-testid="dual-adopt-consensus-save"
                  disabled={busy}
                  className="lx-btn lx-btn-xs lx-btn-primary"
                  onClick={() => {
                    const interp = {};
                    for (const k of EDITABLE_FIELDS) interp[k] = consensusFields[k] || null;
                    handleAdopt("consensus", { action: "corrected", interpretation: interp });
                  }}
                >
                  {t("Konsensfassung in Studienstand übernehmen", "Adopt Consensus Version")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export async function uploadDualReviewPackage(file) {
  return apiUploadBinary(
    `dual-review-import?filename=${encodeURIComponent(file.name || "package")}`,
    file
  );
}
