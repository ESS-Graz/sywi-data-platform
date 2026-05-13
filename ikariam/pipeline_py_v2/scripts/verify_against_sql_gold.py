from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ikariam_pipeline.config import load_config
from ikariam_pipeline.derived import build_derived
from ikariam_pipeline.io_db import load_all_raw
from ikariam_pipeline.io_files import read_building_costs
from ikariam_pipeline.run_pipeline import _filter_prelaunch_players
from ikariam_pipeline.transforms.building_costs import join_building_costs
from ikariam_pipeline.transforms.city_agg import aggregate_to_player_island
from ikariam_pipeline.transforms.city_metrics import compute_city_metrics
from ikariam_pipeline.transforms.donations import process_donations
from ikariam_pipeline.transforms.final_datasets import build_panels
from ikariam_pipeline.transforms.higher_agg import (
    aggregate_by_avatar,
    aggregate_by_island,
    donations_by_avatar,
    donations_by_island,
)
from ikariam_pipeline.transforms.islands import enrich_islands
from ikariam_pipeline.transforms.player_duration import enrich_avatars

TOLERANCE = 1e-6


@dataclass(frozen=True)
class CompareSpec:
    sql_file: str
    table_name: str
    sql_keys: tuple[str, ...]
    py_keys: tuple[str, ...]


COMPARE_SPECS: tuple[CompareSpec, ...] = (
    CompareSpec("A_DS.csv", "player_latest", ("t_id",), ("player_id",)),
    CompareSpec(
        "AVI_DS.csv",
        "player_island_latest",
        ("m_owner_id", "m_island_id"),
        ("player_id", "island_id"),
    ),
    CompareSpec("I_DS.csv", "island_latest", ("i_id",), ("island_id",)),
    CompareSpec("Teilnahme_AV.csv", "player_summary", ("id",), ("player_id",)),
    CompareSpec(
        "Master_Avi.csv",
        "player_island_summary_for_sql",
        ("owner_id", "island_id"),
        ("player_id", "island_id"),
    ),
)


MANUAL_MAPPINGS: dict[str, str] = {
    "registered_at_unix": "a_registration_time",
    "registered_at": "a_Registration_time_normal",
    "government_form": "a_formOfGovernment",
    "account_age_days": "a_Spieldauer",
    "population_total": "c_Buerger_Ges",
    "wood_in_buildings": "c_Holz_verbaut",
    "crystal_in_buildings": "c_Kristall_verbaut",
    "marble_in_buildings": "c_Stein_verbaut",
    "sulfur_in_buildings": "c_Schwefel_verbaut",
    "wine_in_buildings": "c_Wein_verbaut",
    "resources_in_buildings_total": "c_Res_Ges_verbaut",
    "building_resource_score": "c_Baumeister_Highscore",
    "resources_stored_total": "c_Res_Ges_lagernd",
    "resources_in_buildings_and_storage_total": "c_Res_Ges_verb_lag",
    "building_levels_total": "c_Geblev",
    "wonder_donations_total": "d_Don_Wonder_Ges",
    "sawmill_donations_total": "d_Don_Saegewerk_Ges",
    "luxury_mine_donations_total": "d_DonH_Luxusminen_Ges",
    "donations_total": "d_Don_Ges",
    "luxury_resource_type": "i_tradegood",
    "luxury_mine_level": "i_tradegood_level",
    "sawmill_level": "i_resource_level",
    "sawmill_donated_cumulative": "i_resource_donated",
    "luxury_mine_donated_cumulative": "i_tradegood_donated",
    "wonder_donated_cumulative": "i_wonder_donated",
    "snapshots_observed_count": "Anzahl_Vorhanden",
    "player_city_observation_count": "Cities_Vorhanden",
}

MASTER_MAPPINGS: dict[str, str] = {
    "player_city_observation_count": "Cities_Vorhanden",
    "player_snapshots_observed_count": "Anzahl_Teilnahme",
}


def _build_python_outputs(config_path: Path, cache_dir: Path | None) -> dict[str, pl.DataFrame]:
    cfg = load_config(config_path)
    raw = load_all_raw(cfg, cache_dir=cache_dir)
    raw = _filter_prelaunch_players(raw, cfg)

    building_costs = read_building_costs(cfg.building_costs_path)
    city_with_costs = join_building_costs(raw.city, building_costs)
    player_enriched = enrich_avatars(raw.avatar, cfg)
    city_enriched = compute_city_metrics(city_with_costs, player_enriched)
    city_player_island = aggregate_to_player_island(city_enriched)
    donation_enriched = process_donations(raw.donation, city_player_island, raw.island, cfg)
    island_enriched = enrich_islands(raw.island, city_player_island, donation_enriched)

    city3_av = aggregate_by_avatar(city_player_island)
    city4_i = aggregate_by_island(city_player_island)
    donation3_av = donations_by_avatar(donation_enriched)
    donation4_i = donations_by_island(donation_enriched)

    panels = build_panels(
        player_enriched=player_enriched,
        city_player_island=city_player_island,
        city3_av=city3_av,
        city4_i=city4_i,
        donation_enriched=donation_enriched,
        donation3_av=donation3_av,
        donation4_i=donation4_i,
        island_enriched=island_enriched,
    )
    derived = build_derived(
        player_snapshot=panels.player_snapshot,
        player_island_snapshot=panels.player_island_snapshot,
        island_snapshot=panels.island_snapshot,
    )

    player_island_summary_for_sql = derived.player_island_summary.join(
        derived.player_summary.select("player_id", "snapshots_observed_count"),
        on="player_id",
        how="left",
        suffix="_player",
    ).rename({"snapshots_observed_count_player": "player_snapshots_observed_count"})

    return {
        "player_latest": derived.player_latest,
        "player_island_latest": derived.player_island_latest,
        "island_latest": derived.island_latest,
        "player_summary": derived.player_summary,
        "player_island_summary_for_sql": player_island_summary_for_sql,
    }


def _map_columns(py_cols: list[str], sql_cols: list[str], table_name: str) -> dict[str, str]:
    sql_set = set(sql_cols)
    manual = MASTER_MAPPINGS if table_name == "player_island_summary_for_sql" else MANUAL_MAPPINGS
    mapping: dict[str, str] = {}
    for py_col in py_cols:
        if py_col in manual and manual[py_col] in sql_set:
            mapping[py_col] = manual[py_col]
            continue
        for prefix in ("t_", "a_", "c_", "d_", "i_", "m_"):
            candidate = prefix + py_col
            if candidate in sql_set:
                mapping[py_col] = candidate
                break
        else:
            if py_col in sql_set:
                mapping[py_col] = py_col
    return mapping


def _format_key_samples(
    df: pl.DataFrame, keys: tuple[str, ...], limit: int = 10
) -> str:
    rows = df.select(list(keys)).head(limit).iter_rows(named=True)
    return "; ".join(
        ", ".join(f"{key}={row[key]}" for key in keys) for row in rows
    )


def _compare_pair(
    spec: CompareSpec, py_df: pl.DataFrame, sql_gold_dir: Path
) -> tuple[list[str], bool]:
    sql_df = pl.read_csv(sql_gold_dir / spec.sql_file, separator=";", infer_schema_length=10_000)
    sql_for_join = sql_df.rename(dict(zip(spec.sql_keys, spec.py_keys, strict=True)))
    common = py_df.join(sql_for_join, on=list(spec.py_keys), how="inner", suffix="__sql")
    py_only = py_df.join(sql_for_join.select(spec.py_keys), on=list(spec.py_keys), how="anti")
    sql_only = sql_for_join.join(py_df.select(spec.py_keys), on=list(spec.py_keys), how="anti")

    lines = [
        f"## {spec.table_name} vs {spec.sql_file}",
        f"- Python rows: {py_df.height:,}",
        f"- SQL rows: {sql_df.height:,}",
        f"- Common keys: {common.height:,}",
        f"- Python-only keys: {py_only.height:,}",
        f"- SQL-only keys: {sql_only.height:,}",
    ]
    if py_only.height:
        lines.append(f"- Python-only key sample: {_format_key_samples(py_only, spec.py_keys)}")
    if sql_only.height:
        lines.append(f"- SQL-only key sample: {_format_key_samples(sql_only, spec.py_keys)}")

    col_map = _map_columns(py_df.columns, sql_for_join.columns, spec.table_name)
    failures: list[str] = []
    compared_cols = 0
    for py_col, sql_col in col_map.items():
        if py_col in spec.py_keys:
            continue
        sql_joined = sql_col if sql_col not in py_df.columns else f"{sql_col}__sql"
        if sql_joined not in common.columns:
            continue

        py_s = common[py_col]
        sql_s = common[sql_joined]
        sql_non_null = sql_s.is_not_null()
        if int(sql_non_null.sum()) == 0:
            continue

        compared_cols += 1
        if py_s.dtype.is_numeric() and sql_s.dtype.is_numeric():
            py_f = py_s.cast(pl.Float64, strict=False).filter(sql_non_null)
            sql_f = sql_s.cast(pl.Float64, strict=False).filter(sql_non_null)
            diff = (py_f - sql_f).abs()
            max_d = diff.max()
            max_d_val = 0.0 if max_d is None else float(max_d)  # type: ignore[arg-type]
            if max_d_val >= TOLERANCE:
                failures.append(f"{py_col} -> {sql_col}: max_abs_delta={max_d_val:.6g}")
        else:
            py_f = py_s.filter(sql_non_null).to_list()
            sql_f = sql_s.filter(sql_non_null).to_list()
            if py_f != sql_f:
                failures.append(f"{py_col} -> {sql_col}: non-numeric mismatch")

    lines.append(f"- Compared mapped columns: {compared_cols}")
    if failures:
        lines.append("- Result: FAIL")
        lines.extend(f"  - {failure}" for failure in failures[:20])
        if len(failures) > 20:
            lines.append(f"  - ... {len(failures) - 20} more failures")
    else:
        lines.append("- Result: PASS")
    return lines, not failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Python v2 outputs against SQL gold CSVs.")
    parser.add_argument("--config", type=Path, default=Path("config/parameters.yaml"))
    parser.add_argument("--sql-gold-dir", type=Path, default=Path("sql_gold_standard"))
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=Path("docs/python_vs_sql_gold_current.md"))
    args = parser.parse_args()

    outputs = _build_python_outputs(args.config.resolve(), args.cache_dir)

    all_lines = [
        "# Python v2 vs SQL Gold Verification",
        "",
        f"Tolerance: `{TOLERANCE}` absolute.",
        "SQL gold CSVs are the exported outputs from `Alle_Queries_DE_hintereinander.sql`.",
        "Comparison uses rows with common keys and ignores SQL NULL-shell values.",
        "",
    ]
    ok = True
    for spec in COMPARE_SPECS:
        lines, passed = _compare_pair(spec, outputs[spec.table_name], args.sql_gold_dir)
        ok = ok and passed
        all_lines.extend(lines)
        all_lines.append("")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(all_lines), encoding="utf-8")
    print(f"Wrote {args.report}")
    print("\n".join(line for line in all_lines if line.startswith(("##", "- Result:"))))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
