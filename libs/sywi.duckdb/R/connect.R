#' Load environment variables from .env files
#'
#' Reads .env and .env.local files, with .env.local taking precedence.
#' Searches upward from the current directory to find the files.
#'
#' @return Invisibly returns a named list of loaded variables
#' @noRd
load_dotenv <- function() {
  find_env_file <- function(filename) {
    dir <- getwd()
    while (dir != dirname(dir)) {
      path <- file.path(dir, filename)
      if (file.exists(path)) {
        return(path)
      }
      dir <- dirname(dir)
    }
    return(NULL)
  }

  parse_env_file <- function(path) {
    if (is.null(path) || !file.exists(path)) {
      return(list())
    }

    lines <- readLines(path, warn = FALSE)
    env_vars <- list()

    for (line in lines) {
      line <- trimws(line)
      if (nchar(line) == 0 || startsWith(line, "#")) {
        next
      }

      eq_pos <- regexpr("=", line, fixed = TRUE)
      if (eq_pos > 0) {
        key <- trimws(substr(line, 1, eq_pos - 1))
        value <- substr(line, eq_pos + 1, nchar(line))
        value <- gsub("^[\"']|[\"']$", "", value)
        env_vars[[key]] <- value
      }
    }

    return(env_vars)
  }

  env_path <- find_env_file(".env")
  env_local_path <- find_env_file(".env.local")

  env_vars <- parse_env_file(env_path)
  env_local_vars <- parse_env_file(env_local_path)

  all_vars <- modifyList(env_vars, env_local_vars)

  for (key in names(all_vars)) {
    do.call(Sys.setenv, setNames(list(all_vars[[key]]), key))
  }

  invisible(all_vars)
}


#' Get required environment variable
#' @noRd
get_required_env <- function(name) {
  value <- Sys.getenv(name, unset = "")
  if (value == "") {
    stop(sprintf("Required environment variable %s is not set", name),
      call. = FALSE
    )
  }
  return(value)
}


#' Get environment variable with default
#' @noRd
get_env <- function(name, default = "") {
  value <- Sys.getenv(name, unset = "")
  if (value == "") {
    return(default)
  }
  return(value)
}


#' Quote a value as a SQL string literal
#' @noRd
sql_str <- function(value) {
  paste0("'", gsub("'", "''", value, fixed = TRUE), "'")
}


#' Build the SQL statements that attach the Lance databases
#'
#' @return A character vector of SQL statements
#' @noRd
lance_setup_statements <- function() {
  local_uri <- get_env("LANCE_URI", "./data/lance")
  remote_uri <- get_env("LANCE_REMOTE_URI", "")

  if (!startsWith(local_uri, "s3://")) {
    dir.create(local_uri, recursive = TRUE, showWarnings = FALSE)
  }

  buckets <- character()
  for (uri in c(local_uri, remote_uri)) {
    if (startsWith(uri, "s3://")) {
      buckets <- union(buckets, strsplit(uri, "/", fixed = TRUE)[[1]][3])
    }
  }

  statements <- c("INSTALL lance", "LOAD lance")

  for (bucket in buckets) {
    options <- c(
      "TYPE lance",
      "PROVIDER config",
      paste("aws_access_key_id", sql_str(get_required_env("AWS_ACCESS_KEY_ID"))),
      paste("aws_secret_access_key", sql_str(get_required_env("AWS_SECRET_ACCESS_KEY"))),
      paste("aws_region", sql_str(get_env("AWS_REGION", "us-east-1"))),
      "aws_virtual_hosted_style_request 'false'",
      paste("SCOPE", sql_str(sprintf("s3://%s/", bucket)))
    )
    if (get_env("AWS_ENDPOINT_URL") != "") {
      options <- c(options, paste("aws_endpoint", sql_str(get_env("AWS_ENDPOINT_URL"))))
    }
    statements <- c(
      statements,
      sprintf("CREATE SECRET lance_%s (%s)", gsub("-", "_", bucket), paste(options, collapse = ", "))
    )
  }

  statements <- c(statements, sprintf("ATTACH %s AS local (TYPE lance)", sql_str(local_uri)))
  if (remote_uri != "") {
    statements <- c(statements, sprintf("ATTACH %s AS remote (TYPE lance)", sql_str(remote_uri)))
  }

  statements
}


#' Setup Lance connection
#'
#' Configures an existing DuckDB connection with the SYWI Lance databases.
#' @param conn A DuckDB connection
#' @return The configured connection
#' @noRd
setup_lance <- function(conn) {
  load_dotenv()

  tryCatch(
    {
      for (statement in lance_setup_statements()) {
        DBI::dbExecute(conn, statement)
      }
    },
    error = function(e) {
      DBI::dbDisconnect(conn)
      stop(sprintf("Failed to connect to the Lance databases: %s", e$message), call. = FALSE)
    }
  )

  return(conn)
}


#' SYWI DuckDB Driver
#'
#' Creates a DuckDB driver that automatically configures SYWI Lance connections.
#' Use this as a drop-in replacement for `duckdb::duckdb()`.
#'
#' @return A duckdb driver object that can be used with `DBI::dbConnect()`
#'
#' @details
#' When you connect using this driver, the connection will automatically:
#' - Load environment variables from .env and .env.local files
#' - Install and load the DuckDB `lance` extension (needs DuckDB 2.0 or newer)
#' - Attach the `local` database (your local Lance directory)
#' - Attach the `remote` database, if `LANCE_REMOTE_URI` is set
#'
#' Environment variables:
#' - `LANCE_URI`: local Lance database, a directory (default: "./data/lance")
#' - `LANCE_REMOTE_URI`: remote Lance database, e.g. "s3://ikariam/ikariam.lancedb" (optional)
#' - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: S3 credentials, needed when a URI starts with "s3://"
#' - `AWS_ENDPOINT_URL`, `AWS_REGION`: optional S3 endpoint and region (default region: "us-east-1")
#'
#' @examples
#' \dontrun{
#' library(sywi.duckdb)
#'
#' # Connect using standard DBI pattern
#' con <- DBI::dbConnect(sywi_duckdb())
#'
#' # Query local database
#' DBI::dbGetQuery(con, "SELECT * FROM local.my_table")
#'
#' # Query remote database
#' DBI::dbGetQuery(con, "SELECT * FROM remote.my_table")
#'
#' # Disconnect when done
#' DBI::dbDisconnect(con)
#' }
#'
#' @export
#' @import duckdb
#' @import DBI
sywi_duckdb <- function() {
  drv <- duckdb::duckdb()
  class(drv) <- c("sywi_duckdb_driver", class(drv))
  return(drv)
}


#' Connect to SYWI Lance databases
#'
#' @param drv A sywi_duckdb driver created by `sywi_duckdb()`
#' @param ... Additional arguments (ignored, for compatibility)
#' @return A DBI connection with the local (and remote) Lance database attached
#'
#' @rdname sywi_duckdb
#' @export
#' @method dbConnect sywi_duckdb_driver
dbConnect.sywi_duckdb_driver <- function(drv, ...) {
  # Remove our custom class to get the base duckdb driver
  class(drv) <- class(drv)[class(drv) != "sywi_duckdb_driver"]

  # Create connection using base duckdb
  conn <- DBI::dbConnect(drv, ...)

  # Attach the Lance databases
  setup_lance(conn)

  return(conn)
}
