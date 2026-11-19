import React, { useEffect } from "react";
import { Command } from "cmdk";
import {
  BarChart3,
  BookOpen,
  CheckSquare,
  Coins,
  FileText,
  FolderOpen,
  GitBranch,
  Languages,
  Layers,
  MessageSquareCode,
  Moon,
  Search,
  Settings,
  Sparkles,
  Square,
  Sun,
  Terminal,
} from "lucide-react";
import { usePrefs } from "../lib/i18n.jsx";
import { Kbd } from "./ui.jsx";

export function CommandPalette({
  open,
  onOpenChange,
  onNavigate,
  onOpenSynthesisTab,
  onOpenSettingsTab,
  files = [],
  onOpenDocument,
  onSelectAll,
  onClearSelection,
  onOpenImport,
}) {
  const { lang, setLang, theme, toggleTheme, t } = usePrefs();

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onOpenChange]);

  const run = (fn) => {
    onOpenChange(false);
    fn();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label={t("Befehlspalette", "Command Palette")}
      className="lx-cmdk-dialog"
    >
      <div className="lx-cmdk-overlay" onClick={() => onOpenChange(false)} />
      <div className="lx-cmdk-panel">
        <div className="lx-cmdk-input-wrap">
          <Search size={15} className="lx-icon-muted" />
          <Command.Input
            className="lx-cmdk-input"
            placeholder={t(
              "Ansicht wechseln, Dokument öffnen oder Aktion suchen …",
              "Jump to view, inspect document, or run action…"
            )}
          />
          <Kbd>ESC</Kbd>
        </div>

        <Command.List className="lx-cmdk-list">
          <Command.Empty className="lx-cmdk-empty">
            {t("Keine passenden Befehle oder Dokumente.", "No matching commands or documents.")}
          </Command.Empty>

          <Command.Group heading={t("Navigation", "Navigation")} className="lx-cmdk-group">
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("documents"))}>
              <FolderOpen size={14} />
              <span>{t("Studienkorpus & Dokumente", "Study Corpus & Documents")}</span>
              <Kbd>1</Kbd>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("pipeline"))}>
              <Layers size={14} />
              <span>{t("Analyse-Pipeline (A · B · C)", "Analysis Pipeline (A · B · C)")}</span>
              <Kbd>2</Kbd>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("results"))}>
              <Sparkles size={14} />
              <span>{t("Synthese & Findings", "Synthesis & Findings")}</span>
              <Kbd>3</Kbd>
            </Command.Item>
            {onOpenSynthesisTab && (
              <>
                <Command.Item
                  className="lx-cmdk-item"
                  onSelect={() => run(() => onOpenSynthesisTab("charts"))}
                >
                  <BarChart3 size={14} />
                  <span>{t("Diagramme & Triangulations-Matrix", "Charts & Triangulation Matrix")}</span>
                </Command.Item>
                <Command.Item
                  className="lx-cmdk-item"
                  onSelect={() => run(() => onOpenSynthesisTab("telemetry"))}
                >
                  <Coins size={14} />
                  <span>{t("Token- & Kosten-Telemetrie (Evaluation)", "Token & API Cost Telemetry")}</span>
                </Command.Item>
              </>
            )}
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("graph"))}>
              <GitBranch size={14} />
              <span>{t("Evidenz- & Wissensgraph", "Evidence & Knowledge Graph")}</span>
              <Kbd>4</Kbd>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("review"))}>
              <FileText size={14} />
              <span>{t("Quelleninspektor (Dual-View)", "Source Inspector (Dual-View)")}</span>
              <Kbd>5</Kbd>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("terminal"))}>
              <Terminal size={14} />
              <span>{t("Terminal & Auftragsverlauf", "Terminal & Run Ledger")}</span>
              <Kbd>6</Kbd>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(() => onNavigate("settings"))}>
              <Settings size={14} />
              <span>{t("Einstellungen & Modelle", "Settings & Models")}</span>
              <Kbd>7</Kbd>
            </Command.Item>
            {onOpenSettingsTab && (
              <>
                <Command.Item
                  className="lx-cmdk-item"
                  onSelect={() => run(() => onOpenSettingsTab("prompts"))}
                >
                  <MessageSquareCode size={14} />
                  <span>{t("System-Prompts & Zusatzregeln bearbeiten", "Edit Base Prompts & Addenda")}</span>
                </Command.Item>
                <Command.Item
                  className="lx-cmdk-item"
                  onSelect={() => run(() => onOpenSettingsTab("manual"))}
                >
                  <BookOpen size={14} />
                  <span>{t("Benutzerhandbuch & Systemgrenzen öffnen", "Open User Manual & System Limits")}</span>
                </Command.Item>
              </>
            )}
          </Command.Group>

          <Command.Group heading={t("Aktionen & Ansicht", "Actions & Preferences")} className="lx-cmdk-group">
            <Command.Item className="lx-cmdk-item" onSelect={() => run(onOpenImport)}>
              <FolderOpen size={14} />
              <span>{t("Dateien oder Studienordner importieren …", "Import files or study folder…")}</span>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(onSelectAll)}>
              <CheckSquare size={14} />
              <span>{t("Alle sichtbaren Dokumente auswählen", "Select all visible documents")}</span>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(onClearSelection)}>
              <Square size={14} />
              <span>{t("Dokumentauswahl aufheben", "Clear document selection")}</span>
            </Command.Item>
            <Command.Item className="lx-cmdk-item" onSelect={() => run(toggleTheme)}>
              {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
              <span>
                {theme === "dark"
                  ? t("Zum hellen Erscheinungsbild wechseln", "Switch to Light Mode")
                  : t("Zum dunklen Erscheinungsbild wechseln", "Switch to Dark Mode")}
              </span>
            </Command.Item>
            <Command.Item
              className="lx-cmdk-item"
              onSelect={() => run(() => setLang(lang === "de" ? "en" : "de"))}
            >
              <Languages size={14} />
              <span>
                {lang === "de"
                  ? "Switch UI language to English (EN)"
                  : "Oberflächensprache auf Deutsch umstellen (DE)"}
              </span>
            </Command.Item>
          </Command.Group>

          {files.length > 0 && (
            <Command.Group
              heading={t("Dokumente direkt im Dual-View prüfen", "Inspect Documents in Dual-View")}
              className="lx-cmdk-group"
            >
              {files.slice(0, 25).map((f) => (
                <Command.Item
                  key={f.id}
                  value={`${f.name} ${f.origin || ""}`}
                  className="lx-cmdk-item"
                  onSelect={() => run(() => onOpenDocument(f))}
                >
                  <FileText size={14} />
                  <span className="truncate">{f.name}</span>
                  <span className="lx-muted tabular">#{f.id}</span>
                </Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </div>
    </Command.Dialog>
  );
}
