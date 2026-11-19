# Daten und bewusste Übermittlung

Frei ausgewählte Dateien und Unterordner werden mit nativer Formaterkennung verarbeitet. Fehler bleiben pro Datei sichtbar. Lesbare Originale bleiben als unveränderte Kopie verfügbar. Native JSONs und optionale LibreOffice-Anzeige-PDFs sind abgeleitete Versionen.

- **Extraktion** übermittelt die native Modellserialisierung der ausdrücklich gewählten Docling-Versionen an den gewählten Modellendpunkt. Enthaltene Bildmetadaten hängen von der nativen Serialisierung ab.
- **Bildanreicherung** verwendet ein bewusst gewähltes lokales Modell oder übermittelt die Pixel der Auswahl nach Bestätigung an einen OpenAI-kompatiblen Endpunkt. Dateiansicht, Hover und Quellenprüfung laufen lokal.
- **Synthese** übermittelt quellgebundene Beobachtungen, Belege, die zugehörigen nativen Abschnitte aus dem Provenance Ledger, Entscheidungen, bestätigte Relationen und die optionale Forschungsfrage im gewählten Dokumentumfang.

Profil und Laufmetadaten führen Basis-URL und Variablennamen. Zugangsdaten werden zur Laufzeit gelesen. Rohantworten, Traces und Rohquellen bleiben in der lokalen Workspace-Ablage. Die autorisierten R17-Modellversuche mit FAU und Anthropic verwenden ausgewählte öffentliche SERDIF-Belege und synthetische Quellen.

Historische Originale, Native-JSONs, Rohantworten, Notizen und Entscheidungen bleiben erhalten. Neue Entscheidungen werden append-only gespeichert und als menschlich oder automatisiert gekennzeichnet. Quellbindung bestätigt ein Originalvorkommen. Fachliche Aussage, Akteur, Scope und Finding brauchen eine eigenständige Prüfung.

Lokale PDF.js-Texttreffer und native OCR-Boxen bleiben getrennte Anzeigehilfen. Office-Anzeige-PDFs erhalten eine eigene Herkunft und Hashbindung. Mehrdeutige Originalvorkommen werden nicht still ausgewählt. Dokument-HTML bleibt isoliert.
