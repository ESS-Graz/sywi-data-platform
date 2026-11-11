# Agent Instructions

## DuckDB / Lance Gotchas

Tables are LanceDB tables, read with the DuckDB 2.0 core `lance` extension (`INSTALL lance; LOAD lance;`). The Python `duckdb` package must be 2.0 or newer, which needs Python 3.11+.

### S3 access needs a `TYPE lance` secret
The Lance reader has its own S3 client and ignores DuckDB's regular `TYPE s3` secret and `SET s3_*` settings. The error is `Bucket '<name>' not found`.

**This works:**
```sql
CREATE SECRET ikariam_s3 (
    TYPE lance, PROVIDER config,
    aws_access_key_id getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key getenv('AWS_SECRET_ACCESS_KEY'),
    aws_region 'us-east-1',
    aws_endpoint 'https://data.systems-sciences.uni-graz.at',
    aws_virtual_hosted_style_request 'false',
    SCOPE 's3://ikariam/'
);
```
`getenv()` exists in the DuckDB CLI but not in the Python client. In Python, put the values into the statement instead.

### COPY to an existing Lance table needs `mode 'overwrite'`
```sql
COPY (SELECT ...) TO 'path/table.lance' (FORMAT lance, mode 'overwrite');
```
Without the mode the statement fails with `Dataset already exists`.

### Attach a directory of tables with `ATTACH`
```sql
ATTACH 's3://ikariam/ikariam.lancedb' AS ik (TYPE lance);
SELECT * FROM ik.main.player_snapshot;
```
Once a database is the default catalog (`USE local.main`), a literal path such as `FROM 'x/table.lance'` is rejected as an unsafe dataset name. Use the attached table name instead.

### Several remote databases
`LANCE_REMOTE_URI` takes one URI (attached as `remote`) or comma separated `name=uri` pairs (each attached under its name, e.g. `ikariam.player_snapshot`). Every Dagster project writes to its own database, so a single remote only shows one project's tables. The R package supports a single URI only. `just pull` refuses tables above 5 million rows unless a row limit or `--yes` is given. `just pull --db <name>` pulls every table of one remote and overwrites existing local copies.

### Column aliases that are keywords need `AS`
In DuckDB 2.0, `count(*) days` and `date_trunc(...) month` are syntax errors. Write `AS n_days` or `AS mon`.

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
