"""Real-Qt smoke coverage for managed card artwork and clipboard paste."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_CHILD = textwrap.dedent(
    r"""
    import json
    import os
    from pathlib import Path
    import sys

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, "src")

    try:
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
    except Exception:
        sys.exit(77)

    from app.models import Game
    from app.services import (
        save_card_artwork,
        shutdown_artwork_loader,
        shutdown_icon_loader,
    )
    from app.storage.paths import library_json_path
    from app.ui.main_window.window import MainWindow
    from app.ui.theme import apply_theme


    def pump(app, count=12):
        for _ in range(count):
            app.processEvents()


    app = QApplication.instance() or QApplication([])
    apply_theme(app, "dark", "Segoe UI", "default")

    # Managed artwork is normalized, bounded, and replaces its old managed copy.
    large = QImage(2600, 1400, QImage.Format.Format_RGB32)
    large.fill(QColor("#35466d"))
    first = save_card_artwork("managed-test", large)
    first_path = Path(first)
    assert first_path.exists(), "first managed artwork was not written"
    decoded = QImage(first)
    assert not decoded.isNull(), "managed artwork could not be decoded"
    assert max(decoded.width(), decoded.height()) <= 1920, "artwork was not bounded"

    replacement = QImage(960, 540, QImage.Format.Format_RGB32)
    replacement.fill(QColor("#8b5f46"))
    second = save_card_artwork("managed-test", replacement, previous_path=first)
    assert Path(second).exists(), "replacement artwork was not written"
    assert not first_path.exists(), "replaced managed artwork was not cleaned up"

    # The user-facing Paste action adopts clipboard imagery, refreshes Details,
    # and persists the path in the real library document.
    win = MainWindow()
    win.resize(1400, 850)
    game = Game(game_id="cjk-art-test", title="返校")
    win._repo.add(game)
    win._filtered = list(win._all_games)
    win._rebuild_search_cache()
    win._apply_search()
    win.details.show_game(game)
    QApplication.clipboard().setImage(replacement)

    win._paste_card_artwork(game.game_id)
    pump(app)
    win._flush_save()

    assert game.card_artwork_path, "Paste did not attach artwork to the game"
    assert Path(game.card_artwork_path).exists(), "pasted artwork file is missing"
    assert win.details.artwork_preview._artwork_path == game.card_artwork_path
    assert win.details.remove_artwork_btn.isEnabled(), "Remove did not become available"

    document = json.loads(library_json_path().read_text(encoding="utf-8"))
    stored = next(item for item in document["games"] if item["game_id"] == game.game_id)
    assert stored["card_artwork_path"] == game.card_artwork_path

    win.close()
    shutdown_artwork_loader()
    shutdown_icon_loader()
    print("CARD_ARTWORK_OK")
    """
)


def test_managed_card_artwork_and_clipboard_paste(tmp_path):
    env = dict(os.environ)
    env["APPDATA"] = str(tmp_path)
    env["PYTHONIOENCODING"] = "utf-8"
    env["QT_QPA_PLATFORM"] = "offscreen"

    proc = subprocess.run(
        [sys.executable, "-c", _CHILD],
        cwd=str(_PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if proc.returncode == 77:
        pytest.skip("real PySide6 unavailable in child interpreter")

    assert proc.returncode == 0 and "CARD_ARTWORK_OK" in proc.stdout, (
        f"card artwork smoke failed (rc={proc.returncode})\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
