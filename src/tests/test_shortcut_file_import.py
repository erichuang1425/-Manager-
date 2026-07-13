from pathlib import Path

from app.services.scan_service import scan_shortcut_files


def test_scan_shortcut_files_imports_multiple_supported_types(tmp_path):
    url_file = tmp_path / "Web Game.url"
    url_file.write_text(
        "[InternetShortcut]\nURL=https://example.test/play\n", encoding="utf-8"
    )
    html_file = tmp_path / "Local Game.html"
    html_file.write_text("<html></html>", encoding="utf-8")

    games = scan_shortcut_files([url_file, html_file])

    assert {game.title for game in games} == {"Web Game", "Local Game"}
    assert {game.shortcut_type for game in games} == {"url", "html"}
    assert all(game.shortcut_path for game in games)


def test_scan_shortcut_files_ignores_missing_unsupported_and_duplicate_paths(tmp_path):
    shortcut = tmp_path / "Game.url"
    shortcut.write_text(
        "[InternetShortcut]\nURL=https://example.test/play\n", encoding="utf-8"
    )
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("not a shortcut", encoding="utf-8")

    games = scan_shortcut_files(
        [shortcut, Path(str(shortcut)), unsupported, tmp_path / "missing.lnk"]
    )

    assert len(games) == 1
    assert games[0].title == "Game"


def test_scan_shortcut_files_reports_progress(tmp_path):
    shortcut = tmp_path / "Game.html"
    shortcut.write_text("<html></html>", encoding="utf-8")
    progress = []

    scan_shortcut_files(
        [shortcut],
        progress=lambda message, current, total: progress.append(
            (message, current, total)
        ),
    )

    assert progress[0][1:] == (0, 1)
    assert progress[-1][1:] == (1, 1)
