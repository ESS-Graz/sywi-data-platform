# Building-cost audit — 2026-09-11

## Conclusion

The CSV uses cumulative costs, including the newly added Black Market rows.
The code sums each occupied building's cumulative lookup value once per city.
No cumulative-versus-upgrade-cost mismatch was found for the Black Market addition.

This does **not** establish that every inherited historical price is correct.
Independent source disagreements and reference coverage gaps remain below.
Existing costs were not changed during this audit.

## Checks performed

- Compared all 946 pre-existing CSV rows, all five resources, against every
  one of the 17 positional lookup blocks in legacy SQL Git object
  `9f6483d9aea9c23c522114cc6e4b480abead2f54`: zero differences
  across 80,410 resource assignments. The only CSV keys absent from the SQL
  are the 25 new type-31 rows.
- Checked unique keys, contiguous level sequences starting at 1, and
  nonnegative cumulative costs and increments.
- Subtracted each level's CSV value from the next level's value and compared
  the resulting upgrade costs with historical community tables. This directly
  checks cumulative interpretation instead of merely assuming it from increasing values.
- Compared 924 upgrade rows across 29 building types and five resources:
  755 rows agree exactly across all resources. In the remaining 169 rows,
  241 resource entries differ by 1–2 units and 12 differ by more than 2.
  Small differences might be rounding or transcription, but their cause is
  not established by this comparison.
- Checked level-1 entries against Developer Tools, except Black Market,
  whose accepted level-1 values come from the French/Greek wiki evidence.
  Five resource entries across four older buildings disagree (listed below).
- Independently calculated five resource totals for each of the 334,060 raw
  city rows using a plain Python loop and tuple-keyed lookup, then compared
  every result with `add_building_base_costs()`: zero differences.
  This validates the transform against its lookup, not the lookup against the game.
- The lookup covers all 834 distinct positive type/level pairs in the raw cities.
- The existing test suite passed all 30 tests after adding the Black Market rows.

## Sources and comparison limits

The main upgrade reference is
[Ikariam Upgrade Watcher 2](https://greasyfork.org/pt/scripts/5263-ikariam-upgrade-watcher-2/code).
Its table explicitly describes undiscounted base upgrade costs, with arrays
starting at level 2; its changelog dates Black Market support to 2013-10-21.
The retrieved version also contains later changes, so the changelog alone
does not authenticate every number as of October 2013.

[Ikariam Developer Tools](https://greasyfork.org/en/scripts/8494-ikariam-developer-tools-v0-5-0/code)
supplies the separate level-1 comparison and the Pirate Fortress table.
Its Black Market figures are reduced relative to the accepted base costs and
were not substituted into the CSV. Neither script is an authoritative game
export; a disagreement does not establish which side is wrong. Their data may
share wiki origins, so agreement is not necessarily independent corroboration.

Building names were associated with CSV IDs using the existing review context
and matching cost patterns. Equal-cost buildings (notably resource producers,
and Palace/Governor's Residence) cannot be uniquely identified by prices alone.
There is no original export ID mapping left to recover: the server dump
recovered on 2026-09-14 holds only four tables per snapshot, with no column
comments and no building names, and its `p{n}t` values are the game's own
building-type IDs. See
[Data provenance](building_value_and_discount_findings.md#data-provenance).

Resource mapping used throughout: `cost_holz` = wood,
`cost_quartz` = marble, `cost_kristall` = crystal,
`cost_wein` = wine, `cost_schwefel` = sulphur.
The CSV column order differs from some source tables; comparison uses names.

## Black Market and Pirate Fortress

Type 31 is accepted as Black Market based on the October 2013 appearance and
25-level range. Type 30 already has 30 CSV levels and its complete cumulative
wood/marble series matches the Pirate Fortress source exactly, further
supporting the distinction.

All 24 Black Market upgrade differences for levels 2–25 match Upgrade Watcher
2 exactly, in every resource. The starting row is 440 wood and 260 marble;
all other resources are zero. Level 25 is 1,014,299 wood and 659,558 marble.

Across all snapshots, the 3,149 type-31 slots contribute 199,494,342 wood
and 127,212,891 marble at base prices. These sums include repeated snapshots;
they are not one-time expenditure totals.

The accepted rows and their wiki sources are retained in
[building_value_and_discount_findings.md](building_value_and_discount_findings.md)
as a readable record of the change; the CSV itself is now tracked in Git.

## Upgrade discrepancies larger than two units

These are differences between **individual upgrade costs**, computed from the
CSV by subtracting the preceding level. They are not cumulative differences.
Some may be errors in the reference. Do not automatically replace CSV values.

| Type | Reference building | Level | Resource | CSV implied upgrade | Reference upgrade |
| ---: | --- | ---: | --- | ---: | ---: |
| 4 | academy | 32 | crystal | 3790583 | 3790483 |
| 13 | branchOffice | 26 | marble | 140776 | 121067 |
| 13 | branchOffice | 31 | marble | 418980 | 418983 |
| 15 | workshop | 23 | wood | 19880 | 19481 |
| 24 | architect | 28 | marble | 16017 | 16289 |
| 25 | optician | 28 | marble | 17765 | 17762 |
| 26 | vineyard | 18 | wood | 5805 | 5813 |
| 26 | vineyard | 19 | wood | 6709 | 6875 |
| 26 | vineyard | 20 | wood | 7749 | 7941 |
| 27 | fireworker | 24 | marble | 14294 | 13355 |
| 27 | fireworker | 25 | wood | 15025 | 14990 |
| 28 | temple | 25 | wood | 23186 | 23156 |

All 253 differing upgrade resource entries, plus the five level-1 entries,
are recorded in [building_cost_discrepancies.csv](building_cost_discrepancies.csv).

## Level-1 disagreements

| Type | Reference building | Resource | CSV | Developer Tools |
| ---: | --- | --- | ---: | ---: |
| 5 | shipyard | wood | 105 | 98 |
| 6 | barracks | wood | 49 | 48 |
| 15 | workshop | wood | 220 | 206 |
| 15 | workshop | marble | 95 | 89 |
| 27 | fireworker | wood | 273 | 272 |

The Shipyard and Workshop reference values are numerically consistent with
a 6% reduction and rounding down, which is a reason to investigate the source's
discount convention rather than copy these values into a base-cost table.
This observation is an inference, not verification of that convention.

## Rows without an independent upgrade comparison

The available upgrade table stops before these 18 existing CSV levels:

- Type 1 (Town Hall): 41–48.
- Type 3 (Trading Port): 48.
- Type 6 (Barracks): 50–54.
- Type 9 (Tavern): 48.
- Type 10 (Museum): 22–24.

None of these uncovered pairs is directly used by the current raw cities.
They do match the legacy SQL, but historical price correctness remains unverified.

## Next review

Resolve source disagreements and uncovered levels against dated game help,
archived wiki revisions, or another version-appropriate source. Keep base prices,
discounted prices, individual upgrades, and cumulative totals explicitly distinct.

