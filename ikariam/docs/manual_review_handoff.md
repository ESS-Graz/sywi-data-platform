# Ikariam manual review handoff — 2026-09-11

## How to work with the user

We are manually auditing the Ikariam Dagster project for correctness, one
function at a time. The user is learning Python and prefers concise, simple
answers, with detailed explanations when requested. Let the user steer the
review; do not automatically implement unrelated improvements. Two conversations
share this workspace, so inspect and preserve existing changes.

## Current stopping point and accepted decisions

We reviewed and refactored the building-cost lookup and resolved missing
building type 31. The user accepts **type 31 = Black Market**, its historical
base costs, and proceeding **on the assumption that the older lookup data is
correct**. The existing discrepancies are documented, not resolved. Do not
reopen that investigation unless requested or new evidence requires it.

The building-cost calculation is sound under that assumption: it measures the
undiscounted cumulative base cost of buildings currently present. It does not
measure lifetime expenditure; buildings can be demolished and past discount
states are not observable.

## Git state

Branch: `experiment/ikariam-account-age-fix`.

- `4726787` (local `main`): simplified configuration/raw loading, removed YAML
  configuration and unused wrapper code, renamed helper folder `pipeline/` to
  `processing/`. Raw files convention: repository `data/raw/ikariam`.
- `ab963f5` (experimental branch HEAD): account-age and panel changes from the
  other work stream. Age is now calculated at each snapshot, base and estimated
  building costs are separate, and research evidence is carried forward only.
  This commit also removed the legacy SQL comparison verifier.
- Building-cost refactor, new tests, review documentation and CSV additions
  described below have **not been committed**. No merge has been performed.

At handoff, modified source/test files are:

- `src/ikariam/assets/pipeline.py`
- `src/ikariam/processing/transforms/building_costs.py`
- `src/ikariam/processing/transforms/city_metrics.py`
- `tests/test_resource_panels.py`
- New `tests/test_building_costs.py`

Paths above are relative to `ikariam/`. The review documents also have pending
changes. Recheck Git status rather than treating this inventory as permanent.

## Building-cost implementation

`processing/transforms/building_costs.py` now exposes
`add_building_base_costs(city_raw, building_costs)` (formerly
`join_building_costs`). It reshapes the 17 type/level pairs into building rows,
joins costs, and sums five resource totals per original city row. It preserves
city order and validates required columns, duplicate lookup keys and missing
positive type/level pairs. Zero type or zero level is treated as an empty slot.

The output adds `building_base_cost_wood`, `_crystal`, `_marble`, `_sulfur`, and
`_wine`, replacing the former 85 temporary `g...` columns. The asset caller and
`compute_city_metrics` have been adapted. City metrics still apply a separate
research factor to produce estimated costs; factual base costs remain intact.

## Black Market addition

Added type-31 levels 1–25 to `data/raw/ikariam/building_costs.csv`:

- Level 1: 440 wood, 260 marble.
- Level 2 cumulative: 1,327 wood, 785 marble.
- Level 25 cumulative: 1,014,299 wood, 659,558 marble.
- Crystal, wine and sulphur are zero at every level.

The historical userscript provides individual upgrades for levels 2–25; these
were summed with level 1 before insertion. The CSV now has 971 rows and covers
all 834 positive building type/level pairs observed in the raw cities.

**The CSV is tracked in Git** as an explicit exception to the ignored `data/`
tree. Its 25 new rows are also reproduced in
[building_value_and_discount_findings.md](building_value_and_discount_findings.md)
as a readable record of the change. That document includes the sources.

An earlier note incorrectly identified type 31 as Pirate Fortress. This was
corrected: type 30's existing 30-level cost series matches Pirate Fortress.
Type 31's identification is accepted from introduction timing and level range;
an original export-ID dictionary was not recovered.

## Verification and limits

- All 30 tests passed after the addition.
- Every one of the 946 older CSV rows matches all 17 legacy SQL positional
  lookup blocks across all five resources: 80,410 matching assignments.
- A separate plain-Python summation matches the transform for every one of
  334,060 raw city rows and all five resources. No placeholder costs were used
  in this final check.
- All 25 Black Market cumulative rows reconcile with the accepted upgrades.
- Historical-reference comparison of older upgrade costs found 241 resource
  entries differing by 1–2 units and 12 larger disagreements, plus five
  level-1 resource disagreements. The reference may be wrong; these are not
  established CSV errors. No older prices were changed.
- Eighteen higher-level rows lack independent reference coverage; none is
  directly used by the current raw cities.
- A complete end-to-end materialization of all final outputs has not been
  verified in this work stream. Passing cost checks is not a full pipeline audit.

Details: [building_cost_audit.md](building_cost_audit.md) and
[building_cost_discrepancies.csv](building_cost_discrepancies.csv).

Test command, from `ikariam/`: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q`.

## Other conversation and resuming

A separate, newly present
[resource_reduction_buildings_handoff.md](resource_reduction_buildings_handoff.md)
proposes extending the optional estimate with city-local resource-reduction
buildings. It was not created in this review work stream. Read it if that is
the next topic; its proposed implementation is not yet in the inspected code.
Preserve it and coordinate with the user before duplicating the other chat's work.

We are ready to continue the manual audit. A natural next file is
`processing/transforms/city_metrics.py`, which consumes the new base-cost totals;
the user may instead want to finish explaining individual lines of
`add_building_base_costs` or review `player_duration.py`. Follow their lead.
Pending practical steps are committing the current work when requested,
validating the remaining pipeline, and eventually deciding whether to retain
and merge the experimental branch.
