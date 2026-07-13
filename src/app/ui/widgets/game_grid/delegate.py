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
    QLinearGradient, QBrush,
)
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from app.services import (
    icon_path_for_game, request_icon_async,
    request_artwork_async,
    parse_version, compare_versions,
)
from app.services.version_parser import CompareResult
from app.ui.theme import current_theme, status_color
from app.ui.icons import AppIcons
from app.logging_utils import get_logger

from .model import GameRole
from .display_utils import (
    status_label, relative_time,
    tile_initials, tile_gradient_hsl, tile_text_is_light,
    native_icon_size, rating_is_set, status_is_default,
    CJK_FONT_FAMILIES, cover_crop_rect,
)

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
    return icon_path_for_game(game, check_exists=False)


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


def _paint_generated_tile(painter: QPainter, icon_path: QPainterPath, rect: QRect, title: str) -> None:
    """Fill the cover area with a deterministic gradient + the title's initials.

    Used when a game has no artwork or only a tiny shortcut icon.  Colours are
    derived from a stable hash of the title (see ``display_utils``) so a tile is
    consistent across runs and varied across the grid.
    """
    (h1, s1, l1), (h2, s2, l2) = tile_gradient_hsl(title)
    grad = QLinearGradient(
        float(rect.left()), float(rect.top()),
        float(rect.left()), float(rect.bottom()),
    )
    grad.setColorAt(0.0, QColor.fromHslF(h1, s1, l1))
    grad.setColorAt(1.0, QColor.fromHslF(h2, s2, l2))
    painter.fillPath(icon_path, QBrush(grad))

    painter.setPen(QColor(238, 240, 248) if tile_text_is_light(title) else QColor(20, 22, 30))
    f = QFont(painter.font())
    if hasattr(f, "setFamilies"):
        f.setFamilies(list(dict.fromkeys([f.family(), *CJK_FONT_FAMILIES])))
    f.setPixelSize(max(24, round(rect.height() * 0.4)))
    f.setWeight(QFont.Bold)
    painter.setFont(f)
    painter.drawText(rect, Qt.AlignCenter, tile_initials(title))


def _paint_custom_artwork(
    painter: QPainter,
    icon_path: QPainterPath,
    rect: QRect,
    pixmap: QPixmap,
) -> None:
    """Center-crop custom artwork into the rounded cover area."""
    if pixmap.isNull():
        return
    sx, sy, sw, sh = cover_crop_rect(
        pixmap.width(), pixmap.height(), rect.width(), rect.height(),
    )
    if not sw or not sh:
        return
    painter.save()
    painter.setClipPath(icon_path)
    painter.drawPixmap(QRectF(rect), pixmap, QRectF(sx, sy, sw, sh))
    painter.restore()


def _paint_identity_icon(
    painter: QPainter,
    rect: QRect,
    pixmap: QPixmap,
    theme,
) -> None:
    """Paint the original app icon as a native-size identity badge.

    The generated title tile remains the card artwork. The executable/shortcut
    icon is layered at the lower-left and is only reduced, never enlarged.
    """
    if pixmap.isNull():
        return
    dpr = max(1.0, float(pixmap.devicePixelRatio()))
    source_w = pixmap.width() / dpr
    source_h = pixmap.height() / dpr
    max_extent = min(64, max(36, round(rect.height() * 0.40)))
    icon_w, icon_h = native_icon_size(source_w, source_h, max_extent)
    if not icon_w or not icon_h:
        return

    pad = 7
    badge_w = max(32, icon_w + pad * 2)
    badge_h = max(32, icon_h + pad * 2)
    badge = QRectF(
        rect.left() + 10,
        rect.bottom() - badge_h - 10,
        badge_w,
        badge_h,
    )
    painter.save()
    painter.setPen(theme.card_border)
    painter.setBrush(theme.surface_overlay or theme.surface)
    painter.drawRoundedRect(badge, 10, 10)
    target = QRectF(
        badge.center().x() - icon_w / 2,
        badge.center().y() - icon_h / 2,
        icon_w,
        icon_h,
    )
    painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
    painter.restore()


def build_geometry(
    rect: QRect, game, m: CardMetrics, multi_select: bool, hovered: bool = False,
) -> CardGeometry:
    """Compute all sub-rects for a card within ``rect``.

    ``hovered`` gates progressive-disclosure zones: rating stars and the status
    chip only become hit targets when the game carries that data OR the card is
    hovered.  The view passes ``hovered=True`` when hit-testing (a click always
    lands on the card under the cursor), so painted and clickable regions match.
    """
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

    # Stars laid out at the left of the meta row.  They are only interactive /
    # painted when the game is rated, or on hover (so click-to-rate stays
    # discoverable on unrated cards).  ``sx`` still advances through all five
    # slots regardless, so the relative-time text keeps its position exactly.
    star_sz = max(12, m.meta_h - 2)
    show_stars = hovered or rating_is_set(game.rating)
    stars: List[Tuple[int, QRect]] = []
    sx = cx
    for i in range(5):
        star_rect = QRect(sx, cy + (m.meta_h - star_sz) // 2, star_sz, star_sz)
        if show_stars:
            stars.append(((i + 1) * 2, star_rect))
        sx += star_sz + 1
    time_rect = QRect(sx + 6, cy, cw - (sx + 6 - cx), m.meta_h)
    cy += m.meta_h

    chips: List[Tuple[str, object, QRect]] = []
    if m.has_chips:
        cy += 6
        chip_y = cy
        chip_h = m.chip_h
        chx = cx
        # status chip — hidden at rest for default-status (backlog) cards, shown
        # on hover.  Remaining chips left-pack into the freed space.
        if hovered or not status_is_default(game.status):
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
        # Dedupe per rendered cache entry. The shared icon service separately
        # dedupes the actual (path, size) load while retaining every subscriber.
        self._icon_pending: set[str] = set()
        self._artwork_pending: set[str] = set()
        self._artwork_failed: set[str] = set()
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
        if key not in self._icon_pending:
            self._icon_pending.add(key)
            gid = game.game_id

            def _ready(p: str, pixmap, _gid=gid, _key=key, _dpr=dpr):
                self._icon_pending.discard(_key)
                if pixmap is not None and not pixmap.isNull():
                    # Never mutate the service's shared cached pixmap: another
                    # screen may request the same source at a different DPR.
                    rendered = QPixmap(pixmap)
                    rendered.setDevicePixelRatio(_dpr)
                    QPixmapCache.insert(_key, rendered)
                    self._dirty_ids.add(_gid)
                    if not self._repaint_timer.isActive():
                        self._repaint_timer.start()

            request_icon_async(path, target_px, _ready)
        return None

    @staticmethod
    def _artwork_key(game_id: str, path: str, width: int, height: int, dpr: float) -> str:
        return f"gcard-art:{game_id}:{path}:{width}x{height}:{dpr:.2f}"

    def _artwork_pixmap(
        self, game, width: int, height: int, dpr: float,
    ) -> Optional[QPixmap]:
        path = getattr(game, "card_artwork_path", "") or ""
        if not path:
            return None
        key = self._artwork_key(game.game_id, path, width, height, dpr)
        cached = QPixmapCache.find(key)
        if cached is not None:
            return cached
        if key in self._artwork_failed:
            return None
        if key not in self._artwork_pending:
            self._artwork_pending.add(key)
            gid = game.game_id

            def _ready(loaded_path: str, image, _gid=gid, _key=key, _dpr=dpr):
                self._artwork_pending.discard(_key)
                if loaded_path != path or image is None or image.isNull():
                    self._artwork_failed.add(_key)
                    return
                rendered = QPixmap.fromImage(image)
                rendered.setDevicePixelRatio(_dpr)
                QPixmapCache.insert(_key, rendered)
                self._dirty_ids.add(_gid)
                if not self._repaint_timer.isActive():
                    self._repaint_timer.start()

            request_artwork_async(path, width, height, _ready)
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

        geo = build_geometry(option.rect, game, m, multi, hovered)

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

        # The title-derived tile is the cover artwork. The original executable
        # or shortcut icon remains visible as a small identity badge, where its
        # native resolution stays crisp instead of being stretched card-wide.
        dpr = float(option.widget.devicePixelRatioF()) if option.widget else 1.0
        target_px = min(512, max(96, round(max(geo.icon.width(), geo.icon.height()) * dpr)))
        pm = self._icon_pixmap(game, target_px, dpr)
        artwork = self._artwork_pixmap(
            game,
            max(1, round(geo.icon.width() * dpr)),
            max(1, round(geo.icon.height() * dpr)),
            dpr,
        )
        if artwork is not None and not artwork.isNull():
            _paint_custom_artwork(painter, icon_path, geo.icon, artwork)
        else:
            _paint_generated_tile(painter, icon_path, geo.icon, game.title)
        if pm is not None and not pm.isNull():
            _paint_identity_icon(painter, geo.icon, pm, theme)

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

        # --- rating stars (only present when rated or hovered) ---
        if geo.stars:
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
