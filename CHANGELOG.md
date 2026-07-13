## Unreleased

- Replaced the hard-coded featured-game panel and its dead controls with library-driven content.
- Added a first-class Add Games page with direct multi-file shortcut import, folder scanning, backup restore, source URL matching, archive import, and shortcut creation.
- Replaced modal preferences with a full Settings page covering library paths, appearance, browsing, behavior, and data tools.
- Exposed the download queue in the sidebar and added direct URL queueing with validation and status feedback.
- Connected the empty-library import action, added visible sidebar counts, and made numbered sidebar shortcuts skip section headings.
- Preserved each executable or shortcut icon as a native-size identity badge while using generated title artwork for card previews.
- Added Unicode-aware Traditional Chinese, Simplified Chinese, and Japanese title marks, plus per-game card backgrounds from Snipping Tool, clipboard paste, or an image file; identity badges are slightly larger without pixel-stretching.
- Added an explainable **Pick for me** flow with Balanced, Continue, and Discover modes, reroll protection, current-view filtering, and `Ctrl+P`.
- Smoothed navigation and resizing with adaptive home layouts, content-aware toolbar compaction, hidden-page render avoidance, and debounced settings writes.

## v4.1 (2026-02-03) - Code Quality Release
- **Major Refactoring:** Split 4 monolithic files (5,091 lines) into organized packages:
  - `main_window.py` → `main_window/` package with 10 focused mixins
  - `game_grid.py` → `game_grid/` package (card, grid, skeleton, display_utils)
  - `archive_extractor.py` → `archive/` package (models, detection, extraction, passwords, utils)
  - `download_manager.py` → `download/` package (models, worker, manager)
- **Code Deduplication:** Created shared utility modules:
  - `http_utils.py` - Centralized HTTP operations, error handling, download functions
  - `title_matcher.py` - Fuzzy matching with TitleIndex for O(n) performance
  - `filter_utils.py` - Search caching and filter pipelines
- **Bug Fixes:** Resolved all P0/P1 critical bugs including race conditions in download manager and exception dialog
- **Performance:** Search haystack caching, fuzzy matching index (PERF-001, PERF-002)
- **Metrics:** Reduced codebase from ~39K to ~21K lines, average file size from 547 to 219 lines

## v4 (2026-02-01)
- Icon revamp: request jumbo 1024px shell icons, pick the best available source (shortcut → resolved target → archive), and downscale once for crisp cards. Scan now primes icons only for newly touched games and remembers the upscale flag to avoid rework.
- Scan UX: queued worker signals keep the progress dialog responsive and fix the `QObject::startTimer` warning; a modal scan summary reports totals/new/updated/icons refreshed; duplicate detection shows a wait cursor and optional quarantine before scanning.
- Compatibility: icon_upscaled is persisted/merged for older libraries; sidebar/updates/health refresh automatically after scans.
- Reliability: one-scale rendering path prevents quality loss on resize; safer thread cleanup for cancel/finish states.

## v3 (2026-02-01)
- Added duplicate shortcut detection with optional quarantine before scans; merges still preserve user edits.
- Added Bulk Source URLs tool with fuzzy title matching and optional overwrite to speed source_url setup.
- Added Source quick filter, pill counts, tag filter chip, and persisted filter/density prefs for Updates & Health views.
- Added focus mode, responsive typography buckets, and guarded Details sizing; theme/font changes now refresh safely.
- Collections polish: smart presets (low confidence, HTML only, backlog, unplayed), inline rename/delete, and one-click add selected.

## v2 (2026-01-31)
- Added multi-theme system with font/scale controls and safe live application.
- Fixed regression guardrails: prevent orphan top-level windows and orphan game cards; added safe UI refresh path.
- Improved Health fixes with guided focus/hints and resolve/ignore actions.
- Added scanner integration using bundled GameShortcutMaker.
- Added caching TTL + retries for update checker; performance logging for grid/icon loads.
- Added first-run guidance and packaging plan.

## v1
- Initial public release with library grid, updates, health checks, collections, and scan/import.
