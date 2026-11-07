# sywi.duckdb

R package for connecting to SYWI Lance databases.

This is a drop-in wrapper around the `duckdb` R package that automatically configures connections to SYWI Lance databases. It loads environment variables from `.env` and `.env.local` files and attaches the local and, if configured, the remote Lance database. It needs the `duckdb` R package 2.0.0 or newer, because the `lance` extension is a core extension from DuckDB 2.0.

## Installation

Install directly from GitHub:

```r
# Install remotes if you don't have it
install.packages("remotes")

# Install sywi.duckdb
remotes::install_github("ESS-Graz/sywi-data-platform", subdir = "libs/sywi.duckdb")
```

Or install from a local clone:

```r
# From the repository root
install.packages("libs/sywi.duckdb", repos = NULL, type = "source")
```

## Usage

Works just like the standard `duckdb` package - use `sywi_duckdb()` instead of `duckdb()`:

```r
library(sywi.duckdb)

# Connect using standard DBI pattern (just like duckdb)
con <- dbConnect(sywi_duckdb())

# Query local database
local_data <- dbGetQuery(con, "SELECT * FROM local.my_table")

# Query remote database
remote_data <- dbGetQuery(con, "SELECT * FROM remote.my_table")

# List tables
all_tables <- dbGetQuery(con, "SELECT database, name FROM (SHOW ALL TABLES)")

# Copy a remote table to your local database
dbExecute(con, "COPY (SELECT * FROM remote.my_table) TO './data/lance/my_table.lance' (FORMAT lance, mode 'overwrite')")

# Disconnect when done
dbDisconnect(con)
```

### Comparison with standard duckdb

| Standard duckdb | sywi.duckdb |
|-----------------|-------------|
| `library(duckdb)` | `library(sywi.duckdb)` |
| `con <- dbConnect(duckdb())` | `con <- dbConnect(sywi_duckdb())` |
| Manual setup required | Auto-configured with local + remote Lance |

Everything else (querying, writing, disconnecting) works exactly the same.

## Environment Variables

The package automatically loads environment variables from `.env` and `.env.local` files, searching upward from the current working directory. `.env.local` values override `.env` values.

| Variable | Default | Description |
|----------|---------|-------------|
| `LANCE_URI` | `./data/lance` | Local Lance database (a directory) |
| `LANCE_REMOTE_URI` | none | Remote Lance database, e.g. `s3://ikariam/ikariam.lancedb` |
| `AWS_ACCESS_KEY_ID` | none | S3 access key, required when a URI starts with `s3://` |
| `AWS_SECRET_ACCESS_KEY` | none | S3 secret key, required when a URI starts with `s3://` |
| `AWS_ENDPOINT_URL` | none | S3 endpoint, e.g. `https://data.systems-sciences.uni-graz.at` |
| `AWS_REGION` | `us-east-1` | S3 region |

## Comparison with Python Package

| Python | R |
|--------|---|
| `import sywi_duckdb as duckdb` | `library(sywi.duckdb)` |
| `conn = duckdb.connect()` | `con <- dbConnect(sywi_duckdb())` |
| `conn.execute("SELECT ...").fetchdf()` | `dbGetQuery(con, "SELECT ...")` |
| `conn.close()` | `dbDisconnect(con)` |

## Dependencies

- `duckdb` (>= 2.0.0)
- `DBI`
