#!/usr/bin/env python3
"""Build a compact donation-vs-success report from Ikariam Lance output."""

from __future__ import annotations

import html
from pathlib import Path

from build_donation_diagrams import COLORS, fmt_compact, run_query, svg_wrap, text


OUT = Path("donation_success_comparison.html")


def fnum(value: str | float | int | None) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def combo_quintile_chart(
    rows: list[dict[str, str]],
    title: str,
    note: str,
    x_key: str,
    donation_key: str,
    success_key: str,
    success_label: str,
    width: int = 920,
    height: int = 460,
) -> str:
    margin_l, margin_r, margin_t, margin_b = 86, 78, 34, 80
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    max_donation = max(fnum(r[donation_key]) for r in rows) or 1
    max_success = max(fnum(r[success_key]) for r in rows) or 1
    group_w = plot_w / len(rows)
    bar_w = min(64, group_w * 0.46)
    points: list[tuple[float, float, float]] = []
    body: list[str] = []

    for i in range(5):
        tick = max_donation * i / 4
        y = margin_t + plot_h - (tick / max_donation) * plot_h
        body.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{width - margin_r}" y2="{y:.1f}" stroke="{COLORS["grid"]}" />')
        body.append(text(margin_l - 10, y + 4, fmt_compact(tick), 11, "end", color=COLORS["muted"]))

    for i in range(5):
        tick = max_success * i / 4
        y = margin_t + plot_h - (tick / max_success) * plot_h
        body.append(text(width - margin_r + 10, y + 4, fmt_compact(tick), 11, "start", color=COLORS["muted"]))

    for i, row in enumerate(rows):
        center = margin_l + group_w * (i + 0.5)
        donation = fnum(row[donation_key])
        donation_h = (donation / max_donation) * plot_h
        x = center - bar_w / 2
        y = margin_t + plot_h - donation_h
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{donation_h:.1f}" rx="2" fill="#4a5568" opacity="0.86" />')
        body.append(text(center, y - 7, fmt_compact(donation), 10, weight=700))
        success = fnum(row[success_key])
        py = margin_t + plot_h - (success / max_success) * plot_h
        points.append((center, py, success))
        body.append(text(center, height - 46, str(row[x_key]), 13, weight=700))

    path = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y, _) in enumerate(points))
    body.append(f'<path d="{path}" fill="none" stroke="#2b6cb0" stroke-width="3" />')
    for x, y, success in points:
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2b6cb0" />')
        body.append(text(x, y - 12, fmt_compact(success), 10, weight=700, color="#2b6cb0"))

    legend_y = height - 19
    body.append(f'<rect x="{margin_l}" y="{legend_y - 10}" width="13" height="13" rx="2" fill="#4a5568" opacity="0.86" />')
    body.append(text(margin_l + 18, legend_y + 1, "donations per city", 12, "start", color=COLORS["muted"]))
    body.append(f'<line x1="{margin_l + 178}" y1="{legend_y - 4}" x2="{margin_l + 208}" y2="{legend_y - 4}" stroke="#2b6cb0" stroke-width="3" />')
    body.append(text(margin_l + 216, legend_y + 1, success_label, 12, "start", color=COLORS["muted"]))

    return (
        "<section class='chart'>"
        f"<h2>{html.escape(title)}</h2>"
        f"<p>{html.escape(note)}</p>"
        f"{svg_wrap(width, height, chr(10).join(body))}"
        "</section>"
    )


def correlation_table(title: str, rows: list[dict[str, str]], columns: list[tuple[str, str]]) -> str:
    headers = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row[key])}</td>" for key, _ in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        "<section class='table-section'>"
        f"<h2>{html.escape(title)}</h2>"
        "<table><thead><tr>"
        f"{headers}"
        "</tr></thead><tbody>"
        f"{''.join(body_rows)}"
        "</tbody></table></section>"
    )


def page(sections: list[str]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Donation vs Success</title>
  <style>
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7fafc;
      color: #1a202c;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 34px 24px 52px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
      line-height: 1.15;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }}
    p {{
      margin: 6px 0 0;
      color: #718096;
      line-height: 1.45;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .summary article,
    .chart,
    .table-section {{
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(0,0,0,.04);
    }}
    .summary article {{
      padding: 14px;
      font-size: 14px;
    }}
    .summary strong {{
      display: block;
      margin-bottom: 5px;
    }}
    .chart,
    .table-section {{
      margin-top: 16px;
      padding: 18px;
      overflow-x: auto;
    }}
    svg {{
      width: 100%;
      min-width: 760px;
      display: block;
      height: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 8px 10px;
      text-align: right;
      white-space: nowrap;
    }}
    th:first-child, td:first-child {{
      text-align: left;
    }}
    th {{
      color: #4a5568;
      font-weight: 700;
    }}
    code {{
      color: #2d3748;
    }}
    @media (max-width: 800px) {{
      .summary {{
        grid-template-columns: 1fr;
      }}
      main {{
        padding-left: 14px;
        padding-right: 14px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Donation vs Success</h1>
      <p>Final snapshot: <code>2014-11-13</code>. Success is measured as durable development: city count, population, and resources invested in buildings.</p>
    </header>
    <section class="summary">
      <article><strong>Island result</strong>Higher donation intensity is associated with higher population and building investment per city.</article>
      <article><strong>Player result</strong>High-donation players are much more developed, but this is partly a maturity signal.</article>
      <article><strong>Causality caveat</strong>For islands donations plausibly help cause success; for users success also enables donations.</article>
    </section>
    {''.join(sections)}
  </main>
</body>
</html>
"""


def main() -> None:
    island_quintiles = run_query(
        """
        WITH base AS (
          SELECT
            country_code,
            island_id,
            city_count,
            donations_total / city_count AS donations_per_city,
            population_total / city_count AS population_per_city,
            resources_in_buildings_total / city_count AS building_resources_per_city,
            donating_player_share_pct
          FROM ikariam.main.island_latest
          WHERE city_count > 0
        ),
        ranked AS (
          SELECT
            *,
            ntile(5) OVER (PARTITION BY country_code ORDER BY donations_per_city) AS quintile
          FROM base
        )
        SELECT
          quintile,
          count(*) AS islands,
          round(avg(donations_per_city), 0) AS avg_donations_per_city,
          round(avg(population_per_city), 0) AS avg_population_per_city,
          round(avg(building_resources_per_city), 0) AS avg_building_resources_per_city,
          round(avg(donating_player_share_pct), 1) AS avg_donor_share_pct
        FROM ranked
        GROUP BY quintile
        ORDER BY quintile;
        """
    )

    player_quintiles = run_query(
        """
        WITH base AS (
          SELECT
            country_code,
            player_id,
            city_count,
            donations_total / city_count AS donations_per_city,
            population_total / city_count AS population_per_city,
            resources_in_buildings_total / city_count AS building_resources_per_city,
            resources_in_buildings_total / NULLIF(account_age_days, 0) AS building_resources_per_day
          FROM ikariam.main.player_snapshot
          WHERE snapshot_date = DATE '2014-11-13'
            AND city_count > 0
        ),
        ranked AS (
          SELECT
            *,
            ntile(5) OVER (PARTITION BY country_code ORDER BY donations_per_city) AS quintile
          FROM base
        )
        SELECT
          quintile,
          count(*) AS players,
          round(avg(donations_per_city), 0) AS avg_donations_per_city,
          round(avg(city_count), 2) AS avg_cities,
          round(avg(population_per_city), 0) AS avg_population_per_city,
          round(avg(building_resources_per_city), 0) AS avg_building_resources_per_city,
          round(avg(building_resources_per_day), 0) AS avg_building_resources_per_day
        FROM ranked
        GROUP BY quintile
        ORDER BY quintile;
        """
    )

    island_corr = run_query(
        """
        WITH i AS (
          SELECT
            *,
            donations_total / NULLIF(city_count, 0) AS donations_per_city,
            population_total / NULLIF(city_count, 0) AS population_per_city,
            resources_in_buildings_total / NULLIF(city_count, 0) AS building_resources_per_city
          FROM ikariam.main.island_latest
          WHERE city_count > 0
        )
        SELECT
          country_code,
          count(*) AS islands,
          round(corr(donations_total, population_total), 3) AS raw_don_vs_population,
          round(corr(donations_total, resources_in_buildings_total), 3) AS raw_don_vs_buildings,
          round(corr(donations_per_city, population_per_city), 3) AS normalized_pop,
          round(corr(donations_per_city, building_resources_per_city), 3) AS normalized_buildings
        FROM i
        GROUP BY country_code
        ORDER BY country_code;
        """
    )

    player_corr = run_query(
        """
        WITH p AS (
          SELECT
            *,
            donations_total / NULLIF(city_count, 0) AS donations_per_city,
            population_total / NULLIF(city_count, 0) AS population_per_city,
            resources_in_buildings_total / NULLIF(city_count, 0) AS building_resources_per_city
          FROM ikariam.main.player_snapshot
          WHERE snapshot_date = DATE '2014-11-13'
            AND city_count > 0
        )
        SELECT
          country_code,
          count(*) AS players,
          round(corr(donations_total, population_total), 3) AS raw_don_vs_population,
          round(corr(donations_total, resources_in_buildings_total), 3) AS raw_don_vs_buildings,
          round(corr(donations_per_city, population_per_city), 3) AS normalized_pop,
          round(corr(donations_per_city, building_resources_per_city), 3) AS normalized_buildings
        FROM p
        GROUP BY country_code
        ORDER BY country_code;
        """
    )

    growth_corr = run_query(
        """
        WITH start AS (
          SELECT
            country_code,
            player_id,
            donations_total,
            population_total,
            resources_in_buildings_total,
            CAST(city_count AS DOUBLE) AS city_count
          FROM ikariam.main.player_snapshot
          WHERE snapshot_date = DATE '2013-08-15'
        ),
        final AS (
          SELECT
            country_code,
            player_id,
            donations_total,
            population_total,
            resources_in_buildings_total,
            CAST(city_count AS DOUBLE) AS city_count
          FROM ikariam.main.player_snapshot
          WHERE snapshot_date = DATE '2014-11-13'
        ),
        joined AS (
          SELECT
            final.country_code,
            final.player_id,
            final.donations_total - start.donations_total AS donation_growth,
            final.population_total - start.population_total AS population_growth,
            final.resources_in_buildings_total - start.resources_in_buildings_total AS building_resource_growth
          FROM start
          JOIN final USING (country_code, player_id)
          WHERE final.resources_in_buildings_total >= start.resources_in_buildings_total
            AND final.population_total >= start.population_total
        )
        SELECT
          country_code,
          count(*) AS players,
          round(corr(donation_growth, population_growth), 3) AS donation_vs_population_growth,
          round(corr(donation_growth, building_resource_growth), 3) AS donation_vs_building_growth
        FROM joined
        GROUP BY country_code
        ORDER BY country_code;
        """
    )

    sections = [
        combo_quintile_chart(
            island_quintiles,
            "Island Success By Donation Intensity",
            "Within each country, occupied islands are split into donation-per-city quintiles.",
            "quintile",
            "avg_donations_per_city",
            "avg_building_resources_per_city",
            "building resources per city",
        ),
        combo_quintile_chart(
            player_quintiles,
            "Player Success By Donation Intensity",
            "Within each country, final active players are split into donation-per-city quintiles.",
            "quintile",
            "avg_donations_per_city",
            "avg_building_resources_per_city",
            "building resources per city",
        ),
        correlation_table(
            "Island Correlations",
            island_corr,
            [
                ("country_code", "country"),
                ("islands", "islands"),
                ("raw_don_vs_population", "raw vs pop"),
                ("raw_don_vs_buildings", "raw vs buildings"),
                ("normalized_pop", "per-city vs pop/city"),
                ("normalized_buildings", "per-city vs buildings/city"),
            ],
        ),
        correlation_table(
            "Player Correlations",
            player_corr,
            [
                ("country_code", "country"),
                ("players", "players"),
                ("raw_don_vs_population", "raw vs pop"),
                ("raw_don_vs_buildings", "raw vs buildings"),
                ("normalized_pop", "per-city vs pop/city"),
                ("normalized_buildings", "per-city vs buildings/city"),
            ],
        ),
        correlation_table(
            "Player Growth Check: 2013-08-15 To 2014-11-13",
            growth_corr,
            [
                ("country_code", "country"),
                ("players", "players"),
                ("donation_vs_population_growth", "donation vs pop growth"),
                ("donation_vs_building_growth", "donation vs building growth"),
            ],
        ),
    ]

    OUT.write_text(page(sections), encoding="utf-8")
    print(OUT.resolve())


if __name__ == "__main__":
    main()
