# Modellzugänge · R18c

Die Anwendung verwendet den Docling-Graph-`LiteLLMClient` und `resolve_effective_model_config`. Profile speichern eine frei eingebbare Modellkennung, Anbieter, optionalen Endpunkt, Schlüsselvariablennamen und native Optionen. NHR@FAU verwendet `LLMAPI_KEY`, Anthropic `ANTHROPIC_API_KEY`. Profile und lokale Laufdiagnosen enthalten keine Schlüsselwerte.

## Kapazität und Anfrage

- Eine explizite Profileinstellung bleibt wirksam. Aus belastbaren Metadaten stammen der Modellkontext und gegebenenfalls ein separat ausgewiesenes Ausgabelimit. Bei unbekannten Werten zeigt die Anwendung den SDK-Planungsfallback samt Herkunft.
- FAU-Modelldaten können Eingabe und Ausgabe mit demselben Maximum ausweisen. Im Fall Qwen betrugen beide Angaben 262.144 Token. Eine gleich hohe separate Ausgabeforderung würde bereits ohne Eingabe das gesamte gemeinsame Fenster belegen. Im Automatikmodus lässt der FAU-Client `max_tokens` aus. Der Gateway bemisst die Ausgabe gegen das tatsächlich verfügbare Kontextfenster.
- Die frühere projektspezifische Planungsreferenz von 32.768 ist entfernt. Fehlt ein belastbares separates Ausgabelimit, zeigt die Anwendung den nativen Docling-Graph-Fallback mit Herkunft. Dieser Planungswert kann die Auto-Wahl beeinflussen. Mit FAU-Anbieterautomatik fehlt max_tokens weiterhin in der Anfrage. Bewusst gesetzte Profilwerte für die Ausgabe bleiben konfigurierbar.
- Die Modellvorschau in den Einstellungen zeigt Graph-Ausgabeplanung und Anfragewert getrennt. Das Laufprotokoll zeigt die verfügbaren tatsächlich gesendeten Werte pro Anfrage. Im Laufexport ergänzen verfügbare LiteLLM-Daten die tatsächlichen API-Parameter, sichtbare Antwort, Tokenverbrauch, Abschlussgrund und das Vorhandensein von Reasoning. Docling Graph 1.9.2 besitzt in `GenerationOverrides` keinen öffentlichen Thinking-Regler.

Docling Graph steuert Auto, Direct, Dense, Gleaning und Schema-Fallback. Die installierte Fassung begrenzt bei Gleaning die Zusammenfassung auf 8.000 Zeichen und pro Feld die Anleitung auf 200 Zeichen. Das sind native Grenzen. Die Anwendung konfiguriert Gleaning über `PipelineConfig`. [Öffentliche Modellkonfiguration](https://docling-project.github.io/docling-graph/usage/api/llm-model-config/)

## Bildzugang und Freigabe

Die Bestandsaufnahme führt zu einem separaten Konvertierungsauftrag. Bildanreicherung ist dort vorausgewählt. Als Nachweis der Fähigkeit zählt ein konkreter Anbieter-/SDK-Eintrag oder eine überprüfte Modellbereitstellung. Für den aktuellen Eintrag von FAU-Qwen liegt eine erfolgreiche Pixelprobe vor. Ein fehlender Nachweis hält Bildanreicherung offen. Ein späterer bewusst gestarteter Versuch über das vorhandene Vision-Dialogfeld bleibt verfügbar.

Docling nutzt PictureDescriptionApiOptions und bei gewählten Diagrammen seine native API-Engine. Der sichtbare Workspace-Startwert von 120 Sekunden für die Antwortfrist wird an Docling übergeben. Bereits ausdrücklich gespeicherte Fristen gelten weiter. Die Anfrage endet mit der Antwort des Anbieters. Externe Pixel erfordern eine Auftragsfreigabe und einen geeigneten OpenAI-kompatiblen Bildzugang. Anthropic-Messages dient der Textanalyse im LiteLLM-Pfad. Modell, Version, Zeitpunkt und Teilfehler stehen im Workspace. [Native Docling-Optionen](https://docling-project.github.io/docling/reference/pipeline_options/) · [R18a-Abnahme](ACCEPTANCE_R18A.md)

## Auswahl und Auftragsdiagnose

„Aktive Zuordnungen“ wählt gespeicherte Profile für A, B, C und Vision. B und C können A verwenden oder ein eigenes Profil wählen. „Modelle & Profile“ lädt beim Anbieterwechsel den tatsächlichen Katalog mit dem konfigurierten Schlüssel oder lokalen Endpunkt. Die Textprüfung verwendet eine synthetische JSON-Anfrage. FAU nutzt `/models` mit `LLMAPI_KEY`, Ollama `GET /api/tags`. OpenAI, Anthropic, Gemini, Groq, Mistral, NVIDIA und konfigurierte OpenAI-kompatible Endpunkte nutzen ihre jeweiligen Modelllisten. Freie Kennungen bleiben bearbeitbar. Eine Verzeichnisantwort belegt Modellangebote. Die Bildfähigkeit wird getrennt geprüft. [Live-Abnahme](R18C_GESAMTANALYSE.md) · [Ollama-Katalog-API](https://docs.ollama.com/api/tags)

Die Vision-Vorschau prüft verfügbare Anbieterinformationen, Endpunkt und Schlüsselverfügbarkeit. Ein manueller Versuch bei unbekannter Bildfähigkeit bleibt nach ausdrücklicher Pixelfreigabe möglich. Die automatische Konvertierungsanreicherung zeigt einen offenen Schritt, wenn die Bildfähigkeit unbekannt bleibt. Bildklassifizierung und lokale Diagrammextraktion verwenden ihre Docling-Modelle. Der Abschluss prüft tatsächliche Pixel, Bildmetadaten und Beschreibungen. [R18c-Abnahme](R18C_ACCEPTANCE.md)

## R30-Ergänzungen: Multimodale Open-Weights, Live-Vision-Probe & Ehrliche Tarifanzeige

- **Multimodale Modell-Erkennung (`models._infer_open_multimodal`)**: Aktuelle Open-Weight-Familien auf akademischen Gateways wie NHR@FAU (`Qwen/Qwen3.6-35B-A3B-FP8`, `google/gemma-4-*`, `RedHatAI/Mistral-Small-3.2-*`, `moonshotai/Kimi-K2.5`/`K2.6`, `Pixtral`, `Llama-4`) werden im Live-Katalog als `Multimodal (Text+Vision)` gekennzeichnet, sodass dasselbe Profil nahtlos für Textstufen (A/B/C) und Vision genutzt werden kann.
- **Aktive Vision-Probe (`POST /api/vision-probe`)**: Über „Vision testen“ sendet das Studio ein minimales synthetisches `1×1`-PNG an den gewählten Endpunkt und speichert das reale Testergebnis im Workspace (`verified_vision_models`), ohne Studienpixel zu übertragen.
- **Null fiktive API-Preise (`telemetry._estimate_cost`)**: Lokale und akademische Endpunkte (`nhr_fau`, `ollama`, `vllm`, `lm_studio`) werden ehrlich mit `0,00 € / 0,00 $` berechnet. Für kommerzielle Anbieter werden Preise ausschließlich dann berechnet, wenn ein verifizierter Tarif in `litellm.model_cost` hinterlegt ist (inklusive `cached_tokens`-Rabatt und `reasoning_tokens`-Ausweis); nicht gelistete Modelle zeigen transparent `Kein Tarif` (`null`) statt geschätzter Pauschalwerte.
