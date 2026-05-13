# Python vs SQL gold-standard audit

Column-by-column diff between `pipeline_py/output/*.csv` and
`pipeline_py/sql_gold_standard/*.csv`. The SQL outputs are the
authoritative reference.

Tolerance: `1e-06` (absolute). Comparison restricted to rows
where SQL has a non-null value — SQL's A_DS/I_DS have NULL shells for
entities absent from the seeded snapshot (snapshot 36), so only the
subset with real data can be compared.

## A_DS.csv

- SQL rows: **21829**, cols: 136
- Python rows: **21822**, cols: 31
- Common keys: **21822**
- Python-only keys: 0, SQL-only keys: 7

Mapped columns: 22 / 31

Unmapped Python columns: Don_Luxus_Ges, days_observed, duration_adjustment, first_seen, gender, last_seen, research_points, total_cities, total_islands

| Py column | SQL column | compared | matching | nonmatching | SQL nulls | max\|Δ\| | mean\|Δ\| |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ✅ `Anzahl_vorhanden` | `t_Anzahl_vorhanden` | 21822 | 21822 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `registration_time` | `a_registration_time` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Registration_time_normal` | `a_Registration_time_normal` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `gold` | `a_gold` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `formOfGovernment` | `a_formOfGovernment` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Spieldauer` | `a_Spieldauer` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Buerger_Ges` | `c_Buerger_Ges` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Holz_verbaut` | `c_Holz_verbaut` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Kristall_verbaut` | `c_Kristall_verbaut` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Stein_verbaut` | `c_Stein_verbaut` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Schwefel_verbaut` | `c_Schwefel_verbaut` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Wein_verbaut` | `c_Wein_verbaut` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_verbaut` | `c_Res_Ges_verbaut` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Baumeister_Highscore` | `c_Baumeister_Highscore` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_lagernd` | `c_Res_Ges_lagernd` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_verb_lag` | `c_Res_Ges_verb_lag` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Geblev` | `c_Geblev` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Don_Wonder_Ges` | `d_Don_Wonder_Ges` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Don_Saegewerk_Ges` | `d_Don_Saegewerk_Ges` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Don_Luxusminen_Ges` | `d_DonH_Luxusminen_Ges` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |
| ✅ `Don_Ges` | `d_Don_Ges` | 548 | 548 | 0 | 21274 | 0.0000 | 0.0000 |

## AVI_DS.csv

- SQL rows: **41086**, cols: 159
- Python rows: **41079**, cols: 32
- Common keys: **41079**
- Python-only keys: 0, SQL-only keys: 7

Mapped columns: 21 / 32

Unmapped Python columns: Anzahl_Teilnahme, cities_on_island, first_seen, gender, island_city_count, last_seen, latest_snapshot_date, latest_snapshot_id, research_points, snapshots_present, wonder_type_id

| Py column | SQL column | compared | matching | nonmatching | SQL nulls | max\|Δ\| | mean\|Δ\| |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ✅ `Cities_Vorhanden` | `m_Cities_vorhanden` | 41079 | 41079 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `registration_time` | `a_registration_time` | 3124 | 3124 | 0 | 37955 | 0.0000 | 0.0000 |
| ✅ `gold` | `a_gold` | 3124 | 3124 | 0 | 37955 | 0.0000 | 0.0000 |
| ✅ `formOfGovernment` | `a_formOfGovernment` | 3124 | 3124 | 0 | 37955 | 0.0000 | 0.0000 |
| ✅ `Spieldauer` | `a_Spieldauer` | 3124 | 3124 | 0 | 37955 | 0.0000 | 0.0000 |
| ✅ `Buerger_Ges` | `c_Buerger_Ges` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Holz_verbaut` | `c_Holz_verbaut` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_verbaut` | `c_Res_Ges_verbaut` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Baumeister_Highscore` | `c_Baumeister_Highscore` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_lagernd` | `c_Res_Ges_lagernd` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_verb_lag` | `c_Res_Ges_verb_lag` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Geblev` | `c_Geblev` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Don_Wonder_Ges` | `d_Don_Wonder_Ges` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Don_Saegewerk_Ges` | `d_Don_Saegewerk_Ges` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Don_Luxusminen_Ges` | `d_DonH_Luxusminen_Ges` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `Don_Ges` | `d_Don_Ges` | 2516 | 2516 | 0 | 38563 | 0.0000 | 0.0000 |
| ✅ `tradegood` | `i_tradegood` | 41079 | 41079 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `tradegood_level` | `i_tradegood_level` | 41079 | 41079 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `resource_level` | `i_resource_level` | 41079 | 41079 | 0 | 0 | 0.0000 | 0.0000 |

## I_DS.csv

- SQL rows: **5351**, cols: 148
- Python rows: **5351**, cols: 52
- Common keys: **5351**
- Python-only keys: 0, SQL-only keys: 0

Mapped columns: 20 / 52

Unmapped Python columns: Avg_Baumeister_per_player, Avg_Buerger_per_player, Avg_Don_per_player, Sub_Noetig_nextlev_resource, Sub_Noetig_nextlev_tradegood, Sub_Noetig_nextlev_wonder, avg_baumeister_per_player, avg_citizens_per_player, avg_donation_per_city, avg_donation_per_player, calc_city_count, city_count, cost_Nextlev_resource, cost_Nextlev_tradegood, cost_Nextlev_wonder, country, donating_players, donation_participation_rate, island_snapshot_key, snapshot_date, snapshot_id, total_baumeister, total_cities, total_citizens, total_donations, total_holz_verbaut, total_luxury_donations, total_players, total_sawmill_donations, total_wonder_donations, unique_players, wonder_type_id

| Py column | SQL column | compared | matching | nonmatching | SQL nulls | max\|Δ\| | mean\|Δ\| |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ✅ `tradegood` | `i_tradegood` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `tradegood_level` | `i_tradegood_level` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `resource_level` | `i_resource_level` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `resource_donated` | `i_resource_donated` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `tradegood_donated` | `i_tradegood_donated` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `wonder_donated` | `i_wonder_donated` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `wonder_level` | `i_wonder_level` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `wonder_belief` | `i_wonder_belief` | 5351 | 5351 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `Buerger_Ges` | `c_Buerger_Ges` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Holz_verbaut` | `c_Holz_verbaut` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_verbaut` | `c_Res_Ges_verbaut` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Baumeister_Highscore` | `c_Baumeister_Highscore` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_lagernd` | `c_Res_Ges_lagernd` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Res_Ges_verb_lag` | `c_Res_Ges_verb_lag` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Geblev` | `c_Geblev` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Don_Wonder_Ges` | `d_Don_Wonder_Ges` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Don_Saegewerk_Ges` | `d_Don_Saegewerk_Ges` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Don_Luxusminen_Ges` | `d_DonH_Luxusminen_Ges` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |
| ✅ `Don_Ges` | `d_Don_Ges` | 936 | 936 | 0 | 4415 | 0.0000 | 0.0000 |

## Teilnahme_AV.csv

- SQL rows: **21829**, cols: 3
- Python rows: **21822**, cols: 5
- Common keys: **21822**
- Python-only keys: 0, SQL-only keys: 7

Mapped columns: 2 / 5

Unmapped Python columns: days_observed, first_seen, last_seen

| Py column | SQL column | compared | matching | nonmatching | SQL nulls | max\|Δ\| | mean\|Δ\| |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ✅ `Anzahl_vorhanden` | `Anzahl_Vorhanden` | 21822 | 21822 | 0 | 0 | 0.0000 | 0.0000 |

## Master_Avi.csv

- SQL rows: **41086**, cols: 4
- Python rows: **41079**, cols: 7
- Common keys: **41079**
- Python-only keys: 0, SQL-only keys: 7

Mapped columns: 4 / 7

Unmapped Python columns: first_seen, last_seen, snapshots_present

| Py column | SQL column | compared | matching | nonmatching | SQL nulls | max\|Δ\| | mean\|Δ\| |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ✅ `Cities_Vorhanden` | `Cities_Vorhanden` | 41079 | 41079 | 0 | 0 | 0.0000 | 0.0000 |
| ✅ `Anzahl_Teilnahme` | `Anzahl_Teilnahme` | 41079 | 41079 | 0 | 0 | 0.0000 | 0.0000 |