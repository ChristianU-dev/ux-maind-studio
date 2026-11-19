import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

const LANG_KEY = "ux_maind_lang";
const THEME_KEY = "ux_maind_theme";

const StudioPrefsContext = createContext({
  lang: "de",
  theme: "light",
  setLang: () => {},
  setTheme: () => {},
  toggleTheme: () => {},
  t: (de, _en) => de,
});

export function StudioPrefsProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try {
      const s = localStorage.getItem(LANG_KEY);
      if (s === "en" || s === "de") return s;
    } catch {}
    return "de";
  });

  const [theme, setThemeState] = useState(() => {
    try {
      const s = localStorage.getItem(THEME_KEY);
      if (s === "dark" || s === "light") return s;
    } catch {}
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {}
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch {}
  }, [lang]);

  const setLang = useCallback((next) => setLangState(next === "en" ? "en" : "de"), []);
  const setTheme = useCallback((next) => setThemeState(next === "dark" ? "dark" : "light"), []);
  const toggleTheme = useCallback(
    () => setThemeState((prev) => (prev === "dark" ? "light" : "dark")),
    []
  );
  const t = useCallback((de, en) => (lang === "en" ? en : de), [lang]);

  return (
    <StudioPrefsContext.Provider value={{ lang, theme, setLang, setTheme, toggleTheme, t }}>
      {children}
    </StudioPrefsContext.Provider>
  );
}

export function usePrefs() {
  return useContext(StudioPrefsContext);
}

export function statusInfo(status, t) {
  const map = {
    converted: { label: t("Konvertiert", "Converted"), tone: "success" },
    success: { label: t("Konvertiert", "Converted"), tone: "success" },
    partial_success: { label: t("Teilweise konvertiert", "Partial Conversion"), tone: "warning" },
    UNREVIEWED: { label: t("Quellengebunden · Offen", "Source-Bound · Unreviewed"), tone: "warning" },
    SOURCE_RESOLVED: { label: t("Quellengebunden · Offen", "Source-Bound · Unreviewed"), tone: "warning" },
    PARTIAL: { label: t("Teilweise verankert", "Partial Grounding"), tone: "warning" },
    HUMAN_CONFIRMED: { label: t("Menschlich bestätigt", "Human Confirmed"), tone: "success" },
    HUMAN_CORRECTED: { label: t("Menschlich korrigiert", "Human Corrected"), tone: "neutral" },
    HUMAN_REJECTED: { label: t("Verworfen", "Rejected"), tone: "danger" },
    HUMAN_OPEN: { label: t("Zur Prüfung", "Flagged Open"), tone: "warning" },
    ERROR: { label: t("Fehler", "Error"), tone: "danger" },
    failure: { label: t("Konvertierungsfehler", "Conversion Failed"), tone: "danger" },
    WAITING_REVIEW: { label: t("Prüfung erforderlich", "Awaiting Review"), tone: "warning" },
    RUNNING: { label: t("Aktiv", "Running"), tone: "active" },
    NO_PROPOSALS: { label: t("Keine Vorschläge", "No Proposals"), tone: "neutral" },
    skipped: { label: t("Übersprungen", "Skipped"), tone: "neutral" },
    planned: { label: t("Geplant", "Planned"), tone: "neutral" },
  };
  return map[status] || { label: status || "—", tone: "neutral" };
}
