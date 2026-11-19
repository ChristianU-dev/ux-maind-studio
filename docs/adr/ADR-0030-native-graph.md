# ADR-0030 · Native Docling-Graph-Steuerung und gestufte UX-Evidenz

R17 ersetzt die Erstextraktionsentscheidung in [ADR-0029](ADR-0029-versioned-evidence.md). Docling Graph 1.9.2 verarbeitet bereits gespeicherte DoclingDocument-JSONs über `PipelineConfig` und `run_pipeline`. A strukturiert quellennahe Beobachtungen. B und C formen belegbezogene Beziehungen und überprüfbare Finding-Hypothesen aus Beobachtungen und Entscheidungen. Die zweite fachliche Aktion nutzt dieselbe Bibliothekspipeline.

`ux_maind/app/extraction.py` ist gelöscht. Damit entfallen `segments()`, `packet_records()`, Alias- und Paketgenerierung, die appseitige Tokenplanung, der selbst gesteuerte Clientaufruf sowie die erneute JSON-Aufbereitung. `evidence.validate_batch()` und der Laufzeitbestand künstlicher Quellenaliasse sind entfernt. Citations lösen die konkret benötigten Textspans, Zellen oder Bilder mit nativen Elementreferenzen auf. Die bestehende `GraphConverter`-Projektion des Forschungsgraphs behält menschliche Entscheidungen und Belegnavigation.

Die Entscheidung gilt mit den empirischen Grenzen aus den [R17-Versuchen](../ACCEPTANCE.md). Insbesondere sind native Dense-Ausgaben, die Bindung bei wiederholten Textstellen und XLSX-Semantik jeweils eigenständig zu prüfen. Historische [R16-Abnahme](../ACCEPTANCE_R16.md) und [R16-Rückbau](../R16_RUECKBAU.md) bleiben erhalten.
