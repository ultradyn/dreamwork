"""Registry and persistence contract for user settings (#584)."""

from __future__ import annotations

import sqlite3

import pytest

from dreamwork_db import Access, ValidationError, open_database
from dreamwork_db.store import dreamwork_store_spec
from settings import SETTINGS, SettingValidationError, validate_registry, validate_value


KNOWN_KEY = "gfx.dither"


def test_registry_is_nonempty_has_known_key_and_validates():
    assert len(SETTINGS) >= 3, "registry must not pass validation vacuously"
    assert KNOWN_KEY in SETTINGS
    assert validate_registry() == []


def test_known_default_is_pinned_independently_of_registry():
    assert SETTINGS[KNOWN_KEY].default == "ign"


def test_validation_refuses_invalid_value():
    with pytest.raises(SettingValidationError, match="expected one of"):
        validate_value(KNOWN_KEY, "not-a-dither")


def test_validation_refuses_unknown_key():
    with pytest.raises(SettingValidationError, match="unknown setting key"):
        validate_value("unregistered.dump", {"anything": "goes"})


def test_unset_reads_literal_default_and_default_has_no_row(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    spec = dreamwork_store_spec(path)
    with open_database(spec, access=Access.WRITE):
        pass
    with open_database(spec, access=Access.READ) as db:
        assert db.settings.effective()[KNOWN_KEY] == "ign"
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM user_setting").fetchone()[0] == 0
    finally:
        conn.close()


def test_override_round_trip_and_set_to_default_deletes_row(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    spec = dreamwork_store_spec(path)
    with open_database(spec, access=Access.WRITE) as db:
        with db.transaction():
            assert db.settings.set(KNOWN_KEY, "bayer") is True
    with open_database(spec, access=Access.READ) as db:
        assert db.settings.effective()[KNOWN_KEY] == "bayer"
    with open_database(spec, access=Access.WRITE) as db:
        with db.transaction():
            assert db.settings.set(KNOWN_KEY, "ign") is True
    with open_database(spec, access=Access.READ) as db:
        assert db.settings.effective()[KNOWN_KEY] == "ign"
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM user_setting").fetchone()[0] == 0
    finally:
        conn.close()


def test_repository_refuses_invalid_and_unknown_writes(tmp_path):
    spec = dreamwork_store_spec(tmp_path / "ledger.sqlite3")
    with open_database(spec, access=Access.WRITE) as db:
        with pytest.raises(ValidationError, match="expected one of"):
            with db.transaction():
                db.settings.set(KNOWN_KEY, "invalid")
        with pytest.raises(ValidationError, match="unknown setting key"):
            with db.transaction():
                db.settings.set("arbitrary", True)
        with pytest.raises(ValidationError, match="local-only"):
            with db.transaction():
                db.settings.set(KNOWN_KEY, "bayer", userid="someone-else")
