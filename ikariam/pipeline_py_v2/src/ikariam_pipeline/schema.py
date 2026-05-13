"""Column-level documentation for the canonical Lance output tables.

Raw MariaDB table/column names stay upstream. The public tables documented
here use readable lower_snake_case names. The raw database table is named
`avatar`; public outputs call that same entity `player`.
"""

from __future__ import annotations

PLAYER_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier, e.g. de_1311_14", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "registered_at_unix": {"description": "Player registration time", "unit": "unix_seconds"},
    "registered_at": {"description": "Player registration time as string", "unit": "datetime"},
    "gold": {"description": "Gold held by the player at this snapshot", "unit": "gold"},
    "research_points": {"description": "Research points accumulated", "unit": "points"},
    "government_form": {"description": "Government form enum from the raw avatar table", "unit": "enum"},
    "gender": {"description": "Gender flag from the raw avatar table", "unit": "enum"},
    "account_age_days": {"description": "Account age at reference timestamp", "unit": "days"},
    "account_age_adjustment_factor": {
        "description": "Resource adjustment factor derived from account age",
        "unit": "ratio",
    },
    "island_count": {"description": "Distinct islands where this player has cities", "unit": "count"},
    "city_count": {"description": "Total cities owned by this player", "unit": "count"},
    "population_total": {"description": "Total population across this player's cities", "unit": "count"},
    "wood_in_buildings": {"description": "Wood invested in buildings", "unit": "wood"},
    "crystal_in_buildings": {"description": "Crystal invested in buildings", "unit": "crystal"},
    "marble_in_buildings": {"description": "Marble invested in buildings", "unit": "marble"},
    "sulfur_in_buildings": {"description": "Sulfur invested in buildings", "unit": "sulfur"},
    "wine_in_buildings": {"description": "Wine invested in buildings", "unit": "wine"},
    "resources_in_buildings_total": {"description": "All resources invested in buildings", "unit": "sum"},
    "building_resource_score": {
        "description": "Legacy Baumeister_Highscore resource total",
        "unit": "sum",
    },
    "resources_stored_total": {"description": "All resources currently stored", "unit": "sum"},
    "resources_in_buildings_and_storage_total": {
        "description": "Built plus stored resource total",
        "unit": "sum",
    },
    "building_levels_total": {"description": "Sum of all building levels", "unit": "sum_levels"},
    "wonder_donations_total": {"description": "Donations to wonders", "unit": "gold"},
    "sawmill_donations_total": {"description": "Donations to sawmills", "unit": "gold"},
    "luxury_mine_donations_total": {"description": "Donations to luxury mines", "unit": "gold"},
    "donations_total": {"description": "All donations", "unit": "gold"},
    "wonder_and_luxury_mine_donations_total": {
        "description": "Wonder plus luxury mine donations",
        "unit": "gold",
    },
}


PLAYER_ISLAND_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "island_id": {"description": "SHA1 of the island", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "player_city_count_on_island": {
        "description": "Cities this player has on this island",
        "unit": "count",
    },
    "population_total": {"description": "Population in this player's cities here", "unit": "count"},
    "wood_in_buildings": {"description": "Wood invested in buildings here", "unit": "wood"},
    "resources_in_buildings_total": {"description": "All resources invested here", "unit": "sum"},
    "building_resource_score": {
        "description": "Legacy Baumeister_Highscore resource total here",
        "unit": "sum",
    },
    "resources_stored_total": {"description": "Stored resources here", "unit": "sum"},
    "resources_in_buildings_and_storage_total": {
        "description": "Built plus stored resources here",
        "unit": "sum",
    },
    "building_levels_total": {"description": "Sum of building levels here", "unit": "sum_levels"},
    "wonder_donations_total": {"description": "Wonder donations here", "unit": "gold"},
    "sawmill_donations_total": {"description": "Sawmill donations here", "unit": "gold"},
    "luxury_mine_donations_total": {"description": "Luxury mine donations here", "unit": "gold"},
    "donations_total": {"description": "All donations here", "unit": "gold"},
    "wonder_type_id": {"description": "Wonder type id on this island", "unit": "enum"},
    "luxury_resource_type": {
        "description": "Luxury resource type: 1=wine, 2=marble, 3=crystal, 4=sulfur",
        "unit": "enum",
    },
    "luxury_mine_level": {"description": "Luxury mine level", "unit": "level"},
    "sawmill_level": {"description": "Sawmill level", "unit": "level"},
    "island_city_count": {"description": "Raw total cities on the island", "unit": "count"},
}


ISLAND_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "island_id": {"description": "SHA1 of the island", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "island_snapshot_key": {"description": "island_id + '_' + snapshot_id", "unit": "id"},
    "wonder_type_id": {"description": "Wonder type id", "unit": "enum"},
    "wonder_level": {"description": "Wonder level", "unit": "level"},
    "wonder_belief": {"description": "Wonder belief points", "unit": "points"},
    "luxury_resource_type": {
        "description": "Luxury resource type: 1=wine, 2=marble, 3=crystal, 4=sulfur",
        "unit": "enum",
    },
    "luxury_mine_level": {"description": "Luxury mine level", "unit": "level"},
    "sawmill_level": {"description": "Sawmill level", "unit": "level"},
    "raw_city_count": {"description": "Raw city_count field from the island table", "unit": "count"},
    "sawmill_donated_cumulative": {"description": "Cumulative sawmill donations", "unit": "gold"},
    "luxury_mine_donated_cumulative": {
        "description": "Cumulative luxury mine donations",
        "unit": "gold",
    },
    "wonder_donated_cumulative": {"description": "Cumulative wonder donations", "unit": "gold"},
    "sawmill_next_level_cost": {"description": "Cost for next sawmill level", "unit": "gold"},
    "luxury_mine_next_level_cost": {
        "description": "Cost for next luxury mine level",
        "unit": "gold",
    },
    "wonder_next_level_cost": {"description": "Cost for next wonder level", "unit": "gold"},
    "sawmill_next_level_remaining_cost": {
        "description": "Remaining donations needed for next sawmill level",
        "unit": "gold",
    },
    "luxury_mine_next_level_remaining_cost": {
        "description": "Remaining donations needed for next luxury mine level",
        "unit": "gold",
    },
    "wonder_next_level_remaining_cost": {
        "description": "Remaining donations needed for next wonder level",
        "unit": "gold",
    },
    "player_count": {"description": "Distinct players on this island", "unit": "count"},
    "city_count": {"description": "Computed total cities on this island", "unit": "count"},
    "population_total": {"description": "Total population across players", "unit": "count"},
    "wood_in_buildings": {"description": "Wood invested by all players", "unit": "wood"},
    "resources_in_buildings_total": {
        "description": "All building resources invested by all players",
        "unit": "sum",
    },
    "building_resource_score": {
        "description": "Legacy Baumeister_Highscore resource total across players",
        "unit": "sum",
    },
    "resources_stored_total": {"description": "Stored resources across players", "unit": "sum"},
    "resources_in_buildings_and_storage_total": {
        "description": "Built plus stored resources across players",
        "unit": "sum",
    },
    "building_levels_total": {"description": "Sum of building levels across players", "unit": "sum_levels"},
    "avg_population_per_player": {"description": "Average population per player", "unit": "count"},
    "avg_building_resource_score_per_player": {
        "description": "Average building resource score per player",
        "unit": "sum",
    },
    "donating_player_count": {"description": "Players with donations at this snapshot", "unit": "count"},
    "wonder_donations_total": {"description": "Wonder donations", "unit": "gold"},
    "sawmill_donations_total": {"description": "Sawmill donations", "unit": "gold"},
    "luxury_mine_donations_total": {"description": "Luxury mine donations", "unit": "gold"},
    "donations_total": {"description": "All donations", "unit": "gold"},
    "avg_donations_per_player": {"description": "Average donations per player", "unit": "gold"},
    "donating_player_share_pct": {"description": "Donating players / players", "unit": "percent"},
}


SUMMARY_DOCS: dict[str, dict[str, str]] = {
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "island_id": {"description": "SHA1 of the island", "unit": "id"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "snapshots_observed_count": {
        "description": "Distinct snapshots where the entity appears",
        "unit": "count",
    },
    "first_snapshot_date": {"description": "Earliest snapshot date", "unit": "date"},
    "last_snapshot_date": {"description": "Latest snapshot date", "unit": "date"},
    "observation_span_days": {
        "description": "Days between first and last observed snapshots",
        "unit": "days",
    },
    "registered_at_unix": {"description": "Player registration time", "unit": "unix_seconds"},
    "player_city_observation_count": {
        "description": "Sum of player_city_count_on_island across snapshots",
        "unit": "count",
    },
}


TABLE_DOCS: dict[str, dict[str, dict[str, str]]] = {
    "player_snapshot": PLAYER_SNAPSHOT_DOCS,
    "player_island_snapshot": PLAYER_ISLAND_SNAPSHOT_DOCS,
    "island_snapshot": ISLAND_SNAPSHOT_DOCS,
    "player_latest": PLAYER_SNAPSHOT_DOCS,
    "player_island_latest": PLAYER_ISLAND_SNAPSHOT_DOCS,
    "island_latest": ISLAND_SNAPSHOT_DOCS,
    "player_summary": SUMMARY_DOCS,
    "player_island_summary": SUMMARY_DOCS,
    "island_summary": SUMMARY_DOCS,
}


TABLE_DESCRIPTIONS: dict[str, str] = {
    "player_snapshot": (
        "One row per (player, snapshot). Aggregates each player's city and "
        "donation state for a weekly snapshot."
    ),
    "player_island_snapshot": (
        "One row per (player, island, snapshot) where the player had at least "
        "one city on that island."
    ),
    "island_snapshot": (
        "One row per (island, snapshot). Includes island state, upgrade "
        "metrics, and player/city/donation aggregates."
    ),
    "player_latest": "Latest player_snapshot row per player.",
    "player_island_latest": (
        "Latest player_island_snapshot row per player-island pair, with island "
        "metadata from the island's latest snapshot."
    ),
    "island_latest": "Latest island_snapshot row per island.",
    "player_summary": "Cross-snapshot summary per player.",
    "player_island_summary": "Cross-snapshot summary per player-island pair.",
    "island_summary": "Cross-snapshot summary per island.",
}
