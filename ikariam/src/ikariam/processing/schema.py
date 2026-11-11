"""Column-level documentation for the canonical Lance output tables.

Raw MariaDB table/column names stay upstream. The public tables documented
here use readable lower_snake_case names. The game calls a player an
`avatar`. That name is kept only for raw data (the `raw_avatar` table and raw
columns such as `avatar_id`); everything the pipeline produces says `player`.
"""

from __future__ import annotations


_RESOURCE_UNITS: dict[str, str] = {
    "wood": "wood",
    "crystal": "crystal",
    "marble": "marble",
    "sulfur": "sulfur",
    "wine": "wine",
}

# Unit of every *_total column that adds the five resources one to one.
_SUM_UNIT = "resource units (unweighted sum of wood, wine, marble, crystal and sulfur)"
_SUM_NOTE = "Plain sum of the five resources, one unit each; not a value in gold, and dominated by wood, so compare the five resources separately when value matters."

# Raw city column behind each stored resource.
_STORED_SOURCE: dict[str, str] = {
    "wood": "resource",
    "wine": "tradegood1",
    "marble": "tradegood2",
    "crystal": "tradegood3",
    "sulfur": "tradegood4",
}


def _building_cost_docs(scope: str) -> dict[str, dict[str, str]]:
    """Undiscounted list price and current-discount estimate of the standing buildings."""
    docs = {
        f"building_base_cost_{resource}": {
            "description": f"Full list price in {resource} of all buildings standing {scope} at this snapshot, including the town hall, without any discount: for each building, the cumulative cost of all its levels from the building cost table. The starting point for estimated_building_cost_{resource} and historical_building_cost_{resource}.",
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    }
    docs["building_base_cost_total"] = {
        "description": f"building_base_cost_wood + _wine + _marble + _crystal + _sulfur. {_SUM_NOTE}",
        "unit": _SUM_UNIT,
    }
    docs.update(
        {
            f"estimated_building_cost_{resource}": {
                "description": f"building_base_cost_{resource} with this snapshot's discount applied to every standing level {scope}: list price times each city's estimated_{resource}_cost_factor (player research plus the city's own {resource} reduction building). Assumes old buildings got today's discount, so it understates what was really paid; for that, use historical_building_cost_{resource}.",
                "unit": unit,
            }
            for resource, unit in _RESOURCE_UNITS.items()
        }
    )
    docs["estimated_building_cost_total"] = {
        "description": f"estimated_building_cost_wood + _wine + _marble + _crystal + _sulfur. {_SUM_NOTE}",
        "unit": _SUM_UNIT,
    }
    return docs


def _construction_docs(scope: str) -> dict[str, dict[str, str]]:
    """Cost of building levels priced at the discount active when each level was built."""
    docs = {
        f"historical_building_cost_{resource}": {
            "description": f"Estimated {resource} actually paid for the buildings standing {scope}: each level is priced at the discount active when it was built (the midpoint of the city's factor at the two snapshots around its construction). Levels already present at the first snapshot of a building use that snapshot's discount. The best estimate of real spending on standing buildings; check observed_construction_coverage before relying on it.",
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    }
    docs["historical_building_cost_total"] = {
        "description": f"historical_building_cost_wood + _wine + _marble + _crystal + _sulfur. {_SUM_NOTE}",
        "unit": _SUM_UNIT,
    }
    docs.update(
        {
            f"lifetime_construction_spend_{resource}": {
                "description": f"Estimated {resource} paid for every building level ever built {scope}, including levels that were later demolished; priced like historical_building_cost_{resource}. Never decreases over time. The gap to historical_building_cost_{resource} is the value lost to demolition.",
                "unit": unit,
            }
            for resource, unit in _RESOURCE_UNITS.items()
        }
    )
    docs["lifetime_construction_spend_total"] = {
        "description": f"lifetime_construction_spend_wood + _wine + _marble + _crystal + _sulfur. {_SUM_NOTE}",
        "unit": _SUM_UNIT,
    }
    docs["opening_stock_base_cost_total"] = {
        "description": f"Full list price (no discount, five resources summed) of the standing levels {scope} that already existed when their building was first observed, so their build time is unknown and their historical price is a guess. Used for observed_construction_coverage.",
        "unit": _SUM_UNIT,
    }
    docs["observed_construction_coverage"] = {
        "description": "Share of the standing building value whose build time is known: 1 - opening_stock_base_cost_total / building_base_cost_total. Close to 1 on the five long-running servers; 0 on the 13 servers with a single snapshot, where historical_building_cost_* equals estimated_building_cost_*. Reads 1.0 when there are no buildings at all, so exclude rows with building_base_cost_total = 0 when averaging.",
        "unit": "ratio between 0 and 1",
    }
    return docs


_REDUCTION_BUILDING_NAMES: dict[str, str] = {
    "wood": "Carpenter",
    "marble": "Architect's Office",
    "crystal": "Optician",
    "wine": "Wine Press",
    "sulfur": "Firework Test Area",
}


def _reduction_building_docs() -> dict[str, dict[str, str]]:
    """City-local reduction buildings and the resulting discount factor."""
    docs = {
        f"{resource}_reduction_building_level": {
            "description": f"Level of this city's {building} at this snapshot, 0 if the city has none. Each level lowers the {resource} cost of buildings in this city only by one percentage point.",
            "unit": "level",
        }
        for resource, building in _REDUCTION_BUILDING_NAMES.items()
    }
    docs.update(
        {
            f"estimated_{resource}_cost_factor": {
                "description": f"Share of the list price in {resource} this city pays for a new building level at this snapshot: 1 - research reduction (1 - estimated_research_cost_factor) - 0.01 per {building} level. Between 0.54 and 1.00. Multiplies building_base_cost_{resource} into estimated_building_cost_{resource}.",
                "unit": "ratio between 0.54 and 1",
            }
            for resource, building in _REDUCTION_BUILDING_NAMES.items()
        }
    )
    return docs


def _stored_resource_docs(scope: str) -> dict[str, dict[str, str]]:
    """Resources in storage at the snapshot."""
    docs = {
        f"{resource}_stored": {
            "description": f"{resource.capitalize()} in storage {scope} at the moment of this snapshot (raw city column {_STORED_SOURCE[resource]}). A stock that rises with production and falls when the player builds or trades, not the amount produced.",
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    }
    docs["resources_stored_total"] = {
        "description": f"wood_stored + wine_stored + marble_stored + crystal_stored + sulfur_stored. {_SUM_NOTE}",
        "unit": _SUM_UNIT,
    }
    return docs


def _estimated_resource_value_docs(scope: str) -> dict[str, dict[str, str]]:
    """Resources tied up in standing buildings plus storage."""
    docs = {
        f"estimated_{resource}_resource_value": {
            "description": f"{resource.capitalize()} tied up {scope} at this snapshot: estimated_building_cost_{resource} (standing buildings at this snapshot's discount) + {resource}_stored. Leaves out demolished buildings, ships and units, trades and donations, so it is neither income nor total spending.",
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    }
    docs["estimated_resource_value_total"] = {
        "description": f"estimated_building_cost_total + resources_stored_total, the five estimated_*_resource_value columns added. {_SUM_NOTE}",
        "unit": _SUM_UNIT,
    }
    return docs


RESEARCH_COST_ESTIMATE_DOCS: dict[str, dict[str, str]] = {
    "estimated_research_cost_factor": {
        "description": "Share of the list price the player still pays after research discounts (Pulley 2%, Geometry 4%, Spirit Level 8%), the same for all of the player's cities: 1.00, 0.98, 0.94 or 0.86. Research is not in the data, so it is estimated as the stronger of an account-age rule and the buildings the player has built so far (research_evidence_tier). City-specific factors that also include reduction buildings are city_snapshot.estimated_<resource>_cost_factor.",
        "unit": "ratio",
    },
    "estimated_research_cost_factor_source": {
        "description": "Which rule set estimated_research_cost_factor: building_evidence when the player's buildings prove more research than the account age suggests, otherwise age_heuristic.",
        "unit": "enum",
    },
    "research_evidence_tier": {
        "description": "Highest research level proven by buildings seen in this or an earlier snapshot (a building that needs a given research): none, pulley_or_later, geometry_or_later or spirit_level_or_later.",
        "unit": "enum",
    },
}


# Raw donation amounts are running totals per player, island and type: each
# snapshot carries everything donated up to that day, never the donations of
# that week alone. Summing a donation column across snapshots counts the same
# donations many times.
_CUMULATIVE_NOTE = "up to this snapshot (running total, not this week's donations; do not sum across snapshots)"
_PLAYER_DONATION_SCOPE = f"by this player on every island, including islands where the player no longer has a city, {_CUMULATIVE_NOTE}"
_PLAYER_ISLAND_DONATION_SCOPE = f"by this player on this island, {_CUMULATIVE_NOTE}"
_ISLAND_DONATION_SCOPE = f"by players who have a city on this island at this snapshot, {_CUMULATIVE_NOTE}"


PLAYER_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier, e.g. de23_1311_14", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "server": {"description": "Game server number within the country; a country can run several servers over time, each its own world", "unit": "id"},
    "registered_at_unix": {"description": "Player registration time", "unit": "unix_seconds"},
    "registered_at": {"description": "Player registration timestamp in UTC", "unit": "datetime"},
    "gold": {"description": "Gold held by the player at this snapshot", "unit": "gold"},
    "research_points": {"description": "Research points accumulated", "unit": "points"},
    "government_form": {"description": "Government form enum from the raw avatar table", "unit": "enum"},
    "gender": {"description": "Gender flag from the raw avatar table", "unit": "enum"},
    "account_age_days": {
        "description": (
            "Calendar-day difference between the snapshot date and the UTC registration date"
        ),
        "unit": "days",
    },
    **RESEARCH_COST_ESTIMATE_DOCS,
    "island_count": {"description": "Distinct islands where this player has cities", "unit": "count"},
    "city_count": {"description": "Total cities owned by this player", "unit": "count"},
    "population_total": {"description": "Total population across this player's cities", "unit": "count"},
    **_building_cost_docs("across this player's cities"),
    **_stored_resource_docs("across this player's cities"),
    **_estimated_resource_value_docs("across this player's cities"),
    **_construction_docs("across this player's cities"),
    "building_levels_total": {"description": "Sum of all building levels, including town halls", "unit": "sum_levels"},
    "wonder_donations_total": {"description": f"Wonder donations {_PLAYER_DONATION_SCOPE}", "unit": "gold"},
    "sawmill_donations_total": {"description": f"Sawmill donations {_PLAYER_DONATION_SCOPE}", "unit": "gold"},
    "luxury_mine_donations_total": {"description": f"Luxury mine donations {_PLAYER_DONATION_SCOPE}", "unit": "gold"},
    "donations_total": {"description": f"All donations {_PLAYER_DONATION_SCOPE}", "unit": "gold"},
    "wonder_and_luxury_mine_donations_total": {
        "description": f"Wonder plus luxury mine donations {_PLAYER_DONATION_SCOPE}",
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
    "server": {"description": "Game server number within the country; a country can run several servers over time, each its own world", "unit": "id"},
    "is_capital": {"description": "True if the city is the player's capital", "unit": "boolean"},
    "town_hall_level": {"description": "Town hall level", "unit": "level"},
    "citizens": {"description": "Number of free citizens in the city", "unit": "count"},
    "scientists": {"description": "Number of scientists in the academy", "unit": "count"},
    "priests": {"description": "Number of priests in the temple", "unit": "count"},
    "resource_workers": {"description": "Number of workers in the sawmill", "unit": "count"},
    "tradegood_workers": {"description": "Number of workers in the luxury mine", "unit": "count"},
    "population_total": {"description": "Total population in the city", "unit": "count"},
    **RESEARCH_COST_ESTIMATE_DOCS,
    **_reduction_building_docs(),
    **_building_cost_docs("in this city"),
    **_stored_resource_docs("in this city"),
    **_estimated_resource_value_docs("in this city"),
    **_construction_docs("in this city"),
    "building_levels_total": {"description": "Sum of all building levels in this city, including the town hall", "unit": "sum_levels"},
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
    "server": {"description": "Game server number within the country; a country can run several servers over time, each its own world", "unit": "id"},
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
    "raw_city_count": {
        "description": (
            "Raw city_count field from the island source table. This may differ from city_count because the source can count cities whose owner is missing from the player snapshot, and in rare rows the island source underreports compared with raw city rows. Do not use this field for calculations unless the analysis explicitly needs the raw source value."
        ),
        "unit": "count",
    },
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
    "city_count": {
        "description": (
            "Computed total cities on this island from city records that survive the canonical city/player joins. Usually matches raw_city_count, but can be lower when raw city owners are absent from player_snapshot."
        ),
        "unit": "count",
    },
    "population_total": {"description": "Total population across players", "unit": "count"},
    **_building_cost_docs("across all cities on this island"),
    **_stored_resource_docs("across all cities on this island"),
    **_estimated_resource_value_docs("across all cities on this island"),
    **_construction_docs("across all cities on this island"),
    "building_levels_total": {"description": "Sum of building levels across players, including town halls", "unit": "sum_levels"},
    "avg_population_per_player": {"description": "Average population per player", "unit": "count"},
    "donating_player_count": {"description": "Players with a city on this island whose running donation total here is above zero", "unit": "count"},
    "wonder_donations_total": {"description": f"Wonder donations {_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "sawmill_donations_total": {"description": f"Sawmill donations {_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "luxury_mine_donations_total": {"description": f"Luxury mine donations {_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "donations_total": {"description": f"All donations {_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "avg_donations_per_player": {"description": "Average donations per player", "unit": "gold"},
    "donating_player_share_pct": {"description": "Donating players / players", "unit": "percent"},
}


DONATION_ANALYTICS_PLAYER_ISLAND_SNAPSHOT_DOCS: dict[str, dict[str, str]] = {
    "player_id": {"description": "SHA1 of the player account", "unit": "id"},
    "island_id": {"description": "SHA1 of the island", "unit": "id"},
    "snapshot_id": {"description": "Snapshot identifier", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "server": {"description": "Game server number within the country; a country can run several servers over time, each its own world", "unit": "id"},
    "donations_total": {"description": f"All donations {_PLAYER_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "sawmill_donations_total": {"description": f"Sawmill donations {_PLAYER_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "luxury_mine_donations_total": {"description": f"Luxury mine donations {_PLAYER_ISLAND_DONATION_SCOPE}", "unit": "gold"},
    "wonder_donations_total": {"description": f"Wonder donations {_PLAYER_ISLAND_DONATION_SCOPE}", "unit": "gold"},
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
    "building_levels_total": {"description": "Sum of building levels on this player-island, including town halls", "unit": "sum_levels"},
    "resource_workers_total": {"description": "Resource workers on this player-island", "unit": "count"},
    "tradegood_workers_total": {"description": "Luxury-mine workers on this player-island", "unit": "count"},
    "priests_total": {"description": "Priests on this player-island", "unit": "count"},
    **RESEARCH_COST_ESTIMATE_DOCS,
    **_building_cost_docs("across this player's cities on this island"),
    **_stored_resource_docs("across this player's cities on this island"),
    **_estimated_resource_value_docs("across this player's cities on this island"),
    **_construction_docs("across this player's cities on this island"),
    "account_age_days": {
        "description": (
            "Calendar-day difference between the snapshot date and the UTC registration date"
        ),
        "unit": "days",
    },
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
    "cumulative_donations_per_account_age_day": {
        "description": "Cumulative donations divided by account age at this snapshot",
        "unit": "gold_per_day",
    },
    "estimated_wood_donation_resource_share_pct": {
        "description": (
            "Wood-linked donations divided by a denominator of estimated wood resource value plus those donations"
        ),
        "unit": "percent",
    },
    "estimated_wine_wonder_donation_resource_share_pct": {
        "description": (
            "Wine wonder allocation divided by a denominator of estimated wine resource value plus that allocation"
        ),
        "unit": "percent",
    },
    "estimated_marble_wonder_donation_resource_share_pct": {
        "description": (
            "Marble wonder allocation divided by a denominator of estimated marble resource value plus that allocation"
        ),
        "unit": "percent",
    },
    "estimated_crystal_wonder_donation_resource_share_pct": {
        "description": (
            "Crystal wonder allocation divided by a denominator of estimated crystal resource value plus that allocation"
        ),
        "unit": "percent",
    },
    "estimated_sulfur_wonder_donation_resource_share_pct": {
        "description": (
            "Sulfur wonder allocation divided by a denominator of estimated sulfur resource value plus that allocation"
        ),
        "unit": "percent",
    },
    "estimated_donations_resource_share_pct": {
        "description": (
            "Cumulative donations divided by a denominator of estimated total resource value plus cumulative donations"
        ),
        "unit": "percent",
    },
}


_EVENT_IDENTITY_DOCS: dict[str, dict[str, str]] = {
    "country_code": {"description": "Server country code", "unit": "iso2"},
    "server": {"description": "Game server number within the country; a country can run several servers over time, each its own world", "unit": "id"},
    "city_id": {"description": "SHA1 of the city", "unit": "id"},
    "position": {
        "description": (
            "Building position 1-17, or 0 for the town hall, which occupies no numbered slot and is tracked by the city's own level column"
        ),
        "unit": "enum",
    },
    "building_type": {"description": "Game building type id from the raw slot data", "unit": "enum"},
    "building_level": {
        "description": "The single building level this row accounts for",
        "unit": "level",
    },
}


BUILDING_CONSTRUCTION_EVENT_DOCS: dict[str, dict[str, str]] = {
    **_EVENT_IDENTITY_DOCS,
    "built_by_snapshot_id": {
        "description": "Snapshot by which this level was present",
        "unit": "id",
    },
    "built_by_snapshot_date": {
        "description": "Date of the snapshot by which this level was present",
        "unit": "date",
    },
    "built_after_snapshot_date": {
        "description": (
            "Date of the previous observation of this position; the level appeared between this date and built_by_snapshot_date. Null when the level was already present at first sighting"
        ),
        "unit": "date",
    },
    "is_opening_stock": {
        "description": (
            "True when the level was already there the first time this building was observed, so it cannot be dated and is priced at that first observation's factor"
        ),
        "unit": "boolean",
    },
    **{
        f"factor_{resource}": {
            "description": (
                f"Applied {resource} cost multiplier: the midpoint of this city's {resource} factor at the two bracketing observations"
            ),
            "unit": "ratio",
        }
        for resource in _RESOURCE_UNITS
    },
    **{
        f"level_cost_{resource}": {
            "description": (
                f"Undiscounted {resource} cost of this one level: the cumulative lookup value minus the level below it"
            ),
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    },
    **{
        f"paid_cost_{resource}": {
            "description": (
                f"Estimated {resource} paid for this level: level_cost_{resource} times factor_{resource}"
            ),
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    },
}


BUILDING_DEMOLITION_EVENT_DOCS: dict[str, dict[str, str]] = {
    **_EVENT_IDENTITY_DOCS,
    "removed_by_snapshot_id": {
        "description": "Snapshot by which this level no longer stood",
        "unit": "id",
    },
    "removed_at_snapshot_date": {
        "description": "Date of the snapshot by which this level no longer stood",
        "unit": "date",
    },
    "built_by_snapshot_date": {
        "description": (
            "Date of the construction event this removal reverses, so the level is written off at the value it actually carried"
        ),
        "unit": "date",
    },
    "is_opening_stock": {
        "description": "True when the removed level came from undatable opening stock",
        "unit": "boolean",
    },
    **{
        f"level_cost_{resource}": {
            "description": f"Undiscounted {resource} cost of the removed level",
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    },
    **{
        f"paid_cost_{resource}": {
            "description": (
                f"Estimated {resource} that had been paid for the removed level, withdrawn from the standing total"
            ),
            "unit": unit,
        }
        for resource, unit in _RESOURCE_UNITS.items()
    },
}


RAW_COMMON_DOCS: dict[str, dict[str, str]] = {
    "snapshot_id": {"description": "Snapshot identifier, e.g. de23_1311_14", "unit": "id"},
    "snapshot_date": {"description": "Date the snapshot was taken", "unit": "date"},
    "country": {"description": "Server country code", "unit": "iso2"},
    "server": {"description": "Game server number within the country; a country can run several servers over time, each its own world", "unit": "id"},
}


TABLE_DOCS: dict[str, dict[str, dict[str, str]]] = {
    "player_snapshot": PLAYER_SNAPSHOT_DOCS,
    "city_snapshot": CITY_SNAPSHOT_DOCS,
    "island_snapshot": ISLAND_SNAPSHOT_DOCS,
    "donation_analytics_player_island_snapshot": DONATION_ANALYTICS_PLAYER_ISLAND_SNAPSHOT_DOCS,
    "building_construction_event": BUILDING_CONSTRUCTION_EVENT_DOCS,
    "building_demolition_event": BUILDING_DEMOLITION_EVENT_DOCS,
    "raw_avatar": RAW_COMMON_DOCS,
    "raw_city": RAW_COMMON_DOCS,
    "raw_donation": RAW_COMMON_DOCS,
    "raw_island": RAW_COMMON_DOCS,
}


TABLE_DESCRIPTIONS: dict[str, str] = {
    "player_snapshot": (
        "One row per (player, snapshot). Aggregates each player's city and donation state for a weekly snapshot."
    ),
    "city_snapshot": (
        "One row per (city, snapshot): city metrics plus the metadata of the island the city is on, which repeats on every city of that island. Donations are not here, because the game records them per player and island, not per city: see donation_analytics_player_island_snapshot."
    ),
    "island_snapshot": (
        "One row per (island, snapshot). Includes island state, upgrade metrics, and player/city/donation aggregates."
    ),
    "donation_analytics_player_island_snapshot": (
        "One row per (player, island, snapshot). Contains donation totals, denominators, intensity ratios, composition shares, and island peer averages without legacy database-wide broadcast constants."
    ),
    "building_construction_event": (
        "One row per building level ever constructed, per city. Each level is priced at the discount state active in the interval when it appeared, so summing paid_cost_* reproduces lifetime_construction_spend_*. This is the audit trail behind the historical cost columns on the snapshot tables."
    ),
    "building_demolition_event": (
        "One row per building level that stopped standing, valued at the amount it had been paid for. Standing value equals construction minus demolition, so this table explains every gap between historical_building_cost_* and lifetime_construction_spend_*."
    ),
    "raw_avatar": "Raw avatar parquet rows, exported as one LanceDB table per country.",
    "raw_city": "Raw city parquet rows, exported as one LanceDB table per country.",
    "raw_donation": "Raw donation parquet rows, exported as one LanceDB table per country.",
    "raw_island": "Raw island parquet rows, exported as one LanceDB table per country.",
}
