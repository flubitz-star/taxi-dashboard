# Taxi-Nachfrage nach Stunde — Dashboard-Spezifikation

> **Status:** Umgesetzt  
> **Stand:** 20. Oktober 2026
>
> Die Streamlit-Navigation befindet sich in `app.py`. Die Seite „Hourly Overview“
> liegt in `app_pages/hourly_overview.py`; ihre Dashboard-Logik liegt in
> `taxi_dashboard/hourly_overview.py`.

## 1. Ziel

Das Dashboard zeigt, wie sich die Zahl der Taxifahrten über die 24 Stunden eines
Tages verteilt. Es soll sichtbar machen, wann Nachfrage-Spitzen und -Tiefs
auftreten und wie sich die Stundenprofile zwischen Wochentagen, Wochenenden und
Monaten unterscheiden.

Die Kennzahl `trips` zählt Fahrten je Stunde. Sie misst **nicht** die Zahl
gleichzeitig benötigter oder verfügbarer Taxis. Eine belastbare Flottenplanung
benötigt zusätzlich Fahrtüberlappungen, Einsatzzeiten und ein definiertes
Auslastungsziel.

Leitfragen:

- Zu welchen Stunden ist die durchschnittliche Nachfrage an Werktagen und am
	Wochenende am höchsten?
- In welchen Stunden ist der absolute Unterschied zwischen Werktag und
	Wochenende am größten?
- Unterscheiden sich die Stundenprofile je Wochentag oder Monat?
- Zu welchen Stunden verteilen sich Fahrten und Stundenumsatz?

Erwartete Muster aus früheren Analysen sind Hypothesen, keine fest codierten
Ergebnisse. Das Dashboard berechnet alle Werte aus dem ausgewählten Zeitraum.

## 2. Datenquelle und Annahmen

| Eigenschaft | Wert |
| --- | --- |
| Tabelle | `workspace.gold.hourly_ridership` |
| Erwartete Granularität | Eine Zeile je Kalendertag und Stunde |
| Dokumentierter Umfang | Februar und August 2026, zusammen 1.416 Stunden |
| Referenzanalyse | Notebook `05_analytics_taxi_weekday`, Stundenprofil |

### Verfügbare Spalten

| Spalte | Typ | Verwendung |
| --- | --- | --- |
| `pickup_hour_ts` | TIMESTAMP | Datum und Startstunde; Stunde wird als 0 bis 23 dargestellt |
| `pickup_dayofweek` | INT | Wochentag; 1 = Sonntag bis 7 = Samstag |
| `is_weekend` | BOOLEAN | `true` für Samstag und Sonntag |
| `trips` | LONG | Fahrten in der jeweiligen Stunde |
| `total_revenue` | DOUBLE | Umsatz in der jeweiligen Stunde |
| `avg_trip_duration_min` | DOUBLE | Durchschnittliche Fahrtzeit der jeweiligen Stunde |
| `avg_passengers` | DOUBLE | Durchschnittliche Passagierzahl der jeweiligen Stunde |
| `avg_distance_miles` | DOUBLE | Durchschnittliche Distanz der jeweiligen Stunde |
| `avg_temperature_c` | DOUBLE | Wettermerkmal, nicht Teil dieses Dashboards |
| `rainy_trips` | LONG | Wettermerkmal, nicht Teil dieses Dashboards |

Vor der Auswertung prüfen: Sind `pickup_hour_ts`-Werte eindeutig und vollständig?
Enthält die Tabelle auch Stunden mit null Fahrten? Fehlende Stunden dürfen nicht
still als null Nachfrage interpretiert werden. Durchschnittswerte beziehen sich
auf vorhandene Zeilen; die Zahl der Beobachtungen soll in der Detailansicht
sichtbar sein.

## 3. Kennzahlen und Auswertungslogik

- **Stunde:** `HOUR(pickup_hour_ts)`, Wertebereich 0 bis 23.
- **Ø Fahrten pro Stunde:** `AVG(trips)` über alle vorhandenen Tagesstunden der
	gewählten Stunde und Filter. Der Wert ist ein Durchschnitt pro beobachteter
	Stunde, keine Summe über den gesamten Zeitraum.
- **Peak-Stunde:** Stunde mit dem höchsten Ø Fahrtenwert. Bei Gleichstand alle
	betreffenden Stunden anzeigen.
- **Stundenunterschied:** Ø Fahrten Werktag minus Ø Fahrten Wochenende für
	dieselbe Stunde. Die Rangfolge basiert auf dem absoluten Unterschied in
	Fahrten; Prozentwerte sind ergänzend und nur bei einem positiven Vergleichswert
	zulässig.
- **Ø Stundenumsatz:** `AVG(total_revenue)` pro beobachteter Stunde. `SUM` ist
	ungeeignet, um Stunden oder Gruppen mit unterschiedlich vielen Beobachtungen
	direkt zu vergleichen.

Alle Kennzahlen und Diagramme verwenden dieselben Monatsfilter. Für Vergleiche
zwischen Werktag und Wochenende bleiben beide Gruppen im Vergleichsdiagramm
sichtbar.

## 4. Dashboard-Elemente

### 4.1 KPI-Zeile

1. **Peak-Stunde Werktag:** Stunde mit dem höchsten Ø Fahrtenwert für
	 `is_weekend = false`.
2. **Peak-Stunde Wochenende:** Stunde mit dem höchsten Ø Fahrtenwert für
	 `is_weekend = true`.
3. **Ø Fahrten pro Stunde Werktag:** Mittelwert je vorhandener Stundenzeile.
4. **Ø Fahrten pro Stunde Wochenende:** Mittelwert je vorhandener Stundenzeile.

Zusätzlich eine kurze Insight-Zeile: Stunde mit dem größten absoluten Unterschied
zwischen Werktag und Wochenende, einschließlich beider Durchschnittswerte.

### 4.2 Stundenprofile

#### A. Nachfrage nach Stunde und Tagesart

| Eigenschaft | Definition |
| --- | --- |
| Diagramm | Liniendiagramm mit zwei Linien |
| X-Achse | Stunde 0 bis 23 |
| Y-Achse | Ø Fahrten pro beobachteter Stunde |
| Reihen | Werktag und Wochenende (`is_weekend`) |
| Zweck | Tagesverläufe direkt vergleichen und Spitzen/Tiefs erkennen |

#### B. Nachfrage-Heatmap nach Wochentag

| Eigenschaft | Definition |
| --- | --- |
| Diagramm | Heatmap |
| X-Achse | Stunde 0 bis 23 |
| Y-Achse | Wochentag, beschriftet statt als Zahl |
| Farbe | Ø Fahrten pro beobachteter Stunde |
| Zweck | Wiederkehrende Muster einzelner Wochentage erkennen |

Die Wochentagsreihenfolge wird aus `pickup_dayofweek` korrekt aufgelöst
(1 = Sonntag, 2 = Montag, …, 7 = Samstag).

#### C. Unterschied Werktag minus Wochenende

| Eigenschaft | Definition |
| --- | --- |
| Diagramm | Balkendiagramm mit Nulllinie |
| X-Achse | Stunde 0 bis 23 |
| Y-Achse | Differenz der Ø Fahrten pro Stunde |
| Interpretation | Positiv = mehr Fahrten am Werktag; negativ = mehr am Wochenende |
| Zweck | Stunden mit besonders abweichender Nachfrage hervorheben |

#### D. Stundenumsatz (ergänzend)

Zeigt den **durchschnittlichen Stundenumsatz** nach Stunde, getrennt nach
Werktag und Wochenende. Das Diagramm ist sekundär zur Fahrtennachfrage und darf
nicht als Fahrtenzahl interpretiert werden.

### 4.3 Detailtabelle

Eine Zeile je Stunde und Tagesart im ausgewählten Monat. Spalten:

| Spalte | Definition |
| --- | --- |
| Stunde | 0 bis 23 |
| Tagesart | Werktag oder Wochenende |
| Beobachtungen | Anzahl vorhandener Stundenzeilen |
| Ø Fahrten | `AVG(trips)` |
| Ø Stundenumsatz | `AVG(total_revenue)` |

Sortierung: Stunde aufsteigend, danach Tagesart. Fahrtzeit, Passagiere und
Distanz sind optionale Kennzahlen; da die Quelldaten dafür bereits Stundenmittel
enthalten, müssen sie ausdrücklich als Mittel der Stundenmittel bezeichnet
werden.

## 5. Filter und Interaktion

| Filter | Typ | Standard | Verhalten |
| --- | --- | --- | --- |
| Monat | Auswahl | Alle verfügbaren Monate | Optionen aus vorhandenen Daten, derzeit Februar 2026 und August 2026 |

Kein Standardfilter „Letzte 30 Tage“: Für den dokumentierten Datenbestand würde
dieser Zeitraum keine Zeilen liefern. Bei Auswahl „Alle verfügbaren Monate“ werden
die Monate zusammengefasst; für saisonale Unterschiede muss ein Monat einzeln
ausgewählt werden.

## 6. Datenprüfung und fachliche Grenzen

- Datenumfang vor jeder Auswertung aus der Tabelle bestimmen; keine Ergebnisse
	oder Peak-Stunden fest im Dashboard hinterlegen.
- Prüfen, ob die Anzahl der Stundenzeilen je Monat den erwarteten Kalendertagen
	mal 24 entspricht und ob doppelte Zeitstempel vorkommen.
- Fehlende Stunden nicht automatisch mit null Fahrten auffüllen. Falls die
	Tabelle keine Nullstunden enthält, müssen Kennzahlen als Mittel der
	beobachteten Stunden gekennzeichnet werden.
- Die Auswertung beschreibt Fahrtenaufkommen. Aussagen zur Zahl benötigter Taxis
	erfordern zusätzliche Annahmen oder Daten zur Dauer und Überlappung der Fahrten.
- Wettermerkmale sind nicht Bestandteil dieses Dashboards.

## 7. Farbschema

| Kategorie | Farbe | Hex |
| --- | --- | --- |
| Werktag | Blau | `#2196F3` |
| Wochenende | Orange | `#FF9800` |
| Neutral / Differenz | Dunkelgrau | `#424242` |

Die Farben kodieren ausschließlich die Tagesart, nicht den Monat. Monatsvergleiche
werden über den Monatsfilter gesteuert.
