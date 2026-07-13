# LanceDB vs SQL Gold Verification

Generated: 2026-06-17 08:59:42 UTC

- LanceDB: `output/ikariam.lancedb`
- SQL gold CSVs: `data/gold_standard`
- Detail artifacts: `output/verification/lancedb_vs_sql_gold`
- Verification snapshot: `de_1311_14` (2014-11-13)
- Snapshot selection: explicit --snapshot-id de_1311_14

## Public Table Coverage

| Table | Status | Rows | Verified columns | Missing docs | Undocumented | Unverified | Duplicate keys | Formula key gaps | Formula mismatches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| player_snapshot | PASS | 548 | 30/30 | 0 | 0 | 0 | 0 | 0 | 0 |
| city_snapshot | PASS | 3524 | 54/54 | 0 | 0 | 0 | 0 | 0 | 0 |
| island_snapshot | PASS | 5351 | 39/39 | 0 | 0 | 0 | 0 | 0 | 0 |
| donation_analytics_player_island_snapshot | PASS | 2516 | 64/64 | 0 | 0 | 0 | 0 | 0 | 0 |

## Legacy Gold Reconstruction

| Output | Status | Gold rows | Lance rows | Mapped columns | Old-only SQL columns | SQL-only keys | Lance-only keys | Mismatches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Teilnahme_AV | PASS | 21829 | 21829 | 2 | 0 | 0 | 0 | 0 |
| Master_Avi | PASS | 41086 | 41086 | 2 | 0 | 0 | 0 | 0 |
| A_DS | PASS | 21829 | 21829 | 133 | 2 | 0 | 0 | 0 |
| AVI_DS | PASS | 41086 | 41086 | 155 | 2 | 0 | 0 | 0 |
| I_DS | PASS | 5351 | 5351 | 145 | 2 | 0 | 0 | 0 |

## Coverage Notes

The primary pass/fail target is the documented public LanceDB data. Every documented public column must be covered by an invariant, a formula/source check, or the legacy-gold reconstruction path.
Old SQL columns without a current public-table equivalent are reported as old-only SQL columns. They are not treated as missing public data.
Legacy donation columns are reconstructed from `donation_analytics_player_island_snapshot`, not from donation fields duplicated on `city_snapshot`.
The only expected donation columns that remain unmapped are `d_Anz_Don_per_DB` and `d_Don_pro_DB`. They are database-wide donation broadcast constants copied onto every legacy row, not row-level analytics in the canonical LanceDB model.
Mismatch CSVs contain at most 10000 sample rows per output; the summary table shows the full mismatch count.

## Detail Files

### Public player_snapshot

- Keys: `player_id, snapshot_id`
- Verified columns: 30/30
- Missing documented columns: 0
- Undocumented LanceDB columns: 0
- Unverified columns: 0
- Coverage: `output/verification/lancedb_vs_sql_gold/public_player_snapshot_coverage.csv`
- Formula/source mismatches: `output/verification/lancedb_vs_sql_gold/public_player_snapshot_mismatches.csv`
- Formula/source mismatch counts: `output/verification/lancedb_vs_sql_gold/public_player_snapshot_mismatch_counts.csv`
- Expected-only keys: `output/verification/lancedb_vs_sql_gold/public_player_snapshot_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/public_player_snapshot_lancedb_only_keys.csv`

### Public city_snapshot

- Keys: `city_id, snapshot_id`
- Verified columns: 54/54
- Missing documented columns: 0
- Undocumented LanceDB columns: 0
- Unverified columns: 0
- Coverage: `output/verification/lancedb_vs_sql_gold/public_city_snapshot_coverage.csv`
- Formula/source mismatches: `output/verification/lancedb_vs_sql_gold/public_city_snapshot_mismatches.csv`
- Formula/source mismatch counts: `output/verification/lancedb_vs_sql_gold/public_city_snapshot_mismatch_counts.csv`
- Expected-only keys: `output/verification/lancedb_vs_sql_gold/public_city_snapshot_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/public_city_snapshot_lancedb_only_keys.csv`

### Public island_snapshot

- Keys: `island_id, snapshot_id`
- Verified columns: 39/39
- Missing documented columns: 0
- Undocumented LanceDB columns: 0
- Unverified columns: 0
- Coverage: `output/verification/lancedb_vs_sql_gold/public_island_snapshot_coverage.csv`
- Formula/source mismatches: `output/verification/lancedb_vs_sql_gold/public_island_snapshot_mismatches.csv`
- Formula/source mismatch counts: `output/verification/lancedb_vs_sql_gold/public_island_snapshot_mismatch_counts.csv`
- Expected-only keys: `output/verification/lancedb_vs_sql_gold/public_island_snapshot_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/public_island_snapshot_lancedb_only_keys.csv`

### Public donation_analytics_player_island_snapshot

- Keys: `player_id, island_id, snapshot_id`
- Verified columns: 64/64
- Missing documented columns: 0
- Undocumented LanceDB columns: 0
- Unverified columns: 0
- Coverage: `output/verification/lancedb_vs_sql_gold/public_donation_analytics_player_island_snapshot_coverage.csv`
- Formula/source mismatches: `output/verification/lancedb_vs_sql_gold/public_donation_analytics_player_island_snapshot_mismatches.csv`
- Formula/source mismatch counts: `output/verification/lancedb_vs_sql_gold/public_donation_analytics_player_island_snapshot_mismatch_counts.csv`
- Expected-only keys: `output/verification/lancedb_vs_sql_gold/public_donation_analytics_player_island_snapshot_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/public_donation_analytics_player_island_snapshot_lancedb_only_keys.csv`

### Legacy Teilnahme_AV

- Keys: `id`
- Mapped columns: 2
- Old-only SQL columns: 0
- Mismatches: `output/verification/lancedb_vs_sql_gold/teilnahme_av_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/teilnahme_av_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/teilnahme_av_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/teilnahme_av_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/teilnahme_av_unmapped_columns.csv`

### Legacy Master_Avi

- Keys: `owner_id, island_id`
- Mapped columns: 2
- Old-only SQL columns: 0
- Mismatches: `output/verification/lancedb_vs_sql_gold/master_avi_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/master_avi_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/master_avi_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/master_avi_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/master_avi_unmapped_columns.csv`

### Legacy A_DS

- Keys: `t_id`
- Mapped columns: 133
- Old-only SQL columns: 2
- Mismatches: `output/verification/lancedb_vs_sql_gold/a_ds_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/a_ds_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/a_ds_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/a_ds_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/a_ds_unmapped_columns.csv`

### Legacy AVI_DS

- Keys: `m_owner_id, m_island_id`
- Mapped columns: 155
- Old-only SQL columns: 2
- Mismatches: `output/verification/lancedb_vs_sql_gold/avi_ds_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/avi_ds_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/avi_ds_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/avi_ds_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/avi_ds_unmapped_columns.csv`

### Legacy I_DS

- Keys: `i_id`
- Mapped columns: 145
- Old-only SQL columns: 2
- Mismatches: `output/verification/lancedb_vs_sql_gold/i_ds_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/i_ds_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/i_ds_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/i_ds_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/i_ds_unmapped_columns.csv`
