from pathlib import Path

from celesto_sdk.deployment import _resolve_envs


def test_resolve_envs_merges_file_and_cli(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FIRST=1\nSECOND=two\nEMPTY=\n", encoding="utf-8")

    result = _resolve_envs(
        folder_path=tmp_path,
        envs="SECOND=override, CLI_ONLY=foo",
        ignore_env_file=False,
    )

    assert result == {"FIRST": "1", "SECOND": "override", "CLI_ONLY": "foo"}


def test_resolve_envs_ignores_file_when_flag_set(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FIRST=1\n", encoding="utf-8")

    result = _resolve_envs(folder_path=tmp_path, envs=None, ignore_env_file=True)

    assert result == {}
