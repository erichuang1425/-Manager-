"""Choose the best icon for a created shortcut.

Windows shows a .lnk with the target's *first* icon group (icon index 0) — the
same default Explorer uses. That group is sometimes only a small frame (e.g.
16/32/48 px) even when the same .exe embeds a larger icon in a later group, so
the shortcut renders as a tiny image centered in a big white tile. Two fixes:

  1. Scan every icon group in the launcher and point the shortcut at the one
     with the largest native frame (``best_group``), instead of hardcoding 0.
  2. When even the best embedded frame is too small to fill a large Explorer
     tile (< ``ICON_FILL_MIN``), synthesize a smooth-upscaled 256 px ``.ico``
     and point the shortcut at that instead (``generate_filled_ico``).

The pure parsers/assemblers (``parse_group_max_frame``, ``best_group``,
``assemble_ico``) carry no Windows dependency and are unit-tested cross-platform.
The extraction/scaling helpers degrade to the historical ``(target, 0)`` whenever
pywin32 / the Qt image plugins are unavailable, so nothing here can abort an
apply.
"""
from __future__ import annotations
import os
import struct
import hashlib


# Below this native frame size (px), the launcher's own icon won't fill a large
# Explorer tile, so we synthesize an upscaled .ico instead. Set to a full 256 px
# tile: anything smaller (a 48/96/128 px embedded icon) otherwise gets scaled up
# by Explorer with a low-quality filter, which is exactly the pixelation we want
# to take over and do well ourselves.
ICON_FILL_MIN = 256
# Frame sizes packed into a generated .ico, largest first. The 256 frame fills
# the big tile; the smaller frames keep list/detail views crisp.
_GENERATED_FRAMES = (256, 128, 64, 48, 32, 16)

# Windows resource type IDs.
RT_ICON = 3
RT_GROUP_ICON = 14

# Offset of the single image inside a one-frame .ico: 6-byte ICONDIR + one
# 16-byte ICONDIRENTRY.
_SINGLE_FRAME_OFFSET = 22


try:
    import win32api  # type: ignore
    import win32con  # type: ignore
except Exception:  # pragma: no cover - exercised only on the non-Windows host
    win32api = None
    win32con = None


# --------------------------------------------------------------------------
# Pure parsing / assembly (no Windows dependency; unit-tested cross-platform)
# --------------------------------------------------------------------------

def parse_group_max_frame(blob: bytes) -> int:
    """Largest native icon width (px) described by one RT_GROUP_ICON resource.

    ``blob`` is a GRPICONDIR: a 6-byte header (reserved, type, count) followed
    by ``count`` 14-byte GRPICONDIRENTRY records. A stored width byte of 0 means
    256 (the byte field can't encode 256). Returns 0 for a malformed/empty group.
    """
    if len(blob) < 6:
        return 0
    _reserved, _type, count = struct.unpack("<HHH", blob[:6])
    best = 0
    off = 6
    for _ in range(count):
        entry = blob[off:off + 14]
        off += 14
        if len(entry) < 14:
            break
        width = entry[0] or 256
        if width > best:
            best = width
    return best


def best_group(group_blobs) -> tuple[int, int]:
    """Pick which icon group a shortcut should display.

    ``group_blobs`` is the list of GRPICONDIR byte blobs in resource-directory
    order — which is exactly the order Windows' ExtractIcon / SetIconLocation
    index by (named resources first, then integer IDs). Returns
    ``(best_index, best_max_frame_px)``: the index of the group with the largest
    native frame. Ties keep the lower index, so a game's authentic default icon
    (index 0) wins over an equally large launcher/repacker icon. Returns
    ``(0, 0)`` when there are no usable groups.
    """
    best_index = 0
    best_max = 0
    for idx, blob in enumerate(group_blobs):
        mx = parse_group_max_frame(blob)
        if mx > best_max:
            best_max = mx
            best_index = idx
    return best_index, best_max


def assemble_ico(frames) -> bytes:
    """Build a multi-frame .ico from ``frames``: a list of ``(size_px, png_bytes)``.

    Each frame is stored as PNG (allowed inside .ico on Vista+), so a 256 px
    frame stays compact. A size of 256 is written as 0 in the directory entry's
    width/height byte, per the format. Frames with empty payloads are dropped.
    """
    frames = [(size, png) for size, png in frames if png]
    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    payload = b""
    offset = 6 + 16 * count
    for size, png in frames:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        payload += png
        offset += len(png)
    return header + entries + payload


# --------------------------------------------------------------------------
# Windows extraction (degrades to a safe fallback when pywin32 is absent)
# --------------------------------------------------------------------------

def best_icon(exe_path: str) -> tuple[int, int]:
    """``(best_index, best_max_frame_px)`` for an .exe's icon groups; ``(0, 0)``
    when pywin32 is unavailable, the file has no group icons, or parsing fails."""
    if win32api is None:
        return 0, 0
    try:
        handle = win32api.LoadLibraryEx(exe_path, 0, win32con.LOAD_LIBRARY_AS_DATAFILE)
    except Exception:
        return 0, 0
    try:
        names = win32api.EnumResourceNames(handle, RT_GROUP_ICON)
        blobs = [win32api.LoadResource(handle, RT_GROUP_ICON, nm) for nm in names]
    except Exception:
        return 0, 0
    finally:
        try:
            win32api.FreeLibrary(handle)
        except Exception:
            pass
    return best_group(blobs)


def _largest_frame_ico_bytes(exe_path: str, group_index: int) -> bytes | None:
    """Wrap the largest frame of the given icon-group index as a one-frame .ico.

    Reconstructs a loadable .ico from the module's RT_GROUP_ICON directory entry
    and the matching RT_ICON image. Returns None on any failure.
    """
    if win32api is None:
        return None
    try:
        handle = win32api.LoadLibraryEx(exe_path, 0, win32con.LOAD_LIBRARY_AS_DATAFILE)
    except Exception:
        return None
    try:
        names = win32api.EnumResourceNames(handle, RT_GROUP_ICON)
        if not (0 <= group_index < len(names)):
            return None
        blob = win32api.LoadResource(handle, RT_GROUP_ICON, names[group_index])
        if len(blob) < 6:
            return None
        _reserved, _type, count = struct.unpack("<HHH", blob[:6])
        best = None  # (width, nID, width_byte, height_byte)
        off = 6
        for _ in range(count):
            entry = blob[off:off + 14]
            off += 14
            if len(entry) < 14:
                break
            width = entry[0] or 256
            n_id = struct.unpack("<H", entry[12:14])[0]
            if best is None or width > best[0]:
                best = (width, n_id, entry[0], entry[1])
        if best is None:
            return None
        raw = win32api.LoadResource(handle, RT_ICON, best[1])
    except Exception:
        return None
    finally:
        try:
            win32api.FreeLibrary(handle)
        except Exception:
            pass

    icondir = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII", best[2], best[3], 0, 0, 1, 32, len(raw), _SINGLE_FRAME_OFFSET
    )
    return icondir + entry + raw


def _scale_frame(source, size: int):
    """High-quality square scale of a QImage ``source`` to ``size``x``size``.

    Upscaling a small launcher icon straight to 256 px in one bilinear step
    looks soft and blocky — the pixelation users notice. Two things fix that:

      * Step up by at most 2x at a time (each a smooth resample). Repeated
        halving of the gap is much closer to a high-order filter than a single
        large jump, so edges and gradients stay clean.
      * Keep the aspect ratio and center the result on a transparent square, so
        a non-square source is never stretched into a smear.

    Qt is already imported by the only caller; importing here keeps the helper
    self-contained.
    """
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt

    w, h = source.width(), source.height()
    if w <= 0 or h <= 0:
        return source

    cur = source
    cw, ch = w, h
    # Progressive 2x upscaling, only while we're still enlarging toward `size`.
    while min(cw, ch) * 2 <= size:
        cw *= 2
        ch *= 2
        cur = cur.scaled(cw, ch, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    fitted = cur.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    if fitted.width() == size and fitted.height() == size:
        return fitted

    # Non-square source: center the fitted image on a transparent square tile.
    canvas = QImage(size, size, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.drawImage((size - fitted.width()) // 2, (size - fitted.height()) // 2, fitted)
    painter.end()
    return canvas


def generate_filled_ico(exe_path: str, group_index: int, dest_path: str) -> bool:
    """Smooth-upscale the launcher's best icon frame to a filled multi-size .ico.

    Loads the largest frame of ``group_index`` and renders it to each size in
    ``_GENERATED_FRAMES`` with ``_scale_frame`` (progressive, aspect-preserving
    resampling), then writes the assembled .ico to ``dest_path``. Returns True on
    success, False on any failure (the caller then keeps the embedded icon). Qt
    is imported lazily so this module stays importable on a headless/non-Windows
    test host.
    """
    raw_ico = _largest_frame_ico_bytes(exe_path, group_index)
    if not raw_ico:
        return False
    try:
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QBuffer, QByteArray

        source = QImage()
        if not source.loadFromData(raw_ico, "ICO") or source.isNull():
            return False
        # Normalize to ARGB32 so alpha is preserved through every resample step.
        source = source.convertToFormat(QImage.Format_ARGB32)

        frames = []
        for size in _GENERATED_FRAMES:
            scaled = _scale_frame(source, size)
            buffer = QByteArray()
            qbuf = QBuffer(buffer)
            qbuf.open(QBuffer.WriteOnly)
            if not scaled.save(qbuf, "PNG"):
                qbuf.close()
                return False
            qbuf.close()
            frames.append((size, bytes(buffer)))

        data = assemble_ico(frames)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as fh:
            fh.write(data)
        return True
    except Exception:
        return False


def _cache_name(target_path: str) -> str:
    """Stable, collision-free filename for a target's generated icon.

    Keyed by a hash of the (case-folded) target path so re-runs overwrite the
    same file and two games sharing one launcher share one icon. The launcher's
    stem is kept as a readable prefix.
    """
    key = target_path.lower()
    digest = hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()[:16]
    stem = os.path.splitext(os.path.basename(key))[0]
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in stem)[:40]
    return f"{safe or 'icon'}_{digest}.ico"


def resolve_shortcut_icon(target_path: str, icon_cache_dir: str | None = None) -> tuple[str, int]:
    """Pick the ``(icon_path, icon_index)`` for a shortcut to ``target_path``.

    Prefers the largest icon already embedded in the launcher. When even that is
    too small to fill a large Explorer tile (< ``ICON_FILL_MIN``) and an
    ``icon_cache_dir`` is provided, synthesizes a smooth-upscaled .ico there and
    returns it. Always degrades to ``(target_path, 0)`` — the historical
    behavior — on any failure or when extraction is unavailable.
    """
    try:
        index, max_frame = best_icon(target_path)
    except Exception:
        return target_path, 0

    if max_frame <= 0:
        return target_path, 0
    if max_frame >= ICON_FILL_MIN or not icon_cache_dir:
        return target_path, index

    try:
        dest = os.path.join(icon_cache_dir, _cache_name(target_path))
        if generate_filled_ico(target_path, index, dest):
            return dest, 0
    except Exception:
        pass
    return target_path, index
