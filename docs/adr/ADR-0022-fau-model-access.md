# ADR0022 · Fester NHR@FAU-Zugang im vorhandenen Transport

Status: angenommen am12.11.2026 für R9, Basis8720462, Implementierung e9426c6.

Problem: Hochschulzugang nutzen, Originalmodellkennung und Anbieterherkunft erhalten, ohne neue Modellplattform oder Forschungsdatenfreigabe. Offene Modelle bleiben ein eigenständiger Weg.

Alternativen: eigener HTTP-/SDKadapter (verworfen: zweiter Transport), beliebige OpenAI-kompatible URL (verworfen: unnötige allgemeine Oberfläche/Schlüsselrouting), Übernahme von Hersteller-Metadaten (verworfen: kein Gatewaynachweis). Entscheidung: genau nhr_fau in bestehendem Settings/Profile/ENV/DPAPI/Freigabepfad, native LiteLLM-openai-Route mit festem api_base, Originalmodell im Wirebody und expliziter NHR-Herkunft im bestehenden Aufrufprotokoll. Keine Runtime-/Versionänderung und kein Fallback.

Risiken: unbekannte Gatewayfähigkeiten/Quoten und unzuverlässiges Prompt-JSON. Deshalb keine erfundenen Metadaten, kein automatischer Reparaturaufruf, response_format/Reasoning nicht gesendet, produktive Vision unbekannt/blockiert. Host8192/Defaultoutput1024 sind Appgrenzen, keine Serverzusagen. Fehlender Schlüssel/fremde Basis werden vor Dispatch abgewiesen.

Abnahme/negative Befunde:17/17 betroffene Offlinechecks, danach26/26 aktuelle Produktchecks. Fünf neue synthetische FAU-Requests, gpt-oss technisch erfolgreich mit belegten Kontexten/Messwert, fachliche Negations-/Klassifikationskonsistenz PARTIAL. Qwen-Smoke ungültiges JSON; Bildtext richtig, Markdownzaun verletzt PictureReading. Keine Ersatzpipeline oder Antwortrettung. Quelle/Prompt/Schema/Tokenzeiten/Rohartefakte und nicht geprüfte Fähigkeiten kanonisch in [MODEL_ACCESS](../MODEL_ACCESS.md), Ausführung/CI in [ACCEPTANCE](../ACCEPTANCE.md). Kein echter menschlicher Review, keine reale Forschungsdatenfreigabe. Weitere Forschung benötigt neuen Auftrag.
