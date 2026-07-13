"""Polished, explainable "Pick for me" dialog."""
from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models import Game
from app.services import candidates_for_mode, pick_game, playable_candidates
from app.ui.icons import AppIcons
from app.ui.theme import (
    current_theme,
    ghost_btn_style,
    is_reduced_motion,
    primary_btn_style,
    secondary_btn_style,
    segmented_btn_style,
)
from app.ui.widgets.game_artwork import GameArtwork
from app.ui.widgets.game_grid.display_utils import status_label


class RandomGameDialog(QDialog):
    """Choose, explain, and reroll without bouncing through message boxes."""

    MODES = (
        (
            "Balanced",
            "balanced",
            "A thoughtful mix of unplayed, in-progress, highly rated, and not-recently-played games.",
        ),
        (
            "Continue",
            "continue",
            "Prefer games already in progress; fall back to any playable game if needed.",
        ),
        (
            "Discover",
            "discover",
            "Prefer games you have never launched; fall back to any playable game if needed.",
        ),
    )

    def __init__(self, games: Iterable[Game], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._games = list(games)
        # Filesystem validation happens once per dialog. Rerolls stay instant and
        # opening a new picker naturally reflects repaired or removed paths.
        self._playable = playable_candidates(self._games)
        self._seen_by_mode = {value: set() for _label, value, _desc in self.MODES}
        self._mode = "balanced"
        self.selected_game: Game | None = None
        self.action = ""

        self.setWindowTitle("Pick what to play")
        self.setModal(True)
        self.setMinimumWidth(650)
        self.setSizeGripEnabled(False)
        theme = current_theme()
        self.setStyleSheet(
            f"QDialog {{ background: {theme.surface_sunken.name()}; }} "
            f"QLabel {{ background: transparent; border: none; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.spacing_xl, theme.spacing_xl, theme.spacing_xl, theme.spacing_lg)
        outer.setSpacing(theme.spacing_lg)

        heading = QLabel(f"{AppIcons.UI_DICE}  Pick for me")
        heading.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {theme.text.name()};"
        )
        subheading = QLabel(
            "Choose the kind of mood you are in. Only playable games in the current view are considered."
        )
        subheading.setWordWrap(True)
        subheading.setStyleSheet(f"font-size: 13px; color: {theme.text_muted.name()};")
        outer.addWidget(heading)
        outer.addWidget(subheading)

        mode_header = QHBoxLayout()
        mode_label = QLabel("WHAT SOUNDS GOOD?")
        mode_label.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {theme.text_muted.name()};"
        )
        self.candidate_label = QLabel()
        self.candidate_label.setStyleSheet(f"font-size: 12px; color: {theme.text_muted.name()};")
        mode_header.addWidget(mode_label)
        mode_header.addStretch(1)
        mode_header.addWidget(self.candidate_label)
        outer.addLayout(mode_header)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for index, (label, value, description) in enumerate(self.MODES):
            position = "left" if index == 0 else ("right" if index == len(self.MODES) - 1 else "mid")
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(value == self._mode)
            button.setStyleSheet(segmented_btn_style(theme, position))
            button.setToolTip(description)
            button.setAccessibleDescription(description)
            button.clicked.connect(lambda _checked=False, selected=value: self._set_mode(selected))
            self._mode_group.addButton(button)
            mode_row.addWidget(button, 1)
        outer.addLayout(mode_row)

        self.mode_description = QLabel()
        self.mode_description.setWordWrap(True)
        self.mode_description.setStyleSheet(f"font-size: 12px; color: {theme.text_muted.name()};")
        outer.addWidget(self.mode_description)

        self.result_card = QFrame()
        self.result_card.setObjectName("pickerResult")
        self.result_card.setMinimumHeight(178)
        self.result_card.setStyleSheet(
            f"QFrame#pickerResult {{ background: {theme.card.name()}; "
            f"border: 1px solid {theme.card_border.name()}; border-radius: {theme.radius_lg}px; }}"
        )
        result_row = QHBoxLayout(self.result_card)
        result_row.setContentsMargins(theme.spacing_lg, theme.spacing_lg, theme.spacing_xl, theme.spacing_lg)
        result_row.setSpacing(theme.spacing_lg)

        self.artwork = GameArtwork(width=142, height=136)
        result_row.addWidget(self.artwork, 0, Qt.AlignVCenter)

        result_text = QVBoxLayout()
        result_text.setSpacing(theme.spacing_xs)
        self.eyebrow = QLabel("YOUR PICK")
        self.eyebrow.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {theme.accent.name()};"
        )
        self.game_title = QLabel("Finding a game…")
        self.game_title.setWordWrap(True)
        self.game_title.setStyleSheet(
            f"font-size: 23px; font-weight: 700; color: {theme.text.name()};"
        )
        self.game_meta = QLabel()
        self.game_meta.setStyleSheet(f"font-size: 12px; color: {theme.text_muted.name()};")
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        self.reason.setStyleSheet(
            f"font-size: 13px; color: {theme.text.name()}; padding-top: 6px;"
        )
        result_text.addWidget(self.eyebrow)
        result_text.addWidget(self.game_title)
        result_text.addWidget(self.game_meta)
        result_text.addStretch(1)
        result_text.addWidget(self.reason)
        result_row.addLayout(result_text, 1)

        self._result_effect = QGraphicsOpacityEffect(self.result_card)
        self._result_effect.setOpacity(1.0)
        self.result_card.setGraphicsEffect(self._result_effect)
        self._result_anim = QPropertyAnimation(self._result_effect, b"opacity", self)
        self._result_anim.setDuration(theme.anim_normal)
        self._result_anim.setEasingCurve(QEasingCurve.OutCubic)
        outer.addWidget(self.result_card)

        actions = QHBoxLayout()
        actions.setSpacing(theme.spacing_sm)
        self.again_btn = QPushButton(f"{AppIcons.UI_DICE}  Pick another")
        self.view_btn = QPushButton("View in library")
        self.close_btn = QPushButton("Close")
        self.play_btn = QPushButton(f"{AppIcons.ACT_PLAY}  Play this game")
        self.again_btn.setStyleSheet(secondary_btn_style(theme))
        self.view_btn.setStyleSheet(secondary_btn_style(theme))
        self.close_btn.setStyleSheet(ghost_btn_style(theme))
        self.play_btn.setStyleSheet(primary_btn_style(theme))
        for button in (self.again_btn, self.view_btn, self.close_btn, self.play_btn):
            button.setCursor(Qt.PointingHandCursor)
        self.again_btn.clicked.connect(self._pick)
        self.view_btn.clicked.connect(lambda: self._finish("view"))
        self.close_btn.clicked.connect(self.reject)
        self.play_btn.clicked.connect(lambda: self._finish("play"))
        self.play_btn.setDefault(True)
        actions.addWidget(self.again_btn)
        actions.addWidget(self.view_btn)
        actions.addStretch(1)
        actions.addWidget(self.close_btn)
        actions.addWidget(self.play_btn)
        outer.addLayout(actions)

        self._update_mode_copy()
        self._pick(animate=False)

    def _set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self._update_mode_copy()
        self._pick()

    def _update_mode_copy(self) -> None:
        description = next(desc for _label, value, desc in self.MODES if value == self._mode)
        candidates = candidates_for_mode(self._playable, self._mode)
        fallback = ""
        if self._mode == "continue" and candidates and not any(
            getattr(game.status, "value", game.status) == "playing" for game in self._playable
        ):
            fallback = " No in-progress games were found, so all playable games are available."
        elif self._mode == "discover" and candidates and not any(
            game.launch_count == 0 for game in self._playable
        ):
            fallback = " No unplayed games were found, so all playable games are available."
        self.mode_description.setText(description + fallback)
        noun = "match" if len(candidates) == 1 else "matches"
        self.candidate_label.setText(f"{len(candidates)} playable {noun}")

    def _pick(self, _checked: bool = False, *, animate: bool = True) -> None:
        del _checked
        result = pick_game(
            self._playable,
            mode=self._mode,
            exclude_ids=self._seen_by_mode[self._mode],
            validate_paths=False,
        )
        if result is None:
            self.selected_game = None
            self.artwork.set_game(None)
            self.eyebrow.setText("NOTHING TO PICK YET")
            self.game_title.setText("No playable games in this view")
            self.game_meta.setText("Finished, dropped, and missing launch paths are skipped.")
            self.reason.setText("Try another library view or repair a missing shortcut in Health.")
            self.again_btn.setEnabled(False)
            self.view_btn.setEnabled(False)
            self.play_btn.setEnabled(False)
            return

        self.selected_game = result.game
        self._seen_by_mode[self._mode].add(result.game.game_id)
        game = result.game
        played = "Never played" if game.launch_count == 0 else f"Played {game.launch_count} times"
        rating = f"  ·  ★ {game.rating}/10" if game.rating else ""
        self.eyebrow.setText("YOUR PICK")
        self.artwork.set_game(game)
        self.game_title.setText(game.title)
        self.game_meta.setText(f"{status_label(game.status)}  ·  {played}{rating}")
        self.reason.setText(result.reason)
        self.again_btn.setEnabled(result.candidate_count > 1)
        self.view_btn.setEnabled(True)
        self.play_btn.setEnabled(True)

        if animate and not is_reduced_motion():
            self._result_anim.stop()
            self._result_effect.setOpacity(0.62)
            self._result_anim.setStartValue(0.62)
            self._result_anim.setEndValue(1.0)
            self._result_anim.start()
        else:
            self._result_effect.setOpacity(1.0)

    def _finish(self, action: str) -> None:
        if self.selected_game is None:
            return
        self.action = action
        self.accept()

