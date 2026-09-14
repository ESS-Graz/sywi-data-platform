# Resource-reduction buildings: implementation handoff

## Status (2026-09-11)

Implemented. Decisions taken during implementation:

- Type IDs 23 (Carpenter), 24 (Architect's Office), 25 (Optician), 26 (Wine
  Press) and 27 (Firework Test Area) are encoded in one named constant. The
  original server dump, recovered on 2026-09-14, shows the raw `p{n}t` values
  are the game's own building-type IDs and that the source carries no building
  dictionary, so the handoff's "verify against the export's building
  dictionary" step has no artifact to check and is closed. The resource
  assignment rests on cost series, level limits, first-appearance dates and a
  patch-date anchor; only the name-level link remains an inference. See
  [the findings](building_value_and_discount_findings.md#type-id-evidence).
- `estimated_building_cost_*` keeps its name; schema descriptions state its
  counterfactual meaning.
- Reducer levels and per-resource factors are published only in
  `city_snapshot`. Aggregate tables carry summed base and discounted costs.
- Invalid reducer rows raise instead of being clamped: negative levels, levels
  above 32 and duplicate reducers in one city. The raw data contains none.

## Objective

Extend the panel-data pipeline so its optional discounted building-cost estimate
accounts for Ikariam's city-local resource-reduction buildings as well as the
player-wide construction research discount.

This is an implementation handoff, not evidence that the discounted estimate is
historical expenditure. The undiscounted building-cost columns must remain the
primary, stable measure of building stock.

## Why the current calculation is incomplete

`compute_city_metrics()` currently multiplies every cumulative base-resource
cost by the single player/snapshot column `estimated_research_cost_factor`:

```python
estimated_building_cost_resource = building_base_cost_resource * research_factor
```

That represents only the estimated research state. Ikariam also has five
resource-specific buildings. Each level lowers demand for one resource by one
percentage point, and the effect applies only in the city containing the
building.

| Reduction building | Resource | Effect per level | Scope |
| --- | --- | ---: | --- |
| Carpenter | wood | 1 percentage point | containing city |
| Architect's Office | marble | 1 percentage point | containing city |
| Optician | crystal glass | 1 percentage point | containing city |
| Firework Test Area | sulphur | 1 percentage point | containing city |
| Wine Press | wine | 1 percentage point | containing city |

The building reduction is additive with the research reduction. A single
factor for all resources is therefore not valid once city-local buildings are
included.

Example: with the full 14% research discount, a level-20 Carpenter and a
level-10 Architect's Office, the estimated factors are 0.66 for wood and 0.76
for marble. The other resource factors remain 0.86 unless their own reduction
buildings are present.

## Rules relevant to this dataset

The snapshots cover 2013-04-25 through 2014-11-13. During that period:

- Pulley reduced construction resource demand by 2%.
- Geometry added 4%, for a cumulative 6%.
- Spirit Level added 8%, for a cumulative 14%.
- Each reduction building contributed 1% per level for its resource.
- Reduction buildings were capped at level 32, so the maximum combined
  reduction was 46% and the minimum payable factor was 0.54.

Version 8.8.0 raised the reduction-building limit to level 50 in 2022. Modern
documentation therefore describes a 64% maximum reduction and a 0.36 payable
factor. **Do not apply that modern limit to these historical snapshots.**

Research is player-wide and permanent. A reduction building's benefit is
city-local and depends on that city's observed building level at the snapshot.
Do not carry a demolished reduction building's level forward as if its benefit
were permanent. This differs from the existing building-prerequisite evidence
used to infer completed research, which can legitimately be carried forward.

## Important interpretation constraint

The data shows the current level of each building at each snapshot; it does not
show the sequence and exact time of every historical upgrade.

Applying a snapshot's research state and reduction-building level to all
cumulative base costs estimates this counterfactual quantity:

> What the currently observed building stock would cost under the discount
> state observed or inferred at this snapshot.

It does **not** estimate what the player actually spent. Older levels may have
been built before research was completed or before the reduction building
reached its current level. When a reduction building upgrades itself, its new
level cannot have discounted the upgrade that created that level.

Keep the following concepts separate:

- `building_base_cost_*`: undiscounted cumulative cost from the lookup; primary
  comparable building-stock measure.
- `estimated_building_cost_*`: optional snapshot-state discounted rebuild
  estimate; model-derived, not observed expenditure.
- `*_stored`: resources observed in storage at the snapshot.
- `estimated_*_resource_value`: the discounted estimate plus observed storage.

If practical, improve the public name or metadata for the second family to make
the counterfactual meaning explicit (for example,
`estimated_snapshot_discounted_building_cost_*`). Avoid an unnecessary breaking
rename unless all downstream consumers and schemas are migrated together.

## Proposed calculation

First derive the research reduction from the existing payable factor:

```text
research_reduction = 1 - estimated_research_cost_factor
```

For each resource in each city/snapshot:

```text
reducer_level(resource) = observed local level of its reduction building
effective_reducer_level = clamp(reducer_level, 0, 32)

estimated_resource_cost_factor =
    1 - research_reduction - 0.01 * effective_reducer_level

estimated_building_cost_resource =
    building_base_cost_resource * estimated_resource_cost_factor
```

Equivalent formulation:

```text
estimated_resource_cost_factor =
    estimated_research_cost_factor - 0.01 * effective_reducer_level
```

For the historical data, validate that every result is in `[0.54, 1.00]` when
the research factor is one of `1.00`, `0.98`, `0.94`, or `0.86` and observed
levels are valid. Do not silently accept invalid negative levels or historically
impossible levels above 32; decide whether pipeline policy should raise or flag
these rows after checking actual data.

Floating multiplication remains an estimate. If exact in-game payable amounts
are ever required, investigate where the game rounds each individual upgrade.
Applying one factor after summing cumulative base costs may differ slightly from
rounding each upgrade separately.

## Required implementation work

1. Establish the authoritative raw `building_type` IDs for all five reduction
   buildings. The repository already treats type 24 as Architect's Office and
   type 26 as Wine Press. Do not guess the remaining IDs; verify them against
   the export's building dictionary or another authoritative mapping and encode
   the mapping once in a named constant.

2. Derive one reduction-building level per resource for every city row by
   inspecting the 17 `p{n}t` / `p{n}l` pairs. A helper near the wide-to-long
   normalization in `building_costs.py` may prevent duplicating that logic.

3. Retain these local levels as explicit, inspectable columns, suggested names:

   - `wood_reduction_building_level`
   - `marble_reduction_building_level`
   - `crystal_reduction_building_level`
   - `sulfur_reduction_building_level`
   - `wine_reduction_building_level`

4. In `city_metrics.py`, calculate and retain a resource-specific payable
   factor for each resource, then use it for the corresponding
   `estimated_building_cost_*` column. Suggested name:
   `estimated_<resource>_cost_factor`.

5. Continue calculating `building_base_cost_total` solely from the five base
   columns. Calculate `estimated_building_cost_total` from the five separately
   discounted columns. Do not apply a second aggregate discount.

6. Propagate any new analytical columns intentionally through `schema.py`,
   `city_agg.py`, `higher_agg.py`, `islands.py`, `final_datasets.py`, and
   `donation_analytics.py`. For aggregates, do not average city-level discount
   factors unless that statistic has a clear interpretation. Weighted implied
   factors can be derived as discounted cost divided by base cost where useful.

7. Preserve the existing research-inference logic. Architect's Office and Wine
   Press remain positive evidence of research prerequisites while also having
   their separate direct, local effects. These are not competing interpretations.

8. Update documentation so downstream analysts know that base costs are stable
   building-stock measures and discounted costs are snapshot-state estimates.

## Test and validation requirements

At minimum, add tests proving:

- With no reduction buildings, results remain identical to the current
  research-only calculation.
- Full research (`0.86`) plus a level-20 Carpenter produces a wood factor of
  `0.66`, while other resource factors remain `0.86` without their reducers.
- Different reducer levels yield different factors for different resources in
  the same city.
- A reducer in one city does not affect another city owned by the same player.
- A reducer present in one snapshot does not affect an earlier snapshot and is
  not automatically carried into a later snapshot where it is absent.
- A level-32 reducer with full research produces factor `0.54`.
- Base-cost columns and `building_base_cost_total` never change because of
  discount logic.
- Discounted totals equal the sum of the five discounted resource columns.
- Stored-resource columns remain observed values and are never discounted.
- Null/empty building slots produce reducer level zero.
- Duplicate occurrences of the same reducer in a malformed city row are
  handled explicitly (prefer validation over silently choosing a level).
- Historical levels above 32 are surfaced according to the selected validation
  policy.

Also run the complete test suite because these columns feed city, player,
island, country, donation, and final panel outputs.

## Non-goals

Do not include these in the construction-resource factor:

- production boosters such as Forester's House or Stonemason;
- Wine Press savings on recurring tavern consumption;
- Optician effects on experiments or workshop upgrades;
- military or naval upkeep reductions;
- government bonuses that change construction time;
- Ambrosia costs for shortening construction;
- Chronos' Forge, introduced in 2025, which changes construction time rather
  than resource demand;
- miracle donations, which the reduction-building documentation generally
  excludes.

Those can support separate economic measures later, but mixing them into this
factor would change its meaning.

## Repository status warning

At the time this handoff was written, the worktree already contained uncommitted
changes in the cost pipeline and its tests, including:

- `docs/building_value_and_discount_findings.md`
- `src/ikariam/assets/pipeline.py`
- `src/ikariam/processing/transforms/building_costs.py`
- `src/ikariam/processing/transforms/city_metrics.py`
- `tests/test_resource_panels.py`
- untracked cost-audit documents and `tests/test_building_costs.py`

These changes predate this handoff. Inspect and preserve them; do not overwrite
or discard them while implementing the reducer logic.

## Sources

- [Historical Carpenter documentation and additive reduction explanation](https://ikariam.fandom.com/bg/wiki/Carpenter)
- [Historical Wine Press documentation](https://ikariam.fandom.com/bg/wiki/Wine_Press)
- [Historical Optician documentation](https://ikariam.fandom.com/wiki/Building%3AOptician_%28Pre_8.8%29)
- [Historical Firework Test Area documentation](https://ikariam.fandom.com/bg/wiki/Firework_Test_Area)
- [Reduction-building category](https://ikariam.fandom.com/wiki/Category%3AReduction_buildings)
- [Version 8.8.0 discussion documenting level-50 reducers](https://forum.ikariam.gameforge.com/forum/thread/84979-version-8-8-0/?pageNo=6)
- [Modern level-50 effect cap confirmation](https://forum.ikariam.gameforge.com/forum/thread/109628-no-issue-no-effect-beyond-level-50-for-carpenter-architect/)
- [Master Builders scoring uses undiscounted base costs](https://ikariam.fandom.com/wiki/Scores)
- [Aristocracy affects construction time](https://ikariam.fandom.com/wiki/Aristocracy)
- [Patch 14.0.0: Chronos' Forge affects construction time](https://ikariam.fandom.com/wiki/Patch_14.0.0)

The community wiki contains some pages labelled "Pre 8.8" whose shared
boilerplate has since been updated with modern level-50 values. Prefer explicit
historical level tables and cross-check them against dated forum material.
