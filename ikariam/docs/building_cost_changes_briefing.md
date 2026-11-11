# Building Cost Changes — Briefing

> **Column names changed (2026-11).** This note uses the old names. In the current tables:
> `building_base_cost_*` → `standing_cost_undiscounted_*`, `estimated_building_cost_*` → `standing_cost_today_*`,
> `historical_building_cost_*` → `standing_cost_at_build_*`, `lifetime_construction_spend_*` → `ever_built_cost_at_build_*`,
> `estimated_*_resource_value` → `*_tied_up`, `estimated_<r>_cost_factor` → `cost_factor_today_<r>`,
> event columns `level_cost_*` → `cost_undiscounted_*`, `paid_cost_*` → `cost_at_build_*`, `factor_*` → `cost_factor_at_build_*`,
> `is_opening_stock` → `is_preexisting`. `observed_construction_coverage` is replaced by `preexisting_share`
> (= 1 − coverage, NULL without buildings) and `opening_stock_base_cost_total` is no longer published.
> See README *Building Costs*.

**Status:** merged to `main`, 67 tests passing, verified against all 36 snapshots.

---

## In one paragraph

We found that our building-value numbers were wrong in two separate ways: we
were **not counting the town hall at all**, and we were **applying today's
discounts to buildings constructed years earlier**. Both are fixed. Building
value is now reconstructed level by level, with each level priced at the
discount that was actually active when it was built. We also publish two new
event tables that make the whole calculation auditable — and that open up
analyses we simply could not do before, such as when players built what, and
how much value they destroyed by demolishing.

---

## The problem

### Problem 1: the town hall was invisible

Each city has 17 numbered building slots. The town hall is not one of them — the
game stores its level in a separate field. Our cost calculation only read the 17
slots, so **every city's largest single building was missing from its value**.

| resource | understated by |
| --- | ---: |
| marble | **37.9%** |
| wood | **18.3%** |
| total building value | **20.8%** |

Anyone ranking players by marble investment was getting materially wrong
answers.

### Problem 2: today's discounts were applied to the whole past

In the game, buildings get cheaper as a player completes research and levels up
their reduction buildings. We were taking a player's **current** discount and
applying it to **every building they own**, including levels built long before
those discounts existed.

Worst case this misattributed **46 percentage points** of discount. It also
produced a metric that could *fall* while a player was doing well:

```
Before completing research:  100,000 × 0.94 = 94,000
After completing research:   100,000 × 0.86 = 86,000
```

The player lost 8,000 of measured value by *progressing*. That is not a usable
development measure.

---

## What we changed

1. **The town hall is now counted** — folded in as an extra "position 0"
   building, so it goes through exactly the same price lookup, validation and
   summing as every other building. A missing town hall price now fails loudly
   instead of silently counting as zero.

2. **Every building level is now priced at its own vintage.** We follow each
   building position across consecutive snapshots. A level that is absent in one
   snapshot and present in the next was built in between, so we price it at the
   discount state of that window — specifically the midpoint of the two
   surrounding snapshots. The remaining uncertainty is confined to a single
   interval instead of a player's entire history.

3. **Standing value is accounted for as a flow:** everything paid for, minus
   everything torn down, with each demolished level written off at the value it
   actually carried. This guarantees that a later rebuild never retroactively
   changes an earlier snapshot — no number depends on information from the
   future.

---

## The new tables

### `building_construction_event` — 3,538,847 rows

One row per **building level ever constructed**. For each level: which city and
position, the building type, the level, the window it appeared in, the discount
factor applied, its undiscounted price, and what was actually paid.

### `building_demolition_event` — 102,745 rows

One row per **building level that stopped standing**, carrying the value it held
at that moment. Standing value equals construction minus demolition, so this
table explains every difference between the two headline measures.

### New columns on all four existing tables

Added to `city_snapshot`, `player_snapshot`, `island_snapshot` and
`donation_analytics_player_island_snapshot`:

| column | meaning |
| --- | --- |
| `historical_building_cost_*` | what was paid for the buildings **still standing** |
| `lifetime_construction_spend_*` | what was paid for **every level ever built**, including demolished ones; never decreases |
| `opening_stock_base_cost_total` | the portion we cannot date (buildings already there when we first saw them) |
| `observed_construction_coverage` | per-row data-quality measure: how much of this row we could actually date |

Nothing was removed. The existing `building_base_cost_*` (list price) and
`estimated_building_cost_*` (rebuild cost at today's discounts) columns are
unchanged, so no existing analysis breaks.

---

## Why we need this

- **The old numbers were materially wrong.** Marble understated by a third;
  building value understated by 8.3% even after the town hall fix.
- **One of them was methodologically indefensible.** Using a player's current
  research state to value their entire construction history cannot be defended
  in a publication, and it produced a metric that moved the wrong way.
- **We now have a genuine development measure.** `lifetime_construction_spend_*`
  only ever goes up, so it can be used for growth, ranking and trajectory
  analysis — which the old metric could not support.

---

## Additional benefits

1. **Demolition is measurable for the first time.** Previously, a building that
   was torn down simply vanished from the data and the resources spent on it
   disappeared with it. We can now quantify destroyed value: **418,891,292
   resources, 1.1% of all construction spend.**

2. **Construction becomes a time series, not just a stock.** We can now ask when
   a player built what, how fast they developed, and how building activity
   responded to events — none of which was possible from snapshot totals alone.

3. **Every number is auditable.** Any aggregate can be traced to the individual
   building levels behind it. We verified this: replaying all 3.5 million levels
   and subtracting every demolition reproduces the known building value for all
   **333,885** city-snapshot rows with a **maximum difference of zero**.

4. **Data quality is visible per row.** `observed_construction_coverage` lets an
   analysis exclude poorly observed cities instead of silently mixing good and
   bad data.

5. **Three clearly separated concepts** replace one overloaded number: list
   price, rebuild cost at today's prices, and what was actually paid. Each means
   something precise and is documented as such.

---

## Numbers at a glance

Averaged across every city-snapshot row, standing buildings were paid for at
**72.1%** of list price, against **66.6%** under the old method:

| measure (summed across all city-snapshot rows) | total | share of list price |
| --- | ---: | ---: |
| list price, undiscounted | 418,911,056,561 | 100.0% |
| **actually paid, still standing (new)** | **302,086,328,821** | **72.1%** |
| old estimate (today's discount on everything) | 278,898,472,739 | 66.6% |
| **lifetime construction spend (new)** | **304,505,307,489** | 72.7% |

One-time resource quantities, from the event ledgers:

| quantity | resources |
| --- | ---: |
| paid for every level ever built | 38,520,663,046 |
| destroyed by demolition | 418,891,292 (1.1%) |
| still standing at last observation | 38,101,771,754 |

---

## Honest limitations

Worth stating proactively, because they will come up.

- **We cannot date 100% of it.** Levels already present the first time we see a
  building cannot be assigned to a window. That is **2.8% of standing value** —
  small because our data starts at server launch (the first snapshot has 1,487
  players with exactly one city each), so we watch this world almost from the
  beginning. Coverage is **97.2%**.
- **Snapshots are uneven.** Gaps run from 5 to 63 days (mean 16.2), so the
  windows we price into are not uniform.
- **Timing inside a window is unknowable.** 52.5% of built value arrives in
  jumps of more than one level, and we cannot order those levels within the
  window. This is why we use the midpoint.
- **Research timing is nearly settled; reduction buildings are not.** The
  research factor changed across only 3.8% of built value, but reduction-building
  levels changed across 50.6%. That is where the residual uncertainty sits — but
  it is bounded by one interval, not by the whole history.
- **This is still an estimate, not a receipt.** The raw data contains no
  research timestamps and no construction events. We reconstruct; we do not
  observe.

---

## Likely questions

**Does this break existing analyses?**
No. No column was removed or redefined. The new measures are additions.

**Why not publish an uncertainty range instead of one number?**
We considered publishing lower and upper bounds from the two surrounding
snapshots and decided against it: a published interval that gets misread is
worse than a single clearly documented estimate. The coverage column carries the
quality signal instead.

**How confident are we that it's right?**
The reconstruction is verified, not assumed: replaying every level reproduces
the known building totals exactly across all 333,885 rows, and the city, player,
island and player-island levels all report identical totals. 67 automated tests
cover it.

**Why is "lifetime spend" higher than "still standing"?**
The difference is demolition — buildings that were paid for and later torn down.
That gap is the point: it is the first time we can see that value at all.

**Can we do this for a second game server?**
The method carries over, but the construction ledger is the heaviest step in the
pipeline. Adding another country needs a look at memory headroom first.

---

## Appendix: event table columns

Both tables share the same five identity columns, so they join to each other and
to `city_snapshot` on `country_code` + `city_id`.

### `building_construction_event`

**3,538,847 rows** · 24 columns

| # | column | type | unit | description |
| ---: | --- | --- | --- | --- |
| 1 | `country_code` | String | iso2 | Server country code |
| 2 | `city_id` | String | id | SHA1 of the city |
| 3 | `position` | Int64 | enum | Building position 1-17, or 0 for the town hall, which occupies no numbered slot and is tracked by the city's own level column |
| 4 | `building_type` | Int64 | enum | Game building type id from the raw slot data |
| 5 | `building_level` | Int64 | level | The single building level this row accounts for |
| 6 | `built_by_snapshot_id` | String | id | Snapshot by which this level was present |
| 7 | `built_by_snapshot_date` | Date | date | Date of the snapshot by which this level was present |
| 8 | `built_after_snapshot_date` | Date | date | Date of the previous observation of this position; the level appeared between this date and built_by_snapshot_date. Null when the level was already present at first sighting |
| 9 | `is_opening_stock` | Boolean | boolean | True when the level was already there the first time this building was observed, so it cannot be dated and is priced at that first observation's factor |
| 10 | `factor_wood` | Float64 | ratio | Applied wood cost multiplier: the midpoint of this city's wood factor at the two bracketing observations |
| 11 | `factor_crystal` | Float64 | ratio | Applied crystal cost multiplier: the midpoint of this city's crystal factor at the two bracketing observations |
| 12 | `factor_marble` | Float64 | ratio | Applied marble cost multiplier: the midpoint of this city's marble factor at the two bracketing observations |
| 13 | `factor_sulfur` | Float64 | ratio | Applied sulfur cost multiplier: the midpoint of this city's sulfur factor at the two bracketing observations |
| 14 | `factor_wine` | Float64 | ratio | Applied wine cost multiplier: the midpoint of this city's wine factor at the two bracketing observations |
| 15 | `level_cost_wood` | Float64 | wood | Undiscounted wood cost of this one level: the cumulative lookup value minus the level below it |
| 16 | `level_cost_crystal` | Float64 | crystal | Undiscounted crystal cost of this one level: the cumulative lookup value minus the level below it |
| 17 | `level_cost_marble` | Float64 | marble | Undiscounted marble cost of this one level: the cumulative lookup value minus the level below it |
| 18 | `level_cost_sulfur` | Float64 | sulfur | Undiscounted sulfur cost of this one level: the cumulative lookup value minus the level below it |
| 19 | `level_cost_wine` | Float64 | wine | Undiscounted wine cost of this one level: the cumulative lookup value minus the level below it |
| 20 | `paid_cost_wood` | Float64 | wood | Estimated wood paid for this level: level_cost_wood times factor_wood |
| 21 | `paid_cost_crystal` | Float64 | crystal | Estimated crystal paid for this level: level_cost_crystal times factor_crystal |
| 22 | `paid_cost_marble` | Float64 | marble | Estimated marble paid for this level: level_cost_marble times factor_marble |
| 23 | `paid_cost_sulfur` | Float64 | sulfur | Estimated sulfur paid for this level: level_cost_sulfur times factor_sulfur |
| 24 | `paid_cost_wine` | Float64 | wine | Estimated wine paid for this level: level_cost_wine times factor_wine |

### `building_demolition_event`

**102,745 rows** · 19 columns

| # | column | type | unit | description |
| ---: | --- | --- | --- | --- |
| 1 | `country_code` | String | iso2 | Server country code |
| 2 | `city_id` | String | id | SHA1 of the city |
| 3 | `position` | Int64 | enum | Building position 1-17, or 0 for the town hall, which occupies no numbered slot and is tracked by the city's own level column |
| 4 | `building_type` | Int64 | enum | Game building type id from the raw slot data |
| 5 | `building_level` | Int64 | level | The single building level this row accounts for |
| 6 | `removed_by_snapshot_id` | String | id | Snapshot by which this level no longer stood |
| 7 | `removed_at_snapshot_date` | Date | date | Date of the snapshot by which this level no longer stood |
| 8 | `built_by_snapshot_date` | Date | date | Date of the construction event this removal reverses, so the level is written off at the value it actually carried |
| 9 | `is_opening_stock` | Boolean | boolean | True when the removed level came from undatable opening stock |
| 10 | `level_cost_wood` | Float64 | wood | Undiscounted wood cost of the removed level |
| 11 | `level_cost_crystal` | Float64 | crystal | Undiscounted crystal cost of the removed level |
| 12 | `level_cost_marble` | Float64 | marble | Undiscounted marble cost of the removed level |
| 13 | `level_cost_sulfur` | Float64 | sulfur | Undiscounted sulfur cost of the removed level |
| 14 | `level_cost_wine` | Float64 | wine | Undiscounted wine cost of the removed level |
| 15 | `paid_cost_wood` | Float64 | wood | Estimated wood that had been paid for the removed level, withdrawn from the standing total |
| 16 | `paid_cost_crystal` | Float64 | crystal | Estimated crystal that had been paid for the removed level, withdrawn from the standing total |
| 17 | `paid_cost_marble` | Float64 | marble | Estimated marble that had been paid for the removed level, withdrawn from the standing total |
| 18 | `paid_cost_sulfur` | Float64 | sulfur | Estimated sulfur that had been paid for the removed level, withdrawn from the standing total |
| 19 | `paid_cost_wine` | Float64 | wine | Estimated wine that had been paid for the removed level, withdrawn from the standing total |
