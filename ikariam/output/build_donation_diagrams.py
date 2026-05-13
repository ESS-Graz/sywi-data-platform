#!/usr/bin/env python3
"""Build donation-behavior diagrams from the local Ikariam LanceDB output."""

from __future__ import annotations

import csv
import html
import math
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


DB_PATH = "ikariam.lancedb"
OUT = Path("donation_behavior_diagrams.html")

COLORS = {
    "DE": "#2b6cb0",
    "EN": "#805ad5",
    "FR": "#c53030",
    "GR": "#2f855a",
    "TR": "#dd6b20",
    "sawmill": "#2b6cb0",
    "luxury": "#d69e2e",
    "wonder": "#805ad5",
    "neutral": "#4a5568",
    "grid": "#e2e8f0",
    "text": "#1a202c",
    "muted": "#718096",
}


@dataclass(frozen=True)
class Chart:
    title: str
    note: str
    svg: str


def run_query(sql: str) -> list[dict[str, str]]:
    command = [
        "duckdb",
        "-csv",
        "-c",
        f"LOAD lance; ATTACH '{DB_PATH}' AS ikariam (TYPE lance); {sql}",
    ]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return list(csv.DictReader(result.stdout.splitlines()))


def fnum(value: str | float | int | None) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def fmt_compact(value: float) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000_000:
        return f"{sign}{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{sign}{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}{value / 1_000:.0f}k"
    return f"{sign}{value:.0f}"


def fmt_pct(value: float) -> str:
    return f"{value:.0f}%"


def scale_ticks(max_value: float, count: int = 4) -> list[float]:
    if max_value <= 0:
        return [0]
    magnitude = 10 ** math.floor(math.log10(max_value))
    norm = max_value / magnitude
    if norm <= 2:
        step = 0.5 * magnitude
    elif norm <= 5:
        step = 1 * magnitude
    else:
        step = 2 * magnitude
    top = math.ceil(max_value / step) * step
    return [top * i / count for i in range(count + 1)]


def svg_wrap(width: int, height: int, body: str) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'xmlns="http://www.w3.org/2000/svg">{body}</svg>'
    )


def text(x: float, y: float, value: str, size: int = 12, anchor: str = "middle",
         weight: int = 400, color: str = COLORS["text"]) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="{color}">'
        f"{html.escape(value)}</text>"
    )


def grouped_bars(
    rows: list[dict[str, str]],
    label_key: str,
    series: list[tuple[str, str, str]],
    title: str,
    note: str,
    formatter=fmt_compact,
    width: int = 920,
    height: int = 460,
) -> Chart:
    margin_l, margin_r, margin_t, margin_b = 84, 28, 38, 78
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    max_v = max(fnum(row[key]) for row in rows for key, _, _ in series)
    ticks = scale_ticks(max_v)
    top = ticks[-1] or 1
    group_w = plot_w / len(rows)
    bar_w = min(34, group_w / (len(series) + 1.8))
    body: list[str] = []

    for tick in ticks:
        y = margin_t + plot_h - (tick / top) * plot_h
        body.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{width - margin_r}" y2="{y:.1f}" stroke="{COLORS["grid"]}" />')
        body.append(text(margin_l - 10, y + 4, formatter(tick), 11, "end", color=COLORS["muted"]))

    body.append(f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{width - margin_r}" y2="{margin_t + plot_h}" stroke="#a0aec0" />')

    for i, row in enumerate(rows):
        center = margin_l + group_w * (i + 0.5)
        start = center - (len(series) * bar_w + (len(series) - 1) * 7) / 2
        for j, (key, _, color) in enumerate(series):
            value = fnum(row[key])
            h = (value / top) * plot_h
            x = start + j * (bar_w + 7)
            y = margin_t + plot_h - h
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2" fill="{color}" />')
            if h > 34:
                body.append(text(x + bar_w / 2, y + 18, formatter(value), 10, color="white", weight=700))
            else:
                body.append(text(x + bar_w / 2, y - 5, formatter(value), 10, color=COLORS["text"]))
        body.append(text(center, height - 42, row[label_key], 13, weight=700))

    legend_x = margin_l
    legend_y = height - 17
    for key, label, color in series:
        body.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="13" height="13" rx="2" fill="{color}" />')
        body.append(text(legend_x + 18, legend_y + 1, label, 12, "start", color=COLORS["muted"]))
        legend_x += 150

    return Chart(title, note, svg_wrap(width, height, "\n".join(body)))


def stacked_bars(
    rows: list[dict[str, str]],
    label_key: str,
    series: list[tuple[str, str, str]],
    title: str,
    note: str,
    width: int = 920,
    height: int = 430,
) -> Chart:
    margin_l, margin_r, margin_t, margin_b = 72, 28, 34, 76
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    group_w = plot_w / len(rows)
    bar_w = min(84, group_w * 0.56)
    ticks = [0, 25, 50, 75, 100]
    body: list[str] = []

    for tick in ticks:
        y = margin_t + plot_h - (tick / 100) * plot_h
        body.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{width - margin_r}" y2="{y:.1f}" stroke="{COLORS["grid"]}" />')
        body.append(text(margin_l - 10, y + 4, f"{tick}%", 11, "end", color=COLORS["muted"]))

    for i, row in enumerate(rows):
        x = margin_l + group_w * (i + 0.5) - bar_w / 2
        current_y = margin_t + plot_h
        for key, label, color in series:
            value = fnum(row[key])
            h = (value / 100) * plot_h
            current_y -= h
            body.append(f'<rect x="{x:.1f}" y="{current_y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2" fill="{color}" />')
            if h > 24:
                body.append(text(x + bar_w / 2, current_y + h / 2 + 4, fmt_pct(value), 11, color="white", weight=700))
        body.append(text(x + bar_w / 2, height - 42, row[label_key], 13, weight=700))

    legend_x = margin_l
    legend_y = height - 17
    for _, label, color in series:
        body.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="13" height="13" rx="2" fill="{color}" />')
        body.append(text(legend_x + 18, legend_y + 1, label, 12, "start", color=COLORS["muted"]))
        legend_x += 132

    return Chart(title, note, svg_wrap(width, height, "\n".join(body)))


def bars_one_series(
    rows: list[dict[str, str]],
    label_key: str,
    value_key: str,
    title: str,
    note: str,
    formatter=fmt_compact,
    color: str = COLORS["neutral"],
    width: int = 920,
    height: int = 430,
) -> Chart:
    margin_l, margin_r, margin_t, margin_b = 86, 28, 34, 76
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    max_v = max(fnum(row[value_key]) for row in rows)
    ticks = scale_ticks(max_v)
    top = ticks[-1] or 1
    group_w = plot_w / len(rows)
    bar_w = min(68, group_w * 0.58)
    body: list[str] = []

    for tick in ticks:
        y = margin_t + plot_h - (tick / top) * plot_h
        body.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{width - margin_r}" y2="{y:.1f}" stroke="{COLORS["grid"]}" />')
        body.append(text(margin_l - 10, y + 4, formatter(tick), 11, "end", color=COLORS["muted"]))

    for i, row in enumerate(rows):
        value = fnum(row[value_key])
        h = (value / top) * plot_h
        x = margin_l + group_w * (i + 0.5) - bar_w / 2
        y = margin_t + plot_h - h
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2" fill="{color}" />')
        body.append(text(x + bar_w / 2, y - 7, formatter(value), 11, weight=700))
        body.append(text(x + bar_w / 2, height - 42, row[label_key], 13, weight=700))

    return Chart(title, note, svg_wrap(width, height, "\n".join(body)))


def dual_axis_bars_line(
    rows: list[dict[str, str]],
    label_key: str,
    bar_key: str,
    line_key: str,
    title: str,
    note: str,
    width: int = 920,
    height: int = 470,
) -> Chart:
    margin_l, margin_r, margin_t, margin_b = 86, 70, 34, 80
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    max_bar = max(fnum(row[bar_key]) for row in rows)
    bar_ticks = scale_ticks(max_bar)
    bar_top = bar_ticks[-1] or 1
    pct_top = 100.0
    group_w = plot_w / len(rows)
    bar_w = min(60, group_w * 0.5)
    points: list[tuple[float, float]] = []
    body: list[str] = []

    for tick in bar_ticks:
        y = margin_t + plot_h - (tick / bar_top) * plot_h
        body.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{width - margin_r}" y2="{y:.1f}" stroke="{COLORS["grid"]}" />')
        body.append(text(margin_l - 10, y + 4, fmt_compact(tick), 11, "end", color=COLORS["muted"]))

    for tick in [0, 25, 50, 75, 100]:
        y = margin_t + plot_h - (tick / pct_top) * plot_h
        body.append(text(width - margin_r + 10, y + 4, f"{tick}%", 11, "start", color=COLORS["muted"]))

    for i, row in enumerate(rows):
        center = margin_l + group_w * (i + 0.5)
        bar_value = fnum(row[bar_key])
        bar_h = (bar_value / bar_top) * plot_h
        x = center - bar_w / 2
        y = margin_t + plot_h - bar_h
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="2" fill="#4a5568" opacity="0.84" />')
        body.append(text(center, y - 7, fmt_compact(bar_value), 10, weight=700))
        pct = fnum(row[line_key])
        py = margin_t + plot_h - (pct / pct_top) * plot_h
        points.append((center, py))
        body.append(text(center, height - 44, row[label_key], 13, weight=700))

    path = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    body.append(f'<path d="{path}" fill="none" stroke="#c53030" stroke-width="3" />')
    for row, (x, y) in zip(rows, points, strict=True):
        pct = fnum(row[line_key])
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#c53030" />')
        body.append(text(x, y - 12, f"{pct:.1f}%", 11, weight=700, color="#c53030"))

    legend_y = height - 18
    body.append(f'<rect x="{margin_l}" y="{legend_y - 10}" width="13" height="13" rx="2" fill="#4a5568" opacity="0.84" />')
    body.append(text(margin_l + 18, legend_y + 1, "median donations", 12, "start", color=COLORS["muted"]))
    body.append(f'<line x1="{margin_l + 170}" y1="{legend_y - 4}" x2="{margin_l + 200}" y2="{legend_y - 4}" stroke="#c53030" stroke-width="3" />')
    body.append(text(margin_l + 208, legend_y + 1, "donor participation", 12, "start", color=COLORS["muted"]))

    return Chart(title, note, svg_wrap(width, height, "\n".join(body)))


def line_chart(
    rows: list[dict[str, str]],
    title: str,
    note: str,
    width: int = 920,
    height: int = 500,
) -> Chart:
    margin_l, margin_r, margin_t, margin_b = 84, 28, 34, 82
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    dates = sorted({date.fromisoformat(row["snapshot_date"]) for row in rows})
    countries = sorted({row["country_code"] for row in rows})
    date_index = {d: i for i, d in enumerate(dates)}
    max_v = max(fnum(row["donations_total"]) for row in rows)
    ticks = scale_ticks(max_v)
    top = ticks[-1] or 1
    values = {(row["country_code"], date.fromisoformat(row["snapshot_date"])): fnum(row["donations_total"]) for row in rows}
    body: list[str] = []

    for tick in ticks:
        y = margin_t + plot_h - (tick / top) * plot_h
        body.append(f'<line x1="{margin_l}" y1="{y:.1f}" x2="{width - margin_r}" y2="{y:.1f}" stroke="{COLORS["grid"]}" />')
        body.append(text(margin_l - 10, y + 4, fmt_compact(tick), 11, "end", color=COLORS["muted"]))

    for country in countries:
        pts = []
        for d in dates:
            if (country, d) not in values:
                continue
            x = margin_l + (date_index[d] / max(1, len(dates) - 1)) * plot_w
            y = margin_t + plot_h - (values[(country, d)] / top) * plot_h
            pts.append((x, y))
        path = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        body.append(f'<path d="{path}" fill="none" stroke="{COLORS[country]}" stroke-width="2.6" />')
        if pts:
            body.append(text(pts[-1][0] - 4, pts[-1][1] - 7, country, 12, "end", weight=700, color=COLORS[country]))

    for d in [dates[0], dates[len(dates) // 2], dates[-1]]:
        x = margin_l + (date_index[d] / max(1, len(dates) - 1)) * plot_w
        body.append(f'<line x1="{x:.1f}" y1="{margin_t + plot_h}" x2="{x:.1f}" y2="{margin_t + plot_h + 6}" stroke="#a0aec0" />')
        body.append(text(x, height - 46, d.isoformat(), 11, color=COLORS["muted"]))

    return Chart(title, note, svg_wrap(width, height, "\n".join(body)))


def conclusion_cards(country_rows: list[dict[str, str]], concentration_rows: list[dict[str, str]]) -> str:
    highest_intensity = max(country_rows, key=lambda r: fnum(r["donations_per_player"]))
    lowest_city = min(country_rows, key=lambda r: fnum(r["donations_per_city"]))
    most_top_heavy = max(concentration_rows, key=lambda r: fnum(r["top10pct_share_pct"]))
    highest_wonder = max(country_rows, key=lambda r: fnum(r["wonder_pct"]))
    cards = [
        (
            "Highest intensity",
            f"{highest_intensity['country_code']} leads per-player donation intensity "
            f"at {fmt_compact(fnum(highest_intensity['donations_per_player']))} per active player.",
        ),
        (
            "Weakest per-city contribution",
            f"{lowest_city['country_code']} has the lowest donations per city "
            f"({fmt_compact(fnum(lowest_city['donations_per_city']))}), despite large absolute scale.",
        ),
        (
            "Most top-heavy",
            f"{most_top_heavy['country_code']} depends most on the upper tail: "
            f"the top 10% of players carry {fnum(most_top_heavy['top10pct_share_pct']):.1f}% of donations.",
        ),
        (
            "Wonder outlier",
            f"{highest_wonder['country_code']} has the highest wonder share "
            f"({fnum(highest_wonder['wonder_pct']):.1f}%), but wonders remain small everywhere.",
        ),
    ]
    return "\n".join(
        f"<article><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>"
        for title, body in cards
    )


def page(charts: Iterable[Chart], country_rows: list[dict[str, str]], concentration_rows: list[dict[str, str]]) -> str:
    chart_html = []
    for chart in charts:
        chart_html.append(
            "<section class='chart'>"
            f"<h2>{html.escape(chart.title)}</h2>"
            f"<p>{html.escape(chart.note)}</p>"
            f"{chart.svg}"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ikariam Donation Behavior Diagrams</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1a202c;
      --muted: #718096;
      --line: #e2e8f0;
      --panel: #ffffff;
      --bg: #f7fafc;
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 34px 24px 52px;
    }}
    header {{
      margin-bottom: 22px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.15;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 6px;
      font-size: 14px;
      letter-spacing: 0;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0 20px;
    }}
    article,
    .chart {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(0,0,0,.04);
    }}
    article {{
      padding: 14px;
    }}
    article p {{
      font-size: 13px;
      color: var(--ink);
    }}
    .chart {{
      padding: 18px 18px 8px;
      margin-top: 16px;
      overflow-x: auto;
    }}
    .chart p {{
      margin-top: 5px;
      margin-bottom: 10px;
      font-size: 14px;
    }}
    svg {{
      width: 100%;
      min-width: 760px;
      height: auto;
      display: block;
    }}
    .meta {{
      font-size: 13px;
      margin-top: 8px;
    }}
    @media (max-width: 820px) {{
      .cards {{
        grid-template-columns: 1fr 1fr;
      }}
      main {{
        padding-left: 14px;
        padding-right: 14px;
      }}
    }}
    @media (max-width: 520px) {{
      .cards {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Ikariam Donation Behavior</h1>
      <p>Charts generated from <code>output/ikariam.lancedb</code>. Most comparisons use the final shared snapshot, 2014-11-13; time-series charts use all raw-preserved snapshots.</p>
      <p class="meta">Donation amounts are the dataset's normalized donation units from the raw <code>gold</code> field.</p>
    </header>
    <section class="cards">
      {conclusion_cards(country_rows, concentration_rows)}
    </section>
    {''.join(chart_html)}
  </main>
</body>
</html>
"""


def main() -> None:
    country = run_query(
        """
        WITH fp AS (
          SELECT * FROM ikariam.main.player_snapshot WHERE snapshot_date = DATE '2014-11-13'
        ), agg AS (
          SELECT
            country_code,
            count(*) AS players,
            sum(city_count) AS cities,
            sum(population_total) AS population,
            sum(donations_total) AS donations_total,
            sum(CASE WHEN donations_total > 0 THEN 1 ELSE 0 END) AS donors,
            sum(wonder_donations_total) AS wonder,
            sum(sawmill_donations_total) AS sawmill,
            sum(luxury_mine_donations_total) AS luxury,
            sum(resources_in_buildings_total) AS building_resources,
            sum(resources_stored_total) AS stored_resources
          FROM fp
          GROUP BY country_code
        )
        SELECT
          country_code,
          players,
          cities,
          population,
          donations_total,
          donors,
          round(100.0 * donors / players, 1) AS donor_pct,
          round(donations_total / players, 0) AS donations_per_player,
          round(donations_total / cities, 0) AS donations_per_city,
          round(donations_total / population, 1) AS donations_per_population,
          round(100.0 * donations_total / building_resources, 1) AS donations_vs_buildings_pct,
          round(100.0 * sawmill / donations_total, 1) AS sawmill_pct,
          round(100.0 * luxury / donations_total, 1) AS luxury_pct,
          round(100.0 * wonder / donations_total, 1) AS wonder_pct
        FROM agg
        ORDER BY donations_per_player DESC;
        """
    )

    maturity = run_query(
        """
        SELECT
          CASE
            WHEN city_count = 1 THEN '1'
            WHEN city_count BETWEEN 2 AND 3 THEN '2-3'
            WHEN city_count BETWEEN 4 AND 6 THEN '4-6'
            WHEN city_count BETWEEN 7 AND 9 THEN '7-9'
            ELSE '10+'
          END AS city_bucket,
          min(city_count) AS sort_key,
          count(*) AS players,
          round(100.0 * sum(CASE WHEN donations_total > 0 THEN 1 ELSE 0 END) / count(*), 1) AS donor_pct,
          round(avg(donations_total), 0) AS avg_donations,
          round(quantile_cont(donations_total, 0.5), 0) AS median_donations,
          round(quantile_cont(donations_total, 0.9), 0) AS p90_donations
        FROM ikariam.main.player_snapshot
        WHERE snapshot_date = DATE '2014-11-13'
        GROUP BY city_bucket
        ORDER BY sort_key;
        """
    )

    concentration = run_query(
        """
        WITH fp AS (
          SELECT country_code, player_id, donations_total
          FROM ikariam.main.player_snapshot
          WHERE snapshot_date = DATE '2014-11-13'
        ), ranked AS (
          SELECT
            *,
            row_number() OVER (PARTITION BY country_code ORDER BY donations_total DESC) AS rn,
            count(*) OVER (PARTITION BY country_code) AS n,
            sum(donations_total) OVER (PARTITION BY country_code) AS total_donations
          FROM fp
        )
        SELECT
          country_code,
          round(100.0 * sum(CASE WHEN rn <= ceil(n * 0.01) THEN donations_total ELSE 0 END) / max(total_donations), 1) AS top1pct_share_pct,
          round(100.0 * sum(CASE WHEN rn <= ceil(n * 0.05) THEN donations_total ELSE 0 END) / max(total_donations), 1) AS top5pct_share_pct,
          round(100.0 * sum(CASE WHEN rn <= ceil(n * 0.10) THEN donations_total ELSE 0 END) / max(total_donations), 1) AS top10pct_share_pct
        FROM ranked
        GROUP BY country_code
        ORDER BY top10pct_share_pct DESC;
        """
    )

    island_density = run_query(
        """
        SELECT
          CASE
            WHEN city_count BETWEEN 1 AND 2 THEN '1-2'
            WHEN city_count BETWEEN 3 AND 5 THEN '3-5'
            WHEN city_count BETWEEN 6 AND 10 THEN '6-10'
            ELSE '11+'
          END AS city_bucket,
          min(city_count) AS sort_key,
          count(*) AS islands,
          round(avg(donations_total), 0) AS avg_donations,
          round(quantile_cont(donations_total, 0.5), 0) AS median_donations,
          round(avg(donating_player_share_pct), 1) AS avg_donor_share_pct
        FROM ikariam.main.island_latest
        WHERE city_count > 0
        GROUP BY city_bucket
        ORDER BY sort_key;
        """
    )

    resource = run_query(
        """
        SELECT
          CASE luxury_resource_type
            WHEN 1 THEN 'wine'
            WHEN 2 THEN 'marble'
            WHEN 3 THEN 'crystal'
            WHEN 4 THEN 'sulfur'
            ELSE luxury_resource_type::VARCHAR
          END AS luxury_resource,
          sum(city_count) AS cities,
          round(sum(donations_total), 0) AS donations_total,
          round(avg(CASE WHEN city_count > 0 THEN donations_total END), 0) AS avg_donations_occupied,
          round(avg(CASE WHEN city_count > 0 THEN donating_player_share_pct END), 1) AS avg_donor_share_pct
        FROM ikariam.main.island_latest
        GROUP BY luxury_resource_type
        ORDER BY donations_total DESC;
        """
    )

    time_series = run_query(
        """
        SELECT
          country_code,
          snapshot_date,
          round(sum(donations_total), 0) AS donations_total
        FROM ikariam.main.island_snapshot
        GROUP BY country_code, snapshot_date
        ORDER BY snapshot_date, country_code;
        """
    )

    charts = [
        grouped_bars(
            country,
            "country_code",
            [
                ("donations_per_player", "per player", "#2b6cb0"),
                ("donations_per_city", "per city", "#d69e2e"),
            ],
            "Donation Intensity By Country",
            "FR/DE lead on player-level intensity; TR has scale but lower contribution per city/player.",
        ),
        stacked_bars(
            country,
            "country_code",
            [
                ("sawmill_pct", "sawmill", COLORS["sawmill"]),
                ("luxury_pct", "luxury mine", COLORS["luxury"]),
                ("wonder_pct", "wonder", COLORS["wonder"]),
            ],
            "Donation Mix",
            "Economic infrastructure dominates. Wonders are visible socially, but small in total volume.",
        ),
        dual_axis_bars_line(
            maturity,
            "city_bucket",
            "median_donations",
            "donor_pct",
            "Player Maturity Curve",
            "Donation becomes normal once players have 4+ cities; the median stays zero for one-city players.",
        ),
        grouped_bars(
            concentration,
            "country_code",
            [
                ("top1pct_share_pct", "top 1%", "#805ad5"),
                ("top5pct_share_pct", "top 5%", "#2b6cb0"),
                ("top10pct_share_pct", "top 10%", "#dd6b20"),
            ],
            "Donation Concentration",
            "EN is the most top-heavy: fewer donors, but the upper tail carries a larger share.",
            formatter=fmt_pct,
        ),
        dual_axis_bars_line(
            island_density,
            "city_bucket",
            "median_donations",
            "avg_donor_share_pct",
            "Island Density Effect",
            "Dense islands have dramatically higher median donations, while donor share stays broadly high.",
        ),
        bars_one_series(
            resource,
            "luxury_resource",
            "donations_total",
            "Donations By Island Luxury Resource",
            "Marble and wine islands attract the most total donation volume because they host more developed activity.",
            color="#2f855a",
        ),
        line_chart(
            time_series,
            "Cumulative Donation Growth Over Time",
            "Raw totals rise steadily in every country; FR and TR finish close despite very different active-player counts.",
        ),
    ]

    OUT.write_text(page(charts, country, concentration), encoding="utf-8")
    print(OUT.resolve())


if __name__ == "__main__":
    main()
