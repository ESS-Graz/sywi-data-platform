"""Compare current LanceDB output against the legacy SQL gold CSVs.

Reviewer guide:

1. `read_lancedb_frames` and `read_gold_frames` load the two sides.
2. `build_legacy_views` rebuilds SQL-shaped outputs from current LanceDB facts.
   These frames are compatibility projections, not new canonical tables.
3. `compare_frame` compares keys and only columns that exist on both sides.
   Columns that are not explicitly reconstructed are reported as unmapped
   rather than silently treated as verified.
4. `write_markdown_report` writes the human-facing summary and detail paths.

The deliberately awkward parts of this file mirror legacy MySQL behavior from
`Alle_Queries_DE_hintereinander.sql`, including permissive `SELECT * GROUP BY`
representative rows and SQL default-zero helper columns. Comments below call
out those cases because they are compatibility choices, not preferred modeling
patterns for the Dagster pipeline.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from .utils import safe_divide, safe_percent


GOLD_OUTPUTS: tuple[str, ...] = (
    "Teilnahme_AV",
    "Master_Avi",
    "A_DS",
    "AVI_DS",
    "I_DS",
)

DEFAULT_TOLERANCE = 1e-6
MAX_MISMATCH_SAMPLES = 10_000


@dataclass(frozen=True, slots=True)
class ComparisonSpec:
    name: str
    key_columns: tuple[str, ...]
    tolerance: float = DEFAULT_TOLERANCE


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    name: str
    key_columns: tuple[str, ...]
    gold_rows: int
    actual_rows: int
    mapped_columns: tuple[str, ...]
    unmapped_columns: tuple[str, ...]
    gold_duplicate_keys: int
    actual_duplicate_keys: int
    gold_only_keys: int
    actual_only_keys: int
    mismatch_count: int
    mismatch_path: Path
    mismatch_counts_path: Path
    gold_only_path: Path
    actual_only_path: Path
    unmapped_path: Path

    @property
    def failed(self) -> bool:
        return (
            self.gold_duplicate_keys > 0
            or self.actual_duplicate_keys > 0
            or self.gold_only_keys > 0
            or self.actual_only_keys > 0
            or self.mismatch_count > 0
        )


COMPARISON_SPECS: dict[str, ComparisonSpec] = {
    "Teilnahme_AV": ComparisonSpec("Teilnahme_AV", ("id",)),
    "Master_Avi": ComparisonSpec("Master_Avi", ("owner_id", "island_id")),
    "A_DS": ComparisonSpec("A_DS", ("t_id",)),
    "AVI_DS": ComparisonSpec("AVI_DS", ("m_owner_id", "m_island_id")),
    "I_DS": ComparisonSpec("I_DS", ("i_id",)),
}

# Mapping dictionaries use the direction `legacy output column -> LanceDB
# source column` unless noted otherwise. They let a reviewer audit the SQL
# alias contract in one place instead of reading repeated string literals in
# the projection code below.
CITY_SUM_MAP: dict[str, str] = {
    "c_capital": "is_capital_int",
    "c_citizens": "citizens",
    "c_resource_workers": "resource_workers",
    "c_tradegood_workers": "tradegood_workers",
    "c_scientists": "scientists",
    "c_priests": "priests",
    "c_Baumeister_Highscore": "building_resource_score",
    "c_Buerger_Ges": "population_total",
    "c_Geblev": "building_levels_total",
    "c_Holz_Ges_verb_lag": "wood_total",
    "c_Holz_lagernd": "wood_stored",
    "c_Holz_verbaut": "wood_in_buildings",
    "c_Kristall_Ges_verb_lag": "crystal_total",
    "c_Kristall_lagernd": "crystal_stored",
    "c_Kristall_verbaut": "crystal_in_buildings",
    "c_Rathauslev": "town_hall_level",
    "c_Res_Ges_lagernd": "resources_stored_total", # Das darf nicht total heißen
    "c_Res_Ges_verb_lag": "resources_in_buildings_and_storage_total", # Das darf total heißen -> ressources_total
    "c_Res_Ges_verbaut": "resources_in_buildings_total", # Das darf nicht total heißen
    "c_Schwefel_Ges_verb_lag": "sulfur_total",
    "c_Schwefel_lagernd": "sulfur_stored",
    "c_Schwefel_verbaut": "sulfur_in_buildings",
    "c_Stein_Ges_verb_lag": "marble_total",
    "c_Stein_lagernd": "marble_stored",
    "c_Stein_verbaut": "marble_in_buildings",
    "c_Wein_Ges_verb_lag": "wine_total",
    "c_Wein_lagernd": "wine_stored",
    "c_Wein_verbaut": "wine_in_buildings",
}

# Raw city fields that the legacy SQL does not aggregate. MySQL returns a
# representative row for these under permissive `SELECT * ... GROUP BY`.
CITY_REPRESENTATIVE_MAP: dict[str, str] = {
    "c_level": "town_hall_level",
    "c_tradegood1": "wine_stored",
    "c_tradegood2": "marble_stored",
    "c_tradegood3": "crystal_stored",
    "c_tradegood4": "sulfur_stored",
    "c_resource": "wood_stored",
}

# Q35 and Q37 update these average columns only on the player-level
# `city3Av` and island-level `city4Isl` tables using AVG over `city2`.
# `city2` itself keeps the SQL default 0 values, which is why direct
# player-island `AVI_DS` rows intentionally emit zero for this family.
CITY_AVG_MAP: dict[str, str] = {
    "c_Avg_Anz_cities_per_Av": "c_Anz_Cities_per_Av",
    "c_Avg_Buerger_Ges": "c_Buerger_Ges",
    "c_Avg_Holz_Ges_verb_lag": "c_Holz_Ges_verb_lag",
    "c_Avg_Kristall_Ges_verb_lag": "c_Kristall_Ges_verb_lag",
    "c_Avg_Rathauslev": "c_Rathauslev",
    "c_Avg_Res_Ges_verb_lag": "c_Res_Ges_verb_lag",
    "c_Avg_Resource_workers": "c_resource_workers",
    "c_Avg_Schwefel_Ges_verb_lag": "c_Schwefel_Ges_verb_lag",
    "c_Avg_Stein_Ges_verb_lag": "c_Stein_Ges_verb_lag",
    "c_Avg_Tradegood_workers": "c_tradegood_workers",
    "c_Avg_Wein_Ges_verb_lag": "c_Wein_Ges_verb_lag",
}

# Q30 stores these on `island` with legacy names that final SELECTs expose
# under a `c_` prefix. They are global island-level sums divided by the
# database avatar count, repeated for every joined island row.
ISLAND_LEVEL_PER_AVATAR_MAP: dict[str, str] = {
    "c_Avg_Resource_lev_per_Av": "sawmill_level",
    "c_Avg_Tradegood_lev_per_Av": "luxury_mine_level",
    "c_Avg_Wonder_lev_per_Av": "wonder_level",
}

DONATION_SUM_MAP: dict[str, str] = {
    "d_Don_Ges": "donations_total",
    "d_Don_Saegewerk_Ges": "sawmill_donations_total",
    "d_Don_Wonder_Ges": "wonder_donations_total",
    "d_DonH_Luxusminen_Ges": "luxury_mine_donations_total",
    "d_DonH_Ges": "sawmill_and_luxury_mine_donations_total",
}

# Direct island state/cost mappings. Some adjacent island helper fields are
# calculated in `build_legacy_views` because they depend on filtered city2
# counts rather than a one-to-one LanceDB source column.
ISLAND_SUM_MAP: dict[str, str] = {
    "i_resource_donated": "sawmill_donated_cumulative",
    "i_resource_level": "sawmill_level",
    "i_tradegood_donated": "luxury_mine_donated_cumulative",
    "i_tradegood_level": "luxury_mine_level",
    "i_wonder_belief": "wonder_belief",
    "i_wonder_donated": "wonder_donated_cumulative",
    "i_wonder_level": "wonder_level",
    "i_cost_Nextlev_Resource": "sawmill_next_level_cost",
    "i_cost_Nextlev_Tradegood": "luxury_mine_next_level_cost",
    "i_cost_Nextlev_Wonder": "wonder_next_level_cost",
    "i_Sub_Noetig_nextlev_Resource": "sawmill_next_level_remaining_cost",
    "i_Sub_Noetig_nextlev_Tradegood": "luxury_mine_next_level_remaining_cost",
    "i_Sub_Noetig_nextlev_Wonder": "wonder_next_level_remaining_cost",
}


# Direct legacy avatar aliases used by final `A_DS` and `AVI_DS` SELECTs.
AVATAR_MAP: dict[str, str] = {
    "a_id": "player_id",
    "a_gold": "gold",
    "a_registration_time": "registered_at_unix",
    "a_Registration_time_normal": "registered_at",
    "a_Spieldauer": "account_age_days",
    "a_formOfGovernment": "government_form",
}

# These two columns are documented, expected unmapped outputs. They are
# database-wide donation totals/counts copied onto every legacy row, not
# row-level analytics in the canonical LanceDB model.
LEGACY_DONATION_BROADCAST_COLUMNS: tuple[str, ...] = (
    "d_Anz_Don_per_DB",
    "d_Don_pro_DB",
)

# Q38/Q41 aggregate these donation columns by player or island.
LEGACY_DONATION_SUM_COLUMNS: tuple[str, ...] = (
    "d_Don_Ges",
    "d_Don_Saegewerk_Ges",
    "d_Don_Wonder_Anteil_Kristall",
    "d_Don_Wonder_Anteil_Schwefel",
    "d_Don_Wonder_Anteil_Stein",
    "d_Don_Wonder_Anteil_Wein",
    "d_Don_Wonder_Ges",
    "d_DonH_fuer_Kristallmine",
    "d_DonH_fuer_Schwefelgrube",
    "d_DonH_fuer_Steinbruch",
    "d_DonH_fuer_Weinreben",
    "d_DonH_Ges",
    "d_DonH_Luxusminen_Ges",
    "d_gold",
    "d_Holz_Ges_verb_lag_don",
    "d_Kristall_Ges_verb_lag_don",
    "d_Res_Ges_verb_lag_don",
    "d_Schwefel_Ges_verb_lag_don",
    "d_Stein_Ges_verb_lag_don",
    "d_Wein_Ges_verb_lag_don",
)

# Q40/Q43 populate legacy `Avg_*` output columns from the listed base columns.
# Row-level `donation2` keeps these fields at SQL default zero until the
# player/island rollup steps.
LEGACY_DONATION_AVG_MAP: dict[str, str] = {
    "d_Avg_Don_Ges": "d_Don_Ges",
    "d_Avg_Don_Saegewerk_Ges": "d_Don_Saegewerk_Ges",
    "d_Avg_Don_Wonder_Ges": "d_Don_Wonder_Ges",
    "d_Avg_DonH_Luxusminen_Ges": "d_DonH_Luxusminen_Ges",
    "d_Avg_Holz_Ges_verb_lag_don": "d_Holz_Ges_verb_lag_don",
    "d_Avg_Kristall_Ges_verb_lag_don": "d_Kristall_Ges_verb_lag_don",
    "d_Avg_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag": "d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag",
    "d_Avg_Proz_Don_Anteil_Kristall_von_Kristall_Ges_verb_lag": "d_Proz_Don_Anteil_Kristall_von_Kristall_Ges_verb_lag",
    "d_Avg_Proz_Don_Anteil_Schwefel_von_Schwefel_Ges_verb_lag": "d_Proz_Don_Anteil_Schwefel_von_Schwefel_Ges_verb_lag",
    "d_Avg_Proz_Don_Anteil_Stein_von_Stein_Ges_verb_lag": "d_Proz_Don_Anteil_Stein_von_Stein_Ges_verb_lag",
    "d_Avg_Proz_Don_Anteil_Wein_von_Wein_Ges_verb_lag": "d_Proz_Don_Anteil_Wein_von_Wein_Ges_verb_lag",
    "d_Avg_Proz_Don_von_Res_Ges": "d_Proz_Don_von_Res_Ges",
    "d_Avg_Res_Ges_verb_lag_don": "d_Res_Ges_verb_lag_don",
    "d_Avg_Schwefel_Ges_verb_lag_don": "d_Schwefel_Ges_verb_lag_don",
    "d_Avg_Stein_Ges_verb_lag_don": "d_Stein_Ges_verb_lag_don",
    "d_Avg_Wein_Ges_verb_lag_don": "d_Wein_Ges_verb_lag_don",
}

# Per-account-age fields that use city context as numerator.
LEGACY_DONATION_CITY_DURATION_MAP: dict[str, str] = {
    "d_Buerger_Ges_pro_Spieldauer": "c_Buerger_Ges",
    "d_Geblev_pro_Spieldauer": "c_Geblev",
    "d_Rathauslev_pro_Spieldauer": "c_Rathauslev",
    "d_resource_workers_pro_Spieldauer": "c_resource_workers",
    "d_tradegood_workers_pro_Spieldauer": "c_tradegood_workers",
}

# Per-account-age fields that use donation/resource totals as numerator.
LEGACY_DONATION_DURATION_MAP: dict[str, str] = {
    "d_Don_Ges_pro_Spieldauer": "d_Don_Ges",
    "d_Don_Saegewerk_Ges_pro_Spieldauer": "d_Don_Saegewerk_Ges",
    "d_Don_Wonder_Ges_pro_Spieldauer": "d_Don_Wonder_Ges",
    "d_DonH_Ges_pro_Spieldauer": "d_DonH_Ges",
    "d_DonH_Luxusminen_Ges_pro_Spieldauer": "d_DonH_Luxusminen_Ges",
    "d_Holz_Ges_verb_lag_don_pro_Spieldauer": "d_Holz_Ges_verb_lag_don",
    "d_Kristall_Ges_verb_lag_don_pro_Spieldauer": "d_Kristall_Ges_verb_lag_don",
    "d_Res_Ges_verb_lag_don_pro_Spieldauer": "d_Res_Ges_verb_lag_don",
    "d_Schwefel_Ges_verb_lag_don_pro_Spieldauer": "d_Schwefel_Ges_verb_lag_don",
    "d_Stein_Ges_verb_lag_don_pro_Spieldauer": "d_Stein_Ges_verb_lag_don",
    "d_Wein_Ges_verb_lag_don_pro_Spieldauer": "d_Wein_Ges_verb_lag_don",
}

# Resource share percentages: output column -> (donation numerator, resource
# plus donation denominator).
LEGACY_DONATION_SHARE_MAP: dict[str, tuple[str, str]] = {
    "d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag": (
        "d_DonH_Ges",
        "d_Holz_Ges_verb_lag_don",
    ),
    "d_Proz_Don_Anteil_Kristall_von_Kristall_Ges_verb_lag": (
        "d_Don_Wonder_Anteil_Kristall",
        "d_Kristall_Ges_verb_lag_don",
    ),
    "d_Proz_Don_Anteil_Schwefel_von_Schwefel_Ges_verb_lag": (
        "d_Don_Wonder_Anteil_Schwefel",
        "d_Schwefel_Ges_verb_lag_don",
    ),
    "d_Proz_Don_Anteil_Stein_von_Stein_Ges_verb_lag": (
        "d_Don_Wonder_Anteil_Stein",
        "d_Stein_Ges_verb_lag_don",
    ),
    "d_Proz_Don_Anteil_Wein_von_Wein_Ges_verb_lag": (
        "d_Don_Wonder_Anteil_Wein",
        "d_Wein_Ges_verb_lag_don",
    ),
    "d_Proz_Don_von_Res_Ges": ("d_Don_Ges", "d_Res_Ges_verb_lag_don"),
}


def read_lancedb_frames(lancedb_path: Path, country: str = "DE") -> dict[str, pl.DataFrame]:
    """Read current public/raw LanceDB tables needed for SQL-gold comparison.

    `Teilnahme_AV` and `Master_Avi` require the raw country tables because the
    SQL gold counts appearances across all historical snapshots. The final
    `A_DS`, `AVI_DS`, and `I_DS` projections use the public snapshot tables,
    filtered to the requested country and later collapsed to the latest SQL
    working-table snapshot.
    """
    import lancedb

    if not lancedb_path.exists():
        raise FileNotFoundError(f"LanceDB path does not exist: {lancedb_path}")

    db = lancedb.connect(lancedb_path)
    suffix = country.lower()
    required = {
        "player_snapshot",
        "city_snapshot",
        "donation_analytics_player_island_snapshot",
        "island_snapshot",
        f"raw_avatar_{suffix}",
        f"raw_city_{suffix}",
        f"raw_island_{suffix}",
    }

    frames: dict[str, pl.DataFrame] = {}
    missing: list[str] = []
    for name in sorted(required):
        try:
            table = db.open_table(name)
        except Exception:
            missing.append(name)
            continue
        frames[name] = pl.from_arrow(table.to_arrow())
    if missing:
        raise ValueError(f"Missing required LanceDB tables: {', '.join(missing)}")

    country_code = country.upper()
    for name in (
        "player_snapshot",
        "city_snapshot",
        "donation_analytics_player_island_snapshot",
        "island_snapshot",
    ):
        if "country_code" in frames[name].columns:
            frames[name] = frames[name].filter(pl.col("country_code") == country_code)

    return frames


def read_gold_frames(gold_dir: Path) -> dict[str, pl.DataFrame]:
    """Read the five exported SQL gold CSVs using the legacy semicolon format."""
    frames: dict[str, pl.DataFrame] = {}
    for name in GOLD_OUTPUTS:
        path = gold_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Gold CSV does not exist: {path}")
        frames[name] = pl.read_csv(
            path,
            separator=";",
            null_values=[""],
            try_parse_dates=False,
        )
    return frames


def build_legacy_views(frames: dict[str, pl.DataFrame], country: str = "DE") -> dict[str, pl.DataFrame]:
    """Build SQL-shaped outputs from LanceDB frames.

    This is the verifier's main compatibility layer. It does not ask whether
    the legacy SQL model is a good canonical design; it asks whether the
    current LanceDB facts can reproduce each deterministic legacy CSV column.
    The result frames are named like the gold CSVs so `compare_outputs` can
    compare them directly.
    """
    suffix = country.lower()
    raw_avatar = frames[f"raw_avatar_{suffix}"]
    raw_city = frames[f"raw_city_{suffix}"]
    player = frames["player_snapshot"]
    city = frames["city_snapshot"]
    donation_analytics = frames["donation_analytics_player_island_snapshot"]
    island = frames["island_snapshot"]

    teilnahme = build_teilnahme_av(raw_avatar)
    master = build_master_avi(raw_city, teilnahme)

    # The legacy SQL builds Teilnahme_AV and Master_Avi from all snapshots, then
    # runs the final city/donation/island transforms on the single current SQL
    # working table. For the DE gold CSVs that working table is de_1311_14, i.e.
    # the latest snapshot in LanceDB.
    latest_player = latest_snapshot(player) # This should be get snapshot by id
    latest_city = latest_snapshot(city)
    latest_donation_analytics = latest_snapshot(donation_analytics)
    latest_island = latest_snapshot(island)
    avatar = build_legacy_avatar(latest_player)
    city2 = build_legacy_city2(latest_city)
    island_level_per_avatar = build_island_level_per_avatar(latest_island, latest_player)
    donation2 = build_legacy_donation2(latest_donation_analytics, city2, latest_player)

    city_player = aggregate_city2(city2, ("player_id",)).rename({"player_id": "t_id"})
    city_player_island = aggregate_city2(city2, ("player_id", "island_id")).rename(
        {"player_id": "m_owner_id", "island_id": "m_island_id"}
    )
    city_island = aggregate_city2(city2, ("island_id",)).rename({"island_id": "i_id"})

    donations_player = build_legacy_donation3av(donation2, city2, latest_player).rename(
        {"player_id": "t_id"} 
    )
    donations_player_island = donation2.rename(
        {"player_id": "m_owner_id", "island_id": "m_island_id"}
    )
    donations_island = build_legacy_donation4isl(donation2, city2, latest_player).rename(
        {"island_id": "i_id"}
    )
    island_agg = aggregate_island(latest_island).rename({"island_id": "i_id"})
    island_city2_counts = (
        city2.group_by("island_id")
        .agg(pl.len().cast(pl.Float64).alias("i_Anz_Staedte_pro_Insel"))
        .rename({"island_id": "i_id"})
    )
    island_agg = (
        island_agg.join(island_city2_counts, on="i_id", how="left")
        .join(island_level_per_avatar, on="i_id", how="left")
        .with_columns(pl.col("i_Anz_Staedte_pro_Insel").fill_null(0.0))
    )
    inhabited_island_count = float(
        island_agg.filter(pl.col("i_Anz_Staedte_pro_Insel") > 0).height
    )
    island_city_denominator = (
        pl.when(pl.col("i_Anz_Staedte_pro_Insel") == 0)
        .then(1.0)
        .otherwise(pl.col("i_Anz_Staedte_pro_Insel"))
    )
    island_agg = island_agg.with_columns(
        pl.lit(inhabited_island_count).alias("i_Anz_Inseln_per_DB"),
        # The legacy SQL table defines these columns but never updates them.
        pl.lit(0.0).alias("i_Avg_Resource_lev_per_DB"),
        pl.lit(0.0).alias("i_Avg_Tradegood_lev_per_DB"),
        pl.lit(0.0).alias("i_Avg_Wonder_lev_per_DB"),
        safe_divide(
            pl.col("i_Sub_Noetig_nextlev_Resource"),
            island_city_denominator,
        ).alias("i_Don_Saegewerk_noetig_Durchschnitt"),
        safe_divide(
            pl.col("i_Sub_Noetig_nextlev_Wonder"),
            island_city_denominator,
        ).alias("i_Don_Wonder_noetig_Durchschnitt"),
        safe_divide(
            pl.col("i_Sub_Noetig_nextlev_Tradegood"),
            island_city_denominator,
        ).alias("i_DonH_Luxusminen_noetig_Durchschnitt"),
    )
    avatar_for_player = avatar.with_columns(pl.col("a_id").alias("t_id"))
    avatar_for_avi = avatar.with_columns(pl.col("a_id").alias("m_owner_id"))
    city_player = city_player.join(
        island_level_per_avatar,
        left_on="c_island_id",
        right_on="i_id",
        how="left",
    )

    a_ds = (
        teilnahme.rename(
            {
                "Anzahl_Vorhanden": "t_Anzahl_vorhanden",
                "groupid": "t_groupid",
                "id": "t_id",
            }
        )
        .join(city_player.join(avatar_for_player, on="t_id", how="left"), on="t_id", how="left")
        .join(donations_player, on="t_id", how="left")
        .sort("t_id")
    )

    avi_ds = (
        master.rename(
            {
                "Cities_Vorhanden": "m_Cities_vorhanden",
                "owner_id": "m_owner_id",
                "island_id": "m_island_id",
            }
        )
        .join(city_player_island, on=["m_owner_id", "m_island_id"], how="left")
        .join(avatar_for_avi, on="m_owner_id", how="left")
        .join(donations_player_island, on=["m_owner_id", "m_island_id"], how="left")
        .join(island_agg, left_on="m_island_id", right_on="i_id", how="left")
        .with_columns(pl.col("m_island_id").alias("i_id"))
        .sort(["m_island_id", "m_owner_id"])
    )

    i_ds_columns = [
        "i_id",
        *[col for col in city_island.columns if col != "i_id"],
        *[col for col in donations_island.columns if col != "i_id"],
        *[col for col in island_agg.columns if col != "i_id"],
    ]
    i_ds = (
        island_agg.join(city_island, on="i_id", how="left")
        .join(donations_island, on="i_id", how="left")
        .sort("i_id")
        .select(i_ds_columns)
    )

    # `player` is read intentionally even though the first comparison pass
    # reconstructs legacy views from raw/city/island grains. This assert keeps
    # that dependency explicit and fails early if the public table was empty.
    if player.is_empty() and not raw_avatar.is_empty():
        raise ValueError("player_snapshot is empty while raw avatar data exists")

    return {
        "Teilnahme_AV": teilnahme,
        "Master_Avi": master,
        "A_DS": a_ds,
        "AVI_DS": avi_ds,
        "I_DS": i_ds,
    }


def build_teilnahme_av(raw_avatar: pl.DataFrame) -> pl.DataFrame:
    """Rebuild SQL `Teilnahme_AV`: player appearance counts across snapshots."""
    return (
        raw_avatar.group_by("id")
        .agg(pl.len().cast(pl.Float64).alias("Anzahl_Vorhanden"))
        .with_columns(pl.lit(None).alias("groupid"))
        .select("groupid", "id", "Anzahl_Vorhanden")
        .sort("id")
    )


def build_master_avi(raw_city: pl.DataFrame, teilnahme_av: pl.DataFrame) -> pl.DataFrame:
    """Rebuild SQL `Master_Avi`: player-island city appearances plus participation."""
    return (
        raw_city.group_by(["owner_id", "island_id"])
        .agg(pl.len().cast(pl.Float64).alias("Cities_Vorhanden"))
        .join(
            teilnahme_av.select(
                pl.col("id").alias("owner_id"),
                pl.col("Anzahl_Vorhanden").alias("Anzahl_Teilnahme"),
            ),
            on="owner_id",
            how="left",
        )
        .sort(["owner_id", "island_id"])
    )


def build_legacy_avatar(player: pl.DataFrame) -> pl.DataFrame:
    """Reconstruct direct legacy `avatar` fields used in A_DS and AVI_DS.

    Q9 rebuilds the SQL `avatar` table at the single working-table grain; Q31
    then broadcasts `Anz_Av_per_DB` and `Avg_Spieldauer` onto every row. In the
    verifier this comes from the latest `player_snapshot` frame.
    """
    if player.is_empty():
        return pl.DataFrame(schema={"a_id": pl.Utf8})

    required = set(AVATAR_MAP.values())
    missing = sorted(required.difference(player.columns))
    if missing:
        raise ValueError(f"Missing required player columns for avatar mapping: {missing}")

    avg_spieldauer = player.select(pl.col("account_age_days").mean()).item()
    avatar_count = float(player.select("player_id").unique().height)
    selected = player.select(
        *[pl.col(src).alias(dst) for dst, src in AVATAR_MAP.items()],
    )
    if selected.schema["a_Registration_time_normal"].is_temporal():
        selected = selected.with_columns(
            pl.col("a_Registration_time_normal")
            .dt.strftime("%Y-%m-%dT%H:%M:%S.000000")
            .alias("a_Registration_time_normal")
        )
    return selected.with_columns(
        pl.lit(avatar_count).alias("a_Anz_Av_per_DB"),
        pl.lit(avg_spieldauer).alias("a_Avg_Spieldauer"),
    )


def build_island_level_per_avatar(island: pl.DataFrame, player: pl.DataFrame) -> pl.DataFrame:
    """Reconstruct island-derived `c_Avg_*_lev_per_Av` aliases.

    Q30 stores these fields on the SQL `island` table as
    `SUM(island level) / COUNT(avatar.id)`. Later final SELECTs alias the
    unqualified island columns with a misleading `c_` prefix.
    """
    if island.is_empty():
        return pl.DataFrame(schema={"i_id": pl.Utf8})

    player_count = player.select("player_id").unique().height if not player.is_empty() else 0
    denominator = float(player_count) if player_count else 1.0
    sum_columns = {
        output_column: f"_sum_{source_column}"
        for output_column, source_column in ISLAND_LEVEL_PER_AVATAR_MAP.items()
    }
    totals = island.select(
        *[
            pl.col(source_column).sum().alias(sum_columns[output_column])
            for output_column, source_column in ISLAND_LEVEL_PER_AVATAR_MAP.items()
        ]
    ).row(0, named=True)
    values = {
        output_column: float(totals[sum_columns[output_column]]) / denominator
        for output_column in ISLAND_LEVEL_PER_AVATAR_MAP
    }
    return island.select(pl.col("island_id").alias("i_id")).with_columns(
        *[pl.lit(value).alias(column) for column, value in values.items()]
    )


# TODO: This should not just return the latest snapshot but should take an ID for which snapshot to return
def latest_snapshot(df: pl.DataFrame) -> pl.DataFrame:
    """Return the current SQL working-table snapshot used by final gold outputs.

    The legacy script builds `Teilnahme_AV` and `Master_Avi` from all DE
    snapshot schemas, but the later `city`, `avatar`, `donation`, and `island`
    working tables are single-table inputs for Q17-Q46. In the gold data these
    working tables match the latest LanceDB snapshot, `de_1311_14`.
    """
    if df.is_empty() or "snapshot_date" not in df.columns:
        return df
    latest_date = df.select(pl.col("snapshot_date").max()).item()
    return df.filter(pl.col("snapshot_date") == latest_date)


def build_legacy_city2(city: pl.DataFrame) -> pl.DataFrame:
    """Reconstruct the mixed aggregation semantics of legacy SQL `city2`.

    Q17 updates many `city` columns in-place with sums grouped by
    `(owner_id, island_id)`, then creates `city2` with:

        CREATE TABLE city2 AS SELECT * FROM city GROUP BY owner_id, island_id;

    In permissive MySQL, `SELECT * ... GROUP BY owner_id, island_id` returns
    non-grouped, non-aggregated columns from a representative row. It does not
    sum every selected column. The gold CSVs show that representative row is the
    lowest `city.id` in each group after the legacy primary-key table rebuild.

    Therefore this verifier intentionally mirrors the SQL's mixed behavior:
    columns touched by the Q17 `UPDATE ... SUM(...)` statements are summed,
    while raw city columns such as `level`, `resource`, and `tradegood1..4`
    come from the representative city row.
    """
    if city.is_empty():
        return pl.DataFrame(schema={"player_id": pl.Utf8, "island_id": pl.Utf8})

    work = city.with_columns(
        pl.col("is_capital").cast(pl.Int64).alias("is_capital_int"),
        (pl.col("wine_stored") + pl.col("marble_stored") + pl.col("crystal_stored") + pl.col("sulfur_stored")).alias(
            "QKWS_lagernd"
        ),
        (pl.col("resource_workers") + pl.col("tradegood_workers")).alias("Resworkers_Holz_Lux"),
    )

    representative = (
        work.sort("city_id")
        .group_by(["player_id", "island_id"], maintain_order=True)
        .agg(
            pl.col("city_id").first().alias("city_id"),
            pl.col("city_id").first().alias("c_id"),
            pl.col("player_id").first().alias("c_owner_id"),
            pl.col("island_id").first().alias("c_island_id"),
            *[pl.col(src).first().alias(dst) for dst, src in CITY_REPRESENTATIVE_MAP.items()],
        )
    )
    summed_aggs: list[pl.Expr] = [pl.col(src).sum().alias(dst) for dst, src in CITY_SUM_MAP.items()]
    summed_aggs.extend(
        [
            pl.col("QKWS_lagernd").sum().alias("c_QKWS_lagernd"),
            pl.col("Resworkers_Holz_Lux").sum().alias("c_Resworkers_Holz_Lux"),
        ]
    )
    summed = work.group_by(["player_id", "island_id"]).agg(summed_aggs)
    city2 = representative.join(summed, on=["player_id", "island_id"], how="left")
    city_count = float(city2.height)
    # Q32 counts rows in already-collapsed `city2`, so both city and island
    # counts are per player-island row counts rather than raw-city counts.
    return city2.with_columns(
        pl.len().over("player_id").cast(pl.Float64).alias("c_Anz_Cities_per_Av"),
        pl.len().over("player_id").cast(pl.Float64).alias("c_Anz_Ins_per_Av"),
        pl.lit(city_count).alias("c_Anz_Cities_per_DB"),
        pl.lit(0.0).alias("c_GovReslev"),
    )


def aggregate_city2(city2: pl.DataFrame, keys: tuple[str, ...]) -> pl.DataFrame:
    """Reconstruct `city3Av` and `city4Isl` from legacy `city2`.

    Q34 and Q36 repeat the same permissive MySQL pattern:

        CREATE TABLE city3Av AS SELECT * FROM city3a GROUP BY owner_id;
        CREATE TABLE city4Isl AS SELECT * FROM city4I GROUP BY island_id;

    The fields already summed into `city2` are summed again at the player or
    island level. Raw representative fields are carried forward from the lowest
    `city_id`, matching the observed gold CSV behavior. This is a parity shim
    for the legacy outputs only; it is not the canonical Dagster panel model.
    """
    if city2.is_empty():
        return pl.DataFrame(schema={key: pl.Utf8 for key in keys})

    sum_columns = [*CITY_SUM_MAP.keys(), "c_QKWS_lagernd", "c_Resworkers_Holz_Lux", "c_GovReslev"]
    representative_columns = [
        "c_id",
        "c_owner_id",
        "c_island_id",
        "c_Anz_Cities_per_Av",
        "c_Anz_Cities_per_DB",
        "c_Anz_Ins_per_Av",
        *CITY_REPRESENTATIVE_MAP.keys(),
    ]
    avg_expressions: list[pl.Expr]
    if keys == ("player_id", "island_id"):
        avg_expressions = [pl.lit(0.0).alias(col) for col in CITY_AVG_MAP]
    else:
        avg_expressions = [pl.col(src).mean().alias(dst) for dst, src in CITY_AVG_MAP.items()]
    return (
        city2.sort("city_id")
        .group_by(list(keys), maintain_order=True)
        .agg(
            *[pl.col(col).first().alias(col) for col in representative_columns],
            *[pl.col(col).sum().alias(col) for col in sum_columns],
            *avg_expressions,
        )
    )


def build_legacy_donation2(
    donation_analytics: pl.DataFrame,
    city2: pl.DataFrame,
    player: pl.DataFrame,
) -> pl.DataFrame:
    """Project legacy `donation2` row-level analytics from public donation facts.

    This projection is intentionally verifier-only. The canonical pipeline
    exposes these as clean analytics fields in
    `donation_analytics_player_island_snapshot`; the SQL-gold verifier maps the
    old `d_*` names from that public table so reviewers can audit the legacy
    CSV columns from the new LanceDB output data.

    Database-wide broadcast constants such as `d_Anz_Don_per_DB` and
    `d_Don_pro_DB` are intentionally not reproduced.
    """
    if donation_analytics.is_empty() or city2.is_empty():
        return pl.DataFrame(schema={"player_id": pl.Utf8, "island_id": pl.Utf8})

    required = {
        "player_id",
        "island_id",
        "wonder_donations_total",
        "sawmill_donations_total",
        "luxury_mine_donations_total",
        "donations_total",
        "wonder_wine_donations_allocated",
        "wonder_marble_donations_allocated",
        "wonder_crystal_donations_allocated",
        "wonder_sulfur_donations_allocated",
        "luxury_mine_wine_donations",
        "luxury_mine_marble_donations",
        "luxury_mine_crystal_donations",
        "luxury_mine_sulfur_donations",
    }
    missing = sorted(required.difference(donation_analytics.columns))
    if missing:
        raise ValueError(f"Missing required donation analytics columns: {missing}")

    per_player_island = donation_analytics.select(
        "player_id",
        "island_id",
        "wonder_donations_total",
        "sawmill_donations_total",
        "luxury_mine_donations_total",
        "donations_total",
        "wonder_wine_donations_allocated",
        "wonder_marble_donations_allocated",
        "wonder_crystal_donations_allocated",
        "wonder_sulfur_donations_allocated",
        "luxury_mine_wine_donations",
        "luxury_mine_marble_donations",
        "luxury_mine_crystal_donations",
        "luxury_mine_sulfur_donations",
    )

    city_context = city2.select(
        "player_id",
        "island_id",
        "c_Anz_Cities_per_Av",
        "c_Buerger_Ges",
        "c_Geblev",
        "c_Holz_Ges_verb_lag",
        "c_Kristall_Ges_verb_lag",
        "c_priests",
        "c_Rathauslev",
        "c_Res_Ges_verb_lag",
        "c_resource_workers",
        "c_Schwefel_Ges_verb_lag",
        "c_Stein_Ges_verb_lag",
        "c_tradegood_workers",
        "c_Wein_Ges_verb_lag",
    )
    player_context = player.select(
        pl.col("player_id"),
        pl.col("account_age_days").alias("a_Spieldauer"),
    )

    result = (
        per_player_island.join(city_context, on=["player_id", "island_id"], how="left")
        .join(player_context, on="player_id", how="left")
        .with_columns(
            pl.col("player_id").alias("d_avatar_id"),
            pl.col("island_id").alias("d_island_id"),
            pl.col("donations_total").alias("d_gold"),
            pl.col("donations_total").alias("d_Don_Ges"),
            pl.col("sawmill_donations_total").alias("d_Don_Saegewerk_Ges"),
            pl.col("wonder_donations_total").alias("d_Don_Wonder_Ges"),
            pl.col("luxury_mine_donations_total").alias("d_DonH_Luxusminen_Ges"),
            (pl.col("sawmill_donations_total") + pl.col("luxury_mine_donations_total")).alias(
                "d_DonH_Ges"
            ),
            pl.col("wonder_wine_donations_allocated").alias("d_Don_Wonder_Anteil_Wein"),
            pl.col("wonder_marble_donations_allocated").alias("d_Don_Wonder_Anteil_Stein"),
            pl.col("wonder_crystal_donations_allocated").alias(
                "d_Don_Wonder_Anteil_Kristall"
            ),
            pl.col("wonder_sulfur_donations_allocated").alias(
                "d_Don_Wonder_Anteil_Schwefel"
            ),
            pl.col("luxury_mine_wine_donations").alias("d_DonH_fuer_Weinreben"),
            pl.col("luxury_mine_marble_donations").alias("d_DonH_fuer_Steinbruch"),
            pl.col("luxury_mine_crystal_donations").alias("d_DonH_fuer_Kristallmine"),
            pl.col("luxury_mine_sulfur_donations").alias("d_DonH_fuer_Schwefelgrube"),
        )
    )

    result = result.with_columns(
        (pl.col("c_Holz_Ges_verb_lag") + pl.col("d_DonH_Ges")).alias(
            "d_Holz_Ges_verb_lag_don"
        ),
        (pl.col("c_Kristall_Ges_verb_lag") + pl.col("d_Don_Wonder_Anteil_Kristall")).alias(
            "d_Kristall_Ges_verb_lag_don"
        ),
        (pl.col("c_Res_Ges_verb_lag") + pl.col("d_Don_Ges")).alias(
            "d_Res_Ges_verb_lag_don"
        ),
        (pl.col("c_Schwefel_Ges_verb_lag") + pl.col("d_Don_Wonder_Anteil_Schwefel")).alias(
            "d_Schwefel_Ges_verb_lag_don"
        ),
        (pl.col("c_Stein_Ges_verb_lag") + pl.col("d_Don_Wonder_Anteil_Stein")).alias(
            "d_Stein_Ges_verb_lag_don"
        ),
        (pl.col("c_Wein_Ges_verb_lag") + pl.col("d_Don_Wonder_Anteil_Wein")).alias(
            "d_Wein_Ges_verb_lag_don"
        ),
    )
    result = result.with_columns(
        safe_percent(pl.col("d_DonH_Ges"), pl.col("d_Holz_Ges_verb_lag_don")).alias(
            "d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag"
        ),
        safe_percent(
            pl.col("d_Don_Wonder_Anteil_Kristall"),
            pl.col("d_Kristall_Ges_verb_lag_don"),
        ).alias("d_Proz_Don_Anteil_Kristall_von_Kristall_Ges_verb_lag"),
        safe_percent(
            pl.col("d_Don_Wonder_Anteil_Schwefel"),
            pl.col("d_Schwefel_Ges_verb_lag_don"),
        ).alias("d_Proz_Don_Anteil_Schwefel_von_Schwefel_Ges_verb_lag"),
        safe_percent(
            pl.col("d_Don_Wonder_Anteil_Stein"),
            pl.col("d_Stein_Ges_verb_lag_don"),
        ).alias("d_Proz_Don_Anteil_Stein_von_Stein_Ges_verb_lag"),
        safe_percent(
            pl.col("d_Don_Wonder_Anteil_Wein"),
            pl.col("d_Wein_Ges_verb_lag_don"),
        ).alias("d_Proz_Don_Anteil_Wein_von_Wein_Ges_verb_lag"),
        safe_percent(pl.col("d_Don_Ges"), pl.col("d_Res_Ges_verb_lag_don")).alias(
            "d_Proz_Don_von_Res_Ges"
        ),
    )
    result = result.with_columns(
        _legacy_positive_ratio("d_Don_Ges", "c_Buerger_Ges").alias("d_Don_pro_Buerger_Ges"),
        _legacy_positive_ratio("d_Don_Ges", "c_Anz_Cities_per_Av").alias("d_Don_pro_City"),
        _legacy_positive_ratio("d_Don_Wonder_Ges", "c_priests").alias("d_Don_pro_Priester"),
        _legacy_positive_ratio("d_Don_Ges", "c_Rathauslev").alias("d_Don_pro_Rathauslev"),
        _legacy_positive_ratio("d_Don_Saegewerk_Ges", "c_resource_workers").alias(
            "d_Don_pro_Resource_Worker"
        ),
        _legacy_positive_ratio("d_DonH_Luxusminen_Ges", "c_tradegood_workers").alias(
            "d_Don_pro_Tradegood_Worker"
        ),
    )
    result = result.with_columns(
        _legacy_duration_ratio("c_Buerger_Ges").alias("d_Buerger_Ges_pro_Spieldauer"),
        _legacy_duration_ratio("d_Don_Ges").alias("d_Don_Ges_pro_Spieldauer"),
        _legacy_duration_ratio("d_Don_Saegewerk_Ges").alias(
            "d_Don_Saegewerk_Ges_pro_Spieldauer"
        ),
        _legacy_duration_ratio("d_Don_Wonder_Ges").alias("d_Don_Wonder_Ges_pro_Spieldauer"),
        _legacy_duration_ratio("d_DonH_Ges").alias("d_DonH_Ges_pro_Spieldauer"),
        _legacy_duration_ratio("d_DonH_Luxusminen_Ges").alias(
            "d_DonH_Luxusminen_Ges_pro_Spieldauer"
        ),
        _legacy_duration_ratio("c_Geblev").alias("d_Geblev_pro_Spieldauer"),
        _legacy_duration_ratio("d_Holz_Ges_verb_lag_don").alias(
            "d_Holz_Ges_verb_lag_don_pro_Spieldauer"
        ),
        _legacy_duration_ratio("d_Kristall_Ges_verb_lag_don").alias(
            "d_Kristall_Ges_verb_lag_don_pro_Spieldauer"
        ),
        _legacy_duration_ratio("c_Rathauslev").alias("d_Rathauslev_pro_Spieldauer"),
        _legacy_duration_ratio("d_Res_Ges_verb_lag_don").alias(
            "d_Res_Ges_verb_lag_don_pro_Spieldauer"
        ),
        _legacy_duration_ratio("c_resource_workers").alias("d_resource_workers_pro_Spieldauer"),
        _legacy_duration_ratio("d_Schwefel_Ges_verb_lag_don").alias(
            "d_Schwefel_Ges_verb_lag_don_pro_Spieldauer"
        ),
        _legacy_duration_ratio("d_Stein_Ges_verb_lag_don").alias(
            "d_Stein_Ges_verb_lag_don_pro_Spieldauer"
        ),
        _legacy_duration_ratio("c_tradegood_workers").alias(
            "d_tradegood_workers_pro_Spieldauer"
        ),
        _legacy_duration_ratio("d_Wein_Ges_verb_lag_don").alias(
            "d_Wein_Ges_verb_lag_don_pro_Spieldauer"
        ),
    )
    # Q33 leaves the non-peer `Avg_*` columns at their table default on
    # `donation2`; Q40/Q43 populate them only on the player/island rollups.
    result = result.with_columns(
        *[pl.lit(0.0).alias(column) for column in LEGACY_DONATION_AVG_MAP]
    )
    internal_columns = [
        "a_Spieldauer",
        *[col for col in result.columns if col.startswith("c_")],
        *[
            "wonder_donations_total",
            "sawmill_donations_total",
            "luxury_mine_donations_total",
            "donations_total",
            "wonder_wine_donations_allocated",
            "wonder_marble_donations_allocated",
            "wonder_crystal_donations_allocated",
            "wonder_sulfur_donations_allocated",
            "luxury_mine_wine_donations",
            "luxury_mine_marble_donations",
            "luxury_mine_crystal_donations",
            "luxury_mine_sulfur_donations",
        ],
    ]
    return result.drop([col for col in internal_columns if col in result.columns])


def build_legacy_donation3av(
    donation2: pl.DataFrame,
    city2: pl.DataFrame,
    player: pl.DataFrame,
) -> pl.DataFrame:
    """Reconstruct the player-level legacy `donation3Av` projection.

    Q38 first copies `donation2`, sums the core donation fields by avatar, then
    collapses with permissive `SELECT * ... GROUP BY avatar_id`. Q39/Q40 then
    overwrite ratios, per-duration fields, and averages at the player grain.

    The odd-looking `Don_pro_City` expression mirrors the SQL join: `donation2`
    is joined back to every `city2` row for the avatar before summing
    `Don_Ges`, so the numerator is effectively repeated by the player's
    `city2` row count. Tests pin this because simplifying it would break gold
    parity.
    """
    if donation2.is_empty():
        return pl.DataFrame(schema={"player_id": pl.Utf8})

    result = _legacy_donation_rollup_base(
        donation2,
        key="player_id",
        representative_order="island_id",
        include_row_averages=True,
    ).join(_legacy_city_rollup_context(city2, player, "player_id"), on="player_id", how="left")

    result = result.with_columns(
        _legacy_positive_expr(pl.col("d_Don_Ges"), pl.col("_sum_c_Rathauslev")).alias(
            "d_Don_pro_Rathauslev"
        ),
        _legacy_positive_expr(
            pl.col("d_Don_Ges") * pl.col("_city2_count"),
            pl.col("_sum_c_Anz_Cities_per_Av"),
        ).alias("d_Don_pro_City"),
        _legacy_positive_expr(
            pl.col("d_DonH_Luxusminen_Ges"),
            pl.col("_safe_sum_c_tradegood_workers"),
        ).alias("d_Don_pro_Tradegood_Worker"),
        _legacy_positive_expr(
            pl.col("d_Don_Saegewerk_Ges"),
            pl.col("_safe_sum_c_resource_workers"),
        ).alias("d_Don_pro_Resource_Worker"),
        _legacy_positive_expr(pl.col("d_Don_Wonder_Ges"), pl.col("_safe_sum_c_priests")).alias(
            "d_Don_pro_Priester"
        ),
        _legacy_positive_expr(pl.col("d_Don_Ges"), pl.col("_sum_c_Buerger_Ges")).alias(
            "d_Don_pro_Buerger_Ges"
        ),
    )
    result = result.with_columns(
        *[
            _legacy_percent_positive_expr(pl.col(numerator), pl.col(denominator)).alias(output)
            for output, (numerator, denominator) in LEGACY_DONATION_SHARE_MAP.items()
        ],
        *[
            _legacy_positive_expr(pl.col(city_column), pl.col("_first_a_Spieldauer")).alias(output)
            for output, city_column in {
                out: f"_sum_{source}"
                for out, source in LEGACY_DONATION_CITY_DURATION_MAP.items()
            }.items()
        ],
        *[
            _legacy_positive_expr(pl.col(source), pl.col("_first_a_Spieldauer")).alias(output)
            for output, source in LEGACY_DONATION_DURATION_MAP.items()
        ],
    )
    return _drop_auxiliary_columns(result)


def build_legacy_donation4isl(
    donation2: pl.DataFrame,
    city2: pl.DataFrame,
    player: pl.DataFrame,
) -> pl.DataFrame:
    """Reconstruct the island-level legacy `donation4Isl` projection.

    Q41 sums `donation2` fields by island, Q42 recomputes ratios from island
    city context, and Q43 computes average donation/resource columns. This
    remains verifier-only compatibility output; canonical island analytics stay
    in the public LanceDB tables with clearer names and grain.
    """
    if donation2.is_empty():
        return pl.DataFrame(schema={"island_id": pl.Utf8})

    city_context = _legacy_city_rollup_context(city2, player, "island_id")
    donation_age = _legacy_donation_age_context(donation2, player, "island_id")
    percent_averages = donation2.group_by("island_id").agg(
        [
            pl.col(source).mean().alias(output)
            for output, source in LEGACY_DONATION_AVG_MAP.items()
            if source.startswith("d_Proz_")
        ]
    )
    result = (
        _legacy_donation_rollup_base(
            donation2,
            key="island_id",
            representative_order="player_id",
            include_row_averages=False,
        )
        .join(city_context, on="island_id", how="left")
        .join(donation_age, on="island_id", how="left")
        .join(percent_averages, on="island_id", how="left")
    )

    result = result.with_columns(
        _legacy_positive_expr(pl.col("d_Don_Ges"), pl.col("_sum_c_Rathauslev")).alias(
            "d_Don_pro_Rathauslev"
        ),
        _legacy_positive_expr(pl.col("d_Don_Ges"), pl.col("_city2_count")).alias(
            "d_Don_pro_City"
        ),
        _legacy_positive_expr(
            pl.col("d_DonH_Luxusminen_Ges"),
            pl.col("_safe_sum_c_tradegood_workers"),
        ).alias("d_Don_pro_Tradegood_Worker"),
        _legacy_positive_expr(
            pl.col("d_Don_Saegewerk_Ges"),
            pl.col("_safe_sum_c_resource_workers"),
        ).alias("d_Don_pro_Resource_Worker"),
        _legacy_positive_expr(pl.col("d_Don_Wonder_Ges"), pl.col("_safe_sum_c_priests")).alias(
            "d_Don_pro_Priester"
        ),
        _legacy_positive_expr(pl.col("d_Don_Ges"), pl.col("_sum_c_Buerger_Ges")).alias(
            "d_Don_pro_Buerger_Ges"
        ),
    )
    result = result.with_columns(
        *[
            _legacy_percent_positive_expr(pl.col(numerator), pl.col(denominator)).alias(output)
            for output, (numerator, denominator) in LEGACY_DONATION_SHARE_MAP.items()
        ],
        *[
            _legacy_positive_expr(pl.col(f"_sum_{source}"), pl.col("_sum_a_Spieldauer_city")).alias(
                output
            )
            for output, source in LEGACY_DONATION_CITY_DURATION_MAP.items()
        ],
        *[
            _legacy_positive_expr(pl.col(source), pl.col("_sum_a_Spieldauer_donation")).alias(
                output
            )
            for output, source in LEGACY_DONATION_DURATION_MAP.items()
        ],
        safe_divide(pl.col("d_Don_Ges"), pl.col("_city2_count")).alias("d_Avg_Don_Ges"),
        safe_divide(pl.col("d_Don_Saegewerk_Ges"), pl.col("_city2_count")).alias(
            "d_Avg_Don_Saegewerk_Ges"
        ),
        safe_divide(pl.col("d_Don_Wonder_Ges"), pl.col("_city2_count")).alias(
            "d_Avg_Don_Wonder_Ges"
        ),
        safe_divide(pl.col("d_DonH_Luxusminen_Ges"), pl.col("_city2_count")).alias(
            "d_Avg_DonH_Luxusminen_Ges"
        ),
        (
            safe_divide(pl.col("d_DonH_Ges"), pl.col("_city2_count"))
            + pl.col("_avg_c_Holz_Ges_verb_lag")
        ).alias("d_Avg_Holz_Ges_verb_lag_don"),
        (
            safe_divide(pl.col("d_Don_Wonder_Anteil_Kristall"), pl.col("_city2_count"))
            + pl.col("_avg_c_Kristall_Ges_verb_lag")
        ).alias("d_Avg_Kristall_Ges_verb_lag_don"),
        (
            safe_divide(pl.col("d_Don_Ges"), pl.col("_city2_count"))
            + pl.col("_avg_c_Res_Ges_verb_lag")
        ).alias("d_Avg_Res_Ges_verb_lag_don"),
        (
            safe_divide(pl.col("d_Don_Wonder_Anteil_Schwefel"), pl.col("_city2_count"))
            + pl.col("_avg_c_Schwefel_Ges_verb_lag")
        ).alias("d_Avg_Schwefel_Ges_verb_lag_don"),
        (
            safe_divide(pl.col("d_Don_Wonder_Anteil_Stein"), pl.col("_city2_count"))
            + pl.col("_avg_c_Stein_Ges_verb_lag")
        ).alias("d_Avg_Stein_Ges_verb_lag_don"),
        (
            safe_divide(pl.col("d_Don_Wonder_Anteil_Wein"), pl.col("_city2_count"))
            + pl.col("_avg_c_Wein_Ges_verb_lag")
        ).alias("d_Avg_Wein_Ges_verb_lag_don"),
    )
    return _drop_auxiliary_columns(result)


def _legacy_positive_ratio(numerator: str, denominator: str) -> pl.Expr:
    safe_denominator = pl.when(pl.col(denominator) == 0).then(1.0).otherwise(pl.col(denominator))
    return pl.when(pl.col(numerator) > 0).then(pl.col(numerator) / safe_denominator).otherwise(0.0)


def _legacy_duration_ratio(column: str) -> pl.Expr:
    numerator = pl.when(pl.col(column) == 0).then(1.0).otherwise(pl.col(column))
    return safe_divide(numerator, pl.col("a_Spieldauer"))


def _legacy_donation_rollup_base(
    donation2: pl.DataFrame,
    key: str,
    representative_order: str,
    include_row_averages: bool,
) -> pl.DataFrame:
    """Common Q38/Q41 rollup skeleton before ratio/average rewrites."""
    expressions: list[pl.Expr] = [
        pl.col("d_avatar_id").first().alias("d_avatar_id"),
        pl.col("d_island_id").first().alias("d_island_id"),
        *[pl.col(column).sum().alias(column) for column in LEGACY_DONATION_SUM_COLUMNS],
    ]
    if include_row_averages:
        expressions.extend(
            pl.col(source).mean().alias(output)
            for output, source in LEGACY_DONATION_AVG_MAP.items()
        )
    return (
        donation2.sort([key, representative_order])
        .group_by(key, maintain_order=True)
        .agg(expressions)
    )


def _legacy_city_rollup_context(
    city2: pl.DataFrame,
    player: pl.DataFrame,
    key: str,
) -> pl.DataFrame:
    """Summarize `city2` denominators used by legacy donation rollups.

    SQL ratio updates repeatedly join `donation2` to `city2` and use sums of
    citizens, workers, priests, levels, and account age. This helper keeps
    those denominators explicit so the donation rollup functions do not hide
    where each ratio denominator came from.
    """
    if city2.is_empty():
        return pl.DataFrame(schema={key: pl.Utf8})

    player_age = player.select(
        "player_id",
        pl.col("account_age_days").alias("_a_Spieldauer"),
    )
    work = city2.join(player_age, on="player_id", how="left")
    sum_columns = (
        "c_Anz_Cities_per_Av",
        "c_Buerger_Ges",
        "c_Geblev",
        "c_Rathauslev",
        "c_resource_workers",
        "c_tradegood_workers",
        "c_priests",
    )
    avg_columns = (
        "c_Holz_Ges_verb_lag",
        "c_Kristall_Ges_verb_lag",
        "c_Res_Ges_verb_lag",
        "c_Schwefel_Ges_verb_lag",
        "c_Stein_Ges_verb_lag",
        "c_Wein_Ges_verb_lag",
    )
    return work.group_by(key).agg(
        pl.len().cast(pl.Float64).alias("_city2_count"),
        *[pl.col(column).sum().alias(f"_sum_{column}") for column in sum_columns],
        *[pl.col(column).mean().alias(f"_avg_{column}") for column in avg_columns],
        _legacy_safe_denominator_sum("c_resource_workers").alias(
            "_safe_sum_c_resource_workers"
        ),
        _legacy_safe_denominator_sum("c_tradegood_workers").alias(
            "_safe_sum_c_tradegood_workers"
        ),
        _legacy_safe_denominator_sum("c_priests").alias("_safe_sum_c_priests"),
        pl.col("_a_Spieldauer").first().alias("_first_a_Spieldauer"),
        pl.col("_a_Spieldauer").sum().alias("_sum_a_Spieldauer_city"),
    )


def _legacy_donation_age_context(
    donation2: pl.DataFrame,
    player: pl.DataFrame,
    key: str,
) -> pl.DataFrame:
    """Sum account age over donation rows for island-level duration ratios.

    Q42/Q43 age denominators are not always based on `city2` rows. For donation
    totals they join `donation2` to `avatar`, so an avatar with donation rows on
    multiple islands contributes age once per donation row in that island
    group.
    """
    player_age = player.select(
        "player_id",
        pl.col("account_age_days").alias("_a_Spieldauer"),
    )
    return (
        donation2.select("player_id", key)
        .join(player_age, on="player_id", how="left")
        .group_by(key)
        .agg(pl.col("_a_Spieldauer").sum().alias("_sum_a_Spieldauer_donation"))
    )


def _legacy_safe_denominator_sum(column: str) -> pl.Expr:
    """Reproduce SQL `SUM(CASE WHEN denominator = 0 THEN 1 ELSE denominator END)`."""
    return pl.when(pl.col(column) == 0).then(1.0).otherwise(pl.col(column)).sum()


def _legacy_positive_expr(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Reproduce SQL ratio updates that emit 0 unless the numerator is positive."""
    return pl.when(numerator > 0).then(safe_divide(numerator, denominator)).otherwise(0.0)


def _legacy_percent_positive_expr(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Reproduce SQL percentage updates that require positive numerator and denominator."""
    return (
        pl.when((numerator > 0) & (denominator > 0))
        .then(safe_divide(numerator * 100, denominator))
        .otherwise(0.0)
    )


def _drop_auxiliary_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Remove internal denominator columns before exposing a legacy-shaped frame."""
    return df.drop([column for column in df.columns if column.startswith("_")])


def aggregate_donations(city: pl.DataFrame, keys: tuple[str, ...]) -> pl.DataFrame:
    """Aggregate duplicated city-level donation facts without double-counting.

    Public `city_snapshot` repeats player-island donation totals across all
    cities owned by that player on the island. The SQL compatibility projection
    first takes one value per `(player, island, snapshot)`, then sums to the
    requested grain.
    """
    if city.is_empty():
        return pl.DataFrame(schema={key: pl.Utf8 for key in keys})

    base_keys = ["player_id", "island_id", "snapshot_id"]
    donation_columns = (
        "wonder_donations_total",
        "sawmill_donations_total",
        "luxury_mine_donations_total",
        "donations_total",
    )
    per_player_island_snapshot = (
        city.group_by(base_keys)
        .agg([pl.col(col).max().alias(col) for col in donation_columns])
        .with_columns(
            (
                pl.col("sawmill_donations_total") + pl.col("luxury_mine_donations_total")
            ).alias("sawmill_and_luxury_mine_donations_total")
        )
    )

    return per_player_island_snapshot.group_by(list(keys)).agg(
        [pl.col(src).sum().alias(dst) for dst, src in DONATION_SUM_MAP.items()]
    )


def aggregate_island(island: pl.DataFrame) -> pl.DataFrame:
    """Map current island snapshot facts to legacy `i_*` names."""
    if island.is_empty():
        return pl.DataFrame(schema={"island_id": pl.Utf8})

    aggs: list[pl.Expr] = [
        pl.col(src).sum().alias(dst) for dst, src in ISLAND_SUM_MAP.items()
    ]
    aggs.append(pl.col("luxury_resource_type").drop_nulls().first().alias("i_tradegood"))
    return island.group_by("island_id").agg(aggs)


def compare_outputs(
    gold_frames: dict[str, pl.DataFrame],
    actual_frames: dict[str, pl.DataFrame],
    detail_dir: Path,
) -> list[ComparisonResult]:
    """Compare every gold output to its reconstructed LanceDB counterpart."""
    detail_dir.mkdir(parents=True, exist_ok=True)
    return [
        compare_frame(gold_frames[name], actual_frames[name], COMPARISON_SPECS[name], detail_dir)
        for name in GOLD_OUTPUTS
    ]


def compare_frame(
    gold: pl.DataFrame,
    actual: pl.DataFrame,
    spec: ComparisonSpec,
    detail_dir: Path,
) -> ComparisonResult:
    """Compare one output table and write machine-readable detail artifacts.

    The comparison boundary is intentional:

    - keys must match exactly and must be unique on both sides;
    - only columns present in both frames are value-compared;
    - SQL-only columns are listed in `*_unmapped_columns.csv` so a reviewer can
      see exactly what is outside the current verification claim;
    - numeric columns use a small absolute tolerance for float arithmetic.
    """
    gold = _normalize_key_columns(gold, spec.key_columns)
    actual = _normalize_key_columns(actual, spec.key_columns)

    mapped_columns = tuple(
        col for col in gold.columns if col in actual.columns and col not in spec.key_columns
    )
    unmapped_columns = tuple(col for col in gold.columns if col not in actual.columns)

    gold_duplicate_keys = gold.height - gold.select(spec.key_columns).unique().height
    actual_duplicate_keys = actual.height - actual.select(spec.key_columns).unique().height

    gold_keys = gold.select(spec.key_columns).unique()
    actual_keys = actual.select(spec.key_columns).unique()
    gold_only = gold_keys.join(actual_keys, on=list(spec.key_columns), how="anti")
    actual_only = actual_keys.join(gold_keys, on=list(spec.key_columns), how="anti")

    joined = gold.select([*spec.key_columns, *mapped_columns]).join(
        actual.select([*spec.key_columns, *mapped_columns]),
        on=list(spec.key_columns),
        how="inner",
        suffix="__actual",
    )

    numeric_columns = {
        col
        for col in mapped_columns
        if _column_is_numeric(joined.get_column(col))
        and _column_is_numeric(joined.get_column(f"{col}__actual"))
    }
    mismatch_count, mismatch_samples, mismatch_counts = _find_mismatches(
        joined, spec, mapped_columns, numeric_columns
    )

    prefix = spec.name.lower()
    mismatch_path = detail_dir / f"{prefix}_mismatches.csv"
    mismatch_counts_path = detail_dir / f"{prefix}_mismatch_counts.csv"
    gold_only_path = detail_dir / f"{prefix}_sql_only_keys.csv"
    actual_only_path = detail_dir / f"{prefix}_lancedb_only_keys.csv"
    unmapped_path = detail_dir / f"{prefix}_unmapped_columns.csv"

    _write_dicts_csv(mismatch_samples, mismatch_path)
    _write_mismatch_counts_csv(mismatch_counts, mismatch_counts_path)
    gold_only.write_csv(gold_only_path)
    actual_only.write_csv(actual_only_path)
    pl.DataFrame({"column": list(unmapped_columns)}).write_csv(unmapped_path)

    return ComparisonResult(
        name=spec.name,
        key_columns=spec.key_columns,
        gold_rows=gold.height,
        actual_rows=actual.height,
        mapped_columns=mapped_columns,
        unmapped_columns=unmapped_columns,
        gold_duplicate_keys=gold_duplicate_keys,
        actual_duplicate_keys=actual_duplicate_keys,
        gold_only_keys=gold_only.height,
        actual_only_keys=actual_only.height,
        mismatch_count=mismatch_count,
        mismatch_path=mismatch_path,
        mismatch_counts_path=mismatch_counts_path,
        gold_only_path=gold_only_path,
        actual_only_path=actual_only_path,
        unmapped_path=unmapped_path,
    )


def write_markdown_report(
    results: list[ComparisonResult],
    report_path: Path,
    lancedb_path: Path,
    gold_dir: Path,
    detail_dir: Path,
) -> None:
    """Write the reviewer-facing summary of a verification run."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# LanceDB vs SQL Gold Verification",
        "",
        f"Generated: {generated_at}",
        "",
        f"- LanceDB: `{lancedb_path}`",
        f"- SQL gold CSVs: `{gold_dir}`",
        f"- Detail artifacts: `{detail_dir}`",
        "",
        "## Summary",
        "",
        "| Output | Status | Gold rows | Lance rows | Mapped columns | Unmapped SQL columns | SQL-only keys | Lance-only keys | Mismatches |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        status = "FAIL" if result.failed else "PASS"
        lines.append(
            "| "
            f"{result.name} | {status} | {result.gold_rows} | {result.actual_rows} | "
            f"{len(result.mapped_columns)} | {len(result.unmapped_columns)} | "
            f"{result.gold_only_keys} | {result.actual_only_keys} | {result.mismatch_count} |"
        )

    lines.extend(
        [
            "",
            "## Coverage Notes",
            "",
            "This report verifies only columns with explicit mappings from the legacy SQL output to the current Dagster/LanceDB model.",
            "Columns that are selected ambiguously by the legacy SQL or have no current public-table equivalent are reported as unmapped rather than treated as verified.",
            "Legacy donation columns are reconstructed from `donation_analytics_player_island_snapshot`, not from donation fields duplicated on `city_snapshot`.",
            "The only expected donation columns that remain unmapped are `d_Anz_Don_per_DB` and `d_Don_pro_DB`. They are database-wide donation broadcast constants copied onto every legacy row, not row-level analytics in the canonical LanceDB model.",
            f"Mismatch CSVs contain at most {MAX_MISMATCH_SAMPLES} sample rows per output; the summary table shows the full mismatch count.",
            "",
            "## Detail Files",
            "",
        ]
    )
    for result in results:
        lines.extend(
            [
                f"### {result.name}",
                "",
                f"- Keys: `{', '.join(result.key_columns)}`",
                f"- Mapped columns: {len(result.mapped_columns)}",
                f"- Unmapped SQL columns: {len(result.unmapped_columns)}",
                f"- Mismatches: `{result.mismatch_path}`",
                f"- Mismatch counts: `{result.mismatch_counts_path}`",
                f"- SQL-only keys: `{result.gold_only_path}`",
                f"- Lance-only keys: `{result.actual_only_path}`",
                f"- Unmapped columns: `{result.unmapped_path}`",
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_verification(
    lancedb_path: Path,
    gold_dir: Path,
    report_path: Path,
    detail_dir: Path,
    country: str = "DE",
) -> list[ComparisonResult]:
    """Run the full load, projection, comparison, and report-writing workflow."""
    lancedb_frames = read_lancedb_frames(lancedb_path, country)
    gold_frames = read_gold_frames(gold_dir)
    actual_frames = build_legacy_views(lancedb_frames, country)
    results = compare_outputs(gold_frames, actual_frames, detail_dir)
    write_markdown_report(results, report_path, lancedb_path, gold_dir, detail_dir)
    return results


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser used by `scripts/verify_lancedb_against_gold.py`."""
    parser = argparse.ArgumentParser(
        description="Compare existing Ikariam LanceDB output against SQL gold CSVs."
    )
    parser.add_argument("--lancedb", type=Path, default=Path("output/ikariam.lancedb"))
    parser.add_argument("--gold-dir", type=Path, default=Path("data/gold_standard"))
    parser.add_argument("--report", type=Path, default=Path("docs/lancedb_vs_sql_gold.md"))
    parser.add_argument(
        "--detail-dir",
        type=Path,
        default=Path("output/verification/lancedb_vs_sql_gold"),
    )
    parser.add_argument("--country", default="DE")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: print summary lines and return nonzero on failures."""
    args = build_parser().parse_args(argv)
    results = run_verification(
        lancedb_path=args.lancedb,
        gold_dir=args.gold_dir,
        report_path=args.report,
        detail_dir=args.detail_dir,
        country=args.country,
    )
    failed = [result for result in results if result.failed]
    for result in results:
        status = "FAIL" if result.failed else "PASS"
        print(
            f"{result.name}: {status} "
            f"mapped={len(result.mapped_columns)} unmapped={len(result.unmapped_columns)} "
            f"sql_only={result.gold_only_keys} lancedb_only={result.actual_only_keys} "
            f"mismatches={result.mismatch_count}"
        )
    return 1 if failed else 0


def _normalize_key_columns(df: pl.DataFrame, keys: tuple[str, ...]) -> pl.DataFrame:
    missing = [key for key in keys if key not in df.columns]
    if missing:
        raise ValueError(f"Missing key columns {missing} in frame with columns {df.columns}")
    return df.with_columns(pl.col(key).cast(pl.Utf8) for key in keys)


def _column_is_numeric(series: pl.Series) -> bool:
    values = [value for value in series.to_list() if not _is_null(value)]
    if not values:
        return False
    for value in values:
        if _as_float(value) is None:
            return False
    return True


def _find_mismatches(
    joined: pl.DataFrame,
    spec: ComparisonSpec,
    mapped_columns: tuple[str, ...],
    numeric_columns: set[str],
) -> tuple[int, list[dict[str, Any]], dict[str, int]]:
    mismatch_count = 0
    mismatch_counts: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    actual_suffix = "__actual"
    for row in joined.iter_rows(named=True):
        key = {key_col: row[key_col] for key_col in spec.key_columns}
        for col in mapped_columns:
            gold_value = row[col]
            actual_value = row[f"{col}{actual_suffix}"]
            if _values_match(gold_value, actual_value, col in numeric_columns, spec.tolerance):
                continue
            mismatch_count += 1
            mismatch_counts[col] = mismatch_counts.get(col, 0) + 1
            if len(samples) >= MAX_MISMATCH_SAMPLES:
                continue
            diff: float | None = None
            if col in numeric_columns:
                left = _as_float(gold_value)
                right = _as_float(actual_value)
                if left is not None and right is not None:
                    diff = abs(left - right)
            samples.append(
                {
                    **key,
                    "column": col,
                    "sql_value": _display_value(gold_value),
                    "lancedb_value": _display_value(actual_value),
                    "absolute_difference": diff,
                }
            )
    return mismatch_count, samples, mismatch_counts


def _values_match(left: Any, right: Any, numeric: bool, tolerance: float) -> bool:
    if _is_null(left) and _is_null(right):
        return True
    if _is_null(left) != _is_null(right):
        return False
    if numeric:
        left_float = _as_float(left)
        right_float = _as_float(right)
        if left_float is None or right_float is None:
            return False
        return abs(left_float - right_float) <= tolerance
    return str(left) == str(right)


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value == "":
        return True
    return False


def _as_float(value: Any) -> float | None:
    if _is_null(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _display_value(value: Any) -> str | None:
    if _is_null(value):
        return None
    return str(value)


def _write_dicts_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if rows:
        normalized = [
            {key: None if value is None else str(value) for key, value in row.items()}
            for row in rows
        ]
        columns = sorted({key for row in normalized for key in row})
        data = {column: [row.get(column) for row in normalized] for column in columns}
        pl.DataFrame(data, schema={column: pl.Utf8 for column in columns}).write_csv(path)
        return
    pl.DataFrame(
        schema={
            "column": pl.Utf8,
            "sql_value": pl.Utf8,
            "lancedb_value": pl.Utf8,
            "absolute_difference": pl.Float64,
        }
    ).write_csv(path)


def _write_mismatch_counts_csv(counts: dict[str, int], path: Path) -> None:
    rows = [
        {"column": column, "mismatch_count": count}
        for column, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    if rows:
        pl.DataFrame(rows).write_csv(path)
        return
    pl.DataFrame(schema={"column": pl.Utf8, "mismatch_count": pl.Int64}).write_csv(path)
