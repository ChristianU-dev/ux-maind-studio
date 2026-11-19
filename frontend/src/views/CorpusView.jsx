import React, { useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Archive,
  ArrowRight,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Eye,
  FolderPlus,
  Plus,
  RotateCcw,
  Search,
  Square,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { usePrefs, statusInfo } from "../lib/i18n.jsx";
import { api } from "../lib/api.js";
import { InfoPopover, Modal, Select, StatusBadge, Switch } from "../components/ui.jsx";

export function CorpusView({
  filesData,
  search,
  onSearchChange,
  sort,
  onSortChange,
  archived,
  onArchivedChange,
  offset,
  onOffsetChange,
  selectedIds,
  onToggleSelect,
  onSelectVisible,
  onClearSelection,
  onOpenDocument,
  onNavigate,
  onRefreshFiles,
  importModalOpen,
  onImportModalChange,
}) {
  const { t } = usePrefs();
  const items = filesData?.items || [];
  const total = filesData?.total || 0;

  // Import state
  const [importText, setImportText] = useState("");
  const [convertOnImport, setConvertOnImport] = useState(true);
  const [importing, setImporting] = useState(false);

  // Remove/Archive modal state
  const [removeAction, setRemoveAction] = useState(null); // "archive" | "restore" | "remove"
  const [removePreview, setRemovePreview] = useState(null);
  const [removing, setRemoving] = useState(false);

  const convertedCount = useMemo(
    () => items.filter((f) => f.status === "success" || f.status === "partial_success").length,
    [items]
  );
  const stageACount = useMemo(
    () => items.filter((f) => f.extraction && f.extraction !== "NOT_RUN").length,
    [items]
  );

  const pickPaths = async (folder) => {
    try {
      const picked = await api("pick", { folder });
      const list = Array.isArray(picked?.paths) ? picked.paths : [];
      if (list.length) {
        setImportText((prev) => [prev.trim(), ...list].filter(Boolean).join("\n"));
      }
    } catch (err) {
      toast.error(err.message);
    }
  };

  const submitImport = async (e) => {
    e?.preventDefault();
    const paths = importText
      .split(/\r?\n/)
      .map((s) => s.trim().replace(/^"(.*)"$/, "$1"))
      .filter(Boolean);
    if (!paths.length) {
      toast.error(t("Mindestens einen Pfad angeben.", "Provide at least one file or folder path."));
      return;
    }
    setImporting(true);
    try {
      await api("import", { paths, convert: convertOnImport });
      toast.success(
        convertOnImport
          ? t("Import und Docling-Konvertierung gestartet", "Import and Docling conversion started")
          : t("Dateien registriert", "Files registered")
      );
      setImportText("");
      onImportModalChange(false);
      await onRefreshFiles?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setImporting(false);
    }
  };

  const openRemoveModal = async (action) => {
    const docs = [...selectedIds];
    if (!docs.length) return;
    try {
      const preview = await api("remove-preview", { documents: docs });
      setRemovePreview(preview);
      setRemoveAction(action);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const confirmRemove = async (overrideAction = null) => {
    const act = overrideAction || removeAction;
    if (!act) return;
    setRemoving(true);
    try {
      const targetDocs =
        act === "remove" && Array.isArray(removePreview)
          ? removePreview.filter((p) => p.removable).map((p) => p.id)
          : [...selectedIds];
      if (!targetDocs.length) {
        toast.warning(
          t(
            "Alle gewählten Dokumente besitzen Lauf-/Forschungshistorie. Bitte stattdessen archivieren.",
            "Selected documents have audit history and cannot be hard-deleted. Use Archive instead."
          )
        );
        setRemoving(false);
        return;
      }
      const res = await api("remove", {
        documents: targetDocs,
        action: act,
        confirmed: true,
      });
      const blocked = Array.isArray(res) ? res.filter((r) => r.status === "BLOCKED").length : 0;
      if (blocked > 0) {
        toast.warning(
          t(
            `${blocked} Dokument(e) wegen vorhandener Forschungshistorie geschützt (nicht gelöscht).`,
            `${blocked} document(s) protected due to existing research history.`
          )
        );
      } else {
        toast.success(
          act === "archive"
            ? t("Auswahl archiviert", "Selection archived")
            : act === "restore"
            ? t("Dokumente wiederhergestellt", "Documents restored")
            : t("Arbeitsbereichseinträge entfernt", "Workspace entries removed")
        );
      }
      if (act !== "restore") onClearSelection();
      setRemoveAction(null);
      setRemovePreview(null);
      await onRefreshFiles?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setRemoving(false);
    }
  };

  const evidenceItems = useMemo(
    () => items.filter((item) => (item.corpus_role || "evidence") !== "reference"),
    [items]
  );
  const allVisibleSelected =
    evidenceItems.length > 0 && evidenceItems.every((item) => selectedIds.has(item.id));

  const toggleCorpusRole = async (doc) => {
    const nextRole = doc.corpus_role === "reference" ? "evidence" : "reference";
    try {
      await api("corpus-role", { documents: [doc.id], corpus_role: nextRole });
      if (nextRole === "reference" && selectedIds.has(doc.id)) {
        onToggleSelect(doc.id, false);
      }
      toast.success(
        nextRole === "reference"
          ? t(
              `${doc.name} als Referenz / Codebook geschützt (von A/B/C-Synthese ausgenommen)`,
              `${doc.name} marked as Reference / Codebook (excluded from blind A/B/C synthesis)`
            )
          : t(
              `${doc.name} wieder als Primärquelle freigegeben`,
              `${doc.name} restored as Primary Study Source`
            )
      );
      await onRefreshFiles?.();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const columns = useMemo(
    () => [
      {
        id: "select",
        header: () => (
          <input
            type="checkbox"
            className="lx-checkbox"
            checked={allVisibleSelected}
            onChange={(e) => (e.target.checked ? onSelectVisible() : onClearSelection())}
            aria-label={t("Alle sichtbaren Dateien auswählen", "Select all visible files")}
          />
        ),
        cell: ({ row }) => {
          const doc = row.original;
          const isRef = doc.corpus_role === "reference";
          return (
            <input
              type="checkbox"
              className="lx-checkbox"
              disabled={isRef}
              checked={!isRef && selectedIds.has(doc.id)}
              onChange={(e) => onToggleSelect(doc.id, e.target.checked)}
              title={
                isRef
                  ? t(
                      "Referenz-/Codebook-Datei (von blinder Synthese geschützt)",
                      "Reference/Codebook file (protected from blind synthesis)"
                    )
                  : undefined
              }
              aria-label={`${doc.name} ${t("auswählen", "select")}`}
            />
          );
        },
        size: 40,
      },
      {
        id: "document",
        header: () => t("Dokument & Quelle", "Document & Origin"),
        cell: ({ row }) => {
          const doc = row.original;
          return (
            <div className="lx-doc-cell min-w-0">
              <button
                type="button"
                className="lx-doc-link truncate"
                onClick={() => onOpenDocument(doc)}
                title={doc.name}
              >
                {doc.name}
              </button>
              <span className="lx-doc-path truncate" title={doc.origin || ""}>
                {doc.origin || "—"}
              </span>
            </div>
          );
        },
      },
      {
        id: "format",
        header: () => t("Format", "Format"),
        cell: ({ row }) => {
          const ext = (row.original.name.split(".").pop() || "FILE").toUpperCase().slice(0, 6);
          return <span className="lx-fmt-pill tabular">{ext}</span>;
        },
        size: 82,
      },
      {
        id: "role",
        header: () => (
          <div className="lx-row-gap">
            <span>{t("Rolle", "Role")}</span>
            <InfoPopover
              title={t(
                "Kontaminationsschutz: Primärquelle vs. Referenz / Codebook",
                "Contamination Guard: Primary Source vs. Reference / Codebook"
              )}
            >
              <p style={{ marginBottom: 6 }}>
                <strong>{t("Primärquelle (Standard)", "Primary Source (Default)")}:</strong>{" "}
                {t(
                  "Unverfälschte Studiendaten (Transkripte, Notizen, Fragebögen, Folien) für die induktive A/B/C-Synthese.",
                  "Primary study artifacts (transcripts, notes, surveys, slides) eligible for inductive A/B/C synthesis."
                )}
              </p>
              <p>
                <strong>{t("Referenz / Codebook", "Reference / Codebook")}:</strong>{" "}
                {t(
                  "Menschliche Experten-Codebooks oder Ground-Truth-Tabellen bleiben lokal konvertierbar und im Quelleninspektor lesbar, sind aber vor versehentlicher Übergabe an die blinde KI-Synthese geschützt.",
                  "Human codebooks or ground-truth files remain inspectable in Source Inspector, but are blocked from leaking into blind inductive LLM synthesis."
                )}
              </p>
            </InfoPopover>
          </div>
        ),
        cell: ({ row }) => {
          const doc = row.original;
          const isRef = doc.corpus_role === "reference";
          return (
            <button
              type="button"
              className={`lx-btn lx-btn-xs ${isRef ? "lx-tag-warn" : "lx-btn-ghost"}`}
              onClick={() => toggleCorpusRole(doc)}
              title={t(
                "Klicken zum Umschalten zwischen Primärquelle und Referenz/Codebook",
                "Click to toggle between Primary Source and Reference/Codebook"
              )}
            >
              <span>
                {isRef
                  ? t("Referenz / Codebook", "Reference / Codebook")
                  : t("Primärquelle", "Primary")}
              </span>
            </button>
          );
        },
        size: 150,
      },
      {
        id: "docling",
        header: () => t("Docling-Struktur", "Docling Structure"),
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
        size: 185,
      },
      {
        id: "stageA",
        header: () => (
          <div className="lx-row-gap">
            <span>{t("Evidenz A", "Evidence A")}</span>
            <InfoPopover
              title={t(
                "Was bedeuten die Evidenz-Status?",
                "What do Evidence A statuses mean?"
              )}
            >
              <p style={{ marginBottom: 6 }}>
                <strong>{t("Quellengebunden · Offen", "Source-Bound · Open")}:</strong>{" "}
                {t(
                  "Alle Zitate sind im Dokument lokalisiert (100 % verankert), die menschliche Fachprüfung steht optional noch aus.",
                  "All quotes are anchored in the document (100% grounded); human semantic review is still open."
                )}
              </p>
              <p>
                <strong>{t("Teilweise verankert", "Partially Grounded")}:</strong>{" "}
                {t(
                  "Ein Teil der Beobachtungen ist verankert, aber mindestens ein Zitat war mehrdeutig oder nicht wörtlich auffindbar. Klicke in der Analyse-Pipeline auf ‚offene prüfen‘, um Kandidaten mit 1 Klick zuzuordnen oder auszuschließen.",
                  "Most observations are grounded, but at least one quote was ambiguous or non-verbatim. Inspect open items in the Pipeline view to heal in 1 click or exclude."
                )}
              </p>
            </InfoPopover>
          </div>
        ),
        cell: ({ row }) => {
          const ex = row.original.extraction;
          if (!ex || ex === "NOT_RUN") {
            return <StatusBadge label={t("Ausstehend", "Not Run")} tone="neutral" />;
          }
          const explain =
            ex === "PARTIAL"
              ? t(
                  "Mindestens 1 Beobachtung ist mehrdeutig oder nicht wörtlich im Dokument gefunden. In ‚Analyse-Pipeline‘ unter ‚offene prüfen‘ einsehbar und per 1-Klick behebbar.",
                  "At least 1 observation is ambiguous or non-verbatim. Open 'Analysis Pipeline' -> 'inspect open' to view exact reasons and fix in 1 click."
                )
              : ex === "UNREVIEWED"
              ? t(
                  "Alle Beobachtungen sind wörtlich im DoclingDocument verankert; bereit für Stufe B & C sowie menschliche Fachprüfung.",
                  "All observations are verbatim-grounded in the DoclingDocument; ready for Stages B & C and researcher review."
                )
              : ex === "ERROR"
              ? t(
                  "Noch kein gültiger Stufe-A-Lauf vorhanden (letzter Versuch fehlgeschlagen). Details findest du in ‚Terminal & Verlauf‘.",
                  "No valid Stage A run yet (last attempt failed). Inspect exact diagnostics in 'Terminal & History'."
                )
              : null;
          return (
            <div className="lx-row-gap">
              <StatusBadge status={ex} />
              {explain && (
                <InfoPopover title={row.original.name}>
                  <p>{explain}</p>
                </InfoPopover>
              )}
            </div>
          );
        },
        size: 225,
      },
      {
        id: "actions",
        header: () => "",
        cell: ({ row }) => (
          <div className="lx-cell-right">
            <button
              type="button"
              className="lx-btn lx-btn-xs"
              onClick={() => onOpenDocument(row.original)}
            >
              <Eye size={12} />
              <span>{t("Prüfen", "Inspect")}</span>
            </button>
          </div>
        ),
        size: 104,
      },
    ],
    [allVisibleSelected, selectedIds, onSelectVisible, onClearSelection, onToggleSelect, onOpenDocument, t]
  );

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="lx-page">
      {/* Page Header */}
      <header className="lx-page-header">
        <div className="min-w-0">
          <h1 className="lx-page-title">{t("Studienkorpus", "Study Corpus")}</h1>
          <p className="lx-page-subtitle">
            {t(
              "Heterogene Forschungsartefakte verwalten, für die Synthese auswählen und im Original prüfen.",
              "Manage heterogeneous UX study artifacts, select analysis scope, and inspect originals."
            )}
          </p>
        </div>
        <div className="lx-btn-row">
          <button
            type="button"
            className="lx-btn"
            onClick={() => onImportModalChange(true)}
          >
            <Plus size={14} />
            <span>{t("Dateien / Ordner hinzufügen", "Add Files / Folder")}</span>
          </button>
          <button
            type="button"
            className="lx-btn lx-btn-primary"
            disabled={selectedIds.size === 0}
            onClick={() => onNavigate("pipeline")}
          >
            <span>
              {t("Zur Analyse-Pipeline", "Open Analysis Pipeline")}
              {selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}
            </span>
            <ArrowRight size={14} />
          </button>
        </div>
      </header>

      {/* Monochrome KPI Strip */}
      <section className="lx-kpi-grid" aria-label={t("Korpus-Kennzahlen", "Corpus Metrics")}>
        <div className="lx-kpi-card">
          <span className="lx-kpi-label">{t("Dokumente im Korpus", "Documents in Corpus")}</span>
          <strong className="lx-kpi-value tabular">{total}</strong>
          <span className="lx-kpi-sub">{t("PDF, DOCX, PPTX, XLSX, CSV, TXT", "PDF, DOCX, PPTX, XLSX, CSV, TXT")}</span>
        </div>
        <div className="lx-kpi-card">
          <span className="lx-kpi-label">{t("Docling konvertiert", "Docling Converted")}</span>
          <strong className="lx-kpi-value tabular">
            {convertedCount} <span className="lx-kpi-denom">/ {items.length}</span>
          </strong>
          <span className="lx-kpi-sub">{t("Struktur & Seitengeometrie bereit", "Structure & geometry ready")}</span>
        </div>
        <div className="lx-kpi-card">
          <span className="lx-kpi-label">{t("Stufe A extrahiert", "Stage A Extracted")}</span>
          <strong className="lx-kpi-value tabular">
            {stageACount} <span className="lx-kpi-denom">/ {items.length}</span>
          </strong>
          <span className="lx-kpi-sub">{t("Quellengebundene Beobachtungen", "Source-anchored observations")}</span>
        </div>
        <div className={`lx-kpi-card${selectedIds.size > 0 ? " is-highlighted" : ""}`}>
          <span className="lx-kpi-label">{t("Aktive Studienauswahl", "Active Study Scope")}</span>
          <strong className="lx-kpi-value tabular">{selectedIds.size}</strong>
          <span className="lx-kpi-sub">
            {selectedIds.size > 0
              ? t("Bereit für B-Relationen & C-Findings", "Ready for Stage B & C synthesis")
              : t("Dateien unten anhaken", "Check files below to include")}
          </span>
        </div>
      </section>

      {/* Filter & Bulk Action Toolbar */}
      <div className="lx-toolbar-card">
        <div className="lx-toolbar-left">
          <div className="lx-search-wrap" style={{ width: 256 }}>
            <Search size={14} className="lx-search-icon" />
            <input
              type="search"
              className="lx-input lx-input-sm lx-search-input"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={t("Dateiname oder Pfad filtern …", "Filter filename or path…")}
              aria-label={t("Dokumente durchsuchen", "Search documents")}
            />
          </div>
          <div style={{ width: 185 }}>
            <Select
              size="sm"
              value={sort}
              onValueChange={onSortChange}
              ariaLabel={t("Sortierung", "Sort order")}
              options={[
                ["newest", t("Neueste zuerst", "Newest first")],
                ["name", t("Alphabetisch (A–Z)", "Name (A–Z)")],
                ["status", t("Nach Status", "By Status")],
              ]}
            />
          </div>
          <label className="lx-inline-switch">
            <Switch checked={archived} onCheckedChange={onArchivedChange} />
            <span>{t("Archiv", "Archived")}</span>
          </label>
        </div>

        <div className="lx-toolbar-right">
          <button
            type="button"
            className="lx-btn lx-btn-sm lx-btn-ghost"
            disabled={!items.length}
            onClick={onSelectVisible}
          >
            <CheckSquare size={13} />
            <span>{t("Alle wählen", "Select All")}</span>
          </button>
          {selectedIds.size > 0 && (
            <>
              <button
                type="button"
                className="lx-btn lx-btn-sm lx-btn-ghost"
                onClick={onClearSelection}
              >
                <Square size={13} />
                <span>{t("Auswahl leeren", "Clear")}</span>
              </button>
              {archived ? (
                <button
                  type="button"
                  className="lx-btn lx-btn-sm"
                  onClick={() => openRemoveModal("restore")}
                >
                  <RotateCcw size={13} />
                  <span>{t("Wiederherstellen", "Restore")}</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="lx-btn lx-btn-sm"
                  onClick={() => openRemoveModal("archive")}
                >
                  <Archive size={13} />
                  <span>{t("Archivieren", "Archive")}</span>
                </button>
              )}
              <button
                type="button"
                className="lx-btn lx-btn-sm lx-btn-danger-ghost"
                onClick={() => openRemoveModal("remove")}
              >
                <Trash2 size={13} />
                <span>{t("Entfernen", "Remove")}</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Data Table or Empty State */}
      {total === 0 && !search && !archived ? (
        <div className="lx-empty-state">
          <FolderPlus size={28} strokeWidth={1.5} className="lx-icon-muted" />
          <h2>{t("Noch keine Studiendokumente im Arbeitsbereich", "No study documents in workspace yet")}</h2>
          <p>
            {t(
              "Füge einen Untersuchungsordner oder einzelne PDF-, Office-, Tabellen- oder Transkriptdateien hinzu. Externe Originale bleiben unangetastet.",
              "Add a study folder or individual PDF, Office, spreadsheet, or transcript files. External originals remain untouched."
            )}
          </p>
          <button
            type="button"
            className="lx-btn lx-btn-primary"
            onClick={() => onImportModalChange(true)}
          >
            <Plus size={14} />
            <span>{t("Studienordner oder Dateien importieren", "Import Study Folder or Files")}</span>
          </button>
        </div>
      ) : (
        <div className="lx-table-card">
          <div className="lx-table-scroll">
            <table className="lx-table">
              <thead>
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>
                    {hg.headers.map((header) => (
                      <th
                        key={header.id}
                        style={
                          header.column.columnDef.size
                            ? { width: `${header.column.columnDef.size}px` }
                            : undefined
                        }
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length} className="lx-table-empty">
                      {t("Keine passenden Dokumente gefunden.", "No matching documents found.")}
                    </td>
                  </tr>
                ) : (
                  table.getRowModel().rows.map((row) => {
                    const isSel = selectedIds.has(row.original.id);
                    return (
                      <tr key={row.id} className={isSel ? "is-selected" : ""}>
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id}>
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {total > 100 && (
            <footer className="lx-table-footer">
              <span className="lx-muted tabular">
                {offset + 1}–{Math.min(offset + items.length, total)} / {total}
              </span>
              <div className="lx-btn-row">
                <button
                  type="button"
                  className="lx-btn lx-btn-xs"
                  disabled={offset === 0}
                  onClick={() => onOffsetChange(Math.max(0, offset - 100))}
                >
                  <ChevronLeft size={13} />
                  <span>{t("Zurück", "Previous")}</span>
                </button>
                <button
                  type="button"
                  className="lx-btn lx-btn-xs"
                  disabled={offset + 100 >= total}
                  onClick={() => onOffsetChange(offset + 100)}
                >
                  <span>{t("Weiter", "Next")}</span>
                  <ChevronRight size={13} />
                </button>
              </div>
            </footer>
          )}
        </div>
      )}

      {/* Import Modal */}
      <Modal
        open={importModalOpen}
        onOpenChange={onImportModalChange}
        title={t("Studiendokumente importieren", "Import Study Documents")}
        subtitle={t(
          "Frei gewählte Untersuchungsordner oder Einzeldateien ohne Pflichtklassifikation aufnehmen.",
          "Import arbitrary UX research folders or individual files without mandatory pre-classification."
        )}
      >
        <form onSubmit={submitImport} className="lx-form-stack">
          <div className="lx-btn-row">
            <button type="button" className="lx-btn lx-btn-sm" onClick={() => pickPaths(false)}>
              {t("Dateien wählen …", "Pick Files…")}
            </button>
            <button type="button" className="lx-btn lx-btn-sm" onClick={() => pickPaths(true)}>
              {t("Studienordner wählen …", "Pick Folder…")}
            </button>
          </div>
          <label className="lx-field">
            <span className="lx-field-label">
              {t("Lokale Dateipfade oder Ordner (ein Pfad pro Zeile)", "Local file or folder paths (one per line)")}
            </span>
            <textarea
              rows={5}
              className="lx-textarea"
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder="C:\Studien\Usability-Test-Runde-1"
            />
          </label>
          <label className="lx-inline-switch">
            <Switch checked={convertOnImport} onCheckedChange={setConvertOnImport} />
            <span>
              {t(
                "Direkt lokal mit Docling konvertieren (kein externer KI-Versand)",
                "Convert immediately with local Docling (no external LLM transfer)"
              )}
            </span>
          </label>
          <div className="lx-modal-actions">
            <button
              type="button"
              className="lx-btn"
              onClick={() => onImportModalChange(false)}
            >
              {t("Abbrechen", "Cancel")}
            </button>
            <button type="submit" disabled={importing} className="lx-btn lx-btn-primary">
              {importing
                ? t("Wird aufgenommen …", "Importing…")
                : t("In Korpus aufnehmen", "Import into Corpus")}
            </button>
          </div>
        </form>
      </Modal>

      {/* Archive / Remove Confirmation Modal */}
      <Modal
        open={Boolean(removeAction)}
        onOpenChange={(v) => !v && setRemoveAction(null)}
        title={
          removeAction === "archive"
            ? t("Auswahl archivieren", "Archive Selection")
            : removeAction === "restore"
            ? t("Auswahl wiederherstellen", "Restore Selection")
            : t("Aus Arbeitsbereich entfernen", "Remove from Workspace")
        }
        subtitle={t(
          "Externe Originaldateien auf deiner Festplatte werden niemals gelöscht.",
          "External original files on disk are never modified or deleted."
        )}
      >
        <div className="lx-form-stack">
          {(() => {
            const list = Array.isArray(removePreview) ? removePreview : [];
            const blockedDocs = list.filter((d) => !d.removable);
            const removableDocs = list.filter((d) => d.removable);
            return (
              <>
                <p className="lx-text-sm">
                  {t("Betroffene Dokumente", "Selected documents")}:{" "}
                  <strong className="tabular">{list.length || selectedIds.size}</strong>
                </p>
                {removeAction === "remove" && blockedDocs.length > 0 && (
                  <div className="lx-callout-box lx-callout-warning">
                    <p className="lx-text-xs">
                      {t(
                        `${blockedDocs.length} Dokument(e) besitzen gespeicherte Extraktionsläufe, Findings oder Forscherentscheidungen und sind revisionssicher vor endgültigem Löschen geschützt (${blockedDocs
                          .map((b) => b.name)
                          .slice(0, 3)
                          .join(", ")}). Du kannst sie stattdessen archivieren.`,
                        `${blockedDocs.length} document(s) have stored runs, findings, or researcher decisions and are protected against deletion. Archive them instead.`
                      )}
                    </p>
                  </div>
                )}
                <div className="lx-modal-actions">
                  <button type="button" className="lx-btn" onClick={() => setRemoveAction(null)}>
                    {t("Abbrechen", "Cancel")}
                  </button>
                  {removeAction === "remove" && blockedDocs.length > 0 && (
                    <button
                      type="button"
                      disabled={removing}
                      className="lx-btn lx-btn-primary"
                      onClick={() => confirmRemove("archive")}
                    >
                      <Archive size={13} />
                      <span>{t("Stattdessen archivieren", "Archive Instead")}</span>
                    </button>
                  )}
                  {(removeAction !== "remove" || removableDocs.length > 0) && (
                    <button
                      type="button"
                      disabled={removing}
                      className={`lx-btn ${
                        removeAction === "remove" ? "lx-btn-danger" : "lx-btn-primary"
                      }`}
                      onClick={() => confirmRemove()}
                    >
                      {removeAction === "remove" && blockedDocs.length > 0
                        ? t(
                            `Nur ${removableDocs.length} unbenutzte entfernen`,
                            `Remove ${removableDocs.length} unused`
                          )
                        : t("Bestätigen", "Confirm")}
                    </button>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      </Modal>
    </div>
  );
}
