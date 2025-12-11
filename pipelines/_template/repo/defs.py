from dagster import Definitions, asset, define_asset_job

@asset
def hello_world():
    """A simple hello world asset."""
    return "Hello from this pipeline!"

# Define a job to materialize the asset
hello_job = define_asset_job(name="hello_job", selection="*")

defs = Definitions(
    assets=[hello_world],
    jobs=[hello_job],
)
