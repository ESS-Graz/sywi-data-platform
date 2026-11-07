import pandas as pd
from dagster import AssetKey, build_input_context, build_output_context

from sywi_core import LanceIOManager, lance_config_from_env


def _roundtrip(manager, key, df):
    output_context = build_output_context(asset_key=AssetKey(key))
    manager.handle_output(output_context, df)
    return manager.load_input(build_input_context(upstream_output=output_context))


def test_roundtrip_and_overwrite(tmp_path):
    manager = LanceIOManager(str(tmp_path))
    first = pd.DataFrame({"id": [1, 2, 3], "title": ["a", "b", "c"]})
    assert _roundtrip(manager, "stories", first).equals(first)

    # A second write replaces rows and schema.
    second = pd.DataFrame({"id": [9], "score": [0.5]})
    assert _roundtrip(manager, "stories", second).equals(second)


def test_load_input_by_asset_key_without_upstream_output(tmp_path):
    manager = LanceIOManager(str(tmp_path))
    df = pd.DataFrame({"x": [1, 2]})
    manager.handle_output(build_output_context(asset_key=AssetKey("shared")), df)

    loaded = manager.load_input(build_input_context(asset_key=AssetKey("shared")))
    assert loaded.equals(df)


def test_table_is_named_after_last_key_part(tmp_path):
    manager = LanceIOManager(str(tmp_path))
    df = pd.DataFrame({"x": [1]})
    _roundtrip(manager, "stories", df)
    assert (tmp_path / "stories.lance").exists()


def test_config_defaults_to_local(monkeypatch):
    monkeypatch.delenv("LANCE_URI", raising=False)
    assert lance_config_from_env() == {"uri": "./data/lance"}


def test_config_s3_uses_aws_variables(monkeypatch):
    monkeypatch.setenv("LANCE_URI", "s3://bucket/path")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://example.org")
    options = lance_config_from_env()["storage_options"]
    assert options["aws_endpoint"] == "https://example.org"
    assert options["aws_virtual_hosted_style_request"] == "false"
    assert "aws_allow_http" not in options


def test_config_accepts_the_production_variable_names(monkeypatch):
    monkeypatch.setenv("LANCE_URI", "s3://hackernews/lance")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_ENDPOINT", "http://seaweedfs:8333")
    monkeypatch.setenv("AWS_ALLOW_HTTP", "true")
    options = lance_config_from_env()["storage_options"]
    assert options["aws_endpoint"] == "http://seaweedfs:8333"
    assert options["aws_allow_http"] == "true"
