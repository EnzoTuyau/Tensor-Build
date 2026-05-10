"""Panneau de controle Qt du simulateur 2D (design moderne)."""

from __future__ import annotations

import functools

from PySide6.QtCore import QPoint, QSize, QTimer, Qt
from PySide6.QtGui import QGuiApplication
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


# ─── Palette ────────────────────────────────────────────────────
BG          = "#f7f8fa"
CARD        = "#ffffff"
BORDER      = "#e6e8ee"
TEXT        = "#1f2937"
MUTED       = "#6b7280"
ACCENT      = "#2563eb"
ACCENT_HOV  = "#1d4ed8"
ACCENT_SOFT = "#eff4ff"
DANGER      = "#dc2626"
SUCCESS     = "#16a34a"
WARNING     = "#d97706"


PANEL_QSS = f"""
QFrame#panel {{
    background: {BG};
}}

QLabel {{
    color: {TEXT};
    font-size: 12px;
}}
QLabel[role="title"] {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}
QLabel[role="section"] {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.2px;
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

QPushButton {{
    background: {ACCENT};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton:hover    {{ background: {ACCENT_HOV}; }}
QPushButton:pressed  {{ background: {ACCENT_HOV}; }}
QPushButton:disabled {{ background: #d1d5db; color: #f3f4f6; }}

QPushButton[variant="ghost"] {{
    background: transparent;
    color: {ACCENT};
    border: 1px solid {BORDER};
}}
QPushButton[variant="ghost"]:hover {{
    background: {ACCENT_SOFT};
    border-color: {ACCENT};
}}

QPushButton[variant="danger-icon"] {{
    background: transparent;
    color: {MUTED};
    border: none;
    border-radius: 6px;
    padding: 0;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton[variant="danger-icon"]:hover {{
    background: #fee2e2;
    color: {DANGER};
}}

QPushButton[variant="mode"] {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 9px 12px;
    text-align: left;
}}
QPushButton[variant="mode"]:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}

QDoubleSpinBox, QComboBox {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 5px 8px;
    min-height: 22px;
    font-size: 12px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: #f3f4f6;
    color: #9ca3af;
}}
QComboBox::drop-down {{ width: 18px; border: none; }}

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
    margin: 3px 0;
    padding: 2px;
}}
QListWidget::item:selected {{
    background: {ACCENT_SOFT};
    border: 1px solid {ACCENT};
    color: {TEXT};
}}

/* Toggle-style checkbox */
QCheckBox {{
    color: {TEXT};
    font-size: 12px;
    spacing: 10px;
    padding: 2px 0;
}}
QCheckBox::indicator {{
    width: 34px;
    height: 20px;
    border-radius: 10px;
    background: #d1d5db;
    border: none;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #cfd4dc; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #9aa1ac; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QTextEdit {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    font-size: 11px;
}}
"""


# ─── Toggle moderne (QCheckBox stylé sans cocher carré) ─────────
from PySide6.QtCore import QPropertyAnimation, Property
from PySide6.QtGui import QColor, QPainter
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
        bg = QColor(ACCENT) if self.isChecked() else QColor("#d1d5db")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(self.rect(), 11, 11)
        p.setBrush(QColor("white"))
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
    title.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:600;")
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


def _ligne_liste_bloc(panneau, index: int, libelle: str) -> QWidget:
    """Carte d'un bloc : libelle + bouton supprimer discret."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(10, 6, 6, 6)
    h.setSpacing(6)
    lbl = QLabel(libelle)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    lbl.setStyleSheet(f"color:{TEXT}; font-size:12px; font-weight:500;")
    btn = QPushButton("×")
    btn.setProperty("variant", "danger-icon")
    btn.setFixedSize(24, 24)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip("Supprimer ce bloc")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(functools.partial(panneau._supprimer_a_index, index))
    h.addWidget(lbl, stretch=1)
    h.addWidget(btn)

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

    # ── Construction UI ─────────────────────────────────────────

    def _construire_ui(self):
        # Conteneur scrollable global
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

        title = QLabel("Tensor Build")
        title.setProperty("role", "title")
        sub = QLabel("Mode 2D")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px;")

        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.setSpacing(0)
        llay.addWidget(title)
        llay.addWidget(sub)

        self.btn_switch_3d = QPushButton("Passer en 3D")
        self.btn_switch_3d.setProperty("variant", "ghost")
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
        for nom in MATERIAUX:
            self.combo_materiau.addItem(nom)

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
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._ajouter_bloc)
        lay.addWidget(btn)
        return card

    def _card_liste_blocs(self) -> QFrame:
        card, lay = _card("Blocs présents")
        self.liste_blocs = QListWidget()
        self.liste_blocs.setMinimumHeight(110)
        self.liste_blocs.setMaximumHeight(220)
        self.liste_blocs.setSpacing(0)
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
        self.spin_pression = QDoubleSpinBox()
        self.spin_pression.setRange(0, 1e6)
        self.spin_pression.setSuffix(" Pa")
        self.spin_pression.setSingleStep(500)
        self.spin_moment = QDoubleSpinBox()
        self.spin_moment.setRange(-1e6, 1e6)
        self.spin_moment.setSuffix(" N·m")
        self.spin_moment.setSingleStep(100)
        self.spin_force.valueChanged.connect(self._appliquer_charges)
        self.spin_pression.valueChanged.connect(self._appliquer_charges)
        self.spin_moment.valueChanged.connect(self._appliquer_charges)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(self._field_label("Force"), self.spin_force)
        form.addRow(self._field_label("Pression"), self.spin_pression)
        form.addRow(self._field_label("Moment"), self.spin_moment)
        self._charges_form = form
        lay.addLayout(form)

        self._set_charges_enabled(False)
        return card

    def _card_resultats(self) -> QFrame:
        card, lay = _card("Résultats")

        self.lbl_cdgr = QLabel("<i style='color:#9ca3af'>Ajoutez des blocs pour voir le centre de gravité.</i>")
        self.lbl_cdgr.setWordWrap(True)
        self.lbl_cdgr.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_cdgr.setStyleSheet(
            f"background:{ACCENT_SOFT}; color:{TEXT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:10px; font-size:11px;"
        )
        lay.addWidget(self.lbl_cdgr)

        self.lbl_rapport = QTextEdit()
        self.lbl_rapport.setReadOnly(True)
        self.lbl_rapport.setMinimumHeight(220)
        self.lbl_rapport.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_rapport.setHtml(
            "<i style='color:#9ca3af'>Le détail physique apparaîtra ici.</i>"
        )
        lay.addWidget(self.lbl_rapport)
        return card

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:600;")
        return lbl

    def _set_charges_enabled(self, enabled: bool):
        for w in (self.spin_force, self.spin_pression, self.spin_moment):
            w.setEnabled(enabled)
        self.lbl_charges_cible.setVisible(not enabled or self._bloc_selectionne is None)

    # ── Slots / logique ─────────────────────────────────────────

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
        if 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            for spin in (self.spin_force, self.spin_pression, self.spin_moment):
                spin.blockSignals(True)
            self.spin_force.setValue(bloc["ext_force"])
            self.spin_pression.setValue(bloc["pressure"])
            self.spin_moment.setValue(bloc["moment"])
            for spin in (self.spin_force, self.spin_pression, self.spin_moment):
                spin.blockSignals(False)
            self._set_charges_enabled(True)
            self.lbl_charges_cible.setText(
                f"Bloc <b>{ligne + 1}</b> — {bloc['material']}"
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
            bloc["pressure"] = self.spin_pression.value()
            bloc["moment"] = self.spin_moment.value()
            self.callback_physique(refresh_list=False)

    def rafraichir_liste(self):
        mem_ligne = self.liste_blocs.currentRow()
        self.liste_blocs.blockSignals(True)
        self.liste_blocs.clear()
        for i, bloc in enumerate(self.canvas.blocs):
            patch = bloc["patch"]
            libelle = (
                f"<b>Bloc {i + 1}</b>  ·  {bloc['material']}  ·  "
                f"{patch.get_width():.1f} × {patch.get_height():.1f} m"
            )
            row = _ligne_liste_bloc(self, i, libelle)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
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

    # ── Infobulle de contact (inchangé) ─────────────────────────

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
