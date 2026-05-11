"""Panneau de controle Qt du simulateur 2D (design moderne)."""

from __future__ import annotations

import functools

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from deuxDimensions.domain.constantes import MATERIAUX
from deuxDimensions.ui.contact_tooltip import ContactTooltip


#1. Palette de couleurs (alignée avec menu.py)
BG          = "#050607"   # Fond global de l'interface
CARD        = "#06080c"   # Fond des cartes et panneaux
CARD_HOVER  = "#0c111a"   # Survol des cartes et contrôles
BORDER      = "#3b4b62"   # Bordures par défaut
BORDER_HOV  = "#2ea0ff"   # Bordure au survol ou au focus
TEXT        = "#eaf2ff"   # Texte principal
TEXT_BRIGHT = "#f3f7ff"   # Titres et libellés mis en avant
MUTED       = "#9eb4d9"   # Texte secondaire
DIM         = "#6c7c95"   # Texte tertiaire et placeholders
ACCENT      = "#1f94ff"   # Bleu de marque
ACCENT_HOV  = "#2ea0ff"   # Bleu au survol
ACCENT_DIM  = "#13314a"   # Fond bleu foncé pour l'état actif
DANGER      = "#ff6b6b"   # Alertes et erreurs
SUCCESS     = "#5ee1a1"   # Confirmation et états positifs


PANEL_QSS = f"""
QFrame#panel {{
    background: {BG};
}}

QLabel {{
    color: {TEXT};
    font-size: 12px;
}}
QLabel[role="title"] {{
    color: {TEXT_BRIGHT};
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.4px;
}}
QLabel[role="section"] {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}}
QLabel[role="muted"] {{
    color: {MUTED};
    font-size: 11px;
}}

QFrame[role="card"] {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* Boutons = cartes plates, style modeCard du menu */
QPushButton {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
}}
QPushButton:hover {{
    border: 1px solid {ACCENT_HOV};
    background: {CARD_HOVER};
    color: {TEXT_BRIGHT};
}}
QPushButton:pressed {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT};
    color: {TEXT_BRIGHT};
}}
QPushButton:disabled {{
    background: {CARD};
    color: {DIM};
    border: 1px solid #2a3344;
}}

QPushButton[variant="primary"] {{
    background: {ACCENT};
    color: white;
    border: 1px solid {ACCENT};
}}
QPushButton[variant="primary"]:hover {{
    background: {ACCENT_HOV};
    border: 1px solid {ACCENT_HOV};
    color: white;
}}

QPushButton[variant="danger-icon"] {{
    background: transparent;
    color: {DIM};
    border: none;
    border-radius: 6px;
    padding: 0;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton[variant="danger-icon"]:hover {{
    background: #3a1f25;
    color: {DANGER};
}}

QDoubleSpinBox, QComboBox {{
    background: {CARD};
    color: {TEXT_BRIGHT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 26px;
    font-size: 12px;
    font-weight: 600;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_BRIGHT};
}}
QDoubleSpinBox:hover, QComboBox:hover {{
    border: 1px solid {BORDER_HOV};
    background: {CARD_HOVER};
}}
QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT_HOV};
    background: {CARD_HOVER};
}}
QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: #08090d;
    color: {DIM};
    border: 1px solid #25304a;
}}

/* SpinBox : boutons up/down avec flèches SVG nettes */
QDoubleSpinBox {{
    padding-right: 28px;
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: padding;
    width: 22px;
    background: {CARD_HOVER};
    border: 1px solid {BORDER};
}}
QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    margin: 3px 3px 0 0;
    border-top-right-radius: 6px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
}}
QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    margin: 0 3px 3px 0;
    border-bottom-right-radius: 6px;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
}}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT_HOV};
}}
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background: {ACCENT};
}}
QDoubleSpinBox::up-arrow {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='5,0 10,6 0,6' fill='%239eb4d9'/></svg>");
    width: 10px; height: 6px;
}}
QDoubleSpinBox::up-arrow:hover {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='5,0 10,6 0,6' fill='%23f3f7ff'/></svg>");
}}
QDoubleSpinBox::down-arrow {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='0,0 10,0 5,6' fill='%239eb4d9'/></svg>");
    width: 10px; height: 6px;
}}
QDoubleSpinBox::down-arrow:hover {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='0,0 10,0 5,6' fill='%23f3f7ff'/></svg>");
}}
QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='5,0 10,6 0,6' fill='%2325304a'/></svg>");
}}

/* ComboBox : flèche déroulante + popup */
QComboBox::drop-down {{
    width: 24px;
    border: none;
    background: transparent;
    subcontrol-origin: padding;
    subcontrol-position: top right;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {MUTED};
    margin-right: 10px;
}}
QComboBox:hover::down-arrow,
QComboBox:focus::down-arrow {{
    border-top: 6px solid {ACCENT_HOV};
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {ACCENT};
    border-radius: 10px;
    padding: 6px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_BRIGHT};
    outline: 0;
    show-decoration-selected: 1;
}}
QComboBox QAbstractItemView::item {{
    padding: 8px 10px;
    border-radius: 6px;
    min-height: 28px;
    color: {TEXT};
    border: 1px solid transparent;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {CARD_HOVER};
    color: {TEXT_BRIGHT};
    border: 1px solid {BORDER_HOV};
}}
QComboBox QAbstractItemView::item:selected {{
    background: {ACCENT_DIM};
    color: {TEXT_BRIGHT};
    border: 1px solid {ACCENT};
}}

QListWidget {{
    background: transparent;
    border: none;
    outline: 0;
}}
QListWidget::item {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin: 0;
    padding: 0;
    min-height: 44px;
}}
QListWidget::item:hover {{
    border: 1px solid {BORDER_HOV};
    background: {CARD_HOVER};
}}
QListWidget::item:selected {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT};
    color: {TEXT_BRIGHT};
}}

QCheckBox {{
    color: {TEXT};
    font-size: 12px;
    spacing: 10px;
    padding: 2px 0;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2a3852; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {BORDER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QTextEdit {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
    font-size: 11px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_BRIGHT};
}}
"""


#2. Interrupteur moderne (case à cocher stylée sans carré classique)
from PySide6.QtCore import QPropertyAnimation, Property
from PySide6.QtWidgets import QAbstractButton


class ToggleSwitch(QAbstractButton):
    """Toggle switch moderne, animé (remplace QCheckBox visuellement)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 2.0
        self._anim = QPropertyAnimation(self, b"handle_pos", self)
        self._anim.setDuration(140)
        self.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(20.0 if checked else 2.0)
        self._anim.start()

    def get_handle_pos(self):
        return self._pos

    def set_handle_pos(self, v):
        self._pos = v
        self.update()

    handle_pos = Property(float, get_handle_pos, set_handle_pos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(ACCENT) if self.isChecked() else QColor(BORDER)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(self.rect(), 11, 11)
        p.setBrush(QColor(TEXT_BRIGHT))
        p.drawEllipse(int(self._pos), 2, 18, 18)

    def sizeHint(self):
        return QSize(40, 22)


def _row_toggle(label: str, hint: str | None = None) -> tuple[QWidget, ToggleSwitch]:
    """Ligne : libelle + toggle a droite (avec petit hint optionnel)."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    txt = QWidget()
    tlay = QVBoxLayout(txt)
    tlay.setContentsMargins(0, 0, 0, 0)
    tlay.setSpacing(2)
    title = QLabel(label)
    title.setStyleSheet(f"color:{TEXT_BRIGHT}; font-size:12px; font-weight:600;")
    tlay.addWidget(title)
    if hint:
        sub = QLabel(hint)
        sub.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        sub.setWordWrap(True)
        tlay.addWidget(sub)
    lay.addWidget(txt, stretch=1)
    sw = ToggleSwitch()
    lay.addWidget(sw, alignment=Qt.AlignmentFlag.AlignVCenter)
    return w, sw


def _card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """Carte UI moderne avec un titre de section optionnel."""
    card = QFrame()
    card.setProperty("role", "card")
    outer = QVBoxLayout(card)
    outer.setContentsMargins(14, 12, 14, 14)
    outer.setSpacing(10)
    if title:
        lbl = QLabel(title)
        lbl.setProperty("role", "section")
        outer.addWidget(lbl)
    return card, outer


def _icone_materiau(face: str, edge: str) -> QIcon:
    """Petite pastille de couleur représentant un matériau."""
    pm = QPixmap(20, 14)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(face))
    p.setPen(QColor(edge))
    p.drawRoundedRect(QRect(1, 1, 18, 12), 3, 3)
    p.end()
    return QIcon(pm)


def _ligne_liste_bloc(panneau, index: int, libelle: str) -> QWidget:
    """Carte d'un bloc : libelle + bouton supprimer discret."""
    w = QWidget()
    w.setMinimumHeight(42)
    h = QHBoxLayout(w)
    h.setContentsMargins(14, 10, 10, 10)
    h.setSpacing(8)
    lbl = QLabel(libelle)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(
        f"color:{TEXT}; font-size:12px; font-weight:500;"
        "background: transparent; padding: 2px 0;"
    )
    btn = QPushButton("×")
    btn.setProperty("variant", "danger-icon")
    btn.setFixedSize(26, 26)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip("Supprimer ce bloc")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(functools.partial(panneau._supprimer_a_index, index))
    h.addWidget(lbl, stretch=1)
    h.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def _press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            panneau.liste_blocs.setCurrentRow(index)
        QWidget.mousePressEvent(w, event)

    w.mousePressEvent = _press
    return w


class PanneauControle(QFrame):
    """Panneau lateral moderne : empilement de cartes, sans onglets."""

    def __init__(self, canvas, callback_physique, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.canvas = canvas
        self.callback_physique = callback_physique
        self._bloc_selectionne = None
        self._contact_sel = None
        self._infobulle_contact = None
        self._construire_ui()
        self.canvas.set_callback_placement_charge(self._placement_charge_termine)

    #3. Construction de l'interface

    def _construire_ui(self):
        # Conteneur racine avec défilement vertical
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        layout.addWidget(self._header())
        layout.addWidget(self._card_simulation())
        layout.addWidget(self._card_nouveau_bloc())
        layout.addWidget(self._card_liste_blocs())
        layout.addWidget(self._card_charges())
        layout.addWidget(self._card_resultats())
        layout.addStretch(1)

        self.setStyleSheet(PANEL_QSS)

    def _header(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 0)
        lay.setSpacing(8)

        title = QLabel(
            "Tensor<span style='color:#1f94ff;'>Build</span>"
        )
        title.setProperty("role", "title")
        title.setTextFormat(Qt.TextFormat.RichText)
        sub = QLabel("Mode 2D")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px; letter-spacing:1px;")

        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.setSpacing(0)
        llay.addWidget(title)
        llay.addWidget(sub)

        self.btn_switch_3d = QPushButton("Passer en 3D")
        self.btn_switch_3d.setCursor(Qt.CursorShape.PointingHandCursor)

        lay.addWidget(left, stretch=1)
        lay.addWidget(self.btn_switch_3d, alignment=Qt.AlignmentFlag.AlignVCenter)
        return w

    def _card_simulation(self) -> QFrame:
        card, lay = _card("Simulation")

        row_g, self.chk_gravite = _row_toggle(
            "Gravité",
            "Les blocs tombent et s'empilent.",
        )
        self.chk_gravite.toggled.connect(self._toggle_gravite)
        lay.addWidget(row_g)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{BORDER};")
        lay.addWidget(sep)

        row_h, self.chk_carte_chaleur = _row_toggle(
            "Carte de pression",
            "Affiche la pression (Pa) sur chaque bloc.",
        )
        self.chk_carte_chaleur.toggled.connect(self._toggle_carte_chaleur)
        lay.addWidget(row_h)

        hint = QLabel("Cliquez sur une surface de contact pour les détails.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return card

    def _card_nouveau_bloc(self) -> QFrame:
        card, lay = _card("Ajouter un bloc")

        self.spin_largeur = QDoubleSpinBox()
        self.spin_largeur.setRange(0.1, 20)
        self.spin_largeur.setValue(2)
        self.spin_largeur.setSingleStep(0.25)
        self.spin_largeur.setSuffix(" m")

        self.spin_hauteur = QDoubleSpinBox()
        self.spin_hauteur.setRange(0.1, 20)
        self.spin_hauteur.setValue(1)
        self.spin_hauteur.setSingleStep(0.25)
        self.spin_hauteur.setSuffix(" m")

        self.combo_materiau = QComboBox()
        self.combo_materiau.setIconSize(QSize(20, 14))
        for nom, mat in MATERIAUX.items():
            self.combo_materiau.addItem(
                _icone_materiau(mat["face"], mat["edge"]), nom
            )
        self.combo_materiau.view().setSpacing(2)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self._field_label("Largeur"), self.spin_largeur)
        form.addRow(self._field_label("Hauteur"), self.spin_hauteur)
        form.addRow(self._field_label("Matériau"), self.combo_materiau)
        lay.addLayout(form)

        btn = QPushButton("Ajouter bloc")
        btn.setProperty("variant", "primary")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._ajouter_bloc)
        lay.addWidget(btn)
        return card

    def _card_liste_blocs(self) -> QFrame:
        card, lay = _card("Blocs présents")
        self.liste_blocs = QListWidget()
        self.liste_blocs.setMinimumHeight(160)
        self.liste_blocs.setMaximumHeight(320)
        self.liste_blocs.setSpacing(4)
        self.liste_blocs.setUniformItemSizes(False)
        self.liste_blocs.setFrameShape(QFrame.Shape.NoFrame)
        self.liste_blocs.currentRowChanged.connect(self._selectionner_bloc)
        lay.addWidget(self.liste_blocs)

        self.lbl_vide_liste = QLabel("Aucun bloc — ajoutez-en un ci-dessus.")
        self.lbl_vide_liste.setProperty("role", "muted")
        self.lbl_vide_liste.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_vide_liste)
        return card

    def _card_charges(self) -> QFrame:
        card, lay = _card("Charges")

        self.lbl_charges_cible = QLabel("Sélectionnez un bloc pour appliquer des charges.")
        self.lbl_charges_cible.setProperty("role", "muted")
        self.lbl_charges_cible.setWordWrap(True)
        lay.addWidget(self.lbl_charges_cible)

        self.spin_force = QDoubleSpinBox()
        self.spin_force.setRange(0, 1e7)
        self.spin_force.setSuffix(" N")
        self.spin_force.setSingleStep(10000)
        self.spin_force_x = QDoubleSpinBox()
        self.spin_force_x.setRange(-1e7, 1e7)
        self.spin_force_x.setSuffix(" N")
        self.spin_force_x.setSingleStep(10000)
        self.spin_pression = QDoubleSpinBox()
        self.spin_pression.setRange(0, 1e6)
        self.spin_pression.setSuffix(" Pa")
        self.spin_pression.setSingleStep(500)
        self.spin_force.valueChanged.connect(self._appliquer_charges)
        self.spin_force_x.valueChanged.connect(self._appliquer_charges)
        self.spin_pression.valueChanged.connect(self._appliquer_charges)

        self.btn_placer_fz = self._bouton_placement("F_z")
        self.btn_placer_fx = self._bouton_placement("F_x")

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(
            self._field_label("Force F_z"),
            self._champ_avec_placement(self.spin_force, self.btn_placer_fz),
        )
        form.addRow(
            self._field_label("Force F_x"),
            self._champ_avec_placement(self.spin_force_x, self.btn_placer_fx),
        )
        form.addRow(self._field_label("Pression"), self.spin_pression)
        self._charges_form = form
        lay.addLayout(form)

        self._set_charges_enabled(False)
        return card

    def _champ_avec_placement(
        self, spinbox: QDoubleSpinBox, bouton: QPushButton
    ) -> QWidget:
        """Combine un spinbox et un mini-bouton de placement par clic."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(spinbox, stretch=1)
        h.addWidget(bouton)
        return w

    def _bouton_placement(self, mode: str) -> QPushButton:
        btn = QPushButton("◎")
        btn.setCheckable(True)
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(
            f"Cliquer puis cliquer sur un bloc pour y placer {mode}"
        )
        btn.setStyleSheet(
            f"QPushButton {{ padding: 0; font-size: 14px; "
            f"background: {CARD}; color: {MUTED}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; font-weight: 700; }}"
            f"QPushButton:hover {{ border: 1px solid {ACCENT_HOV}; color: {ACCENT_HOV}; }}"
            f"QPushButton:checked {{ background: {ACCENT_DIM}; "
            f"border: 1px solid {ACCENT}; color: {TEXT_BRIGHT}; }}"
        )
        btn.clicked.connect(lambda _checked, m=mode: self._toggle_placement(m))
        return btn

    def _toggle_placement(self, mode: str):
        # Désactive l'autre bouton de placement pour éviter deux modes actifs
        other = self.btn_placer_fx if mode == "F_z" else self.btn_placer_fz
        if other.isChecked():
            other.setChecked(False)
        cible_btn = self.btn_placer_fz if mode == "F_z" else self.btn_placer_fx
        if cible_btn.isChecked():
            self.canvas.activer_mode_placement(mode)
        else:
            self.canvas.activer_mode_placement(None)

    def _placement_charge_termine(self, mode: str | None):
        """Appele par le canvas une fois la position appliquee."""
        self.btn_placer_fz.setChecked(False)
        self.btn_placer_fx.setChecked(False)

    def _card_resultats(self) -> QFrame:
        card, lay = _card("Résultats")

        self.lbl_cdgr = QLabel(
            f"<i style='color:{DIM}'>Ajoutez des blocs pour voir le centre de gravité.</i>"
        )
        self.lbl_cdgr.setWordWrap(True)
        self.lbl_cdgr.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_cdgr.setStyleSheet(
            f"background:{CARD}; color:{TEXT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:12px; font-size:11px;"
        )
        lay.addWidget(self.lbl_cdgr)

        self.lbl_rapport = QTextEdit()
        self.lbl_rapport.setReadOnly(True)
        self.lbl_rapport.setMinimumHeight(220)
        self.lbl_rapport.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_rapport.setHtml(
            f"<i style='color:{DIM}'>Le détail physique apparaîtra ici.</i>"
        )
        lay.addWidget(self.lbl_rapport)
        return card

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{MUTED}; font-size:10px; font-weight:700;"
            "letter-spacing:0.8px; text-transform:uppercase;"
        )
        return lbl

    def _set_charges_enabled(self, enabled: bool):
        for w in (
            self.spin_force, self.spin_force_x, self.spin_pression
        ):
            w.setEnabled(enabled)
        for b in (self.btn_placer_fz, self.btn_placer_fx):
            b.setEnabled(enabled)
            if not enabled and b.isChecked():
                b.setChecked(False)
                self.canvas.activer_mode_placement(None)
        self.lbl_charges_cible.setVisible(not enabled or self._bloc_selectionne is None)

    #4. Slots et logique métier

    def _toggle_gravite(self, active):
        self.canvas.activer_gravite(active)

    def _toggle_carte_chaleur(self, active):
        self.canvas.activer_carte_chaleur(active)
        self.callback_physique()

    def _ajouter_bloc(self):
        nom_mat = self.combo_materiau.currentText()
        mat = MATERIAUX[nom_mat]
        self.canvas.ajouter_bloc(
            self.spin_largeur.value(),
            self.spin_hauteur.value(),
            materiau=nom_mat,
            densite=mat["density"],
        )

    def _supprimer_a_index(self, index):
        if 0 <= index < len(self.canvas.blocs):
            self.canvas.supprimer_bloc(index)

    def _selectionner_bloc(self, ligne):
        self._bloc_selectionne = ligne
        # Changement de bloc sélectionné : quitte le mode placement par clic
        if self.btn_placer_fz.isChecked() or self.btn_placer_fx.isChecked():
            self.btn_placer_fz.setChecked(False)
            self.btn_placer_fx.setChecked(False)
            self.canvas.activer_mode_placement(None)
        if 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            spins = (self.spin_force, self.spin_force_x, self.spin_pression)
            for spin in spins:
                spin.blockSignals(True)
            self.spin_force.setValue(bloc["ext_force"])
            self.spin_force_x.setValue(bloc.get("ext_force_x", 0.0))
            self.spin_pression.setValue(bloc["pressure"])
            for spin in spins:
                spin.blockSignals(False)
            self._set_charges_enabled(True)
            self.lbl_charges_cible.setText(
                f"Bloc <b style='color:{ACCENT_HOV}'>{ligne + 1}</b> — "
                f"<span style='color:{TEXT_BRIGHT}'>{bloc['material']}</span>"
            )
            self.lbl_charges_cible.setVisible(True)
            self.lbl_charges_cible.setStyleSheet(
                f"color:{TEXT}; font-size:11px;"
            )
        else:
            self._set_charges_enabled(False)
            self.lbl_charges_cible.setText("Sélectionnez un bloc pour appliquer des charges.")
            self.lbl_charges_cible.setStyleSheet("")
            self.lbl_charges_cible.setProperty("role", "muted")
            self.lbl_charges_cible.style().unpolish(self.lbl_charges_cible)
            self.lbl_charges_cible.style().polish(self.lbl_charges_cible)

    def _appliquer_charges(self):
        ligne = self._bloc_selectionne
        if ligne is not None and 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            bloc["ext_force"] = self.spin_force.value()
            bloc["ext_force_x"] = self.spin_force_x.value()
            bloc["pressure"] = self.spin_pression.value()
            self.callback_physique(refresh_list=False)

    def rafraichir_liste(self):
        mem_ligne = self.liste_blocs.currentRow()
        self.liste_blocs.blockSignals(True)
        self.liste_blocs.clear()
        for i, bloc in enumerate(self.canvas.blocs):
            lw = float(bloc.get("largeur", bloc.get("w", 0.0)))
            libelle = (
                f"<b>Bloc {i + 1}</b>  ·  {bloc['material']}  ·  "
                f"{lw:.1f} × {bloc['h0']:.1f} m"
            )
            row = _ligne_liste_bloc(self, i, libelle)
            item = QListWidgetItem()
            hint = row.sizeHint()
            item.setSizeHint(QSize(hint.width(), max(46, hint.height())))
            self.liste_blocs.addItem(item)
            self.liste_blocs.setItemWidget(item, row)
        self.liste_blocs.blockSignals(False)

        empty = len(self.canvas.blocs) == 0
        self.lbl_vide_liste.setVisible(empty)
        self.liste_blocs.setVisible(not empty)

        if 0 <= mem_ligne < self.liste_blocs.count():
            self.liste_blocs.setCurrentRow(mem_ligne)
            self._bloc_selectionne = mem_ligne
        elif empty:
            self._bloc_selectionne = None
            self._set_charges_enabled(False)

    def afficher_cdgr(self, html):
        self.lbl_cdgr.setText(html)

    def afficher_rapport_detail(self, html):
        self.lbl_rapport.setHtml(html)

    #5. Infobulle de détail sur une surface de contact

    def _infobulle_contact_assuree(self):
        if self._infobulle_contact is None:
            self._infobulle_contact = ContactTooltip(self.canvas)
        return self._infobulle_contact

    def _html_infobulle_contact(self, d):
        ib, it = d["i_bot"], d["i_top"]
        frac, fc = d["frac"], d["F_c"]
        return (
            "<b style='color:#bf360c'>Surface de contact</b><br>"
            f"Bloc supérieur <b>{it + 1}</b> → bloc inférieur <b>{ib + 1}</b><br>"
            f"Effort transmis <b>Fc = {fc:.0f} N</b><br>"
            f"Recouvrement : <b>{frac * 100:.0f} %</b> "
        )

    def _placer_infobulle_contact(self, tip, centre_contact_global: QPoint):
        tip.adjustSize()
        gap_px = 6
        w, h = tip.width(), tip.height()
        x = centre_contact_global.x() - w // 2
        y = centre_contact_global.y() - h - gap_px
        tip.move(tip._clamp_top_left(QPoint(x, y)))

    def on_contact_pick(self, d):
        self._contact_sel = (d["i_bot"], d["i_top"])
        tip = self._infobulle_contact_assuree()

        def _open():
            tip.set_plot_bounds_global(self.canvas.rectangle_axes_global())
            tip.set_rich_text(self._html_infobulle_contact(d))
            pt = d.get("_press_global")
            if pt is None:
                pt = self.canvas.point_contact_global(d)
            self._placer_infobulle_contact(tip, pt)
            tip.setWindowOpacity(1.0)
            tip.show()
            tip.raise_()
            self.canvas.rafraichir_position_infobulle_contact(tip)
            c = tip.frameGeometry().center()
            if QGuiApplication.screenAt(c) is None:
                ps = QGuiApplication.primaryScreen()
                if ps is not None:
                    fr = tip.frameGeometry()
                    fr.moveCenter(ps.availableGeometry().center())
                    tip.move(fr.topLeft())
            QApplication.processEvents()

        QTimer.singleShot(10, _open)

    def _masquer_infobulle_contact(self):
        if self._infobulle_contact is not None:
            self._infobulle_contact.hide()
        self._contact_sel = None

    def rafraichir_infobulle_contact(self, paires, donnees_stress):
        tip = self._infobulle_contact
        if tip is None or not tip.isVisible() or self._contact_sel is None:
            return
        ib, it = self._contact_sel
        for p in paires:
            if p[0] == ib and p[1] == it:
                frac = p[2]
                sd = donnees_stress[it] if it < len(donnees_stress) else None
                if sd is None:
                    self._masquer_infobulle_contact()
                    return
                fc = sd["F_axial"]
                tip.set_rich_text(
                    self._html_infobulle_contact(
                        {"i_bot": ib, "i_top": it, "frac": frac, "F_c": fc}
                    )
                )
                tip.adjustSize()
                self.canvas.rafraichir_position_infobulle_contact(tip)
                return
        self._masquer_infobulle_contact()
