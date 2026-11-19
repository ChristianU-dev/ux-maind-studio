# ADR-0029 · Versionsgebundene Evidenz mit einem Erstextraktionsvertrag

Historische R16-Entscheidung. Die Extraktionssteuerung wurde in [ADR-0030](ADR-0030-native-graph.md) ersetzt. Quellenbindung und Historie bleiben erhalten.

R16 übernimmt freie native Konvertierung, Anzeige, Profile und Fachentscheidungen aus R15. Im ersten Modellaufruf werden quellennahe Beobachtungen erfasst. Bewertung und Finding-Synthese folgen in getrennten Arbeitsschritten.

Die native Gegenprobe verwendete denselben Referenzentwurf und denselben kurzen synthetischen Inhalt mit Ollama `qwen2.5:7b`. Direct mit `use_chunking=True` bot den Inhalt als Ganzdokument an und lieferte drei Beobachtungen und eine Relation in zwei Aufrufen. Dense verwendete fünf Aufrufe für Skeleton und Fill. Es gab eine Beobachtung, keine Relation und einen Text als Messwert aus. Direct-Graphprojektion der Referenz enthält Containerkanten. Für fachliche Endpunkte verwendet die Anwendung stattdessen validierte Beobachtungsreferenzen in der nativen GraphConverter-Projektion. Der Versuch belegt ein Verhalten am Testfall.

Die Anwendung übermittelt separat gepackte, native Quellenrecords über `LiteLLMClient.get_json_response`. Dadurch können Rohantwort und Eingabeumfang je Aufruf geprüft werden und die Hostvalidierung behält gültige Geschwister. Die Graph-Backendvalidierung würde Daten teilweise ergänzen oder bereinigen. Tabellenrecords gehen direkt über native Zellen, da der geprüfte native OTSL-Serializer ein vollständiges Grid anlegt.

Die native Vision-Verarbeitung kann zusätzlich über das Docling-JSON-Backend laufen. Basis und Ergebnis sind durch Inhaltshashes gebunden und vorhandene Ref-Struktur wird geprüft. Ein optionaler Anbieter erhält ausdrücklich gewählte Pixel. Bildbeschreibungen und Chartdaten bleiben abgeleitete Inhalte.

Nachweis und offene Fälle stehen in [Abnahme](../ACCEPTANCE_R16.md). Der Ausgangsstand und die entfernten Teile stehen unter [Rückbau](../R16_RUECKBAU.md).
