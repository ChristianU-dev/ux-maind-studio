import React, { useState } from "react";
import { ArrowUpRight, Check, Eye, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import { usePrefs } from "../lib/i18n.jsx";
import { api, pictureSourceLabel } from "../lib/api.js";
import { StatusDot } from "./ui.jsx";

export function observationKey(ref) {
  return ref ? [ref.document, ref.run, ref.observation].join("/") : "";
}

export function isOpenEvidence(entry) {
  if (!entry) return false;
  return (
    !entry.source_check?.matches?.length ||
    Boolean(entry.source_issues?.length) ||
    Boolean(entry.measurements?.some((m) => !m.sources?.length))
  );
}

function anchorKey(anchor) {
  return (
    anchor?.evidence_id ||
    JSON.stringify([
      anchor?.ref,
      anchor?.start,
      anchor?.end,
      anchor?.row,
      anchor?.row_end,
      anchor?.column,
      anchor?.column_end,
      anchor?.prov?.map((p) => p.page_no),
      anchor?.origin,
    ])
  );
}

function formatCueTime(sec) {
  if (typeof sec !== "number" || !Number.isFinite(sec)) return null;
  const mins = Math.floor(sec / 60);
  const rem = Math.floor(sec % 60);
  return `${mins}:${String(rem).padStart(2, "0")}`;
}

export function EvidenceCard({
  entry,
  roles = [],
  onShowSource,
  onAnchorConfirmed,
  compact = false,
}) {
  const { t } = usePrefs();
  const [savingCand, setSavingCand] = useState(false);
  if (!entry) return null;

  const confirmCandidateAnchor = async (cand) => {
    if (!cand || savingCand) return;
    setSavingCand(true);
    try {
      await api("ux-decision", {
        target_type: "observation",
        target: entry.ref,
        action: "confirmed",
        reason: `Fundstelle bestätigt: ${cand.ref}`,
        payload: { primary: cand },
      });
      toast.success(
        t("Beleganker verbindlich zugeordnet", "Source anchor verified and bound")
      );
      await onAnchorConfirmed?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSavingCand(false);
    }
  };

  const anchors = entry.selected_source
    ? [entry.selected_source]
    : entry.source_check?.matches || [];

  const resolved = anchors.length > 0;
  const quoteText =
    anchors[0]?.quote ||
    entry.raw?.quote ||
    t("Bild-, Tabellen- oder nicht wortwörtliche Stelle", "Visual, tabular, or non-verbatim span");

  const contextAnchors = [
    ...(entry.context_sources || []),
    ...(entry.context_decisions || []).map((c) => c.evidence).filter(Boolean),
  ];

  const seen = new Set(anchors.map(anchorKey));
  const extraAnchors = [];
  const pushExtra = (anchor, label) => {
    if (!anchor) return;
    const k = anchorKey(anchor);
    if (seen.has(k)) return;
    seen.add(k);
    extraAnchors.push({ anchor, label });
  };
  for (const ca of contextAnchors) pushExtra(ca, t("Kontext", "Context"));
  for (const m of entry.measurements || []) {
    for (const ma of m.sources || []) pushExtra(ma, t("Messwert", "Metric"));
  }

  return (
    <section className={`lx-evidence-card${compact ? " is-compact" : ""}`}>
      <header className="lx-evidence-head">
        <div className="lx-row-wrap min-w-0">
          {roles.map((r) => (
            <span key={r} className="lx-tag">
              {r}
            </span>
          ))}
          <span className="lx-evidence-doc truncate" title={entry.name}>
            {entry.name}
          </span>
        </div>
        <span className="lx-evidence-meta tabular">
          <StatusDot tone={resolved ? "success" : "warning"} />
          <span>
            A #{entry.ref.run}/{entry.ref.observation}
          </span>
        </span>
      </header>

      {entry.effective?.statement && !compact && (
        <p className="lx-evidence-stmt">{entry.effective.statement}</p>
      )}

      <blockquote className="lx-evidence-quote">{quoteText}</blockquote>

      {(entry.raw?.origin === "picture_description" || entry.raw?.origin === "chart_enrichment") && (
        <div className="lx-muted lx-text-xs">
          {entry.raw.origin === "picture_description"
            ? t("Abgeleitet aus Bildbeschreibung (Vision)", "Derived from visual description (Vision)")
            : t("Abgeleitet aus Diagrammextraktion (Chart)", "Derived from chart table extraction")}
        </div>
      )}

      {entry.measurements?.length > 0 && (
        <div className="lx-row-wrap">
          {entry.measurements.map((m, idx) => {
            const ok = Boolean(m.sources?.length);
            const parts = [
              m.raw_value,
              m.unit,
              m.scope,
              m.scale_direction && !["unknown", "not_applicable"].includes(m.scale_direction)
                ? `${t("Skala", "Scale")}: ${m.scale_direction}`
                : null,
              m.negated ? t("negiert", "negated") : null,
              !ok ? t("Quelle offen", "open source") : null,
            ].filter(Boolean);
            return (
              <span key={idx} className={`lx-tag tabular${ok ? "" : " lx-tag-warn"}`}>
                <StatusDot tone={ok ? "neutral" : "warning"} />
                <span>{parts.join(" · ")}</span>
              </span>
            );
          })}
        </div>
      )}

      {entry.source_issues?.length > 0 && (
        <div className="lx-issue-notes">
          {entry.source_issues.map((iss, idx) => (
            <p key={idx} className="lx-text-warn lx-text-xs">
              {iss}
            </p>
          ))}
        </div>
      )}

      {!anchors.length && entry.candidate_anchors?.length > 0 && (
        <div
          className="lx-card lx-card-subtle"
          style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6 }}
        >
          <span className="lx-text-xs" style={{ fontWeight: 600 }}>
            {entry.raw?.ambiguous_count > entry.candidate_anchors.length
              ? t(
                  `Mehrdeutige Fundstelle (${entry.candidate_anchors.length} von ${entry.raw.ambiguous_count} identischen Vorkommen gezeigt) — passende Stelle prüfen & festlegen:`,
                  `Ambiguous occurrence (showing ${entry.candidate_anchors.length} of ${entry.raw.ambiguous_count} identical matches) — inspect & bind:`
                )
              : t(
                  `Mehrdeutige Fundstelle (${entry.raw?.ambiguous_count || entry.candidate_anchors.length} Vorkommen) — passende Dokumentstelle prüfen & mit 1 Klick festlegen:`,
                  `Ambiguous occurrence (${entry.raw?.ambiguous_count || entry.candidate_anchors.length} matches) — inspect & bind exact source location in 1 click:`
                )}
          </span>
          <div className="lx-row-wrap" style={{ gap: 6 }}>
            {entry.candidate_anchors.map((cand, cIdx) => {
              const pNo = cand.prov?.[0]?.page_no;
              const locTxt = [
                cand.ref,
                pNo != null ? `${t("S.", "p.")}${pNo}` : null,
                Number.isInteger(cand.row) ? `Z.${cand.row + 1}/Sp.${cand.column + 1}` : null,
              ]
                .filter(Boolean)
                .join(" · ");
              return (
                <div key={cIdx} className="lx-row-gap" style={{ gap: 4 }}>
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs lx-btn-ghost"
                    onClick={() => onShowSource?.(entry.ref, cand)}
                  >
                    <Eye size={11} />
                    <span>{locTxt}</span>
                  </button>
                  <button
                    type="button"
                    className="lx-btn lx-btn-xs lx-btn-primary"
                    disabled={savingCand}
                    onClick={() => confirmCandidateAnchor(cand)}
                  >
                    <Check size={11} />
                    <span>{t("Festlegen", "Bind")}</span>
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="lx-evidence-actions">
        {anchors.map((anchor, idx) => {
          const track = anchor.track?.[0];
          const trackPos = track
            ? [
                track.voice ? `${track.voice}` : null,
                track.start_time != null && track.end_time != null
                  ? `${formatCueTime(track.start_time)}–${formatCueTime(track.end_time)}`
                  : null,
              ]
                .filter(Boolean)
                .join(" ")
            : "";
          const pos = anchor.worksheet
            ? ` · ${anchor.worksheet.name}`
            : anchor.prov?.length === 1
            ? ` · S.${anchor.prov[0].page_no}`
            : trackPos
            ? ` · ${trackPos}`
            : "";
          const cell = Number.isInteger(anchor.row)
            ? ` · Z.${anchor.row + 1}/Sp.${anchor.column + 1}`
            : "";
          const span = Number.isInteger(anchor.start)
            ? ` · [${anchor.start}–${anchor.end}]`
            : "";
          const label = anchor.picture_source
            ? `${pictureSourceLabel(anchor.picture_source, t)} · ${anchor.ref}${pos}`
            : `${t("Original prüfen", "Inspect Original")}${anchors.length > 1 ? ` ${idx + 1}` : ""} · ${anchor.ref}${pos}${cell}${span}`;
          return (
            <button
              key={idx}
              type="button"
              className="lx-btn lx-btn-xs"
              onClick={() => onShowSource?.(entry.ref, anchor)}
            >
              {anchor.picture_source ? <ImageIcon size={12} /> : <Eye size={12} />}
              <span className="truncate">{label}</span>
              <ArrowUpRight size={11} />
            </button>
          );
        })}

        {(entry.picture_sources || [])
          .filter((ps) => !anchors.some((a) => a.ref === ps.ref))
          .map((ps, idx) => (
            <button
              key={`pic-${idx}`}
              type="button"
              className="lx-btn lx-btn-xs lx-btn-ghost"
              onClick={() => onShowSource?.(entry.ref, ps)}
            >
              <ImageIcon size={12} />
              <span>{t("Bild öffnen", "Open Image")}</span>
            </button>
          ))}

        {extraAnchors.map(({ anchor, label }, idx) => (
          <button
            key={`extra-${idx}`}
            type="button"
            className="lx-btn lx-btn-xs lx-btn-ghost"
            onClick={() => onShowSource?.(entry.ref, anchor)}
          >
            <span>
              {label} · {anchor.ref}
            </span>
            <ArrowUpRight size={11} />
          </button>
        ))}

        {!anchors.length && (
          <button
            type="button"
            className="lx-btn lx-btn-xs"
            onClick={() => onShowSource?.(entry.ref, null)}
          >
            <Eye size={12} />
            <span>{t("Dokument öffnen (Anker offen)", "Open Document (Unanchored)")}</span>
          </button>
        )}
      </div>
    </section>
  );
}
