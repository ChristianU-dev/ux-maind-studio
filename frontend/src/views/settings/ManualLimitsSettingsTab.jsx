import React, { useEffect, useMemo, useState } from "react";
import { BookOpen, Download, Search, ShieldAlert } from "lucide-react";
import { usePrefs } from "../../lib/i18n.jsx";
import { api } from "../../lib/api.js";
import { StatusBadge } from "../../components/ui.jsx";

function downloadMarkdownFile(filename, content) {
  const blob = new Blob([content || ""], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function parseMarkdownSections(mdText) {
  if (!mdText) return [];
  const lines = mdText.split(/\r?\n/);
  const sections = [];
  let current = { title: "Überblick", lines: [] };
  for (const line of lines) {
    if (line.startsWith("## ")) {
      if (current.lines.length) sections.push(current);
      current = { title: line.slice(3).trim(), lines: [] };
    } else if (!line.startsWith("# ")) {
      current.lines.push(line);
    }
  }
  if (current.lines.length) sections.push(current);
  return sections;
}

function renderMarkdownBlock(lines) {
  const elements = [];
  let idx = 0;
  while (idx < lines.length) {
    const raw = lines[idx];
    const trimmed = raw.trim();
    if (!trimmed || trimmed === "---") {
      idx++;
      continue;
    }
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={idx} className="lx-manual-h3">
          {trimmed.slice(4)}
        </h4>
      );
      idx++;
      continue;
    }
    if (trimmed.startsWith("|")) {
      const tableLines = [];
      while (idx < lines.length && lines[idx].trim().startsWith("|")) {
        tableLines.push(lines[idx].trim());
        idx++;
      }
      const rows = tableLines
        .filter((l) => !/^\|[\s:-]+\|/.test(l.replace(/\|/g, "|")))
        .filter((l) => !l.includes(":---") && !l.includes("---:"))
        .map((l) =>
          l
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map((c) => c.trim().replace(/\*\*/g, "").replace(/`/g, ""))
        );
      if (rows.length >= 1) {
        const [head, ...body] = rows;
        elements.push(
          <div key={`tbl-${idx}`} className="lx-table-wrap" style={{ margin: "8px 0" }}>
            <table className="lx-table">
              <thead>
                <tr>
                  {head.map((h, hi) => (
                    <th key={hi}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((r, ri) => (
                  <tr key={ri}>
                    {r.map((cell, ci) => (
                      <td key={ci} style={{ whiteSpace: "normal", verticalAlign: "top" }}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      continue;
    }
    if (trimmed.startsWith("> ")) {
      const quoteLines = [];
      while (idx < lines.length && lines[idx].trim().startsWith(">")) {
        quoteLines.push(
          lines[idx]
            .trim()
            .replace(/^>\s*(\[!IMPORTANT\]|\[!NOTE\]|\[!TIP\])?\s*/, "")
            .replace(/\*\*/g, "")
        );
        idx++;
      }
      elements.push(
        <div
          key={`q-${idx}`}
          className="lx-review-guide is-warn"
          style={{ margin: "6px 0", fontSize: "12px" }}
        >
          {quoteLines.filter(Boolean).join(" ")}
        </div>
      );
      continue;
    }
    if (trimmed.startsWith("- ") || /^\d+\.\s/.test(trimmed)) {
      const listItems = [];
      while (
        idx < lines.length &&
        (lines[idx].trim().startsWith("- ") || /^\d+\.\s/.test(lines[idx].trim()))
      ) {
        listItems.push(
          lines[idx]
            .trim()
            .replace(/^(?:-\s+|\d+\.\s+)/, "")
            .replace(/\*\*/g, "")
            .replace(/`/g, "")
        );
        idx++;
      }
      elements.push(
        <ul key={`ul-${idx}`} className="lx-review-guide-list" style={{ margin: "4px 0 8px" }}>
          {listItems.map((li, lIdx) => (
            <li key={lIdx}>{li}</li>
          ))}
        </ul>
      );
      continue;
    }
    elements.push(
      <p key={idx} className="lx-text-sm" style={{ margin: "4px 0" }}>
        {trimmed.replace(/\*\*/g, "").replace(/`/g, "")}
      </p>
    );
    idx++;
  }
  return elements;
}

export function ManualLimitsSettingsTab() {
  const { t } = usePrefs();
  const [docData, setDocData] = useState({ user_manual: "", system_limits: "" });
  const [activeDoc, setActiveDoc] = useState("manual");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api("manual")
      .then((res) => {
        if (alive && res) setDocData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const rawContent =
    activeDoc === "manual" ? docData.user_manual : docData.system_limits;

  const sections = useMemo(() => {
    const parsed = parseMarkdownSections(rawContent);
    const q = search.trim().toLowerCase();
    if (!q) return parsed;
    return parsed.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.lines.some((l) => l.toLowerCase().includes(q))
    );
  }, [rawContent, search]);

  return (
    <div className="lx-form-stack">
      <section className="lx-card lx-form-stack">
        <div className="lx-between" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <div className="lx-row-gap">
              <BookOpen size={15} style={{ color: "var(--dot-active)" }} />
              <h2 className="lx-card-title">
                {t(
                  "Benutzerhandbuch, Metadaten-Lexikon & Systemgrenzen (Live aus Markdown)",
                  "User Manual, Metadata Glossary & System Limits (Live from Markdown)"
                )}
              </h2>
              <StatusBadge
                label={t("Immer synchron mit docs/", "Synced with docs/")}
                tone="success"
              />
            </div>
            <p className="lx-card-sub">
              {t(
                "Dokumentiert alle Einstellungen nach Dokumenttyp, sämtliche Status- und Metadatenfelder (inkl. Nielsen H1–H10 & ISO 9241-110) sowie alle Format-, Bibliotheks- und Methodik-Grenzen.",
                "Documents recommended settings per file format, all status & metadata fields (incl. Nielsen H1–H10 & ISO 9241-110), and all format, library, and methodological limits."
              )}
            </p>
          </div>
          <div className="lx-btn-row">
            <button
              type="button"
              className="lx-btn lx-btn-sm"
              disabled={!docData.user_manual}
              onClick={() => downloadMarkdownFile("UX-mAInd_USER_MANUAL.md", docData.user_manual)}
            >
              <Download size={13} />
              <span>{t("Handbuch (.md)", "Manual (.md)")}</span>
            </button>
            <button
              type="button"
              className="lx-btn lx-btn-sm"
              disabled={!docData.system_limits}
              onClick={() =>
                downloadMarkdownFile("UX-mAInd_SYSTEM_LIMITS.md", docData.system_limits)
              }
            >
              <ShieldAlert size={13} />
              <span>{t("Systemgrenzen (.md)", "System Limits (.md)")}</span>
            </button>
          </div>
        </div>

        <div className="lx-between" style={{ flexWrap: "wrap", gap: 10 }}>
          <div className="lx-seg">
            <button
              type="button"
              className={`lx-seg-btn${activeDoc === "manual" ? " is-active" : ""}`}
              onClick={() => setActiveDoc("manual")}
            >
              {t(
                "1. Benutzerhandbuch & Metadaten-Lexikon",
                "1. User Manual & Metadata Glossary"
              )}
            </button>
            <button
              type="button"
              className={`lx-seg-btn${activeDoc === "limits" ? " is-active" : ""}`}
              onClick={() => setActiveDoc("limits")}
            >
              {t(
                "2. Format-, Bibliotheks- & Methodik-Grenzen",
                "2. Format, Library & Method Limits"
              )}
            </button>
          </div>

          <div className="lx-search-wrap" style={{ minWidth: 260 }}>
            <Search size={13} className="lx-search-icon" />
            <input
              type="search"
              className="lx-input lx-input-sm lx-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t(
                "Im Handbuch / Grenzen suchen (z. B. Nielsen, Teilweise verankert, PPTX) …",
                "Search manual & limits (e.g. Nielsen, Partially grounded, PPTX)…"
              )}
            />
          </div>
        </div>
      </section>

      <div className="lx-manual-viewer">
        {loading ? (
          <p className="lx-muted">{t("Lade Dokumentation …", "Loading documentation…")}</p>
        ) : sections.length === 0 ? (
          <p className="lx-muted">
            {t("Keine passenden Abschnitte gefunden.", "No matching sections found.")}
          </p>
        ) : (
          sections.map((sec, idx) => (
            <section key={idx} className="lx-manual-section">
              <h3 className="lx-manual-h2">{sec.title}</h3>
              {renderMarkdownBlock(sec.lines)}
            </section>
          ))
        )}
      </div>
    </div>
  );
}
