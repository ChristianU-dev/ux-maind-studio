# ADR 0010 · Lokaler Studien-Inspektor und ein UX-Vertrag

**Entscheidung.** Getrennte native Dokumente und deren eingebettete Ressourcen bleiben die maßgebliche Darstellung. Pydantic beschreibt fachliche Kandidaten. LiteLLM liefert die strukturierte Antwort. Der Host erzeugt Fundstellen und Identitäten. Zwei kleine Webpakete übernehmen HTTP und Routing. Die Oberfläche besteht aus lokal ausgeliefertem HTML, CSS und JavaScript.

**Ausgangsbefund.** Schema A leitete Graphidentitäten aus Modell-Dateiname und Zitat ab. Gleicher Wortlaut und mehrere Aussagen am selben Ort sind damit schwer auseinanderzuhalten. Der Graph-HTML-Export bot keine Originalvorschau. Der frühere Entwicklungscheck erforderte Forschungsdateien, die das Wheel selbst bereits ausschloss.

**Abgewogene Wege.** Docling Graph hatte keinen notwendigen Anteil an der nativen Konvertierung, der Originalvorschau oder der neuen Identität. Die Auslieferung entfernt ihn und nutzt die vorhandene LiteLLM-Schnittstelle direkt. Ein eigener HTTP-Parser und ein Buildstack für das Frontend hätten jeweils zusätzliche Wartung verursacht. Starlette 1.10.0 und Uvicorn 0.54.0 sind gepinnt. Pillow und PDFium kommen aus dem bestehenden Docling-Abhängigkeitsbaum.

**Grenzen.** Ein passender Text oder Tabellenwert beweist die Fundstelle. Gemeinsame Themenlabels führen zu überprüfbaren Vorschlägen. Bildpixel gehen in diesem Modellweg nicht an den Anbieter. PDF-Markierungen decken den nativen Elementbereich ab. Office-Dateien erscheinen als Struktur- und Textvorschau. Native Modellressourcen und ein tatsächlicher Providerlauf sind getrennte Abnahmen.

**Portabilitätsgegenprobe.** In einem Installationspfad mit Umlaut fand Docling Parse unter Windows seine installierten Glyphenressourcen nicht. Für solche Ressourcenpfade verwendet die App den mitgelieferten nativen PDFium-Backend mit derselben Docling-Pipeline. Der erneute Import konvertierte das synthetische PDF und lieferte eine auf der Originalseite sichtbare native Region.

**Formatabhängigkeit.** Der ODT-Backend verlangt die optionale OpenDocument-Abhängigkeit. Der Standardimport schlug im separaten ZIP-Installationspfad mit ImportError fehl. Das zusätzliche Extra am bestehenden Docling-Slim-Pin liefert den nativen Backend vollständig aus. Die installierte Regression prüft ODT-Text sowie XLSX-Zellen mit Zeilenkontext.

**Nachweise.** [N4b-Ausgangsstand](https://github.com/ChristianU-dev/ux-maind-docling/tree/b9a1b174a335c9d2c0b1f204f5341540845507f8) · [Docling Visual Grounding](https://docling-project.github.io/docling/_generated/examples/visual_grounding/) · [Starlette-Sicherheitsmeldungen](https://github.com/Kludex/starlette/security/advisories) · [Abnahme](../ACCEPTANCE.md)
