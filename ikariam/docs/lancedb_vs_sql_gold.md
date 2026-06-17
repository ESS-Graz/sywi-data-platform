# LanceDB vs SQL Gold Verification

Generated: 2026-06-16 12:40:35 UTC

- LanceDB: `output/ikariam.lancedb`
- SQL gold CSVs: `data/gold_standard`
- Detail artifacts: `output/verification/lancedb_vs_sql_gold`

## Summary

| Output | Status | Gold rows | Lance rows | Mapped columns | Unmapped SQL columns | SQL-only keys | Lance-only keys | Mismatches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Teilnahme_AV | PASS | 21829 | 21829 | 2 | 0 | 0 | 0 | 0 |
| Master_Avi | PASS | 41086 | 41086 | 2 | 0 | 0 | 0 | 0 |
| A_DS | PASS | 21829 | 21829 | 133 | 2 | 0 | 0 | 0 |
| AVI_DS | PASS | 41086 | 41086 | 155 | 2 | 0 | 0 | 0 |
| I_DS | PASS | 5351 | 5351 | 145 | 2 | 0 | 0 | 0 |

## Coverage Notes

This report verifies only columns with explicit mappings from the legacy SQL output to the current Dagster/LanceDB model.
Columns that are selected ambiguously by the legacy SQL or have no current public-table equivalent are reported as unmapped rather than treated as verified.
Legacy donation columns are reconstructed from `donation_analytics_player_island_snapshot`, not from donation fields duplicated on `city_snapshot`.
The only expected donation columns that remain unmapped are `d_Anz_Don_per_DB` and `d_Don_pro_DB`. They are database-wide donation broadcast constants copied onto every legacy row, not row-level analytics in the canonical LanceDB model.
Mismatch CSVs contain at most 10000 sample rows per output; the summary table shows the full mismatch count.

## Detail Files

### Teilnahme_AV

- Keys: `id`
- Mapped columns: 2
- Unmapped SQL columns: 0
- Mismatches: `output/verification/lancedb_vs_sql_gold/teilnahme_av_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/teilnahme_av_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/teilnahme_av_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/teilnahme_av_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/teilnahme_av_unmapped_columns.csv`

### Master_Avi

- Keys: `owner_id, island_id`
- Mapped columns: 2
- Unmapped SQL columns: 0
- Mismatches: `output/verification/lancedb_vs_sql_gold/master_avi_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/master_avi_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/master_avi_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/master_avi_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/master_avi_unmapped_columns.csv`

### A_DS

- Keys: `t_id`
- Mapped columns: 133
- Unmapped SQL columns: 2
- Mismatches: `output/verification/lancedb_vs_sql_gold/a_ds_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/a_ds_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/a_ds_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/a_ds_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/a_ds_unmapped_columns.csv`

### AVI_DS

- Keys: `m_owner_id, m_island_id`
- Mapped columns: 155
- Unmapped SQL columns: 2
- Mismatches: `output/verification/lancedb_vs_sql_gold/avi_ds_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/avi_ds_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/avi_ds_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/avi_ds_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/avi_ds_unmapped_columns.csv`

### I_DS

- Keys: `i_id`
- Mapped columns: 145
- Unmapped SQL columns: 2
- Mismatches: `output/verification/lancedb_vs_sql_gold/i_ds_mismatches.csv`
- Mismatch counts: `output/verification/lancedb_vs_sql_gold/i_ds_mismatch_counts.csv`
- SQL-only keys: `output/verification/lancedb_vs_sql_gold/i_ds_sql_only_keys.csv`
- Lance-only keys: `output/verification/lancedb_vs_sql_gold/i_ds_lancedb_only_keys.csv`
- Unmapped columns: `output/verification/lancedb_vs_sql_gold/i_ds_unmapped_columns.csv`
