# Dashboard-Architektur

## Überblick

Das Dashboard ist eine Streamlit-Anwendung. `app.py` konfiguriert die App und
registriert die Seiten. Die Seiteneinstiegspunkte in `app_pages/` delegieren an
Funktionen im Python-Paket `taxi_dashboard/`.

```text
app.py
  └── app_pages/                 Streamlit-Seiteneinstiegspunkte
        └── taxi_dashboard/      Datenzugriff, Aufbereitung und Darstellung
              ├── config.py      Gemeinsame Konfiguration
              ├── data/          Databricks-Zugriff
              └── analysis/      Stundenübersicht und Wetteranalyse
```

## Schichten und Zuständigkeiten

### Anwendungseinstieg: `app.py`

- Setzt Seitentitel, Symbol und Layout.
- Definiert die Navigation mit `st.navigation`.
- Führt die ausgewählte Seite aus.

Neue Dashboard-Seiten werden hier registriert und erhalten einen eigenen
Einstiegspunkt in `app_pages/`.

### Seiten: `app_pages/`

Die Dateien in diesem Ordner sind dünne Streamlit-Einstiegspunkte. Sie importieren
die zuständige Render-Funktion und rufen sie auf. Datenzugriff und Berechnungen
sollten nicht hier ergänzt werden.

### Konfiguration: `taxi_dashboard/config.py`

Enthält gemeinsam genutzte Werte wie die Warehouse-ID, Tabellennamen und
Diagramm-Farbgruppen. Neue gemeinsame Konfigurationswerte gehören hierher,
anstatt sie mehrfach in einzelnen Seiten zu definieren.

### Datenzugriff: `taxi_dashboard/data/`

`data/databricks.py` stellt gemeinsame Funktionen für die Databricks-SQL-Abfragen
bereit:

- `query_table(...)` führt die Abfrage aus, prüft Fehler und erwartete Spalten
  und liefert ein `pandas.DataFrame`.
- `normalize_boolean(...)` vereinheitlicht Boolean-Werte, die aus Databricks
  zurückkommen.

Die Abfrageergebnisse werden von den Seiten mit `st.cache_data` zeitlich begrenzt
gecached. Aktuell beträgt die Cache-Dauer fünf Minuten.

### Analyse und Darstellung: `taxi_dashboard/analysis/`

`analysis/hourly.py` enthält den Datenlade-, Aufbereitungs-, Berechnungs- und
Streamlit-Darstellungscode für die Stundenübersicht. Die Berechnungen
`peak_label(...)` und `weighted_trip_average(...)` sind dort ebenfalls definiert.

`analysis/weather.py` lädt die Dev-Gold-Tabellen
`taxi_dev.gold.mobility_daily_comparison` und
`taxi_dev.gold.mobility_hourly_comparison`. Sie enthalten Taxi-, Bike- und
Wetterkennzahlen und ermöglichen den Vergleich der Mobilitätsarten mit
Temperatur und Niederschlag.

Diese Schicht ist noch nicht vollständig in Analyse und Darstellung getrennt:
Die Datei nutzt Streamlit und Plotly direkt. Reine Berechnungen sollten bei
Bedarf in Streamlit-unabhängige Funktionen verschoben werden, damit sie leichter
zu testen und wiederzuverwenden sind.

## Datenfluss

1. `app.py` zeigt die Navigation und führt die gewählte Seite aus.
2. Ein Einstiegspunkt in `app_pages/` ruft die Render-Funktion auf.
3. Die Render-Funktion lädt Daten über eine gecachte Ladefunktion.
4. Der gemeinsame Datenzugriff fragt Databricks ab und prüft die Antwort.
5. Die Seitenlogik konvertiert Datentypen, berechnet Kennzahlen und rendert
   Streamlit-Komponenten und Plotly-Diagramme.

## Aktueller Stand und nächste sinnvolle Schritte

- **Berechnungen von der UI trennen:** Aggregationen und KPI-Berechnungen sollten
  schrittweise von den `st.*`-Aufrufen getrennt werden.
- **Tests ergänzen:** Reine Umwandlungs- und Berechnungsfunktionen eignen sich für
  Unit-Tests. Datenzugriffsfehler und leere Ergebnisse sollten ebenfalls
  abgedeckt werden.
- **Typen vervollständigen:** Öffentliche Lade- und Analysefunktionen sollten
  klare Parameter- und Rückgabetypen erhalten.

Diese Schritte können inkrementell umgesetzt werden. Bestehende Seiten sollten
weiterhin über ihre `app_pages/`-Einstiegspunkte gestartet werden.
