import PySide6
from PySide6.QtCore import qVersion

from app.ui.main_window import MainWindow
from app.storage import load_settings, settings_json_path
from app.ui.theme import apply_theme
from app.ui.exception_hook import install, SafeApplication
from app.logging_utils import get_logger, kv, show_log_path_message
from app.storage.paths import paths_diag

def main() -> None:
    log = get_logger("app")
    install()
    app = SafeApplication([])
    log.info("app.start %s", kv(qt_version=qVersion(), pyside_version=PySide6.__version__))

    settings = load_settings(settings_json_path())
    theme = settings.get("theme", "dark")
    font_family = settings.get("font_family", "Segoe UI")
    font_scale = settings.get("font_scale", "default")
    apply_theme(app, theme, font_family, font_scale)
    log.info("theme_applied %s", kv(theme=theme, font=font_family, scale=font_scale))
    paths_diag(log)
    show_log_path_message()

    w = MainWindow()
    w.show()
    try:
        app.exec()
    except Exception:
        log.exception("app.exec_failure")
        raise
    finally:
        from app.services.icon_service import shutdown_icon_loader
        from app.services.artwork_service import shutdown_artwork_loader
        shutdown_icon_loader()
        shutdown_artwork_loader()

if __name__ == "__main__":
    main()
