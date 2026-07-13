"""Smoke test for the QStackedWidget page architecture.

The shared conftest mocks PySide6 so the headless logic tests can run without the
GUI toolkit. This test needs the *real* toolkit, so it runs the check in an
isolated subprocess (a fresh interpreter that never imports the conftest mock).
The child builds a real MainWindow offscreen, drives every sidebar nav key, and
asserts the stack switches to the expected, non-empty page. It skips cleanly when
a real PySide6 is unavailable (e.g. Linux CI).
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Runs in a clean child interpreter (no conftest, real PySide6).
_CHILD = textwrap.dedent(
    """
    import os, sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, "src")
    try:
        from PySide6.QtWidgets import QApplication, QWidget
    except Exception:
        sys.exit(77)  # real PySide6 unavailable -> caller skips

    from app.ui.theme import apply_theme
    from app.ui.main_window.window import MainWindow

    def pump(app, n=6):
        for _ in range(n):
            app.processEvents()

    app = QApplication.instance() or QApplication([])
    apply_theme(app, "dark", "Segoe UI", "default")
    win = MainWindow(); win.resize(1600, 950)
    pump(app, 8)

    # Startup lands on Home.
    assert win.page_stack.currentWidget() is win.home_page, "startup page is not Home"

    expected = {
        "home": win.home_page,
        "all": win.library_page,
        "updates": win.updates,
        "health": win.health,
        "downloads": win.downloads,
        "import": win.import_page,
        "settings": win.settings_page,
    }
    for key, page in expected.items():
        win.sidebar.set_selected(key)
        pump(app)
        current = win.page_stack.currentWidget()
        assert current is page, f"{key}: expected {page.__class__.__name__}, got {current.__class__.__name__}"
        assert current.findChildren(QWidget), f"{key}: page has no child widgets"

    # A collection key routes to the shared library page.
    win.sidebar.set_selected("all")
    pump(app)
    win._on_nav_changed("collection:does-not-exist")
    pump(app)
    assert win.page_stack.currentWidget() is win.library_page, "collection key did not map to library page"

    # Opening details narrows the real library pane even though the outer
    # window stays wide. Primary toolbar actions must compact before clipping.
    win.resize(1275, 800)
    win._details_visible = True
    win._focus_mode = False
    win._apply_details_visibility()
    pump(app)
    assert win._toolbar_compact, "details pane did not compact the narrow toolbar"

    win._details_visible = False
    win._apply_details_visibility()
    pump(app)
    assert not win._toolbar_compact, "toolbar stayed compact after details closed"

    print("SMOKE_OK")
    """
)


def test_page_stack_navigation_smoke(tmp_path):
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    # Isolate app data so the child never reads or writes real user settings.
    env["APPDATA"] = str(tmp_path)

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

    assert proc.returncode == 0 and "SMOKE_OK" in proc.stdout, (
        f"navigation smoke failed (rc={proc.returncode})\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
