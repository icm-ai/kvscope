from pathlib import Path

from kvscope.resources import default_profile_directory


def test_default_profile_directory_prefers_installed_data(
    tmp_path: Path, monkeypatch: object
) -> None:
    installed_profiles = tmp_path / "share" / "kvscope" / "profiles" / "models"
    installed_profiles.mkdir(parents=True)
    monkeypatch.setattr(
        "kvscope.resources.sysconfig.get_path", lambda _: str(tmp_path)
    )

    assert default_profile_directory("models") == installed_profiles


def test_default_profile_directory_falls_back_to_source_tree(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setattr(
        "kvscope.resources.sysconfig.get_path", lambda _: str(tmp_path)
    )

    assert default_profile_directory("hardware").is_dir()
