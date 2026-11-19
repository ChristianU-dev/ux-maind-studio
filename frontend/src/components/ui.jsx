import React, { useState } from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Check, ChevronDown, Edit3, Info, X, CheckCircle2, XCircle, Clock } from "lucide-react";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";

export function StatusDot({ tone = "neutral", pulse = false }) {
  return <span className={`lx-dot lx-dot-${tone}${pulse ? " lx-dot-pulse" : ""}`} aria-hidden="true" />;
}

export function StatusBadge({ status, label, tone }) {
  const { t } = usePrefs();
  const resolved = status ? statusInfo(status, t) : { label, tone: tone || "neutral" };
  const text = label || resolved.label;
  const tTone = tone || resolved.tone;
  return (
    <span className="lx-badge" title={text}>
      <StatusDot tone={tTone} pulse={tTone === "active"} />
      <span className="truncate">{text}</span>
    </span>
  );
}

export function Kbd({ children }) {
  return <kbd className="lx-kbd">{children}</kbd>;
}

export function Select({ value, onValueChange, options = [], placeholder = "—", ariaLabel, disabled, size = "md", className = "" }) {
  const safeVal = value === "" || value == null ? "__EMPTY__" : String(value);
  const mapped = options.map((opt) =>
    Array.isArray(opt)
      ? { value: opt[0] === "" ? "__EMPTY__" : String(opt[0]), rawValue: opt[0], label: opt[1], disabled: Boolean(opt[2]) }
      : {
          value: opt.value === "" ? "__EMPTY__" : String(opt.value),
          rawValue: opt.value,
          label: opt.label,
          disabled: Boolean(opt.disabled),
        }
  );

  return (
    <SelectPrimitive.Root
      value={safeVal}
      disabled={disabled}
      onValueChange={(v) => {
        const found = mapped.find((m) => m.value === v);
        onValueChange(found ? found.rawValue : v === "__EMPTY__" ? "" : v);
      }}
    >
      <SelectPrimitive.Trigger
        className={`lx-select-trigger lx-select-${size} ${className}`}
        aria-label={ariaLabel}
      >
        <span className="lx-select-value truncate">
          <SelectPrimitive.Value placeholder={placeholder} />
        </span>
        <SelectPrimitive.Icon className="lx-select-icon">
          <ChevronDown size={14} strokeWidth={1.8} />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="lx-select-content" position="popper" sideOffset={5}>
          <SelectPrimitive.Viewport className="lx-select-viewport">
            {mapped.map((opt) => (
              <SelectPrimitive.Item
                key={opt.value}
                value={opt.value}
                disabled={opt.disabled}
                className="lx-select-item"
              >
                <SelectPrimitive.ItemText>{opt.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="lx-select-check">
                  <Check size={13} strokeWidth={2.2} />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export function Modal({ open, onOpenChange, title, subtitle, children, width = 560 }) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="lx-modal-overlay" />
        <DialogPrimitive.Content
          className="lx-modal-content"
          style={{ maxWidth: `${width}px` }}
        >
          <div className="lx-modal-header">
            <div className="min-w-0">
              <DialogPrimitive.Title className="lx-modal-title">{title}</DialogPrimitive.Title>
              {subtitle && (
                <DialogPrimitive.Description className="lx-modal-subtitle">
                  {subtitle}
                </DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close asChild>
              <button type="button" className="lx-icon-btn" aria-label="Close">
                <X size={15} />
              </button>
            </DialogPrimitive.Close>
          </div>
          <div className="lx-modal-body">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function Switch({ checked, onCheckedChange, id, disabled }) {
  return (
    <SwitchPrimitive.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className="lx-switch"
    >
      <SwitchPrimitive.Thumb className="lx-switch-thumb" />
    </SwitchPrimitive.Root>
  );
}

export function Tip({ content, children }) {
  if (!content) return children;
  return (
    <TooltipPrimitive.Provider delayDuration={250}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="lx-tooltip" sideOffset={5}>
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

export function InfoPopover({ title, children, align = "center", side = "top", label = "Info" }) {
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          className="lx-info-trigger"
          aria-label={title || label}
          title={title || label}
          onClick={(e) => e.stopPropagation()}
        >
          <Info size={13} strokeWidth={2} />
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          className="lx-popover-card"
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={12}
        >
          {title && <div className="lx-popover-title">{title}</div>}
          <div className="lx-popover-body">{children}</div>
          <PopoverPrimitive.Arrow className="lx-popover-arrow" />
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

const UX_HEURISTIC_SUGGESTIONS = [
  "Nielsen H1: Visibility of system status",
  "Nielsen H2: Match between system and the real world",
  "Nielsen H3: User control and freedom",
  "Nielsen H4: Consistency and standards",
  "Nielsen H5: Error prevention",
  "Nielsen H6: Recognition rather than recall",
  "Nielsen H7: Flexibility and efficiency of use",
  "Nielsen H8: Aesthetic and minimalist design",
  "Nielsen H9: Help users recognize, diagnose, and recover from errors",
  "Nielsen H10: Help and documentation",
  "ISO 9241-110: Aufgabenangemessenheit",
  "ISO 9241-110: Selbstbeschreibungsfähigkeit",
  "ISO 9241-110: Erwartungskonformität",
  "ISO 9241-110: Erlernbarkeit",
  "ISO 9241-110: Steuerbarkeit",
  "ISO 9241-110: Fehlertoleranz / Gebrauchsfehler-Robustheit",
  "ISO 9241-110: Nutzerbindung (User engagement)",
  "W3C WCAG 2.2 · 1.1.1 Non-text Content (Textalternativen)",
  "W3C WCAG 2.2 · 1.3.1 Info and Relationships (Semantik & Struktur)",
  "W3C WCAG 2.2 · 1.4.3 Contrast Minimum (Kontrast)",
  "W3C WCAG 2.2 · 2.1.1 Keyboard (Tastaturbedienbarkeit)",
  "W3C WCAG 2.2 · 2.4.7 Focus Visible / 2.4.11 Focus Appearance",
  "W3C WCAG 2.2 · 2.5.8 Target Size Minimum (Zielgröße)",
  "W3C WCAG 2.2 · 3.3.1 Error Identification / 3.3.3 Error Suggestion",
  "W3C WCAG 2.2 · 3.3.8 Accessible Authentication",
];

export function latestHumanDecision(decisions = []) {
  for (let i = decisions.length - 1; i >= 0; i--) {
    if (decisions[i]?.origin === "human" || decisions[i]?.origin === "human_carried_forward") {
      return decisions[i];
    }
  }
  return null;
}

export function ResearcherReviewBlock({
  targetType,
  target,
  decisions = [],
  currentEffective = null,
  onSaved,
  apiCall,
  compact = false,
}) {
  const { t } = usePrefs();
  const human = (decisions || []).filter(
    (d) => d?.origin === "human" || d?.origin === "human_carried_forward"
  );
  const latest = human.length ? human[human.length - 1] : null;
  const [reason, setReason] = useState(latest?.reason || "");
  const [busy, setBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [draftFields, setDraftFields] = useState({});

  // Sync input when switching records
  React.useEffect(() => {
    setReason(latest?.reason || "");
    setEditOpen(false);
    if (currentEffective && typeof currentEffective === "object") {
      setDraftFields({
        title: currentEffective.title || "",
        statement: currentEffective.statement || "",
        valence: currentEffective.valence || "",
        finding_type: currentEffective.finding_type || "",
        usability_heuristic: currentEffective.usability_heuristic || "",
        improvement_hypothesis: currentEffective.improvement_hypothesis || "",
        kind: currentEffective.kind || "",
        rationale: currentEffective.rationale || "",
        observed_effect: currentEffective.observed_effect || "",
        scope: currentEffective.scope || "",
        uncertainty: currentEffective.uncertainty || "",
      });
    } else {
      setDraftFields({});
    }
  }, [JSON.stringify(target), latest?.at, latest?.reason]);

  const submit = async (action, extraPayload = {}) => {
    if (busy) return;
    setBusy(true);
    try {
      await apiCall("ux-decision", {
        target_type: targetType,
        target,
        action,
        reason: reason.trim(),
        payload: extraPayload,
      });
      setEditOpen(false);
      await onSaved?.(action);
    } finally {
      setBusy(false);
    }
  };

  const submitCorrection = async () => {
    const interpretation = {};
    if (targetType === "finding") {
      for (const k of [
        "title",
        "valence",
        "finding_type",
        "usability_heuristic",
        "rationale",
        "observed_effect",
        "scope",
        "uncertainty",
        "improvement_hypothesis",
      ]) {
        if (draftFields[k] !== undefined) {
          const v = String(draftFields[k]).trim();
          if (v !== "" || k === "usability_heuristic" || k === "improvement_hypothesis") {
            interpretation[k] = v || null;
          }
        }
      }
    } else if (targetType === "relation") {
      for (const k of ["kind", "rationale", "uncertainty"]) {
        if (draftFields[k] !== undefined && String(draftFields[k]).trim() !== "") {
          interpretation[k] = String(draftFields[k]).trim();
        }
      }
    } else if (targetType === "observation") {
      for (const k of ["statement", "kind", "uncertainty"]) {
        if (draftFields[k] !== undefined && String(draftFields[k]).trim() !== "") {
          interpretation[k] = String(draftFields[k]).trim();
        }
      }
    }
    await submit("corrected", Object.keys(interpretation).length ? { interpretation } : {});
  };

  const actionMeta = {
    confirmed: { label: t("Menschlich bestätigt", "Human Confirmed"), tone: "success" },
    rejected: { label: t("Verworfen", "Rejected"), tone: "danger" },
    corrected: { label: t("Menschlich korrigiert", "Human Corrected"), tone: "active" },
    open: { label: t("Zur Prüfung markiert", "Flagged for Review"), tone: "warning" },
  };

  return (
    <div className={`lx-review-stack${compact ? " lx-review-compact" : ""}`}>
      {latest && (
        <div className={`lx-review-callout lx-callout-${actionMeta[latest.action]?.tone || "neutral"}`}>
          <div className="lx-review-callout-head">
            <span className="lx-review-callout-title">
              <StatusDot tone={actionMeta[latest.action]?.tone || "neutral"} />
              <strong>{actionMeta[latest.action]?.label || latest.action}</strong>
              {latest.payload?.reviewer?.name && (
                <span className="lx-muted" style={{ fontWeight: 500 }}>
                  · {latest.payload.reviewer.name}
                </span>
              )}
            </span>
            {latest.at && (
              <span className="lx-muted tabular">
                {latest.at.replace("T", " ").slice(0, 16)} UTC
              </span>
            )}
          </div>
          <p className={latest.reason ? "lx-review-note-quote" : "lx-muted"}>
            {latest.reason ? `„${latest.reason}“` : t("Keine Notiz hinterlegt", "No rationale note recorded")}
          </p>
          {human.length > 1 && (
            <details className="lx-review-history">
              <summary>{t(`Änderungsprotokoll (${human.length})`, `Audit Log (${human.length})`)}</summary>
              <div className="lx-review-history-list">
                {[...human].reverse().map((d, idx) => (
                  <div key={idx} className="lx-review-history-item">
                    <span className="tabular">{(d.at || "").slice(0, 16).replace("T", " ")}</span>
                    <strong>{d.action}</strong>
                    {d.payload?.reviewer?.name && (
                      <span className="lx-muted">({d.payload.reviewer.name})</span>
                    )}
                    {d.reason && <span>— {d.reason}</span>}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      <div className="lx-decision-bar">
        <input
          type="text"
          className="lx-input lx-decision-input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t("Begründung / Korrekturnotiz …", "Rationale / review note…")}
          aria-label={t("Begründung der Forschungsentscheidung", "Research decision rationale")}
        />
        <div className="lx-decision-actions">
          <button
            type="button"
            disabled={busy}
            className="lx-btn lx-btn-sm lx-btn-confirm"
            onClick={() => submit("confirmed")}
          >
            <CheckCircle2 size={13} />
            <span>{t("Bestätigen", "Confirm")}</span>
          </button>
          {!compact && currentEffective && (
            <button
              type="button"
              disabled={busy}
              className="lx-btn lx-btn-sm"
              onClick={() => setEditOpen((v) => !v)}
            >
              <Edit3 size={13} />
              <span>{t("Korrigieren", "Correct")}</span>
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            className="lx-btn lx-btn-sm"
            onClick={() => submit("rejected")}
          >
            <XCircle size={13} />
            <span>{t("Verwerfen", "Reject")}</span>
          </button>
          <button
            type="button"
            disabled={busy}
            className="lx-btn lx-btn-sm lx-btn-ghost"
            onClick={() => submit("open")}
          >
            <Clock size={13} />
            <span>{t("Offen", "Open")}</span>
          </button>
        </div>
      </div>

      {editOpen && currentEffective && (
        <div className="lx-correction-editor">
          <div className="lx-between">
            <strong className="lx-text-xs">
              {t(
                "Inhaltliche Forscher-Korrektur (append-only Revisionsprotokoll, Originalzitate bleiben unverändert)",
                "Researcher Interpretation Override (append-only audit trail; verbatim quotes remain immutable)"
              )}
            </strong>
          </div>
          {targetType === "finding" && (
            <div className="lx-form-stack">
              <div className="lx-grid-2">
                <label className="lx-field">
                  <span className="lx-field-label">{t("Finding-Titel", "Finding Title")}</span>
                  <input
                    type="text"
                    className="lx-input lx-input-sm"
                    value={draftFields.title || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, title: e.target.value }))}
                  />
                </label>
                <label className="lx-field">
                  <span className="lx-field-label">{t("Valenz", "Valence")}</span>
                  <Select
                    size="sm"
                    value={draftFields.valence || "neutral"}
                    onValueChange={(v) => setDraftFields((f) => ({ ...f, valence: v }))}
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
                    {t(
                      "Usability- & A11y-Kriterium (Nielsen / ISO / WCAG 2.2)",
                      "UX & A11y Criterion (Nielsen / ISO / WCAG 2.2)"
                    )}
                  </span>
                  <input
                    type="text"
                    list="ux-heuristic-options"
                    className="lx-input lx-input-sm"
                    placeholder={t(
                      "z. B. Nielsen H1, ISO 9241-110 oder W3C WCAG 2.2 …",
                      "e.g., Nielsen H1, ISO 9241-110, or W3C WCAG 2.2…"
                    )}
                    value={draftFields.usability_heuristic || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, usability_heuristic: e.target.value }))}
                  />
                  <datalist id="ux-heuristic-options">
                    {UX_HEURISTIC_SUGGESTIONS.map((h) => (
                      <option key={h} value={h} />
                    ))}
                  </datalist>
                </label>
                <label className="lx-field">
                  <span className="lx-field-label">{t("Befundtyp (finding_type)", "Finding Type")}</span>
                  <input
                    type="text"
                    className="lx-input lx-input-sm"
                    placeholder="usability_problem, positive_practice, recovery_pattern…"
                    value={draftFields.finding_type || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, finding_type: e.target.value }))}
                  />
                </label>
              </div>
              <label className="lx-field">
                <span className="lx-field-label">{t("Synthese & Begründung", "Synthesis & Rationale")}</span>
                <textarea
                  rows={3}
                  className="lx-textarea"
                  value={draftFields.rationale || ""}
                  onChange={(e) => setDraftFields((f) => ({ ...f, rationale: e.target.value }))}
                />
              </label>
              <label className="lx-field">
                <span className="lx-field-label">
                  {t("Verbesserungshypothese / Empfehlung (optional)", "Improvement Hypothesis / Recommendation (optional)")}
                </span>
                <textarea
                  rows={2}
                  className="lx-textarea"
                  value={draftFields.improvement_hypothesis || ""}
                  onChange={(e) => setDraftFields((f) => ({ ...f, improvement_hypothesis: e.target.value }))}
                />
              </label>
              <div className="lx-grid-2">
                <label className="lx-field">
                  <span className="lx-field-label">{t("Geltungsbereich (Scope)", "Scope")}</span>
                  <input
                    type="text"
                    className="lx-input lx-input-sm"
                    value={draftFields.scope || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, scope: e.target.value }))}
                  />
                </label>
                <label className="lx-field">
                  <span className="lx-field-label">{t("Unsicherheit", "Uncertainty")}</span>
                  <input
                    type="text"
                    className="lx-input lx-input-sm"
                    value={draftFields.uncertainty || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, uncertainty: e.target.value }))}
                  />
                </label>
              </div>
            </div>
          )}
          {targetType === "relation" && (
            <div className="lx-form-stack">
              <label className="lx-field">
                <span className="lx-field-label">{t("Relationstyp (kind)", "Relation Type")}</span>
                <input
                  type="text"
                  className="lx-input lx-input-sm"
                  value={draftFields.kind || ""}
                  onChange={(e) => setDraftFields((f) => ({ ...f, kind: e.target.value }))}
                />
              </label>
              <label className="lx-field">
                <span className="lx-field-label">{t("Begründung", "Rationale")}</span>
                <textarea
                  rows={2}
                  className="lx-textarea"
                  value={draftFields.rationale || ""}
                  onChange={(e) => setDraftFields((f) => ({ ...f, rationale: e.target.value }))}
                />
              </label>
            </div>
          )}
          {targetType === "observation" && (
            <div className="lx-form-stack">
              <label className="lx-field">
                <span className="lx-field-label">{t("Quellennahe Aussage (Statement)", "Source-Near Statement")}</span>
                <textarea
                  rows={2}
                  className="lx-textarea"
                  value={draftFields.statement || ""}
                  onChange={(e) => setDraftFields((f) => ({ ...f, statement: e.target.value }))}
                />
              </label>
              <div className="lx-grid-2">
                <label className="lx-field">
                  <span className="lx-field-label">{t("Evidenztyp (kind)", "Evidence Kind")}</span>
                  <input
                    type="text"
                    className="lx-input lx-input-sm"
                    value={draftFields.kind || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, kind: e.target.value }))}
                  />
                </label>
                <label className="lx-field">
                  <span className="lx-field-label">{t("Unsicherheit", "Uncertainty")}</span>
                  <input
                    type="text"
                    className="lx-input lx-input-sm"
                    value={draftFields.uncertainty || ""}
                    onChange={(e) => setDraftFields((f) => ({ ...f, uncertainty: e.target.value }))}
                  />
                </label>
              </div>
            </div>
          )}
          <div className="lx-btn-row">
            <button
              type="button"
              disabled={busy}
              className="lx-btn lx-btn-sm lx-btn-primary"
              onClick={submitCorrection}
            >
              <Check size={13} />
              <span>{t("Korrektur revisionssicher speichern", "Save Audited Correction")}</span>
            </button>
            <button
              type="button"
              className="lx-btn lx-btn-sm lx-btn-ghost"
              onClick={() => setEditOpen(false)}
            >
              {t("Abbrechen", "Cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function EpistemicFlagsRow({ record }) {
  const { t } = usePrefs();
  const eff = record?.effective || record || {};
  const ctx = eff.context || {};
  const human = latestHumanDecision(record?.decisions || []);
  const review =
    record?.review ||
    (human
      ? {
          confirmed: "HUMAN_CONFIRMED",
          rejected: "HUMAN_REJECTED",
          corrected: "HUMAN_CORRECTED",
          open: "HUMAN_OPEN",
        }[human.action]
      : record?.source_check?.status === "SOURCE_RESOLVED"
      ? "UNREVIEWED"
      : null);

  const pills = [];
  if (review) {
    const si = statusInfo(review, t);
    pills.push({ key: "rev", label: si.label, tone: si.tone });
  }
  if (ctx.epistemic_role) {
    pills.push({ key: "role", label: `${t("Rolle", "Role")}: ${ctx.epistemic_role}`, tone: "neutral" });
  }
  if (ctx.referenced_person) {
    pills.push({ key: "person", label: `${t("Person", "Subject")}: ${ctx.referenced_person}`, tone: "neutral" });
  }
  if (eff.negated_or_struck) {
    pills.push({ key: "strike", label: t("Durchgestrichen / negiert", "Struck / Negated"), tone: "warning" });
  }
  if (eff.context_reference?.cue || eff.context_reference?.kind) {
    const cr = eff.context_reference;
    const ok = cr.target_self_ref && cr.target_valid !== false;
    pills.push({
      key: "ctxref",
      label: ok
        ? `${t("Verweis", "Ref")} → ${cr.target_self_ref}`
        : `${t("Offener Verweis", "Open Ref")}${cr.cue ? `: "${cr.cue}"` : ""}`,
      tone: ok ? "neutral" : "warning",
    });
  }
  for (const m of record?.measurements || eff.measurements || []) {
    if (
      m.numeric_value != null &&
      (!m.scale_direction || m.scale_direction === "unknown") &&
      (m.measurement_kind == null || m.measurement_kind === "rating_scale")
    ) {
      pills.push({
        key: "scale",
        label: t(`Skalenrichtung offen (${m.raw_value})`, `Scale unanchored (${m.raw_value})`),
        tone: "warning",
      });
      break;
    }
  }
  const flagMap = {
    unanchored_scale_direction: [t("Skalenrichtung unbelegt", "Unanchored Scale Polarity"), "warning"],
    contains_negated_or_struck: [t("Enthält Streichung/Negation", "Contains Strike/Negation"), "warning"],
    unresolved_context_reference: [t("Offener Kontextverweis", "Unresolved Context Ref"), "warning"],
    dependent_visual_overlap: [t("Abhängiger Folienbeleg", "Dependent Slide Render"), "neutral"],
  };
  for (const fl of record?.epistemic_flags || []) {
    if (fl === "technical_source_only") continue;
    if (fl === "unanchored_scale_direction" && pills.some((p) => p.key === "scale")) continue;
    const [lbl, tn] = flagMap[fl] || [fl, "neutral"];
    pills.push({ key: fl, label: lbl, tone: tn });
  }
  if (record?.independence?.dependent_visual_overlap) {
    pills.push({
      key: "indep",
      label: t(
        `Unabhängige Anker: ${record.independence.effective_independent_supports}/${record.independence.raw_supports}`,
        `Independent Anchors: ${record.independence.effective_independent_supports}/${record.independence.raw_supports}`
      ),
      tone: "neutral",
    });
  }
  if (!pills.length) return null;
  return (
    <div className="lx-badge-row">
      {pills.map((p) => (
        <StatusBadge key={p.key} label={p.label} tone={p.tone} />
      ))}
    </div>
  );
}
