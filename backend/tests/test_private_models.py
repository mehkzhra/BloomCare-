import hashlib

import pytest
from deploy.private_models import database_engine, expected_hashes, restore, seed, validate
from sqlalchemy import create_engine, text


def test_private_assets_roundtrip_and_corruption_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    payloads = {"forest.json": b'{"demo": 1}', "manifest.json": b'{}'}
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in payloads.items()}
    for name, value in payloads.items():
        (source / name).write_bytes(value)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        seed(connection, source, hashes)
        seed(connection, source, hashes)
        assert connection.scalar(text("SELECT count(*) FROM bloomcare_runtime_assets")) == 2
        target = tmp_path / "restored"
        restore(connection, target, hashes)
        assert {name: (target / name).read_bytes() for name in hashes} == payloads
        connection.execute(text("UPDATE bloomcare_runtime_assets SET payload = 'corrupted'"))
        with pytest.raises(ValueError, match="checksum"):
            restore(connection, tmp_path / "rejected", hashes)
        assert not (tmp_path / "rejected").exists()
    engine.dispose()


def test_incomplete_bundle_never_creates_a_table(tmp_path):
    engine = create_engine("sqlite://")
    (tmp_path / "forest.json").write_bytes(b'{}')
    with engine.begin() as connection:
        with pytest.raises(ValueError, match="checksum"):
            seed(connection, tmp_path, {"forest.json": "0" * 64})
        assert connection.scalar(text(
            "SELECT count(*) FROM sqlite_master WHERE name = 'bloomcare_runtime_assets'"
        )) == 0
    engine.dispose()


def test_contract_contains_only_three_pinned_assets():
    hashes = expected_hashes()
    assert set(hashes) == {"forest.json", "manifest.json", "explanation-weights.json"}
    assert all(len(value) == 64 for value in hashes.values())
    with pytest.raises(ValueError):
        validate({}, hashes)
    with pytest.raises(ValueError):
        database_engine("sqlite://")


def test_missing_database_asset_writes_nothing(tmp_path):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE bloomcare_runtime_assets (sha256 VARCHAR(64) PRIMARY KEY, payload TEXT)"
        ))
        with pytest.raises(ValueError, match="provisioned"):
            restore(connection, tmp_path / "missing", {"forest.json": "0" * 64})
        assert not (tmp_path / "missing").exists()
    engine.dispose()


def test_bundled_valid_models_do_not_need_database(tmp_path, monkeypatch):
    import deploy.private_models as module

    directory = tmp_path / "ml/artifacts/legacy_pe_v0.7.1"
    directory.mkdir(parents=True)
    payload = b'{}'
    (directory / "forest.json").write_bytes(payload)
    monkeypatch.setattr(module, "expected_hashes", lambda root: {
        "forest.json": hashlib.sha256(payload).hexdigest()
    })
    monkeypatch.setattr(module, "database_engine", lambda url: pytest.fail("Unexpected DB access"))
    module.ensure_private_models("unused", root=tmp_path)
