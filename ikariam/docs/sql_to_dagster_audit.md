# SQL to Dagster Audit

This audit maps the legacy `Alle_Queries_DE_hintereinander.sql` workflow to the
current Dagster pipeline under `src/ikariam`. It is intentionally conservative:
only behavior with a clear implementation path is marked as matched.

Status values:

- `matched`: the current pipeline implements the same behavior or the verifier
  can reconstruct the legacy output from current LanceDB tables.
- `intentional_change`: the current public model uses different names, grain,
  or materialization but preserves the underlying information.
- `missing`: no current equivalent was found.
- `needs_investigation`: the SQL is ambiguous or the current equivalent needs a
  closer value-level audit.

| SQL section | Legacy output or behavior | Current Dagster location | Status | Notes |
| --- | --- | --- | --- | --- |
| Q3 `Spieldauer` | Adds account age from reference timestamp `1415923200 - registration_time` | `src/ikariam/pipeline/transforms/player_duration.py::enrich_avatars` | intentional_change | The pipeline computes seconds internally and exposes `account_age_days`; duration adjustment still uses seconds via `duration_adjustment_expr`. |
| Q4-Q5 `Teilnahme_AV` | Counts player appearances across DE snapshot databases | Reconstructed in `src/ikariam/pipeline/verification.py::build_teilnahme_av` from `raw_avatar_de` | matched | Not materialized by Dagster as a public table; verifier compares it directly to `Teilnahme_AV.csv`. |
| Q6-Q7 `Master_Avi` | Counts city appearances by `(owner_id, island_id)` and joins participation count | Reconstructed in `src/ikariam/pipeline/verification.py::build_master_avi` from `raw_city_de` plus `Teilnahme_AV` | matched | Not materialized by Dagster as a public table; verifier compares it directly to `Master_Avi.csv`. |
| Q8-Q13 city building-cost enrichment | Adds building cost columns for each building type and level | `src/ikariam/pipeline/transforms/building_costs.py::join_building_costs` | matched | Current pipeline uses `data/building_costs.csv` rather than thousands of literal SQL `UPDATE` statements. |
| Q14 city building totals | Computes built resources and `Baumeister_Highscore` | `src/ikariam/pipeline/transforms/city_metrics.py::compute_city_metrics` | matched | Current public names are lower snake case, e.g. `wood_in_buildings` and `building_resource_score`. |
| Q15 account-age resource adjustment | Applies duration-band factors to built resources | `src/ikariam/pipeline/transforms/city_metrics.py::compute_city_metrics`; `src/ikariam/pipeline/utils.py::duration_adjustment_expr` | matched | Existing tests pin the strict SQL boundary behavior. |
| Q16 city totals and population | Computes stored resources, built-plus-stored resources, population, workers, and building levels | `src/ikariam/pipeline/transforms/city_metrics.py::compute_city_metrics` | matched | The verifier maps the core resource and population totals to legacy `c_*` columns. |
| Q17-Q18 player-island city aggregation | Aggregates city rows to `(owner_id, island_id)` | `src/ikariam/pipeline/transforms/city_agg.py::aggregate_to_player_island` | intentional_change | Current pipeline keeps canonical per-snapshot grain; verifier collapses across snapshots for `AVI_DS`. |
| Q19 zero-donation rows | Adds zero rows for player-island-snapshot combinations with cities but no donations | `src/ikariam/pipeline/transforms/donations.py::process_donations` | matched | Implemented from city keys before downstream donation aggregation. |
| Q22 wonder split | Splits wonder donations by non-matching luxury resources | `src/ikariam/pipeline/transforms/donations.py::process_donations` | matched | Current comments document the audited SQL behavior and distinguish it from the older R implementation. |
| Q29 donation filtering | Removes donations without a matching player-city island | `src/ikariam/pipeline/transforms/donations.py::process_donations` | matched | Implemented as a semi-join against player-island city keys. |
| Q30-Q33 donation ratios and peer averages | Computes many legacy donation ratios, per-duration fields, and peer-relative percentages | Core totals in `src/ikariam/pipeline/transforms/donations.py`, `islands.py`, and `higher_agg.py`; canonical analytics in `donation_analytics_player_island_snapshot`; SQL compatibility in `src/ikariam/pipeline/verification.py` | matched_for_verifier | Canonical LanceDB keeps the clean analytics table; the verifier projects legacy `d_*` names for gold CSV parity. Only database-wide donation broadcasts remain intentionally unmapped. |
| Q34 `city3AV` | Aggregates city metrics by player | `src/ikariam/pipeline/transforms/higher_agg.py::aggregate_by_avatar`; verifier collapse from `city_snapshot` | intentional_change | Current pipeline stores per-snapshot `player_snapshot`; verifier collapses mapped city totals across snapshots for `A_DS`. |
| Q35 `city4Isl` | Aggregates city metrics by island | `src/ikariam/pipeline/transforms/higher_agg.py::aggregate_by_island`; verifier collapse from `city_snapshot` | intentional_change | Current pipeline stores per-snapshot `island_snapshot`; verifier collapses mapped city totals across snapshots for `I_DS`. |
| Q36-Q43 island and donation island aggregates | Computes island costs, remaining upgrade costs, donation totals, averages, and participation | `src/ikariam/pipeline/transforms/islands.py::enrich_islands`; `src/ikariam/pipeline/transforms/higher_agg.py::donations_by_island`; SQL compatibility in `src/ikariam/pipeline/verification.py` | matched_for_verifier | The verifier reconstructs legacy island donation averages and ratios from the canonical facts for gold CSV parity. |
| Q44 `A_DS` | Final player-level legacy SQL output | Reconstructed in `src/ikariam/pipeline/verification.py::build_legacy_views` | matched_for_verifier | Stable aggregates and legacy donation rollups are mapped; only database-wide donation broadcasts remain intentionally unmapped. |
| Q45 `AVI_DS` | Final player-island legacy SQL output | Reconstructed in `src/ikariam/pipeline/verification.py::build_legacy_views` | matched_for_verifier | Backbone, city totals, row-level donation analytics, and island state are mapped; only database-wide donation broadcasts remain intentionally unmapped. |
| Q46 `I_DS` | Final island-level legacy SQL output | Reconstructed in `src/ikariam/pipeline/verification.py::build_legacy_views` | matched_for_verifier | Island state, aggregate totals, and legacy donation rollups are mapped; only database-wide donation broadcasts remain intentionally unmapped. |
| Q47 cleanup | Drops legacy SQL working tables | Not applicable | intentional_change | Dagster assets and LanceDB outputs do not use SQL working tables. |

## Formal Validation of Resolved Investigation Rows

This section is intentionally based on SQL definitions and transform definitions, not on empirical comparison output.

Decision rule:

- A current-contract problem exists only when a value is part of the documented public LanceDB model and the Dagster definition is not formally equivalent to the SQL definition.
- A legacy-compatibility gap exists when the value is needed only to recreate the old `A_DS`, `AVI_DS`, or `I_DS` CSV shape.
- A non-problem exists when the SQL selected a helper or analysis column that is not part of the current public contract and can be rebuilt in a dedicated compatibility layer if needed.

### Q30-Q33 Donation Ratios and Peer Averages

Game-rule grounding:

- Ikariam islands have one luxury good resource; wood exists separately on
  every island. See Gameforge's luxury-resource guide and the Ikariam
  resources reference.
- Miracle/wonder donations can use resources that are not produced on the
  island. With one luxury good produced locally, that leaves the other three
  luxury goods as eligible donation resources.
- The raw donation rows identify donation type and total amount, but not the
  exact luxury good used for a wonder donation. Therefore
  `wonder_*_donations_allocated` fields are an equal allocation across the
  eligible non-produced luxury goods, not observed resource-specific facts.
  This is also why the SQL compatibility names stay in the verifier as
  `d_Don_Wonder_Anteil_*`.

Formal SQL definition:

- Q30 updates `island` with post-filter city counts, per-city remaining upgrade needs, and database-wide level averages.
- Q31 updates `avatar` with total avatars per database and average `Spieldauer`.
- Q32 updates `city2` with player city/island counts and worker-share percentages.
- Q33 updates `donation2` with global donation constants, island peer averages excluding the current avatar, differences from those peer averages, per-duration ratios, donation-per-worker/person/building-level ratios, and resource-share percentages.

Current equivalent:

- Core donation totals are implemented: total, sawmill, wonder, luxury mine, and wonder-plus-luxury totals.
- Core island upgrade-cost fields are implemented from literal SQL cost tables.
- Core city/player/island counts exist in the canonical snapshot model.
- Donation analytics now have a canonical table,
  `donation_analytics_player_island_snapshot`, at `(player, island, snapshot)`
  grain. It contains row-level totals, denominators, intensity ratios,
  composition shares, and island peer averages without copying database-wide
  constants onto every row.
- The verifier now recreates the legacy `city2` count fields, the Q35/Q37 city average fields, and the Q30 island level-per-avatar fields that the final SQL aliases with a misleading `c_` prefix.
- The verifier also projects legacy row-level `donation2` columns for `AVI_DS`
  from current LanceDB facts. Database-wide broadcast constants such as
  `d_Anz_Don_per_DB` and `d_Don_pro_DB` remain intentionally unmapped.
- The verifier also projects the legacy player-level `donation3Av` and
  island-level `donation4Isl` rollups, including the SQL ratio, per-duration,
  resource-share, and average columns. These are compatibility projections,
  not canonical public columns.

Decision:

- Not a problem for the current canonical LanceDB contract. The canonical model preserves normalized facts and selected aggregates, not every historical analysis column.
- A problem only if exact legacy SQL CSV compatibility is required. In that case, create a separate compatibility projection for these columns rather than expanding the canonical public tables.
- Caveat for exact SQL compatibility: SQL computes `Sub_Noetig_nextlev_* = cost_nextlev_* - donated` directly, so negative values are possible. The current transform treats remaining cost as non-negative. That is a better semantic field name, but it is not formally identical to the SQL helper column.
- Caveat for `Anz_Staedte_pro_Insel`: SQL defines it from `COUNT(city2.id)` after player filtering. The closest public field is computed `island_snapshot.city_count`, not raw `island_snapshot.raw_city_count` or `city_snapshot.island_city_count`.

### Q44 A_DS

Formal SQL definition:

- `A_DS` groups by `t.id` and joins `Teilnahme_AV`, `city3AV`, `avatar`, `donation3AV`, and `island`.
- Stable player-level aggregate fields are the sums/averages from `city3AV` and `donation3AV`.
- Several selected fields are not functionally determined by `t.id`: raw `a_*`, `c_id`, `c_island_id`, `d_avatar_id`, `d_island_id`, and similar columns depend on which joined row MySQL chooses under permissive `GROUP BY` behavior.

Current equivalent:

- `player_snapshot` represents the canonical player-snapshot panel.
- Player-level participation, city totals, and donation totals can be projected from current tables.
- The legacy donation ratio/average family is projected in the verifier from
  `donation2` compatibility rows and current city/player context.

Decision:

- Not a problem for the current public model.
- Exact reproduction of arbitrary non-aggregated `A_DS` fields is not a good
  canonical target. The verifier intentionally emulates the observed MySQL
  representative-row behavior so the SQL gold CSV can still be audited.

### Q45 AVI_DS

Formal SQL definition:

- `AVI_DS` groups by `(m.owner_id, m.island_id)` and joins `Master_Avi`, `city2`, `avatar`, `donation2`, and `island`.
- The backbone key and core city/donation/island sums are meaningful player-island aggregates.
- Legacy donation ratios, peer averages, and raw selected helper columns are inherited from Q30-Q33.

Current equivalent:

- `city_snapshot` contains city facts plus duplicated player-island donation and island metadata for analysis convenience.
- A deterministic player-island projection can be built from current city and donation facts.
- Island cost/state fields are present, but exact SQL compatibility must use computed city counts for `Anz_Staedte_pro_Insel` and must decide how to handle the SQL-vs-canonical remaining-cost semantics.
- The verifier maps row-level legacy `donation2` analytics for `AVI_DS`,
  including the default-zero `Avg_*` columns that the SQL table defines but
  does not populate before the final player-island output.

Decision:

- Not a problem for the canonical model.
- Legacy-compatible `AVI_DS` is a separate projection concern. The current
  verifier maps all deterministic legacy columns except the two database-wide
  donation broadcast constants.

### Q46 I_DS

Formal SQL definition:

- `I_DS` groups by `i.id` and joins `island`, `city4Isl`, and `donation4Isl`.
- Island state, city aggregates, donation aggregates, costs, and remaining-cost fields are meaningful island-level aggregates.
- The donation average/ratio columns are again inherited legacy analytic fields.

Current equivalent:

- `island_snapshot` is the canonical island-snapshot table.
- It preserves island state, computed city/player aggregates, donation totals, and selected public averages.
- The verifier projects the full legacy `donation4Isl` ratio/average family
  from canonical facts for SQL gold comparison.

Decision:

- Not a problem for the canonical model.
- Exact `I_DS` compatibility is handled as a verifier projection that
  collapses the snapshot panel to the legacy grain and adds the Q30-Q43
  analysis columns. These remain verifier-only compatibility fields.

## Current Verification Boundary

The executable verifier proves parity only for mapped columns. The unmapped
columns are not ignored: each run writes per-output `*_unmapped_columns.csv`
files and summarizes unmapped coverage in `docs/lancedb_vs_sql_gold.md`.

After the formal pass above, the remaining unmapped columns are scoped and
intentional: `d_Anz_Don_per_DB` and `d_Don_pro_DB`. They are database-wide
donation broadcast constants copied onto each legacy row, not row-level
analytics in the canonical LanceDB model.

The verifier now compares the deterministic compatibility tranche
value-by-value against the SQL gold CSVs: legacy `c_*` totals, counts, city
averages, representative-row fields, island level-per-avatar aliases, row-level
`AVI_DS` `d_*` donation analytics, player-level `donation3Av` rollups, and
island-level `donation4Isl` rollups.
