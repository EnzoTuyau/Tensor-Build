"""Système de toasts modernes (notifications éphémères empilables)."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from deuxDimensions.domain.constantes import (
    TOAST_DUREE_MS,
    TOAST_LARGEUR,
    TOAST_MAX_VISIBLES,
)


_PROG_HEIGHT = 3
_GAP = 8
_MARGE_DROITE = 18
_MARGE_HAUT = 18


class _ProgressBar(QWidget):
    """Mince barre de progression sous le toast (décroît avec le temps restant)."""

    def __init__(self, couleur: str, parent=None):
        super().__init__(parent)
        self._couleur = QColor(couleur)
        self._ratio = 1.0
        self.setFixedHeight(_PROG_HEIGHT)

    def set_ratio(self, r: float):
        self._ratio = max(0.0, min(1.0, r))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2a161a"))
        p.drawRoundedRect(rect, 1.5, 1.5)
        w = int(rect.width() * self._ratio)
        if w > 0:
            p.setBrush(self._couleur)
            p.drawRoundedRect(QRect(0, 0, w, rect.height()), 1.5, 1.5)


class Toast(QFrame):
    """Carte de notification : bandeau gauche coloré, icône, titre, sous-titre, barre."""

    def __init__(
        self,
        titre: str,
        sous_titre: str = "",
        duree_ms: int = TOAST_DUREE_MS,
        accent: str = "#dc2626",
        icone: str = "⚠",
        on_close=None,
        parent=None,
    ):
        super().__init__(None)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setFixedWidth(TOAST_LARGEUR)
        self._duree_ms = max(800, int(duree_ms))
        self._restant_ms = self._duree_ms
        self._accent = accent
        self._on_close = on_close
        self._ferme = False

        self.setStyleSheet(
            f"""
            QFrame#toast {{
                background-color: #120a0c;
                border: none;
                border-radius: 12px;
            }}
            QLabel[role="t-title"] {{
                color: #f8fafc; font-size: 14px; font-weight: 800;
                letter-spacing: 0.3px;
                background-color: transparent;
            }}
            QLabel[role="t-sub"] {{
                color: #fecaca; font-size: 11px;
                background-color: transparent;
            }}
            QLabel[role="t-icon"] {{
                color: {accent}; font-size: 22px; font-weight: 800;
                background-color: transparent;
            }}
            QPushButton[role="t-close"] {{
                background: transparent; color: #ffd8d8; border: none;
                font-size: 14px; font-weight: 700;
                border-radius: 4px;
            }}
            QPushButton[role="t-close"]:hover {{
                background: #3a1f25; color: #ffffff;
            }}
            QWidget#toastInner {{
                background-color: #120a0c;
            }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body.setObjectName("toastInner")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(body)
        h.setContentsMargins(12, 10, 8, 10)
        h.setSpacing(10)

        lbl_icone = QLabel(icone)
        lbl_icone.setProperty("role", "t-icon")
        lbl_icone.setFixedWidth(20)
        lbl_icone.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        h.addWidget(lbl_icone)

        textes = QVBoxLayout()
        textes.setSpacing(2)
        textes.setContentsMargins(0, 0, 0, 0)
        self._lbl_titre = QLabel(titre)
        self._lbl_titre.setProperty("role", "t-title")
        self._lbl_titre.setWordWrap(True)
        textes.addWidget(self._lbl_titre)
        if sous_titre:
            self._lbl_sub = QLabel(sous_titre)
            self._lbl_sub.setProperty("role", "t-sub")
            self._lbl_sub.setWordWrap(True)
            textes.addWidget(self._lbl_sub)
        h.addLayout(textes, stretch=1)

        btn = QPushButton("×")
        btn.setProperty("role", "t-close")
        btn.setFixedSize(22, 22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.fermer)
        h.addWidget(btn, alignment=Qt.AlignmentFlag.AlignTop)

        outer.addWidget(body)

        prog_wrap = QWidget()
        pwl = QVBoxLayout(prog_wrap)
        pwl.setContentsMargins(10, 0, 10, 8)
        pwl.setSpacing(0)
        self._prog = _ProgressBar(accent)
        pwl.addWidget(self._prog)
        outer.addWidget(prog_wrap)

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setWindowOpacity(0.0)

    def afficher_anime(self):
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.start()

    def enterEvent(self, _):
        self._timer.stop()

    def leaveEvent(self, _):
        if not self._ferme:
            self._timer.start()

    def _tick(self):
        self._restant_ms -= self._timer.interval()
        if self._restant_ms <= 0:
            self.fermer()
            return
        self._prog.set_ratio(self._restant_ms / self._duree_ms)

    def fermer(self):
        if self._ferme:
            return
        self._ferme = True
        self._timer.stop()
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._final)
        self._fade.start()

    def _final(self):
        if callable(self._on_close):
            self._on_close(self)
        self.hide()
        self.deleteLater()


class ToastStack(QObject):
    """
    Empile les toasts en haut-droite du parent (overlay, sans layout).
    Au-delà de TOAST_MAX_VISIBLES, met les suivants en file et affiche '+N'.
    """

    def __init__(self, parent: QWidget, dock_a_eviter: QWidget | None = None):
        super().__init__(parent)
        self._parent = parent
        self._dock = dock_a_eviter
        self._toasts: list[Toast] = []
        self._file: list[tuple[str, str, int, str, str]] = []
        self._compteur = _OverflowChip()
        self._compteur.hide()
        parent.installEventFilter(self)

    def push(
        self,
        titre: str,
        sous_titre: str = "",
        duree_ms: int = TOAST_DUREE_MS,
        accent: str = "#dc2626",
        icone: str = "⚠",
    ):
        if len(self._toasts) >= TOAST_MAX_VISIBLES:
            self._file.append((titre, sous_titre, duree_ms, accent, icone))
            self._mettre_a_jour_compteur()
            return
        self._creer_toast(titre, sous_titre, duree_ms, accent, icone)

    def _creer_toast(self, titre, sous_titre, duree_ms, accent, icone):
        t = Toast(
            titre, sous_titre, duree_ms,
            accent=accent, icone=icone,
            on_close=self._on_toast_close,
        )
        t.adjustSize()
        self._toasts.append(t)
        self._reagencer()
        t.show()
        t.raise_()
        t.afficher_anime()

    def _on_toast_close(self, t: Toast):
        if t in self._toasts:
            self._toasts.remove(t)
        self._reagencer()
        if self._file and len(self._toasts) < TOAST_MAX_VISIBLES:
            args = self._file.pop(0)
            self._creer_toast(*args)
        self._mettre_a_jour_compteur()

    def _reagencer(self):
        if self._parent is None or not self._parent.isVisible():
            return
        top_right_global = self._parent.mapToGlobal(
            QPoint(self._parent.width(), 0)
        )
        offset_dock = 0
        if self._dock is not None and self._dock.isVisible():
            offset_dock = self._dock.width()
        right_x = top_right_global.x() - offset_dock - _MARGE_DROITE
        y = top_right_global.y() + _MARGE_HAUT
        for t in self._toasts:
            t.adjustSize()
            t.move(QPoint(right_x - t.width(), y))
            t.raise_()
            y += t.height() + _GAP
        self._compteur.adjustSize()
        self._compteur.move(
            QPoint(right_x - self._compteur.width(), y)
        )
        if self._compteur.isVisible():
            self._compteur.raise_()

    def _mettre_a_jour_compteur(self):
        n = len(self._file)
        if n <= 0:
            self._compteur.hide()
            return
        self._compteur.set_count(n)
        self._compteur.show()
        self._reagencer()

    def eventFilter(self, obj, event):
        if obj is self._parent and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Move,
            QEvent.Type.WindowStateChange,
            QEvent.Type.WindowActivate,
        ):
            self._reagencer()
        return False


class _OverflowChip(QFrame):
    """Petite pastille '+N autres' sous la pile de toasts (fenêtre top-level)."""

    def __init__(self, parent=None):
        super().__init__(None)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setStyleSheet(
            "background-color:#06080c; color:#9eb4d9; border:1px solid #3b4b62;"
            "border-radius:10px; padding:4px 10px;"
            "font-size:11px; font-weight:700; letter-spacing:0.6px;"
        )
        self._lbl = QLabel("", self)
        self._lbl.setStyleSheet("color:#9eb4d9; background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.addWidget(self._lbl)
        self.setFixedHeight(28)

    def set_count(self, n: int):
        self._lbl.setText(f"+{n} autre{'s' if n > 1 else ''}")
        self.adjustSize()
