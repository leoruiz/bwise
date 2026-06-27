import os

import pytest

from bwise import env


def test_shell_quote_escapes_single_quotes():
    assert env.shell_quote("a'b") == "'a'\\''b'"


def collect(fields):
    warnings: list[str] = []
    files: dict[str, str] = {}
    exports = env.materialize(
        fields,
        warn=warnings.append,
        write_file=lambda p, v: files.__setitem__(p, v),
    )
    return exports, warnings, files


def test_env_name_field_becomes_export():
    exports, warnings, files = collect([{"name": "API_KEY", "value": "secret"}])
    assert exports == ["export API_KEY='secret'"]
    assert not warnings and not files


def test_file_field_is_written_not_exported():
    exports, warnings, files = collect([{"name": "@file:~/x.pem", "value": "data"}])
    assert exports == []
    assert files == {"~/x.pem": "data"}


def test_file_field_with_empty_path_warns():
    exports, warnings, files = collect([{"name": "@file:", "value": "data"}])
    assert exports == [] and not files
    assert any("empty path" in w for w in warnings)


def test_non_identifier_name_is_skipped_with_warning():
    exports, warnings, _ = collect([{"name": "has space", "value": "v"}])
    assert exports == []
    assert any("non-identifier" in w for w in warnings)


def test_linked_field_is_skipped():
    exports, warnings, _ = collect(
        [{"name": "X", "value": "", "type": env.LINKED_FIELD_TYPE}]
    )
    assert exports == []
    assert any("linked field" in w for w in warnings)


def test_placeholder_value_warns_but_still_exports():
    exports, warnings, _ = collect([{"name": "TOK", "value": env.PLACEHOLDER}])
    assert exports == [f"export TOK={env.shell_quote(env.PLACEHOLDER)}"]
    assert any("placeholder" in w for w in warnings)


def test_write_secret_file_is_mode_600(tmp_path):
    target = tmp_path / "secret"
    env.write_secret_file(str(target), "value")
    assert target.read_text() == "value"
    assert (target.stat().st_mode & 0o777) == 0o600


def test_write_secret_file_no_parent_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env.write_secret_file("bare", "v")
    assert (tmp_path / "bare").read_text() == "v"


def test_write_secret_file_refuses_symlink(tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("original")
    link = tmp_path / "link"
    os.symlink(victim, link)
    with pytest.raises(OSError):
        env.write_secret_file(str(link), "evil")
    assert victim.read_text() == "original"
