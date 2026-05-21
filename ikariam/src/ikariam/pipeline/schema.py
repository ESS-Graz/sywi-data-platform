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


CITY_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "city_id": {"description": "SHA1 of the city", "unit": "id"},
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "island_id": {"description": "SHA1 of the island", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "is_capital": {"description": "True if the city is the player's capital", "unit": "boolean"},
    "town_hall_level": {"description": "Town hall level", "unit": "level"},
    "citizens": {"description": "Number of free citizens in the city", "unit": "count"},
    "scientists": {"description": "Number of scientists in the academy", "unit": "count"},
    "priests": {"description": "Number of priests in the temple", "unit": "count"},
    "resource_workers": {"description": "Number of workers in the sawmill", "unit": "count"},
    "tradegood_workers": {"description": "Number of workers in the luxury mine", "unit": "count"},
    "population_total": {"description": "Total population in the city", "unit": "count"},
    "wood_in_buildings": {"description": "Wood invested in buildings in this city", "unit": "wood"},
    "crystal_in_buildings": {"description": "Crystal invested in buildings in this city", "unit": "crystal"},
    "marble_in_buildings": {"description": "Marble invested in buildings in this city", "unit": "marble"},
    "sulfur_in_buildings": {"description": "Sulfur invested in buildings in this city", "unit": "sulfur"},
    "wine_in_buildings": {"description": "Wine invested in buildings in this city", "unit": "wine"},
    "resources_in_buildings_total": {"description": "Total resources invested in buildings in this city", "unit": "sum"},
    "building_resource_score": {"description": "Baumeister score of this city", "unit": "sum"},
    "wood_stored": {"description": "Stored wood in the city", "unit": "wood"},
    "crystal_stored": {"description": "Stored crystal in the city", "unit": "crystal"},
    "marble_stored": {"description": "Stored marble in the city", "unit": "marble"},
    "sulfur_stored": {"description": "Stored sulfur in the city", "unit": "sulfur"},
    "wine_stored": {"description": "Stored wine in the city", "unit": "wine"},
    "resources_stored_total": {"description": "Total stored resources in this city", "unit": "sum"},
    "wood_total": {"description": "Total wood (built + stored) in this city", "unit": "wood"},
    "crystal_total": {"description": "Total crystal (built + stored) in this city", "unit": "crystal"},
    "marble_total": {"description": "Total marble (built + stored) in this city", "unit": "marble"},
    "sulfur_total": {"description": "Total sulfur (built + stored) in this city", "unit": "sulfur"},
    "wine_total": {"description": "Total wine (built + stored) in this city", "unit": "wine"},
    "resources_in_buildings_and_storage_total": {"description": "Total resources in buildings and storage in this city", "unit": "sum"},
    "building_levels_total": {"description": "Sum of all building levels in this city", "unit": "sum_levels"},
    "wonder_donations_total": {"description": "Wonder donations of this player on this island (intentionally duplicated across cities owned by the same player on this island)", "unit": "gold"},
    "sawmill_donations_total": {"description": "Sawmill donations of this player on this island (intentionally duplicated across cities owned by the same player on this island)", "unit": "gold"},
    "luxury_mine_donations_total": {"description": "Luxury mine donations of this player on this island (intentionally duplicated across cities owned by the same player on this island)", "unit": "gold"},
    "donations_total": {"description": "All donations of this player on this island (intentionally duplicated across cities owned by the same player on this island)", "unit": "gold"},
    "wonder_type_id": {"description": "Wonder type id on this island (intentionally duplicated across cities on this island)", "unit": "enum"},
    "wonder_level": {"description": "Wonder level (intentionally duplicated across cities on this island)", "unit": "level"},
    "wonder_belief": {"description": "Wonder belief points (intentionally duplicated across cities on this island)", "unit": "points"},
    "luxury_resource_type": {"description": "Luxury resource type: 1=wine, 2=marble, 3=crystal, 4=sulfur (intentionally duplicated across cities on this island)", "unit": "enum"},
    "luxury_mine_level": {"description": "Luxury mine level (intentionally duplicated across cities on this island)", "unit": "level"},
    "sawmill_level": {"description": "Sawmill level (intentionally duplicated across cities on this island)", "unit": "level"},
    "island_city_count": {"description": "Raw total cities on the island (intentionally duplicated across cities on this island)", "unit": "count"},
    "sawmill_donated_cumulative": {"description": "Cumulative sawmill donations on the island (intentionally duplicated across cities on this island)", "unit": "gold"},
    "luxury_mine_donated_cumulative": {"description": "Cumulative luxury mine donations on the island (intentionally duplicated across cities on this island)", "unit": "gold"},
    "wonder_donated_cumulative": {"description": "Cumulative wonder donations on the island (intentionally duplicated across cities on this island)", "unit": "gold"},
    "sawmill_next_level_cost": {"description": "Cost for next sawmill level (intentionally duplicated across cities on this island)", "unit": "gold"},
    "luxury_mine_next_level_cost": {"description": "Cost for next luxury mine level (intentionally duplicated across cities on this island)", "unit": "gold"},
    "wonder_next_level_cost": {"description": "Cost for next wonder level (intentionally duplicated across cities on this island)", "unit": "gold"},
    "sawmill_next_level_remaining_cost": {"description": "Remaining donations needed for next sawmill level (intentionally duplicated across cities on this island)", "unit": "gold"},
    "luxury_mine_next_level_remaining_cost": {"description": "Remaining donations needed for next luxury mine level (intentionally duplicated across cities on this island)", "unit": "gold"},
    "wonder_next_level_remaining_cost": {"description": "Remaining donations needed for next wonder level (intentionally duplicated across cities on this island)", "unit": "gold"},
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


DONATION_ANALYTICS_PLAYER_ISLAND_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "island_id": {"description": "SHA1 of the island", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "donations_total": {"description": "All donations by this player on this island", "unit": "gold"},
    "sawmill_donations_total": {"description": "Sawmill donations by this player on this island", "unit": "gold"},
    "luxury_mine_donations_total": {"description": "Luxury mine donations by this player on this island", "unit": "gold"},
    "wonder_donations_total": {"description": "Wonder donations by this player on this island", "unit": "gold"},
    "wonder_and_luxury_mine_donations_total": {"description": "Wonder plus luxury mine donations", "unit": "gold"},
    "wonder_wine_donations_allocated": {"description": "Wonder donations allocated to wine by equal split across luxury goods not produced on the island", "unit": "gold"},
    "wonder_marble_donations_allocated": {"description": "Wonder donations allocated to marble by equal split across luxury goods not produced on the island", "unit": "gold"},
    "wonder_crystal_donations_allocated": {"description": "Wonder donations allocated to crystal by equal split across luxury goods not produced on the island", "unit": "gold"},
    "wonder_sulfur_donations_allocated": {"description": "Wonder donations allocated to sulfur by equal split across luxury goods not produced on the island", "unit": "gold"},
    "luxury_mine_wine_donations": {"description": "Luxury-mine donations on wine islands", "unit": "gold"},
    "luxury_mine_marble_donations": {"description": "Luxury-mine donations on marble islands", "unit": "gold"},
    "luxury_mine_crystal_donations": {"description": "Luxury-mine donations on crystal islands", "unit": "gold"},
    "luxury_mine_sulfur_donations": {"description": "Luxury-mine donations on sulfur islands", "unit": "gold"},
    "player_island_city_count": {"description": "Cities this player owns on this island", "unit": "count"},
    "player_total_city_count": {"description": "Cities this player owns across all islands", "unit": "count"},
    "island_player_count": {"description": "Players with cities on this island", "unit": "count"},
    "island_city_count": {"description": "Cities on this island across all players", "unit": "count"},
    "population_total": {"description": "Population in this player's cities on this island", "unit": "count"},
    "town_hall_levels_total": {"description": "Sum of town hall levels on this player-island", "unit": "sum_levels"},
    "building_levels_total": {"description": "Sum of building levels on this player-island", "unit": "sum_levels"},
    "resource_workers_total": {"description": "Resource workers on this player-island", "unit": "count"},
    "tradegood_workers_total": {"description": "Luxury-mine workers on this player-island", "unit": "count"},
    "priests_total": {"description": "Priests on this player-island", "unit": "count"},
    "wood_total": {"description": "Wood in buildings and storage on this player-island", "unit": "wood"},
    "wine_total": {"description": "Wine in buildings and storage on this player-island", "unit": "wine"},
    "marble_total": {"description": "Marble in buildings and storage on this player-island", "unit": "marble"},
    "crystal_total": {"description": "Crystal in buildings and storage on this player-island", "unit": "crystal"},
    "sulfur_total": {"description": "Sulfur in buildings and storage on this player-island", "unit": "sulfur"},
    "resources_total": {"description": "All resources in buildings and storage on this player-island", "unit": "sum"},
    "account_age_days": {"description": "Account age at reference timestamp", "unit": "days"},
    "island_donations_total": {"description": "All donations by players on this island", "unit": "gold"},
    "island_sawmill_donations_total": {"description": "Sawmill donations by players on this island", "unit": "gold"},
    "island_luxury_mine_donations_total": {"description": "Luxury-mine donations by players on this island", "unit": "gold"},
    "island_wonder_donations_total": {"description": "Wonder donations by players on this island", "unit": "gold"},
    "island_avg_donations_per_player": {"description": "Average island donations per player with cities", "unit": "gold"},
    "island_avg_sawmill_donations_per_player": {"description": "Average island sawmill donations per player with cities", "unit": "gold"},
    "island_avg_luxury_mine_donations_per_player": {"description": "Average island luxury-mine donations per player with cities", "unit": "gold"},
    "island_avg_wonder_donations_per_player": {"description": "Average island wonder donations per player with cities", "unit": "gold"},
    "island_peer_donations_avg": {"description": "Average donations by other players on the island", "unit": "gold"},
    "island_peer_sawmill_donations_avg": {"description": "Average sawmill donations by other players on the island", "unit": "gold"},
    "island_peer_luxury_mine_donations_avg": {"description": "Average luxury-mine donations by other players on the island", "unit": "gold"},
    "island_peer_wonder_donations_avg": {"description": "Average wonder donations by other players on the island", "unit": "gold"},
    "donations_minus_island_peer_avg": {"description": "Player-island donations minus island peer average", "unit": "gold"},
    "sawmill_donation_share_pct": {"description": "Sawmill donations as a share of total donations", "unit": "percent"},
    "luxury_mine_donation_share_pct": {"description": "Luxury-mine donations as a share of total donations", "unit": "percent"},
    "wonder_donation_share_pct": {"description": "Wonder donations as a share of total donations", "unit": "percent"},
    "donations_per_city": {"description": "Donations divided by player-island city count", "unit": "gold_per_city"},
    "donations_per_citizen": {"description": "Donations divided by player-island population", "unit": "gold_per_count"},
    "donations_per_town_hall_level": {"description": "Donations divided by town hall level sum", "unit": "gold_per_level"},
    "sawmill_donations_per_resource_worker": {"description": "Sawmill donations divided by resource workers", "unit": "gold_per_worker"},
    "luxury_mine_donations_per_tradegood_worker": {"description": "Luxury-mine donations divided by luxury-mine workers", "unit": "gold_per_worker"},
    "wonder_donations_per_priest": {"description": "Wonder donations divided by priests", "unit": "gold_per_priest"},
    "donations_per_account_age_day": {"description": "Donations divided by account age in days", "unit": "gold_per_day"},
    "wood_donation_resource_share_pct": {"description": "Wood-linked donations divided by wood total plus those donations", "unit": "percent"},
    "wine_wonder_donation_resource_share_pct": {"description": "Wine wonder allocation divided by wine total plus that allocation", "unit": "percent"},
    "marble_wonder_donation_resource_share_pct": {"description": "Marble wonder allocation divided by marble total plus that allocation", "unit": "percent"},
    "crystal_wonder_donation_resource_share_pct": {"description": "Crystal wonder allocation divided by crystal total plus that allocation", "unit": "percent"},
    "sulfur_wonder_donation_resource_share_pct": {"description": "Sulfur wonder allocation divided by sulfur total plus that allocation", "unit": "percent"},
    "donations_resource_share_pct": {"description": "Donations divided by resource total plus donations", "unit": "percent"},
}


RAW_COMMON_DOCS: dict[str, dict[str, str]] = {
    "snapshot_id": {"description": "Snapshot identifier, e.g. de_1311_14", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country": {"description": "Server country code", "unit": "iso2"},
}


TABLE_DOCS: dict[str, dict[str, dict[str, str]]] = {
    "player_snapshot": PLAYER_SNAPSHOT_DOCS,
    "city_snapshot": CITY_SNAPSHOT_DOCS,
    "island_snapshot": ISLAND_SNAPSHOT_DOCS,
    "donation_analytics_player_island_snapshot": DONATION_ANALYTICS_PLAYER_ISLAND_SNAPSHOT_DOCS,
    "raw_avatar": RAW_COMMON_DOCS,
    "raw_city": RAW_COMMON_DOCS,
    "raw_donation": RAW_COMMON_DOCS,
    "raw_island": RAW_COMMON_DOCS,
}


TABLE_DESCRIPTIONS: dict[str, str] = {
    "player_snapshot": (
        "One row per (player, snapshot). Aggregates each player's city and "
        "donation state for a weekly snapshot."
    ),
    "city_snapshot": (
        "One row per (city, snapshot). Contains detailed city-level metrics "
        "and corresponding player-island donations and island metadata. Note: "
        "duplication of player-island level donations and island metadata is intentional "
        "for the sake of ease of downstream analysis (avoiding complex multi-table joins)."
    ),
    "island_snapshot": (
        "One row per (island, snapshot). Includes island state, upgrade "
        "metrics, and player/city/donation aggregates."
    ),
    "donation_analytics_player_island_snapshot": (
        "One row per (player, island, snapshot). Contains donation totals, "
        "denominators, intensity ratios, composition shares, and island peer "
        "averages without legacy database-wide broadcast constants."
    ),
    "raw_avatar": "Raw avatar parquet rows, exported as one LanceDB table per country.",
    "raw_city": "Raw city parquet rows, exported as one LanceDB table per country.",
    "raw_donation": "Raw donation parquet rows, exported as one LanceDB table per country.",
    "raw_island": "Raw island parquet rows, exported as one LanceDB table per country.",
}
