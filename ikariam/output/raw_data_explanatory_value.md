# Does Raw Data Help Explain Donation Behavior?

Yes. The current Lance analytics output is good for high-level success and donation analysis, but it strips some fields that would help explain **why** players start donating.

## What The Raw Data Contains

Recurring raw tables:

| raw table | recurring snapshots | useful fields |
|---|---:|---|
| `avatar.parquet` | 184 | player id, registration time, gold, research points, government, gender |
| `city.parquet` | 184 | city location, citizens, workers, scientists, priests, city hall level, stored resources, building slots/types/levels |
| `donation.parquet` | 184 | player, island, donation amount, donation type |
| `island.parquet` | 184 | island resource, sawmill/luxury/wonder levels, cumulative island donations, wonder belief |

One non-recurring raw table:

| raw table | snapshots | useful fields |
|---|---:|---|
| `logGovernmentChanges.parquet` | 1 | government-change events |

No obvious alliance, chat, pillage, trade, message, or military-action table exists in the raw archive.

## What The Current Output Keeps Well

The current `ikariam.lancedb` keeps:

- player, player-island, and island snapshot panels
- cumulative donations by type: sawmill, luxury mine, wonder
- city count, island count, population
- total building resources and building levels
- total stored resources
- island sawmill/luxury/wonder levels
- island donor participation
- first/last seen summary tables

That is enough to answer:

- Do donors become more successful?
- Are highly donated islands more successful?
- When do players first start donating?
- How concentrated are donations?
- Which island resource types attract donations?

## What We Strip That Would Help Explain Motivation

The biggest loss is from raw `city.parquet`.

Current output aggregates away:

- `resource_workers`
- `tradegood_workers`
- `scientists`
- `priests`
- `citizens`
- `level` / city hall level
- per-resource stored stockpiles:
  - wood
  - wine
  - marble
  - crystal
  - sulfur
- building slot detail:
  - `p1t..p17t` building type
  - `p1l..p17l` building level
- capital city flag

Some of these are computed internally in the pipeline, but not published in the final Lance tables.

## Why That Matters For Donations

Donation starts likely depend on:

- whether a player has enough workers to benefit from better sawmill/mine levels
- whether they are production-focused or research-focused
- whether they have resource surplus available
- whether they have temples/priests and therefore care about wonders
- whether they just built/expanded cities
- whether they have specific buildings that imply a strategic phase

The current output can approximate this with population, city count, and building resources. The raw city data can explain it more directly.

Example raw-only signal around reliable first donation events:

| group | avg cities | avg citizens | avg wood workers | avg luxury workers | avg scientists | avg priests | avg townhall level | avg stored resources |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| first donation starters | 2.09 | 264 | 223 | 135 | 49 | 2 | 5.1 | 27,057 |
| zero donors at final | 1.96 | 347 | 184 | 170 | 39 | 5 | 4.9 | 80,198 |

And among first starters:

| city bucket | wood worker share | luxury worker share | scientist share | priest share |
|---|---:|---:|---:|---:|
| 1 city | 37.9% | 11.5% | 7.9% | 0.1% |
| 2-3 cities | 36.0% | 16.5% | 7.9% | 0.2% |
| 4+ cities | 29.9% | 24.5% | 6.6% | 0.5% |

This supports a more specific story: first donations happen when players become production-oriented, especially as luxury-resource production becomes more important.

## Recommended Additions To The Lance Output

Add these to `player_snapshot` and `player_island_snapshot`:

- `citizens_total`
- `resource_workers_total`
- `tradegood_workers_total`
- `scientists_total`
- `priests_total`
- `worker_total`
- `resource_worker_share_pct`
- `tradegood_worker_share_pct`
- `scientist_share_pct`
- `priest_share_pct`
- `city_hall_levels_total`
- `avg_city_hall_level`
- `capital_city_count`
- per-resource stored totals:
  - `wood_stored`
  - `wine_stored`
  - `marble_stored`
  - `crystal_stored`
  - `sulfur_stored`

Add these as separate optional detail tables:

- `city_snapshot`
  - one row per city per snapshot
  - keeps worker allocation, city hall level, stored resources, capital flag
- `city_building_snapshot`
  - one row per city/building-slot/snapshot
  - normalized from `p1t..p17t` and `p1l..p17l`
- `donation_event_snapshot`
  - one row per raw donation record
  - keeps donation type and amount before aggregation

## Bottom Line

We are not stripping too much for high-level descriptive analytics. But for explaining **why** players start donating, we are stripping important behavioral features.

The highest-value additions are worker allocation, city hall level, per-resource stockpiles, capital count, and optional city-level detail.
