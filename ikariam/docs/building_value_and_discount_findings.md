# Ikariam building value and discount findings

## Purpose

This document summarizes the review of the Ikariam building-cost calculation,
the legacy account-age discount, and the limits of interpreting the result as
historical player investment.

## Executive summary

The reviewed pipeline calculated the undiscounted cumulative base cost of all
buildings visible in a city and then overwrote it with an amount multiplied by
a factor inferred from the player's account age.

This creates a non-monotonic metric: when a player crosses a research-age
threshold, their calculated value can decrease even if they have not demolished
anything. It also incorrectly applies the player's inferred current research
discount to building levels constructed before that research was completed.

The implemented panel model is:

1. Preserve `building_base_cost_*` as the factual, undiscounted value of the
   buildings currently present.
2. Calculate `account_age_days` independently at each snapshot.
3. Expose a separate `estimated_building_cost_*` family as a rebuilding-cost
   proxy, never as observed historical expenditure.
4. Infer its research component from the stronger of a documented age
   heuristic and one-way building evidence, with factor, source, and evidence
   tier exposed.
5. Apply each city's observed reduction-building level per resource at that
   snapshot, publishing the levels and resulting per-resource factors.
6. Keep stored resources separate and combine them with the estimate only in
   explicitly named `estimated_*_resource_value` fields.

## Data provenance

The chain from the game to the current pipeline is fully traced:

1. **Server backup.** `ikariam-raw/DE_all_createDB_withoriginaldata.sql`
   (186 MB, recovered 2026-09-14) is a phpMyAdmin 3.4.10 dump of
   `backup_ikariam_de_23`, a backup of the live Ikariam DE server database
   (MySQL 5.5.29). It contains `CREATE DATABASE` plus data for all 36 German
   snapshots, each exported on its snapshot date, mostly around 10-11am.
   Each snapshot database holds exactly four tables: `avatar`, `city`,
   `donation`, and `island`. There are no column comments, no enums, and no
   building-name dictionary.
2. **CSV export.** `1_2_Save_DBs_as_CSV.txt` in the legacy R project ran
   `SELECT * FROM <db>.<table> INTO OUTFILE ...` per snapshot and table,
   semicolon-delimited. A plain `SELECT *`, so values passed through unchanged.
3. **Legacy processing.** The R scripts widened and cleaned those CSVs.
   `4_Update_Cities_Building_Resources_Use.R` read `City_Gebäudekosten.csv`
   (columns `building, level, wood, quarry, crystal, wine, sulphur`, asserted
   to be exactly 946 rows) and matched it on `building == p{n}t` and
   `level == p{n}l`. The legacy SQL did the same with roughly 946 x 17 literal
   `UPDATE ... WHERE p1t = 23 AND p1l = '1'` statements. Today's
   `building_costs.csv` is that same table, renamed
   (`quarry` becomes `cost_quartz`, which is marble) and extended to 971 rows
   by the 25 Black Market rows added on 2026-09-11.
4. **Current raw input.** Per-country, per-snapshot parquet under
   `data/raw/ikariam/<country>/<date>/`. The `city` parquet carries exactly
   the original 49 export columns and no legacy `g*` cost columns, so the
   pipeline recomputes costs from the lookup rather than inheriting them.

Fidelity was verified directly against the dump: all 36 snapshots match on row
count for all four tables (334,060 city rows in total), per-snapshot reduction
building maximum levels and type-31 city counts match, no city contains the
same reducer twice, and `research_points` is zero in every original avatar row.

Three details worth knowing:

- The `de_0207_13` snapshot was exported on 20 Aug 2013, out of order with the
  rest. Its content fits the early-July trend, so it looks like a later
  re-export from backup rather than mislabelled data.
- The DE dump has no `logGovernmentChanges` table, yet an empty
  `logGovernmentChanges.parquet` sits in every snapshot directory. The
  pipeline ignores it.
- Parquet data for `en`, `fr`, `gr`, and `tr` also exists in the sync folder.
  The pipeline currently reads only `de`.

## What the building-cost calculation measures

Each city contains 17 building positions:

```text
p1t / p1l ... p17t / p17l
```

`add_building_base_costs()` reshapes these positions into building rows, looks
up cumulative base costs by building type and level, and sums the costs per
city. It adds five `building_base_cost_*` columns for wood, marble, crystal,
wine, and sulphur directly, without the former 85 per-position cost columns.

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
boundaries. The former Python implementation reproduced this behavior for
legacy parity.

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

## Implemented hybrid estimate

The secondary estimate uses exact calendar-day bands at each snapshot: days
0–2 map to `1.00`, 3–16 to `0.98`, 17–152 to `0.94`, and 153 or more to `0.86`.
At the same time, the strongest qualifying building observed across all of a
player's cities establishes a minimum research tier. Because completed research
persists even if the evidence building is later demolished, that positive
evidence is carried forward through the player's panel but never backward into
earlier snapshots.

The final factor is the smaller of the age and evidence factors. Its source is
`building_evidence` only when evidence makes the factor strictly smaller;
otherwise it is `age_heuristic`. The evidence tier remains visible even when it
does not determine the final factor.

## Local reduction buildings

The research factor alone is not the payable construction factor. Five
city-local buildings each lower one resource's construction demand by one
percentage point per level, additively with research:

| Type | Building | Resource |
| ---: | --- | --- |
| 23 | Carpenter | wood |
| 24 | Architect's Office | marble |
| 25 | Optician | crystal |
| 26 | Wine Press | wine |
| 27 | Firework Test Area | sulphur |

For each city, snapshot, and resource the pipeline calculates:

```text
estimated_<resource>_cost_factor =
    (100 - research reduction points - local reducer level) / 100
estimated_building_cost_<resource> =
    building_base_cost_<resource> × estimated_<resource>_cost_factor
```

The research reduction is `1 - estimated_research_cost_factor` expressed in
whole percentage points (0, 2, 6, or 14). Until version 8.8.0 (2022),
reducers were capped at level 32, so the historical factors range from 0.54
to 1.00; the modern level-50 limit does not apply to these snapshots.
`city_snapshot` publishes the five `*_reduction_building_level` and five
`estimated_*_cost_factor` columns. Aggregate tables sum the per-city
discounted costs and do not publish averaged factors; a weighted implied
factor is the discounted cost divided by the base cost.

Unlike research evidence, a reducer's effect is not carried forward: each
snapshot uses the level observed in that city at that snapshot, so a
demolished reducer stops discounting. Architect's Office and Wine Press
remain positive research evidence at the same time.

The discounted family therefore estimates what the currently observed
buildings would cost under the snapshot's discount state. It is still not
historical expenditure: older levels may predate the research or the current
reducer level, and a reducer's newest level cannot have discounted the upgrade
that created it. Applying one factor to summed cumulative costs may also
differ slightly from the game's per-upgrade rounding.

### Type-ID evidence

The original server dump (see [Data provenance](#data-provenance)) settles two
questions. The `p{n}t` integers are the game's own building-type IDs, copied
out of a backup of the live Ikariam DE database without any intermediate
renumbering step. And the source contains **no building dictionary at all**:
each of the 36 snapshot databases has exactly four tables, no column comments,
no enums, and not one building name anywhere in its 186 MB. There is therefore
no export ID mapping left to recover, and the resource assignment rests on the
following evidence.

- The staggered first appearance of each reducer matches the Economy research
  chain deepening over time, with the cheapest and earliest reducer
  (Carpenter) both present in the first snapshot and by far the most common:

  | Type | Building | First seen | Slots |
  | ---: | --- | --- | ---: |
  | 23 | Carpenter | 2013-04-25, already level 5 | 207,727 |
  | 24 | Architect's Office | 2013-05-09 | 113,988 |
  | 25 | Optician | 2013-05-16 | 15,745 |
  | 27 | Firework Test Area | 2013-05-23 | 12,288 |
  | 26 | Wine Press | 2013-05-30 | 44,882 |

- Type 31 first appears on exactly `2013-10-24`, immediately after the Black
  Market's introduction in patch 0.5.9 in October 2013. That release-date
  anchor independently confirms the numbering follows the game's own history.
- Level-1 lookup costs match the historical buildings: 63 wood (Carpenter),
  185 wood and 106 marble (Architect's Office), 119 wood (Optician), 339 wood
  and 123 marble (Wine Press), and 273 wood and 135 marble (Firework Test
  Area; 272 wood in Developer Tools).
- The [cost audit](building_cost_audit.md) matched each type's full upgrade
  series against Upgrade Watcher 2, whose tables are keyed by the same game
  IDs under the labels `carpentering` 23, `architect` 24, `optician` 25,
  `vineyard` 26, and `fireworker` 27.
- All five lookup series, and every level observed across 334,060 city rows,
  end at exactly level 32, the pre-8.8.0 reduction-building limit.
- The observed ID set is 3-31 with gaps at 1, 2, and 14. Type 1 carries a
  town-hall cost curve in the lookup but never occupies a building slot,
  because the town hall's level is the separate `level` column; those lookup
  rows are simply unused.

What remains unproven is only the name-level link: no game artifact states
that type 23 is the Carpenter. That rests on the community cost tables, now on
much firmer ground because the IDs they are keyed by are the same game IDs
that appear in the raw data.

### Validation

Invalid reducer rows raise instead of being clamped: negative building levels,
reducer levels above 32, and the same reducer twice in one city row. A scan of
all 36 snapshots (334,060 city rows) found none of these and no null slots.
Built reducer slots: 207,626 Carpenter, 113,956 Architect's Office, 15,744
Optician, 44,861 Wine Press, and 12,282 Firework Test Area. The 161 reducer
slots with a type but level 0 are treated as absent, like every level-0 slot.

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

The implemented separate measurements are:

- `building_base_cost_*`: current infrastructure at base prices;
- `estimated_building_cost_*`: an explicitly modeled rebuilding-cost proxy
  under the snapshot's inferred research state and each city's observed
  reduction-building levels;
- `estimated_<resource>_cost_factor` and `*_reduction_building_level`: the
  city-level factors and reducer levels behind that proxy;
- `*_stored`: resources currently visible in storage;
- `estimated_*_resource_value`: modeled building cost plus visible storage;
- `account_age_days`: time since registration at the snapshot;
- `donations_total`: observed contributions;
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

The [2026-09-11 row-by-row audit](building_cost_audit.md) confirms the cumulative
format and exact legacy-SQL parity, but records unresolved price disagreements
with historical community tables. Coverage of raw building pairs is complete;
historical correctness of every inherited price is not established.

The file `data/raw/ikariam/building_costs.csv` loads successfully and contains:

- 971 rows after adding the 25 Black Market rows on 2026-09-11;
- the expected resource columns;
- no duplicate `(building_type, building_level)` keys.

The real city data uses 834 distinct nonzero building type/level combinations.
The CSV now covers all 834. Previously it covered 809, omitting levels 1–25
of building type 31.

Type 31 appears in 3,149 building slots across the snapshots, beginning on
`2013-10-24`. We accept its identification as the Black Market based on the
October 2013 introduction of that building in version 0.5.9 and its 25-level
limit. This is an inference from the release history and observed data, not
a recovered export-ID mapping. The previous identification as Pirate Fortress
in this document was incorrect.

The legacy SQL also contains no entries for building type 31. It contains many
entries for other building types at building level 31, but no condition of the
form `p1t = 31`. Therefore the missing CSV rows reproduce a legacy omission,
not a CSV-conversion mistake.

The former join replaced missing cost lookups with zero, assigning every Black
Market zero value. Lookup validation now rejects missing nonempty buildings;
the accepted historical costs below resolve this data gap.

### Black Market cost sources and reconstruction

Level 1 uses 440 wood and 260 marble, as listed in the French wiki and the
Greek wiki's cost arrays. Levels 2–25 use the base upgrade costs in Ikariam
Upgrade Watcher 2, whose changelog records Black Market support on 2013-10-21.
The Greek wiki's arrays agree with those levels. These are community sources;
their agreement supports the accepted values but is not an archived official
2013 game export. The French page's level-2 wood figure disagrees, so that
page is used only as corroboration for level 1.

The 378 wood and 223 marble listed in other tables for level 1 are consistent
with a 14% research reduction and rounding down; they are not used as base
costs. Crystal, wine, and sulphur costs are zero at every level.

Each CSV row is the sum of upgrade costs from level 1 through that row's level.
For example, level 2 totals 1,327 wood and 785 marble; level 25 totals
1,014,299 wood and 659,558 marble. No research discount is included.

The CSV is tracked in Git at `data/raw/ikariam/building_costs.csv`, an explicit
exception to the otherwise ignored `data/` tree. The following accepted
cumulative rows are also retained here as a readable record of the addition:

```csv
building_type;building_level;cost_holz;cost_quartz;cost_kristall;cost_wein;cost_schwefel
31;1;440;260;0;0;0
31;2;1327;785;0;0;0
31;3;2687;1592;0;0;0
31;4;4577;2718;0;0;0
31;5;7093;4227;0;0;0
31;6;10381;6215;0;0;0
31;7;14644;8816;0;0;0
31;8;20149;12206;0;0;0
31;9;27235;16609;0;0;0
31;10;36321;22302;0;0;0
31;11;47911;29617;0;0;0
31;12;62602;38948;0;0;0
31;13;81091;50755;0;0;0
31;14;104179;65567;0;0;0
31;15;132779;83987;0;0;0
31;16;167922;106695;0;0;0
31;17;210761;134452;0;0;0
31;18;262581;168106;0;0;0
31;19;324799;208592;0;0;0
31;20;398974;256940;0;0;0
31;21;486812;314274;0;0;0
31;22;590168;381820;0;0;0
31;23;711056;460907;0;0;0
31;24;851652;552971;0;0;0
31;25;1014299;659558;0;0;0
```

## Recommended implementation decisions

1. Use the accepted cumulative Black Market rows above for type 31 in
   `building_costs.csv` (implemented).
2. Validate that `(building_type, building_level)` is unique in the lookup.
3. Validate that every nonzero type/level pair used by the city data has a
   lookup row; do not silently convert missing real buildings to zero.
4. Continue treating empty positions `(0, 0)` as zero cost.
5. Preserve undiscounted resource totals as the canonical building value.
6. Keep the hybrid research-cost estimate in a separate, explicitly estimated
   field family with factor provenance.
7. Calculate account age relative to each snapshot and never overwrite factual
   base-cost fields with an age-derived value.
8. Carry positive building evidence forward only; never infer it backward from
   a future observation.

## Remaining analytical questions

1. Is the intended measure current infrastructure, historical expenditure,
   development performance, or donation generosity? These are different
   scientific constructs and require different metrics.
2. Which population should define age peers: all visible players, active
   players only, or players meeting another participation rule?
3. Should expected-value models be fitted separately per snapshot, or should a
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
- [Gameforge discussion: completed research remains permanent](https://forum.ikariam.gameforge.com/forum/thread/102076-vor%C3%BCbergehende-forschungen-verbesserungen/)
- [Gameforge discussion: academy can be demolished after research completion](https://forum.ikariam.gameforge.com/forum/thread/47730-que-faire-une-fois-les-recherches-termin%C3%A9es/)
- [Patch 0.5.9: Black Market introduction](https://ikariam.fandom.com/wiki/Patch_0.5.9)
- [Ikariam Upgrade Watcher 2: historical base costs and changelog](https://greasyfork.org/pt/scripts/5263-ikariam-upgrade-watcher-2/code)
- [French wiki: level-1 Black Market costs](https://ikariam.fandom.com/fr/wiki/Marche_noir)
- [Greek wiki: Black Market cost arrays](https://ikariam.fandom.com/el/wiki/Μαύρη_Αγορά)
- [Gameforge forum building-level reference](https://forum.ikariam.gameforge.com/forum/thread/102643-wbbl-worldwide-biggest-building-levels/)
