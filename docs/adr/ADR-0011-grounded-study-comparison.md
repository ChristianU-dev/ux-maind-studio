# ADR 0011 · Quellenabgleich und Einzelbildanalyse

**Problem.** Die alte Gruppierung verband Einheiten anhand gleicher Themenlabels. Außerdem überdeckte ein einzelner Abdeckungsgrund andere Lücken, und ein erfolgreich konvertiertes Bild blieb semantisch unerschlossen. Das vorhandene Monday-Paket zeigt alle drei Grenzen.

**Entscheidung.** Ein lokaler Wortabgleich gewichtet seltene Überlappungen in Aussagen und Originalauszügen. Das Suchfenster enthält höchstens 320 Einheiten und 48 Paare, mit höchstens drei Paaren pro Einheit. Das Modell erhält je Aufruf bis zu vier Paare. Begründung, Beziehungstyp und ein gültiger Originalanker pro Seite sind Voraussetzung für die Verbindung. Positive, negative und widersprüchliche Aussagen bleiben als eigenständige Einheiten erhalten. Die App bildet keine transitiven Gruppen. Der lokale Vergleich mit manueller Begründung bleibt möglich.

**Native Alternative.** Doclings gepinnter Picture-Description-API-Backend ist an eine OpenAI-kompatible Schnittstelle und den Enrichment-Pfad gebunden. Sein eingebautes Antwortobjekt ist eine Beschreibung und enthält keinen getrennten UX-Vertrag für Bildtext, sichtbare Unsicherheit und Claims. Der Inspektor liest deshalb das vorhandene native PictureItem und verwendet den bestehenden LiteLLM-Adapter für eine separat freigegebene, strukturierte Bildlesart. Es gibt keine neue OCR und keine erneute Konvertierung alter Bilder.

**Grenzen.** Der Abgleich kann synonyme Sachverhalte ohne lexikalische Überschneidung übersehen. Eine Folienstruktur aus Docling ist keine gerenderte Office-Originalseite. Vision ist eine Modelllesart mit festem Bildanker und liefert keine verifizierte Abschrift oder Pixelkoordinaten. Ollama bleibt eine mögliche lokale Route über den bestehenden Modelladapter. Es wurde kein Ollama-Server angebunden oder als getestete Funktion freigegeben.

[Docling Picture Description](https://docling-project.github.io/docling/_generated/examples/pictures_description/) · [LiteLLM Vision](https://docs.litellm.ai/docs/completion/vision) · [Abnahme](../ACCEPTANCE.md)
