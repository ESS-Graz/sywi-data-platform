# Ikariam building value and discount findings

## Purpose

This document summarizes the review of the Ikariam building-cost calculation,
the legacy account-age discount, and the limits of interpreting the result as
historical player investment.

## Executive summary

The current pipeline calculates the undiscounted cumulative base cost of all
buildings visible in a city and then multiplies the complete amount by a factor
inferred from the player's account age.

This creates a non-monotonic metric: when a player crosses a research-age
threshold, their calculated value can decrease even if they have not demolished
anything. It also incorrectly applies the player's inferred current research
discount to building levels constructed before that research was completed.

The recommendation is:

1. Use undiscounted cumulative base costs as the canonical value of the
   buildings currently present.
2. Name this metric `current_building_base_value` or similarly. It is not the
   player's total historical expenditure.
3. Keep account age separate and use it for peer comparisons or statistical
   normalization, not to modify the underlying building value.
4. Retain the legacy discounted calculation only if required for verification,
   and label it explicitly as a legacy metric.

## What the building-cost calculation measures

Each city contains 17 building positions:

```text
p1t / p1l ... p17t / p17l
```

For each position, `join_building_costs()` looks up the cumulative base cost by
building type and level. Five resource columns are added per position:

```text
g{position}h  wood
g{position}q  marble
g{position}k  crystal
g{position}w  wine
g{position}s  sulphur
```

This produces 85 cost columns: 17 positions times 5 resources. The following
city-metric step sums them to obtain the cumulative base value of the buildings
currently visible in the city.

The lookup values are cumulative. For example, the value for level 10 is the
sum of the construction costs for levels 1 through 10, not only the cost of the
level-10 upgrade.

## What the calculation cannot measure

The raw snapshots cannot reconstruct the exact resources historically spent by
a player. They do not contain:

- research-completion timestamps;
- the research state when each building level was constructed;
- the reduction-building levels present when each upgrade was purchased;
- a complete history of constructed and demolished buildings;
- exact resources refunded when buildings were demolished;
- individual building construction events between snapshots.

Consequently, the current building cost is a measure of current infrastructure
stock at undiscounted base prices. It is not a lifetime expenditure measure.

## Effect of demolition

Players can demolish buildings to:

- free a limited building slot;
- recover part of the resources;
- remove temporary buildings after their purpose has been fulfilled;
- change the specialization of a city.

Examples include removing a Workshop after permanent military upgrades are
finished or reducing temporary storage capacity after an expensive expansion.

When a building is demolished, most of its historical cost disappears from the
snapshot data. Therefore a player may have invested considerably more resources
than the buildings currently present indicate.

This is not a problem if the metric is explicitly defined as current
infrastructure value. It is a problem if the metric is described as total
resources spent.

## The legacy research discount

The legacy calculation uses these factors:

| Account-age band | Factor | Assumed research state |
| --- | ---: | --- |
| Below 180,000 seconds (about 2.08 days) | 1.00 | No discount |
| Up to 1,440,000 seconds (about 16.67 days) | 0.98 | Pulley: 2% |
| Up to 13,149,000 seconds (about 152.19 days) | 0.94 | Pulley + Geometry: 6% |
| Above 13,149,001 seconds | 0.86 | Pulley + Geometry + Spirit Level: 14% |

The factors correspond to real cumulative Ikariam research discounts:

- Pulley: 2%;
- Geometry: an additional 4%, or 6% cumulative;
- Spirit Level: an additional 8%, or 14% cumulative.

However, no justification was found for the account-age thresholds. The
historical SQL contains the same values but no source or explanation. Research
completion depends on academies, scientists, player choices, and other factors;
it is not determined by account age.

The SQL also uses unusual strict inequalities that leave small gaps at exact
boundaries. The Python implementation reproduces this behavior for legacy
parity.

## Why applying the factor to cumulative costs is problematic

The pipeline applies the player's factor to all cumulative building resources:

```text
adjusted value = complete cumulative base value × current factor
```

Example with a cumulative base value of 100,000:

```text
Before Spirit Level: 100,000 × 0.94 = 94,000
After Spirit Level:  100,000 × 0.86 = 86,000
```

The player loses 8,000 of evaluated value merely by completing research.

If the player then constructs another building worth 5,000 base resources:

```text
105,000 × 0.86 = 90,300
```

They have built more but are still evaluated below their previous value of
94,000. This makes the adjusted metric non-monotonic and unsuitable as a stable
measure of development or investment.

The calculation also assumes that the newest research discount applied to all
older building levels. In reality, levels constructed before completing the
research cost more. Per-city reduction buildings introduce another unobserved
historical discount that the legacy calculation does not reconstruct.

At best, the discounted total approximates the cost of rebuilding the current
buildings under one inferred research state. It should not be presented as
historical expenditure.

## Direct research information in the raw data

The avatar data includes a `research_points` column. Across all 108,027 avatar
rows in the 36 available snapshots, its value is always exactly `0.0`.
Therefore it cannot be used to infer completed research.

Certain buildings provide reliable positive evidence of completed prerequisite
research:

| Building type | Building | Minimum research evidence |
| ---: | --- | --- |
| 9 | Tavern | At least Pulley, because Wine Culture occurs later in the Economy chain |
| 24 | Architect's Office | At least Geometry, because Architecture follows Geometry |
| 26 | Wine Press | Spirit Level, because Wine Cellars follows Spirit Level |
| 29 | Depot/Dump | Spirit Level, because Depot occurs later in the Economy chain |

This evidence only works in one direction. The presence of such a building
proves a minimum research state, but its absence proves nothing: construction
is optional and buildings can be demolished.

In the latest snapshot, containing 551 players:

- 514 players have Tavern evidence for Pulley;
- 379 have Architect's Office evidence for Geometry;
- 360 have Wine Press or Depot evidence for Spirit Level;
- 8 have definite Spirit Level evidence while younger than the legacy
  152.19-day threshold.

The last result proves that the age heuristic is wrong for at least some
players. Improving that heuristic would still not solve the conceptual problem
of applying one factor to all cumulative historical construction.

## Snapshot-relative account age

The reviewed implementation used the fixed Unix timestamp `1415923200`
(`2014-11-14T00:00:00Z`) to calculate account age for every snapshot.

Because the raw data contains snapshots from `2013-04-25` through `2014-11-13`,
using a single November 2014 reference date assigns future account age to older
snapshots. For the first snapshot, all 1,480 players passing the registration
filter are approximately zero days old relative to the snapshot but about 568
days old relative to the fixed timestamp. The fixed timestamp therefore assigns
all of them the strongest legacy discount.

Account age should be calculated relative to each snapshot date. This remains
important for age-based comparisons even if account age is removed from the
building-value calculation.

## Scientifically defensible metrics

The undiscounted cumulative value is scientifically defensible when its meaning
is stated precisely:

> The undiscounted base-resource value of the buildings currently present in
> the player's cities.

Further-developed players will naturally have a larger absolute value. That is
appropriate when measuring current infrastructure, but it is not sufficient for
comparing development performance or generosity.

Recommended separate measurements are:

- `current_building_base_value`: current infrastructure at base prices;
- `stored_resources`: resources currently visible in storage;
- `account_age_days`: time since registration at the snapshot;
- `total_donations`: observed contributions;
- age- and development-relative analytical indicators derived from the factual
  measurements above.

The base measurements should remain separate. A statistical analysis can then
compare players with peers of similar age and development without changing the
underlying facts.

## Expected building value by account age

A transparent initial approach is:

1. Aggregate undiscounted building value per player and snapshot.
2. Group players into account-age ranges within the same snapshot.
3. Calculate the median building value for each age group.
4. Compare each player's actual value with that median.

For example:

```text
account age:         120 days
actual base value:   800,000
expected median:     600,000
difference:         +200,000
relative difference:    +33%
```

The median is more robust than the mean when a small number of highly developed
players have extreme values.

A later model could estimate a smooth relationship between
`log(1 + building_value)` and account age. It should account for snapshot or
calendar effects, avoid placing observations from the same player in both
training and validation sets, and report uncertainty. The simple age-group
median is preferable until a more complex model demonstrates a clear benefit.

For generosity analysis, building value and account age are context variables,
not generosity themselves. Donations should be compared among players with
similar opportunity and development rather than divided by one unstable metric
without validation.

## Building-cost CSV review

The file `data/raw/ikariam/building_costs.csv` loads successfully and contains:

- 946 rows;
- the expected resource columns;
- no duplicate `(building_type, building_level)` keys.

The real city data uses 834 distinct nonzero building type/level combinations.
The CSV covers 809 of them. The 25 missing combinations are all levels 1–25 of
building type 31.

Type 31 appears in 3,149 building slots across the snapshots, beginning on
`2013-10-24`. Its introduction date and maximum level identify it as the Black
Market.

The legacy SQL also contains no entries for building type 31. It contains many
entries for other building types at building level 31, but no condition of the
form `p1t = 31`. Therefore the missing CSV rows reproduce a legacy omission,
not a CSV-conversion mistake.

The current join replaces missing cost lookups with zero. As a result, every
Black Market is currently assigned zero value. Missing nonempty building
lookups should instead fail validation.

## Historical Black Market costs

Historical Ikariam wiki tables provide the undiscounted per-level Black Market
costs for levels 1–25. The building uses wood and marble. These per-level costs
must be cumulatively summed to match the convention used by the CSV.

Selected cumulative values are:

| Level | Cumulative wood | Cumulative marble |
| ---: | ---: | ---: |
| 1 | 440 | 260 |
| 2 | 1,327 | 785 |
| 10 | 36,321 | 22,302 |
| 20 | 398,974 | 256,940 |
| 25 | 1,014,299 | 659,558 |

Complete cumulative type-31 values:

| Level | Wood | Marble |
| ---: | ---: | ---: |
| 1 | 440 | 260 |
| 2 | 1,327 | 785 |
| 3 | 2,687 | 1,592 |
| 4 | 4,577 | 2,718 |
| 5 | 7,093 | 4,227 |
| 6 | 10,381 | 6,215 |
| 7 | 14,644 | 8,816 |
| 8 | 20,149 | 12,206 |
| 9 | 27,235 | 16,609 |
| 10 | 36,321 | 22,302 |
| 11 | 47,911 | 29,617 |
| 12 | 62,602 | 38,948 |
| 13 | 81,091 | 50,755 |
| 14 | 104,179 | 65,567 |
| 15 | 132,779 | 83,987 |
| 16 | 167,922 | 106,695 |
| 17 | 210,761 | 134,452 |
| 18 | 262,581 | 168,106 |
| 19 | 324,799 | 208,592 |
| 20 | 398,974 | 256,940 |
| 21 | 486,812 | 314,274 |
| 22 | 590,168 | 381,820 |
| 23 | 711,056 | 460,907 |
| 24 | 851,652 | 552,971 |
| 25 | 1,014,299 | 659,558 |

The official Gameforge table independently supports the historical raw costs.
For example, it displays level-1 values of 378 wood and 223 marble, which match
the base values after the 14% Spirit Level discount:

```text
440 × 0.86 ≈ 378
260 × 0.86 ≈ 223
```

## Recommended implementation decisions

1. Add the 25 cumulative type-31 rows to `building_costs.csv`.
2. Validate that `(building_type, building_level)` is unique in the lookup.
3. Validate that every nonzero type/level pair used by the city data has a
   lookup row; do not silently convert missing real buildings to zero.
4. Continue treating empty positions `(0, 0)` as zero cost.
5. Preserve undiscounted resource totals as the canonical building value.
6. Remove account-age discounting from canonical building-resource totals.
7. If legacy parity remains necessary, expose the discounted result under an
   explicitly legacy name and keep it out of canonical analytical metrics.
8. Calculate account age relative to each snapshot and use it for peer analysis
   rather than modifying factual infrastructure values.

## Open questions for the team

1. Is the intended measure current infrastructure, historical expenditure,
   development performance, or donation generosity? These are different
   scientific constructs and require different metrics.
2. Is exact output parity with the legacy SQL still required for public data,
   or only for a verification layer?
3. Should current stored resources be combined with current building value, or
   exposed separately because one is liquid stock and the other is
   infrastructure?
4. Which population should define age peers: all visible players, active
   players only, or players meeting another participation rule?
5. Should expected-value models be fitted separately per snapshot, or should a
   pooled model include snapshot effects?

## Sources

- Historical legacy SQL from Git object:
  `9f6483d9aea9c23c522114cc6e4b480abead2f54`
- [Ikariam research overview](https://ikariam.fandom.com/wiki/Research)
- [Geometry](https://ikariam.fandom.com/wiki/Research%3AGeometry)
- [Spirit Level](https://ikariam.fandom.com/wiki/Research%3ASpirit_Level)
- [Architect's Office (pre-8.8)](https://ikariam.fandom.com/wiki/Building%3AArchitect%27s_Office_%28Pre_8.8%29)
- [Wine Press](https://ikariam.fandom.com/wiki/Building%3AWine_Press)
- [Guide to Building](https://ikariam.fandom.com/wiki/Guide_to_Building)
- [Historical Black Market levels 21–25](https://ikariam.fandom.com/tr/wiki/Building%3ABlack_Market/21-25)
- [Official Gameforge Black Market table](https://gameforge.com/en-GB/games/ikariam-black-market.html)

