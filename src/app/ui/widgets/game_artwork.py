"""Reusable generated game artwork with a crisp executable-icon identity badge."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap,
)
from PySide6.QtWidgets import QWidget

from app.models import Game
from app.services import icon_path_for_game, request_artwork_async, request_icon_async
from app.ui.theme import current_theme
from app.ui.widgets.game_grid.display_utils import (
    native_icon_size,
    CJK_FONT_FAMILIES,
    cover_crop_rect,
    tile_gradient_hsl,
    tile_initials,
    tile_text_is_light,
)


class GameArtwork(QWidget):
    """Paint a stable title tile and retain the source app icon at native size."""

    def __init__(
        self,
        game: Game | None = None,
        *,
        width: int = 112,
        height: int = 96,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._game: Game | None = None
        self._icon_path = ""
        self._pixmap: QPixmap | None = None
        self._artwork_path = ""
        self._artwork_pixmap: QPixmap | None = None
        if game is not None:
            self.set_game(game)

    def set_game(self, game: Game | None) -> None:
        self._game = game
        self._pixmap = None
        self._artwork_pixmap = None
        self._icon_path = icon_path_for_game(game, check_exists=False) if game else ""
        self._artwork_path = getattr(game, "card_artwork_path", "") if game else ""
        title = game.title if game else "Game"
        self.setAccessibleName(f"Artwork for {title}")
        self.setToolTip(title)
        self.update()
        if self._artwork_path:
            artwork_path = self._artwork_path
            dpr = max(1.0, float(self.devicePixelRatioF()))

            def _art_ready(loaded_path: str, image, *, expected=artwork_path, expected_dpr=dpr) -> None:
                if loaded_path != expected or expected != self._artwork_path:
                    return
                try:
                    from shiboken6 import isValid
                    if not isValid(self):
                        return
                except ImportError:
                    pass
                if image is not None and not image.isNull():
                    rendered = QPixmap.fromImage(image)
                    rendered.setDevicePixelRatio(expected_dpr)
                    self._artwork_pixmap = rendered
                self.update()

            request_artwork_async(
                artwork_path,
                max(1, round(self.width() * dpr)),
                max(1, round(self.height() * dpr)),
                _art_ready,
            )
        if not self._icon_path:
            return

        path = self._icon_path
        dpr = max(1.0, float(self.devicePixelRatioF()))
        request_size = min(256, max(96, round(96 * dpr)))

        def _ready(loaded_path: str, pixmap, *, expected=path, expected_dpr=dpr) -> None:
            if loaded_path != expected or expected != self._icon_path:
                return
            try:
                from shiboken6 import isValid
                if not isValid(self):
                    return
            except ImportError:
                pass
            if pixmap is not None and not pixmap.isNull():
                rendered = QPixmap(pixmap)
                rendered.setDevicePixelRatio(expected_dpr)
                self._pixmap = rendered
            self.update()

        request_icon_async(path, request_size, _ready)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        theme = current_theme()
        title = self._game.title if self._game else ""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = min(theme.radius_lg, max(8, min(self.width(), self.height()) // 7))
        (h1, s1, l1), (h2, s2, l2) = tile_gradient_hsl(title)
        gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        gradient.setColorAt(0.0, QColor.fromHslF(h1, s1, l1))
        gradient.setColorAt(1.0, QColor.fromHslF(h2, s2, l2))
        if self._artwork_pixmap is not None and not self._artwork_pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)
            sx, sy, sw, sh = cover_crop_rect(
                self._artwork_pixmap.width(),
                self._artwork_pixmap.height(),
                rect.width(),
                rect.height(),
            )
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(rect, self._artwork_pixmap, QRectF(sx, sy, sw, sh))
            painter.restore()
            painter.setPen(theme.card_border)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.setPen(theme.card_border)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(rect, radius, radius)

        if self._artwork_pixmap is None or self._artwork_pixmap.isNull():
            initials_font = QFont(painter.font())
            if hasattr(initials_font, "setFamilies"):
                initials_font.setFamilies(list(dict.fromkeys([
                    initials_font.family(), *CJK_FONT_FAMILIES,
                ])))
            initials_font.setPixelSize(max(22, round(self.height() * 0.30)))
            initials_font.setWeight(QFont.Bold)
            painter.setFont(initials_font)
            painter.setPen(
                QColor(238, 240, 248, 225)
                if tile_text_is_light(title)
                else QColor(20, 22, 30, 225)
            )
            if self._icon_path:
                initials_rect = rect.adjusted(10, 9, -10, -9)
                initials_alignment = Qt.AlignTop | Qt.AlignRight
            else:
                initials_rect = rect
                initials_alignment = Qt.AlignCenter
            painter.drawText(initials_rect, initials_alignment, tile_initials(title))

        if self._pixmap is None or self._pixmap.isNull():
            return
        dpr = max(1.0, float(self._pixmap.devicePixelRatio()))
        source_w = self._pixmap.width() / dpr
        source_h = self._pixmap.height() / dpr
        icon_w, icon_h = native_icon_size(
            source_w,
            source_h,
            min(50, max(32, round(self.height() * 0.40))),
        )
        if not icon_w or not icon_h:
            return

        pad = 6
        badge_w = max(28, icon_w + pad * 2)
        badge_h = max(28, icon_h + pad * 2)
        badge = QRectF(
            rect.left() + 8,
            rect.bottom() - badge_h - 8,
            badge_w,
            badge_h,
        )
        painter.setPen(theme.card_border)
        painter.setBrush(theme.surface_overlay or theme.surface)
        painter.drawRoundedRect(badge, 9, 9)
        target = QRectF(
            badge.center().x() - icon_w / 2,
            badge.center().y() - icon_h / 2,
            icon_w,
            icon_h,
        )
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
