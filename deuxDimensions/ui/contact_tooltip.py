"""Infobulle de contact deplacable pour la vue 2D."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ContactTooltip(QWidget):
    """Petite fenetre HTML deplacable pour detailler un contact."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("ContactTooltip")
        self._bounds = QRect()
        self._drag_offset = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(6)
        self._drag_hint = QWidget()
        self._drag_hint.setMinimumHeight(18)
        self._drag_hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._drag_hint.setCursor(Qt.CursorShape.SizeAllCursor)
        self._drag_hint.setToolTip("Glisser pour deplacer (reste dans le plan de dessin)")
        head.addWidget(self._drag_hint, stretch=1)
        self._btn_close = QPushButton("×")
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setStyleSheet(
            "QPushButton { background:#ff6f00; color:white; font-size:14px; "
            "font-weight:bold; border:none; border-radius:3px; } "
            "QPushButton:hover { background:#e65100; }"
        )
        self._btn_close.setToolTip("Fermer")
        self._btn_close.clicked.connect(self.hide)
        head.addWidget(self._btn_close)
        lay.addLayout(head)
        self._lbl = QLabel()
        self._lbl.setWordWrap(True)
        self._lbl.setTextFormat(Qt.TextFormat.RichText)
        self._lbl.setStyleSheet("font-family: Consolas; font-size: 10px; color: #1a1a1a;")
        lay.addWidget(self._lbl)
        self.setStyleSheet(
            "QWidget#ContactTooltip { background:#fffef0; color:#1a1a1a; "
            "border:1px solid #c9a000; border-radius:5px; }"
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumSize(180, 72)

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()

    def _drag_blocked_widget(self, child):
        if child is None:
            return False
        return child is self._btn_close or self._btn_close.isAncestorOf(child)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if not self._drag_blocked_widget(child):
                self._drag_offset = event.globalPosition().toPoint() - self.pos()
                self.grabMouse()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            p = event.globalPosition().toPoint() - self._drag_offset
            self.move(self._clamp_top_left(p))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_offset is not None:
                self.releaseMouse()
                self._drag_offset = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def set_plot_bounds_global(self, rect: QRect):
        """Rectangle global (ecran) dans lequel l'infobulle peut glisser."""
        self._bounds = QRect(rect)

    def _clamp_top_left(self, top_left: QPoint) -> QPoint:
        """Recadre le coin haut-gauche pour rester dans _bounds, avec une marge."""
        x, y = top_left.x(), top_left.y()
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            self.adjustSize()
            w, h = self.width(), self.height()
        if self._bounds.isNull() or self._bounds.isEmpty():
            return QPoint(x, y)
        m = 2
        r = self._bounds
        x_min, y_min = r.left() + m, r.top() + m
        x_max = r.right() - w - m
        y_max = r.bottom() - h - m
        if x_max < x_min:
            x = r.left() + m
        else:
            x = min(max(x_min, x), x_max)
        if y_max < y_min:
            y = r.top() + m
        else:
            y = min(max(y_min, y), y_max)
        return QPoint(x, y)

    def clamp_to_bounds(self):
        """Apres redimensionnement : garde la fenetre visible dans la zone autorisee."""
        self.move(self._clamp_top_left(self.pos()))

    def set_rich_text(self, html):
        """Affiche du texte riche (HTML) dans le corps de l'infobulle."""
        self._lbl.setText(html)
