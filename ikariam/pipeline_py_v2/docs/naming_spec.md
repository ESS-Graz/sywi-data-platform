# Pipeline v2 Naming Spec

Status: draft for review.

Goal: make the v2 pipeline readable without requiring knowledge of the legacy
R/SQL naming style. Legacy names should remain available only for SQL parity
tests and compatibility exports.

Terminology boundary: the raw MariaDB table is named `avatar`. In all public
derived outputs and documentation, the same entity is called `player`. Raw
input loaders and SQL-parity transform internals may still use `avatar_id`;
public tables expose it as `player_id`.

## Principles

1. Public output names use English `lower_snake_case`.
2. Names describe the grain: player, player-island, island, snapshot.
3. IDs use the base-data entity name: `player_id`, `island_id`, `snapshot_id`.
4. Dates and timestamps are explicit: `_date`, `_unix`, `_days`, `_seconds`.
5. Counts end in `_count`; percentages end in `_pct`; factors end in `_factor`.
6. Resource names are English: `wood`, `marble`, `crystal`, `sulfur`, `wine`.
7. Keep legacy German/R/SQL names only behind a compatibility boundary.
8. Comments may reference legacy query names, but function names should state
   what the step does.

## Public Table Names

| Current name | Canonical name | Grain |
| --- | --- | --- |
| `avatars` | `player_snapshot` | one row per player per snapshot |
| `avatar_islands` | `player_island_snapshot` | one row per player-island pair per snapshot |
| `islands` | `island_snapshot` | one row per island per snapshot |
| `avatars_latest` | `player_latest` | latest row per player |
| `avatar_islands_latest` | `player_island_latest` | latest row per player-island pair |
| `islands_latest` | `island_latest` | latest row per island |
| `avatars_summary` | `player_summary` | cross-snapshot player summary |
| `avatar_islands_summary` | `player_island_summary` | cross-snapshot player-island summary |
| `islands_summary` | `island_summary` | cross-snapshot island summary |

Legacy SQL table names:

| Legacy name | Meaning | Canonical replacement |
| --- | --- | --- |
| `A_DS` | player dataset | `player_latest` or `player_snapshot` |
| `AVI_DS` | player-island dataset | `player_island_latest` or `player_island_snapshot` |
| `I_DS` | island dataset | `island_latest` or `island_snapshot` |
| `Teilnahme_AV` | player participation count | `player_summary` |
| `Master_Avi` | player-island participation backbone | `player_island_summary` |

## Pipeline Step Names

| Current function/module language | Canonical name |
| --- | --- |
| `Q28_Delete_Players` | `filter_prelaunch_players` |
| `Q14_Update_City` | `calculate_city_building_cost_totals` |
| `Q15_Update_City` | `apply_account_age_resource_adjustment` |
| `Q16_Update_City` | `calculate_city_resource_and_population_totals` |
| `Q19_Create_NoDons` | `add_zero_donation_rows` |
| `Q22` wonder split | `split_wonder_donations_by_resource` |
| `Q23_Update_Island_Calc` | `calculate_island_upgrade_costs` |
| `Q29_Delete_Donations_without_city` | `filter_donations_without_city` |
| `Q45_Create_AVI` latest island join | `attach_latest_island_metadata` |
| `join_building_costs` | `add_building_costs_to_city_slots` |
| `enrich_avatars` | `add_player_tenure_metrics` |
| `compute_city_metrics` | `compute_city_snapshot_metrics` |
| `aggregate_to_player_island` | `aggregate_city_to_player_island_snapshot` |
| `process_donations` | `aggregate_player_island_donations` |
| `enrich_islands` | `add_island_upgrade_metrics` |
| `aggregate_by_avatar` | `aggregate_city_to_player_snapshot` |
| `aggregate_by_island` | `aggregate_city_to_island_snapshot` |
| `donations_by_avatar` | `aggregate_donations_to_player_snapshot` |
| `donations_by_island` | `aggregate_donations_to_island_snapshot` |
| `build_panels` | `build_snapshot_tables` |
| `build_derived` | `build_latest_and_summary_tables` |

## Column Mapping

### Keys And Time

| Current column | Canonical column |
| --- | --- |
| `id` | table-local raw id; avoid in public tables |
| `avatar_id`, `owner_id` | `player_id` |
| `island_id` | `island_id` |
| `snapshot_id` | `snapshot_id` |
| `snapshot_date` | `snapshot_date` |
| `country` | `country_code` |
| `registration_time` | `registered_at_unix` |
| `Registration_time_normal` | `registered_at` |
| `Spieldauer_seconds` | `account_age_seconds` |
| `Spieldauer` | `account_age_days` |
| `duration_adjustment` | `account_age_adjustment_factor` |
| `duration_band` | `account_age_band` |
| `n_snapshots`, `Anzahl_vorhanden`, `Anzahl_Teilnahme` | `snapshots_observed_count` |
| `first_seen` | `first_snapshot_date` |
| `last_seen` | `last_snapshot_date` |
| `days_observed` | `observation_span_days` |

### Population And Labor

| Current column | Canonical column |
| --- | --- |
| `citizens` | `idle_citizens_count` |
| `resource_workers` | `wood_workers_count` |
| `tradegood_workers` | `luxury_resource_workers_count` |
| `scientists` | `scientists_count` |
| `priests` | `priests_count` |
| `Buerger_Ges` | `population_total` |
| `Resworkers_Holz_Lux` | `resource_workers_total` |
| `Proz_resource_workers_pro_Buerger_Ges` | `wood_worker_share_pct` |
| `Proz_tradegood_workers_pro_Buerger_Ges` | `luxury_resource_worker_share_pct` |

### Buildings And Built Resources

| Current column | Canonical column |
| --- | --- |
| `p1t` ... `p17t` | `building_slot_01_type` ... `building_slot_17_type` |
| `p1l` ... `p17l` | `building_slot_01_level` ... `building_slot_17_level` |
| `g1h` ... `g17h` | `building_slot_01_wood_cost` ... `building_slot_17_wood_cost` |
| `g1q` ... `g17q` | `building_slot_01_marble_cost` ... `building_slot_17_marble_cost` |
| `g1k` ... `g17k` | `building_slot_01_crystal_cost` ... `building_slot_17_crystal_cost` |
| `g1s` ... `g17s` | `building_slot_01_sulfur_cost` ... `building_slot_17_sulfur_cost` |
| `g1w` ... `g17w` | `building_slot_01_wine_cost` ... `building_slot_17_wine_cost` |
| `Holz_verbaut` | `wood_in_buildings` |
| `Stein_verbaut` | `marble_in_buildings` |
| `Kristall_verbaut` | `crystal_in_buildings` |
| `Schwefel_verbaut` | `sulfur_in_buildings` |
| `Wein_verbaut` | `wine_in_buildings` |
| `Res_Ges_verbaut` | `resources_in_buildings_total` |
| `Baumeister_Highscore` | `building_resource_score` |
| `Geblev` | `building_levels_total` |
| `Rathauslev` | `town_hall_level` |
| `GovReslev` | `governor_residence_level` |

### Stored Resources

| Current column | Canonical column |
| --- | --- |
| `resource` | `wood_stored_raw` |
| `tradegood1` | `wine_stored_raw` |
| `tradegood2` | `marble_stored_raw` |
| `tradegood3` | `crystal_stored_raw` |
| `tradegood4` | `sulfur_stored_raw` |
| `Holz_lagernd` | `wood_stored` |
| `Stein_lagernd` | `marble_stored` |
| `Kristall_lagernd` | `crystal_stored` |
| `Schwefel_lagernd` | `sulfur_stored` |
| `Wein_lagernd` | `wine_stored` |
| `QKWS_lagernd` | `luxury_resources_stored_total` |
| `Res_Ges_lagernd` | `resources_stored_total` |
| `Holz_Ges_verb_lag` | `wood_in_buildings_and_storage` |
| `Stein_Ges_verb_lag` | `marble_in_buildings_and_storage` |
| `Kristall_Ges_verb_lag` | `crystal_in_buildings_and_storage` |
| `Schwefel_Ges_verb_lag` | `sulfur_in_buildings_and_storage` |
| `Wein_Ges_verb_lag` | `wine_in_buildings_and_storage` |
| `Res_Ges_verb_lag` | `resources_in_buildings_and_storage_total` |

### Donations

| Current column | Canonical column |
| --- | --- |
| `Don_Wonder_Ges` | `wonder_donations_total` |
| `Don_Saegewerk_Ges` | `sawmill_donations_total` |
| `Don_Luxusminen_Ges` | `luxury_mine_donations_total` |
| `Don_Ges` | `donations_total` |
| `Don_Luxus_Ges` | `wonder_and_luxury_mine_donations_total` |
| `Don_Wonder_Wein` | `wonder_donation_wine_share` |
| `Don_Wonder_Stein` | `wonder_donation_marble_share` |
| `Don_Wonder_Kristall` | `wonder_donation_crystal_share` |
| `Don_Wonder_Schwefel` | `wonder_donation_sulfur_share` |
| `Don_Luxus_Wein` | `luxury_mine_donation_wine_share` |
| `Don_Luxus_Stein` | `luxury_mine_donation_marble_share` |
| `Don_Luxus_Kristall` | `luxury_mine_donation_crystal_share` |
| `Don_Luxus_Schwefel` | `luxury_mine_donation_sulfur_share` |
| `Don_Wein_Ges` | `wine_donations_total` |
| `Don_Stein_Ges` | `marble_donations_total` |
| `Don_Kristall_Ges` | `crystal_donations_total` |
| `Don_Schwefel_Ges` | `sulfur_donations_total` |
| `Don_Wonder_Proz` | `wonder_donation_share_pct` |
| `Don_Saegewerk_Proz` | `sawmill_donation_share_pct` |
| `Don_Luxusminen_Proz` | `luxury_mine_donation_share_pct` |
| `donation_records` | `donation_record_count` |
| `donating_players` | `donating_player_count` |
| `donation_participation_rate` | `donating_player_share_pct` |

### Island State And Upgrade Metrics

| Current column | Canonical column |
| --- | --- |
| `wonder_type_id` | `wonder_type_id` |
| `wonder_level` | `wonder_level` |
| `wonder_belief` | `wonder_belief` |
| `tradegood` | `luxury_resource_type` |
| `tradegood_level` | `luxury_mine_level` |
| `resource_level` | `sawmill_level` |
| `city_count` | `raw_city_count` |
| `calc_city_count` | `city_count` |
| `island_city_count` | `island_city_count` |
| `resource_donated` | `sawmill_donated_cumulative` |
| `tradegood_donated` | `luxury_mine_donated_cumulative` |
| `wonder_donated` | `wonder_donated_cumulative` |
| `cost_Nextlev_resource` | `sawmill_next_level_cost` |
| `cost_Nextlev_tradegood` | `luxury_mine_next_level_cost` |
| `cost_Nextlev_wonder` | `wonder_next_level_cost` |
| `Sub_Noetig_nextlev_resource` | `sawmill_next_level_remaining_cost` |
| `Sub_Noetig_nextlev_tradegood` | `luxury_mine_next_level_remaining_cost` |
| `Sub_Noetig_nextlev_wonder` | `wonder_next_level_remaining_cost` |

### Aggregates

| Current column | Canonical column |
| --- | --- |
| `total_islands` | `island_count` |
| `total_cities` | `city_count` |
| `cities_on_island`, `Cities_Vorhanden` | `player_city_count_on_island` |
| `unique_players`, `total_players` | `player_count` |
| `total_citizens` | `population_total` when island-grain, otherwise avoid duplicate |
| `total_donations` | `donations_total` when island-grain, otherwise avoid duplicate |
| `Avg_Buerger_Ges` | `avg_population_per_city` |
| `Avg_Buerger_per_player` | `avg_population_per_player` |
| `Avg_Baumeister` | `avg_building_resource_score_per_island` |
| `Avg_Baumeister_per_player` | `avg_building_resource_score_per_player` |
| `Avg_Don_per_island` | `avg_donations_per_island` |
| `Avg_Don_per_player` | `avg_donations_per_player` |

## Implementation Path

1. Build canonical public tables in `final_datasets.py` by selecting and
   aliasing legacy transform columns at the output boundary.
2. Keep raw MariaDB input table/column names unchanged in `io_db.py`.
3. Keep legacy SQL/R column names inside SQL-parity transforms until each
   transform is renamed and tested in isolation.
4. Update `schema.py` metadata to document canonical names only.
5. Remove old Lance tables on each write so stale legacy names do not remain
   in `output/ikariam.lancedb`.

## Open Decisions

1. Should `Baumeister_Highscore` be exposed as `building_resource_score`,
   `builder_score`, or both with one marked legacy?
2. Should current legacy Lance tables be kept as compatibility tables during
   the transition?
