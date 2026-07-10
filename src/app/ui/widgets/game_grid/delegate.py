"""
GameCardDelegate — paints an entire game card in ``paint()`` with no child
widgets.  A single delegate instance renders every visible row, so scrolling
allocates zero widgets.

Geometry (icon area, accent strip, title, meta/stars, chips, badges, play
button, checkbox) is computed once by :func:`build_geometry` and shared between
``paint`` and the view's hit-testing so clicks land exactly where things are
drawn.

Icons are loaded asynchronously via the existing icon service and cached in
``QPixmapCache`` keyed by ``game_id + size + devicePixelRatio``.  A neutral
placeholder is painted immediately; when an icon arrives the affected row is
repainted (coalesced through a short timer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QRect, QRectF, QSize, QTimer
from PySide6.QtGui import (
    QColor, QPainter, QPixmap, QPixmapCache, QFont, QFontMetrics, QPainterPath,
)
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from app.services import (
    request_icon_async,
    parse_version, compare_versions,
)
from app.services.version_parser import CompareResult
from app.ui.theme import current_theme, status_color
from app.ui.icons import AppIcons
from app.logging_utils import get_logger

from .model import GameRole
from .display_utils import status_label, relative_time

_log = get_logger("ui.game_card_delegate")

_SCALE = {"small": 0.9, "normal": 1.0, "large": 1.1}


# ---------------------------------------------------------------------------
#  Metrics — fixed dimensions for a card at the current width / view mode.
#  Computed by the view (single source of truth) and shared with the delegate.
# ---------------------------------------------------------------------------

@dataclass
class CardMetrics:
    card_w: int
    view_mode: str = "comfortable"
    scale_name: str = "normal"
    # derived
    scale: float = 1.0
    pad: int = 10
    icon_h: int = 120
    strip_h: int = 3
    title_fs: int = 14
    meta_fs: int = 11
    chip_fs: int = 10
    title_h: int = 20
    meta_h: int = 16
    chip_h: int = 22
    has_chips: bool = True
    card_h: int = 220

    @classmethod
    def compute(cls, card_w: int, view_mode: str, scale_name: str) -> "CardMetrics":
        scale = _SCALE.get(scale_name, 1.0)
        comfortable = view_mode == "comfortable"
        pad = 10 if comfortable else 8
        icon_ratio = 0.58 if comfortable else 0.5
        icon_h = max(72, round(card_w * icon_ratio))
        strip_h = 3
        title_fs = max(10, round((14 if comfortable else 12.5) * scale))
        meta_fs = max(9, round(11 * scale))
        chip_fs = max(8, round(10 * scale))
        title_h = round(title_fs * 1.35) + 2
        meta_h = round(meta_fs * 1.5) + 2
        chip_h = round(chip_fs * 1.7) + 8
        has_chips = comfortable
        # Vertical stack: icon + strip + top pad + title + gap + meta + (gap + chips) + bottom pad
        card_h = icon_h + strip_h + 8 + title_h + 3 + meta_h
        if has_chips:
            card_h += 6 + chip_h
        card_h += pad
        return cls(
            card_w=card_w, view_mode=view_mode, scale_name=scale_name, scale=scale,
            pad=pad, icon_h=icon_h, strip_h=strip_h, title_fs=title_fs,
            meta_fs=meta_fs, chip_fs=chip_fs, title_h=title_h, meta_h=meta_h,
            chip_h=chip_h, has_chips=has_chips, card_h=card_h,
        )

    def size(self) -> QSize:
        return QSize(self.card_w, self.card_h)


# ---------------------------------------------------------------------------
#  Geometry / hit zones
# ---------------------------------------------------------------------------

# A hit zone: (kind, rect, payload)
Zone = Tuple[str, QRect, object]


@dataclass
class CardGeometry:
    body: QRect
    icon: QRect
    strip: QRect
    title: QRect
    meta: QRect
    stars: List[Tuple[int, QRect]] = field(default_factory=list)
    time_rect: Optional[QRect] = None
    chips: List[Tuple[str, object, QRect]] = field(default_factory=list)  # (kind, payload, rect)
    play: Optional[QRect] = None
    update_badge: Optional[QRect] = None
    checkbox: Optional[QRect] = None

    def zones(self) -> List[Zone]:
        """Hit zones in priority (topmost-first) order."""
        z: List[Zone] = []
        if self.checkbox is not None:
            z.append(("checkbox", self.checkbox, None))
        if self.update_badge is not None:
            z.append(("update", self.update_badge, None))
        if self.play is not None:
            z.append(("play", self.play, None))
        for value, r in self.stars:
            z.append(("rating", r, value))
        for kind, payload, r in self.chips:
            z.append((kind, r, payload))
        # The painted strip is only ~3px tall; expand its clickable target to
        # ~8px (centred on the strip, extending down into the card body edge)
        # so cycling status is not a pixel-hunt.
        cx = self.strip.center().y()
        hit = QRect(self.strip.x(), cx - 4, self.strip.width(), 8)
        z.append(("strip", hit, None))
        return z


# Memoise update-availability: build_geometry runs on every paint *and* every
# hit test for every visible card, and a full-viewport repaint (e.g. on
# selection change) multiplies that.  parse_version/compare_versions are pure
# w.r.t. these fields, so cache on them.  No eviction needed at library scale.
_update_cache: dict[tuple, bool] = {}


def _icon_candidate(game) -> str:
    """Pick an icon source path *without* probing the filesystem.

    ``best_icon_path()`` calls ``Path.exists()`` on each candidate, which is a
    ``stat()`` syscall — cached, but the first one runs synchronously and can
    block the GUI thread when the path lives on slow or disconnected storage.
    paint() must never do that, so mirror the old card: take the first
    non-empty candidate and let the background loader resolve/fall back.
    """
    return (
        (getattr(game, "shortcut_path", "") or "")
        or (getattr(game, "backup_target_path", "") or "")
        or (getattr(game, "archive_folder_path", "") or "")
        or (getattr(game, "compressed_archive_path", "") or "")
    )


def _update_available(game) -> bool:
    key = (
        game.game_id,
        game.installed_version_raw,
        game.source_version_raw,
        bool(game.source_url),
    )
    cached = _update_cache.get(key)
    if cached is not None:
        return cached
    if not game.source_url:
        result = False
    else:
        inst = parse_version(game.installed_version_raw) if game.installed_version_raw else None
        src = parse_version(game.source_version_raw) if game.source_version_raw else None
        cmp = compare_versions(inst, src)
        result = cmp in (CompareResult.OLDER, CompareResult.UNKNOWN)
    _update_cache[key] = result
    return result


def build_geometry(rect: QRect, game, m: CardMetrics, multi_select: bool) -> CardGeometry:
    """Compute all sub-rects for a card within ``rect``."""
    x, y, w = rect.x(), rect.y(), rect.width()
    body = QRect(rect)

    icon = QRect(x, y, w, m.icon_h)
    strip = QRect(x, y + m.icon_h, w, m.strip_h)

    cx = x + m.pad
    cw = w - 2 * m.pad
    cy = y + m.icon_h + m.strip_h + 8

    title = QRect(cx, cy, cw, m.title_h)
    cy += m.title_h + 3

    meta = QRect(cx, cy, cw, m.meta_h)

    # Stars laid out at the left of the meta row.
    star_sz = max(12, m.meta_h - 2)
    stars: List[Tuple[int, QRect]] = []
    sx = cx
    for i in range(5):
        stars.append(((i + 1) * 2, QRect(sx, cy + (m.meta_h - star_sz) // 2, star_sz, star_sz)))
        sx += star_sz + 1
    time_rect = QRect(sx + 6, cy, cw - (sx + 6 - cx), m.meta_h)
    cy += m.meta_h

    chips: List[Tuple[str, object, QRect]] = []
    if m.has_chips:
        cy += 6
        chip_y = cy
        chip_h = m.chip_h
        chx = cx
        # status chip
        st_label = status_label(game.status)
        st_w = min(cw, 14 + int(len(st_label) * m.chip_fs * 0.62))
        chips.append(("status", game.status, QRect(chx, chip_y, st_w, chip_h)))
        chx += st_w + 6
        # up to 2 tags
        for tag in (game.tags or [])[:2]:
            if chx >= x + w - m.pad:
                break
            tw = min(120, 14 + int(len(tag) * m.chip_fs * 0.62))
            if chx + tw > x + w - m.pad:
                tw = x + w - m.pad - chx
            if tw < 20:
                break
            chips.append(("tag", tag, QRect(chx, chip_y, tw, chip_h)))
            chx += tw + 6

    # Play button (hover) — circle centred in the icon area.  Disabled in
    # multi-select mode so clicking the cover toggles selection instead.
    play = None
    if not multi_select:
        pd = max(40, min(56, m.icon_h // 3 + 24))
        play = QRect(
            icon.center().x() - pd // 2, icon.center().y() - pd // 2, pd, pd
        )

    # Update badge (top-right of icon).
    update_badge = None
    if _update_available(game):
        bs = 24
        update_badge = QRect(x + w - bs - 8, y + 8, bs, bs)

    # Checkbox (top-left) in multi-select mode.
    checkbox = None
    if multi_select:
        cs = 22
        checkbox = QRect(x + 8, y + 8, cs, cs)

    return CardGeometry(
        body=body, icon=icon, strip=strip, title=title, meta=meta,
        stars=stars, time_rect=time_rect, chips=chips, play=play,
        update_badge=update_badge, checkbox=checkbox,
    )


class GameCardDelegate(QStyledItemDelegate):
    """Paints a full game card per item; no child widgets are created."""

    def __init__(self, view) -> None:
        super().__init__(view)
        self._view = view
        self.metrics = CardMetrics.compute(240, "comfortable", "normal")
        # Dedupe async icon requests (keyed by path) so paint doesn't stack
        # callbacks while a load is pending.
        self._icon_pending: set[str] = set()
        # Coalesce viewport repaints when icons arrive.
        self._repaint_timer = QTimer(view)
        self._repaint_timer.setSingleShot(True)
        self._repaint_timer.setInterval(16)
        self._repaint_timer.timeout.connect(self._flush_repaint)
        self._dirty_ids: set[str] = set()

    # -- metrics ------------------------------------------------------- #

    def set_metrics(self, metrics: CardMetrics) -> None:
        self.metrics = metrics

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return self.metrics.size()

    # -- icon plumbing ------------------------------------------------- #

    @staticmethod
    def _icon_key(game_id: str, path: str, size: int, dpr: float) -> str:
        # The path is part of the key so that when a game's shortcut/archive
        # path changes (e.g. a health fix) under the same game_id, the lookup
        # misses and the new icon is loaded instead of serving the stale one.
        return f"gcard:{game_id}:{path}:{size}:{dpr:.2f}"

    def _icon_pixmap(self, game, target_px: int, dpr: float) -> Optional[QPixmap]:
        """Return a ready-to-draw pixmap from cache, or None (requesting async)."""
        # _icon_candidate is non-probing (no filesystem stat), so it is cheap to
        # resolve before the cache lookup and lets the path feed the cache key.
        path = _icon_candidate(game)
        if not path:
            return None
        key = self._icon_key(game.game_id, path, target_px, dpr)
        pm = QPixmapCache.find(key)
        if pm is not None:
            return pm
        # Request asynchronously (deduped by path).  request_icon_async invokes
        # the callback synchronously when the icon is already in the service's
        # async cache and queues a background load otherwise — so paint never
        # blocks on QFileIconProvider for an uncached (possibly slow) file.
        if path not in self._icon_pending:
            self._icon_pending.add(path)
            gid = game.game_id

            def _ready(p: str, pixmap, _gid=gid, _key=key, _dpr=dpr, _path=path):
                self._icon_pending.discard(_path)
                if pixmap is not None and not pixmap.isNull():
                    pixmap.setDevicePixelRatio(_dpr)
                    QPixmapCache.insert(_key, pixmap)
                    self._dirty_ids.add(_gid)
                    if not self._repaint_timer.isActive():
                        self._repaint_timer.start()

            request_icon_async(path, target_px, _ready)
        return None

    def _flush_repaint(self) -> None:
        from shiboken6 import isValid
        if not isValid(self._view):
            return
        model = self._view.model()
        if model is not None and hasattr(model, "notify_game_changed"):
            for gid in list(self._dirty_ids):
                model.notify_game_changed(gid)
        else:
            self._view.viewport().update()
        self._dirty_ids.clear()

    # -- painting ------------------------------------------------------ #

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        game = index.data(GameRole)
        if game is None:
            return
        m = self.metrics
        theme = current_theme()
        view = self._view

        hovered = bool(option.state & QStyle.State_MouseOver)
        selected = view.is_selected(game.game_id)
        multi = view.is_multi_select()
        focused = (index == view.currentIndex()) and view.hasFocus()

        geo = build_geometry(option.rect, game, m, multi)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        radius = theme.radius_lg
        body = QRectF(geo.body).adjusted(0.5, 0.5, -0.5, -0.5)

        # --- card background + border ---
        if selected:
            border = theme.accent
            bwidth = 2.0
        elif hovered:
            border = theme.card_hover
            bwidth = 1.0
        else:
            border = theme.card_border
            bwidth = 1.0
        bg = (theme.surface_raised or theme.surface_alt) if hovered else theme.card

        path = QPainterPath()
        path.addRoundedRect(body, radius, radius)
        painter.fillPath(path, bg)

        # --- icon area (rounded top corners only) ---
        icon_path = QPainterPath()
        ir = QRectF(geo.icon)
        icon_path.moveTo(ir.left(), ir.bottom())
        icon_path.lineTo(ir.left(), ir.top() + radius)
        icon_path.arcTo(ir.left(), ir.top(), radius * 2, radius * 2, 180, -90)
        icon_path.lineTo(ir.right() - radius, ir.top())
        icon_path.arcTo(ir.right() - radius * 2, ir.top(), radius * 2, radius * 2, 90, -90)
        icon_path.lineTo(ir.right(), ir.bottom())
        icon_path.closeSubpath()
        painter.fillPath(icon_path, theme.surface_alt)

        # icon pixmap
        dpr = float(option.widget.devicePixelRatioF()) if option.widget else 1.0
        target_px = min(512, max(96, round(max(geo.icon.width(), geo.icon.height()) * dpr)))
        pm = self._icon_pixmap(game, target_px, dpr)
        if pm is not None and not pm.isNull():
            painter.save()
            painter.setClipPath(icon_path)
            pw = pm.width() / pm.devicePixelRatio()
            ph = pm.height() / pm.devicePixelRatio()
            avail = geo.icon.adjusted(6, 6, -6, -6)
            scale = min(avail.width() / pw, avail.height() / ph) if pw and ph else 1.0
            scale = min(scale, 1.0) if max(pw, ph) < 64 else scale
            dw, dh = pw * scale, ph * scale
            dx = geo.icon.x() + (geo.icon.width() - dw) / 2
            dy = geo.icon.y() + (geo.icon.height() - dh) / 2
            painter.drawPixmap(QRectF(dx, dy, dw, dh), pm, QRectF(0, 0, pm.width(), pm.height()))
            painter.restore()

        # --- accent status strip ---
        sc = status_color(theme, game.status)
        painter.fillRect(geo.strip, sc)

        # --- title (single line, elided, semibold) ---
        title_font = QFont(painter.font())
        title_font.setPixelSize(m.title_fs)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(theme.text)
        fm = QFontMetrics(title_font)
        elided = fm.elidedText(game.title, Qt.ElideRight, geo.title.width())
        painter.drawText(geo.title, Qt.AlignLeft | Qt.AlignVCenter, elided)

        # --- rating stars ---
        star_font = QFont(painter.font())
        star_font.setPixelSize(max(11, m.meta_fs + 1))
        painter.setFont(star_font)
        rating = game.rating or 0
        filled = max(0, min(5, round(rating / 2)))
        for i, (_value, r) in enumerate(geo.stars):
            painter.setPen(theme.accent if i < filled else theme.text_muted)
            painter.drawText(r, Qt.AlignCenter, "★" if i < filled else "☆")

        # --- relative time (muted) ---
        if geo.time_rect is not None:
            rel = relative_time(game.last_played)
            ver = game.installed_version_raw
            bits = []
            if ver:
                bits.append(f"v{ver}")
            if rel:
                bits.append(rel)
            if bits:
                meta_font = QFont(painter.font())
                meta_font.setPixelSize(m.meta_fs)
                painter.setFont(meta_font)
                painter.setPen(theme.text_muted)
                mfm = QFontMetrics(meta_font)
                txt = mfm.elidedText("  ·  ".join(bits), Qt.ElideRight, geo.time_rect.width())
                painter.drawText(geo.time_rect, Qt.AlignLeft | Qt.AlignVCenter, txt)

        # --- chips (status + up to 2 tags) ---
        if geo.chips:
            chip_font = QFont(painter.font())
            chip_font.setPixelSize(m.chip_fs)
            painter.setFont(chip_font)
            cfm = QFontMetrics(chip_font)
            for kind, payload, r in geo.chips:
                if kind == "status":
                    tint = status_color(theme, payload)
                    label = status_label(payload)
                else:
                    tint = theme.accent
                    label = str(payload)
                fill = QColor(tint)
                fill.setAlpha(38)
                bpen = QColor(tint)
                bpen.setAlpha(90)
                painter.setPen(bpen)
                painter.setBrush(fill)
                painter.drawRoundedRect(QRectF(r), theme.radius_sm - 1, theme.radius_sm - 1)
                painter.setPen(theme.text)
                txt = cfm.elidedText(label, Qt.ElideRight, r.width() - 10)
                painter.drawText(r, Qt.AlignCenter, txt)
            painter.setBrush(Qt.NoBrush)

        # --- update badge ---
        if geo.update_badge is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.accent)
            painter.drawEllipse(geo.update_badge)
            painter.setPen(theme.bg)
            bfont = QFont(painter.font())
            bfont.setPixelSize(12)
            bfont.setBold(True)
            painter.setFont(bfont)
            painter.drawText(geo.update_badge, Qt.AlignCenter, AppIcons.STS_UPDATE)
            painter.setBrush(Qt.NoBrush)

        # --- checkbox (multi-select) ---
        if geo.checkbox is not None:
            painter.setRenderHint(QPainter.Antialiasing, True)
            if selected:
                painter.setPen(Qt.NoPen)
                painter.setBrush(theme.accent)
                painter.drawRoundedRect(QRectF(geo.checkbox), 5, 5)
                check_fg = theme.bg if theme.accent.value() > 140 else QColor(255, 255, 255)
                painter.setPen(check_fg)
            else:
                bgc = QColor(0, 0, 0, 130)
                painter.setPen(Qt.NoPen)
                painter.setBrush(bgc)
                painter.drawRoundedRect(QRectF(geo.checkbox), 5, 5)
                painter.setPen(QColor(255, 255, 255))
            cfont = QFont(painter.font())
            cfont.setPixelSize(14)
            cfont.setBold(True)
            painter.setFont(cfont)
            painter.drawText(geo.checkbox, Qt.AlignCenter, "✓" if selected else "")
            painter.setBrush(Qt.NoBrush)

        # --- hover play button ---
        if hovered and geo.play is not None and not multi:
            painter.setPen(Qt.NoPen)
            fill = QColor(theme.accent)
            fill.setAlpha(235)
            painter.setBrush(fill)
            painter.drawEllipse(geo.play)
            painter.setBrush(theme.bg)
            # simple play triangle
            c = geo.play.center()
            s = geo.play.width() * 0.26
            tri = QPainterPath()
            tri.moveTo(c.x() - s * 0.5, c.y() - s)
            tri.lineTo(c.x() + s, c.y())
            tri.lineTo(c.x() - s * 0.5, c.y() + s)
            tri.closeSubpath()
            painter.fillPath(tri, theme.bg)
            painter.setBrush(Qt.NoBrush)

        # --- selection / focus border ---
        if selected:
            painter.setPen(theme.accent)
            painter.setBrush(Qt.NoBrush)
            pen = painter.pen()
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawRoundedRect(body, radius, radius)
        elif focused:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(theme.focus)
            pen = painter.pen()
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawRoundedRect(body.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        else:
            painter.setBrush(Qt.NoBrush)
            pen = painter.pen()
            pen.setColor(border)
            pen.setWidthF(bwidth)
            painter.setPen(pen)
            painter.drawRoundedRect(body, radius, radius)

        painter.restore()
