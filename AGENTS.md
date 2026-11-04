# Agent Instructions

## DuckDB / DuckLake Gotchas

### ALTER TABLE ADD COLUMN with DEFAULT
DuckDB/DuckLake does not support expressions like `FALSE` or `TRUE` as default values in `ALTER TABLE ADD COLUMN` statements. Only literals are supported.

**This will fail:**
```sql
ALTER TABLE my_table ADD COLUMN IF NOT EXISTS is_flag BOOLEAN DEFAULT FALSE
```

**This works:**
```sql
ALTER TABLE my_table ADD COLUMN IF NOT EXISTS is_flag BOOLEAN
```

If you need to set a default value for existing rows, do it in a separate UPDATE statement:
```sql
ALTER TABLE my_table ADD COLUMN IF NOT EXISTS is_flag BOOLEAN;
UPDATE my_table SET is_flag = false WHERE is_flag IS NULL;
```

## Python Style

### No implicit string concatenation
The linter rejects adjacent string literals, whether on one line or split across lines inside parentheses.

**This will fail:**
```python
raise ValueError(
    "Raw data is missing the column "
    f"{name} in {path}"
)
```

**This works:** use a single literal (long lines are fine) or build the text in a variable first.
```python
raise ValueError(f"Raw data is missing the column {name} in {path}")
```
Ruff's `ISC` rules only catch some cases (e.g. `ISC004` in collections), so also avoid any two string literals separated only by whitespace or a newline.
