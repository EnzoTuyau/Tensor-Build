"""Panneau de controle Qt du simulateur 2D."""

from __future__ import annotations

import functools

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from deuxDimensions.domain.constantes import MATERIAUX
from deuxDimensions.ui.contact_tooltip import ContactTooltip


def _ligne_liste_bloc(panneau, index: int, libelle: str) -> QWidget:
    """Une ligne de liste : libelle du bloc + bouton × pour supprimer."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(2, 2, 2, 2)
    lbl = QLabel(libelle)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    btn = QPushButton("×")
    btn.setObjectName("btnRemoveRow")
    btn.setFixedSize(26, 26)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setToolTip("Supprimer ce bloc")
    btn.clicked.connect(functools.partial(panneau._supprimer_a_index, index))
    h.addWidget(lbl, stretch=1)
    h.addWidget(btn)

    def _press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            panneau.liste_blocs.setCurrentRow(index)
        QWidget.mousePressEvent(w, event)

    w.mousePressEvent = _press
    return w


PANEL_QSS = """
/* Palette alignée sur menu.py TensorBuild (sombre, accents bleu / orange) */
QFrame {
    background-color: #050607;
    border: none;
}
QLabel {
    color: #dbe8ff;
    background: transparent;
}
QLabel#panelMutedHint {
    color: #7a8fb0;
    font-size: 11px;
}
QLabel#panelRichText {
    color: #c5d4eb;
    font-family: 'SF Mono', Menlo, Monaco, monospace;
    font-size: 10px;
    background-color: #0a1018;
    border-radius: 8px;
    padding: 8px;
    border: 1px solid #223753;
}
QGroupBox {
    color: #9ec8ff;
    border: 1px solid #223753;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 18px;
    padding-bottom: 10px;
    padding-left: 12px;
    padding-right: 12px;
    font-weight: bold;
    background-color: #06080c;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #eaf2ff;
}
QPushButton {
    background-color: #0d1624;
    color: #eaf2ff;
    border: 1px solid #3b4b62;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    border: 1px solid #2ea0ff;
    background-color: #131f31;
}
QPushButton:pressed {
    background-color: #0a1420;
}
QPushButton#panelLaunchBtn {
    background-color: #e67e22;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#panelLaunchBtn:hover {
    background-color: #f08f35;
    border: none;
}
QPushButton#panelLaunchBtn:pressed {
    background-color: #cf711f;
    border: none;
}
QPushButton#btnRemoveRow {
    background-color: #2a1518;
    color: #ff9aa2;
    border: 1px solid #5c2a32;
    border-radius: 8px;
    font-weight: bold;
    font-size: 15px;
    padding: 0px;
}
QPushButton#btnRemoveRow:hover {
    border: 1px solid #ff6b7a;
    background-color: #3d1f24;
}
QListWidget {
    background-color: #0a1018;
    color: #eaf2ff;
    border: 1px solid #2f4d72;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 2px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #131f31;
    border: 1px solid #1f94ff;
}
QListWidget::item:hover:!selected {
    background-color: #0f1723;
}
QComboBox,
QDoubleSpinBox {
    background-color: #0f1723;
    color: #eaf2ff;
    border: 1px solid #2f4d72;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
}
QComboBox:hover,
QDoubleSpinBox:hover {
    border: 1px solid #3d6a9e;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #0f1723;
    color: #eaf2ff;
    selection-background-color: #131f31;
    selection-color: #eaf2ff;
    border: 1px solid #2f4d72;
    outline: none;
}
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background-color: #131f31;
    border: none;
    width: 20px;
}
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {
    background-color: #1a2840;
}
QTabWidget::pane {
    border: 1px solid #223753;
    border-radius: 10px;
    background-color: #06080c;
    top: -1px;
    padding: 4px;
}
QTabBar::tab {
    background-color: #0a1018;
    color: #9eb4d9;
    padding: 9px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid #223753;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #06080c;
    color: #eaf2ff;
    font-weight: bold;
    border-bottom: 2px solid #1f94ff;
}
QTabBar::tab:hover:!selected {
    background-color: #131f31;
    color: #dbe8ff;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
QCheckBox {
    color: #dbe8ff;
    spacing: 10px;
    font-weight: 600;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid #3b4b62;
    background-color: #0f1723;
}
QCheckBox::indicator:checked {
    background-color: #1f94ff;
    border: 2px solid #1f94ff;
}
QCheckBox::indicator:hover {
    border: 2px solid #2ea0ff;
}
QListWidget QWidget {
    background-color: transparent;
}
"""


class PanneauControle(QFrame):
    """Panneau lateral : 3D, gravite, carte de pression, blocs, charges, resultats."""

    def __init__(self, canvas, callback_physique, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.callback_physique = callback_physique
        self._bloc_selectionne = None
        self._contact_sel = None
        self._infobulle_contact = None
        self._construire_ui()
        self.canvas.set_callback_bloc_pour_charges(self.selectionner_bloc_depuis_canvas)

    def _construire_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        self.btn_switch_3d = QPushButton("Passer en mode 3D")
        self.btn_switch_3d.setObjectName("panelLaunchBtn")
        self.btn_switch_3d.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_switch_3d)

        grp_gravite = QGroupBox("Simulation physique")
        lay_grav = QVBoxLayout(grp_gravite)

        self.chk_gravite = QCheckBox("Activer la gravité")
        self.chk_gravite.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_gravite.toggled.connect(self._toggle_gravite)
        lay_grav.addWidget(self.chk_gravite)

        self.chk_carte_chaleur = QCheckBox("Carte contrainte / charge (Pa)")
        self.chk_carte_chaleur.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_carte_chaleur.setToolTip(
            "Champ scalaire sur le bloc : contrainte normale estimée (flexion + axial) "
            "et rampe liée à la pression surfacique (max en tête). Échelle globale ; "
            "dégradé bilinéaire ; contour épousé sous cisaillement visuel."
        )
        self.chk_carte_chaleur.toggled.connect(self._toggle_carte_chaleur)
        lay_grav.addWidget(self.chk_carte_chaleur)

        self.chk_animer_rupture = QCheckBox("Animer la rupture (von Mises)")
        self.chk_animer_rupture.setChecked(True)
        self.chk_animer_rupture.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_animer_rupture.setToolTip(
            "Si un bloc dépasse le seuil d'utilisation : fissures et fondu avant suppression. "
            "Décochez pour une suppression immédiate."
        )
        self.chk_animer_rupture.toggled.connect(self._toggle_animer_rupture)
        lay_grav.addWidget(self.chk_animer_rupture)

        self.chk_reduce_motion = QCheckBox("Réduire les mouvements (accessibilité)")
        self.chk_reduce_motion.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_reduce_motion.setToolTip(
            "Pas d'animation de rupture : le bloc est retiré tout de suite si le seuil est franchi."
        )
        self.chk_reduce_motion.toggled.connect(self._toggle_reduce_motion)
        lay_grav.addWidget(self.chk_reduce_motion)

        info_gravite = QLabel(
            "Quand la gravité est activée : les nouveaux blocs\n"
            "tombent et s'empilent. Les blocs ne se traversent pas."
        )
        info_gravite.setObjectName("panelMutedHint")
        info_gravite.setWordWrap(True)
        lay_grav.addWidget(info_gravite)

        grp_gravite.setLayout(lay_grav)
        layout.addWidget(grp_gravite)

        lbl_hint = QLabel(
            "<span style='color:#7a8fb0;font-size:11px;line-height:1.35'>"
            "Cliquez sur une surface de contact pour afficher les détails.<br>"
            "Survolez un bloc sur le graphe pour voir charges et contraintes (infobulle)."
            "</span>"
        )
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

        onglets = QTabWidget()
        self._onglet_blocs(onglets)
        self._onglet_charges(onglets)
        self._onglet_resultats(onglets)

        layout.addWidget(onglets)
        self.setStyleSheet(PANEL_QSS)

    def _onglet_blocs(self, onglets: QTabWidget) -> None:
        tab_blocs = QWidget()
        lay_blocs = QVBoxLayout(tab_blocs)

        grp_nouveau = QGroupBox("Nouveau bloc")
        form_nouveau = QFormLayout()
        self.spin_largeur = QDoubleSpinBox()
        self.spin_largeur.setRange(0.1, 20)
        self.spin_largeur.setValue(2)
        self.spin_largeur.setSingleStep(0.25)
        self.spin_hauteur = QDoubleSpinBox()
        self.spin_hauteur.setRange(0.1, 20)
        self.spin_hauteur.setValue(1)
        self.spin_hauteur.setSingleStep(0.25)
        self.combo_materiau = QComboBox()
        for nom in MATERIAUX:
            self.combo_materiau.addItem(nom)
        form_nouveau.addRow("Largeur (m):", self.spin_largeur)
        form_nouveau.addRow("Hauteur (m):", self.spin_hauteur)
        form_nouveau.addRow("Matériau:", self.combo_materiau)
        grp_nouveau.setLayout(form_nouveau)
        lay_blocs.addWidget(grp_nouveau)

        btn_ajouter = QPushButton("Ajouter bloc")
        btn_ajouter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ajouter.clicked.connect(self._ajouter_bloc)
        lay_blocs.addWidget(btn_ajouter)

        grp_liste = QGroupBox("Blocs présents")
        lay_liste = QVBoxLayout(grp_liste)
        self.liste_blocs = QListWidget()
        self.liste_blocs.setMaximumHeight(180)
        self.liste_blocs.currentRowChanged.connect(self._selectionner_bloc)
        lay_liste.addWidget(self.liste_blocs)
        grp_liste.setLayout(lay_liste)
        lay_blocs.addWidget(grp_liste)
        lay_blocs.addStretch()
        onglets.addTab(tab_blocs, "Blocs")

    def _onglet_charges(self, onglets: QTabWidget) -> None:
        tab_charges = QWidget()
        lay_charges = QVBoxLayout(tab_charges)
        grp_charges = QGroupBox("Charges — bloc sélectionné")
        lay_grp_charges = QVBoxLayout(grp_charges)

        self.chk_selection_graphe = QCheckBox(
            "Cliquer sur le graphe pour choisir le bloc à charger"
        )
        self.chk_selection_graphe.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_selection_graphe.setToolTip(
            "Active : un clic sur un bloc dans la vue le sélectionne pour les charges "
            "(sans déplacer le bloc). Sinon : clic-glisser pour déplacer."
        )
        self.chk_selection_graphe.toggled.connect(self._toggle_selection_graphe)
        lay_grp_charges.addWidget(self.chk_selection_graphe)

        form_charges = QFormLayout()

        self.spin_force = QDoubleSpinBox()
        self.spin_force.setRange(0, 1e7)
        self.spin_force.setSuffix(" N")
        self.spin_force.setSingleStep(10000)
        self.spin_force_x = QDoubleSpinBox()
        self.spin_force_x.setRange(-1e7, 1e7)
        self.spin_force_x.setSuffix(" N")
        self.spin_force_x.setSingleStep(10000)
        self.spin_force_x.setToolTip(
            "Effort horizontal F_x sur le bloc (cisaillement global τ_moy = F_x / A)."
        )
        self.spin_pression = QDoubleSpinBox()
        self.spin_pression.setRange(0, 1e6)
        self.spin_pression.setSuffix(" Pa")
        self.spin_pression.setSingleStep(500)
        self.spin_moment = QDoubleSpinBox()
        self.spin_moment.setRange(-1e6, 1e6)
        self.spin_moment.setSuffix(" N·m")
        self.spin_moment.setSingleStep(100)
        self.spin_force.valueChanged.connect(self._appliquer_charges)
        self.spin_force_x.valueChanged.connect(self._appliquer_charges)
        self.spin_pression.valueChanged.connect(self._appliquer_charges)
        self.spin_moment.valueChanged.connect(self._appliquer_charges)

        form_charges.addRow("Force ponctuelle (vertical):", self.spin_force)
        form_charges.addRow("Effort horizontal F_x:", self.spin_force_x)
        form_charges.addRow("Pression dist.:", self.spin_pression)
        form_charges.addRow("Moment fléch.:", self.spin_moment)
        lay_grp_charges.addLayout(form_charges)
        grp_charges.setLayout(lay_grp_charges)
        lay_charges.addWidget(grp_charges)

        btn_appliquer = QPushButton("Appliquer les charges")
        btn_appliquer.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_appliquer.clicked.connect(self._appliquer_charges)
        lay_charges.addWidget(btn_appliquer)
        lay_charges.addStretch()
        onglets.addTab(tab_charges, "Charges")

    def _onglet_resultats(self, onglets: QTabWidget) -> None:
        tab_resultats = QWidget()
        lay_res = QVBoxLayout(tab_resultats)
        lay_res.setContentsMargins(4, 4, 4, 4)
        lay_res.setSpacing(8)

        grp_cdgr = QGroupBox("Centre de gravité")
        lay_cdgr = QVBoxLayout(grp_cdgr)
        self.lbl_cdgr = QLabel(
            "<i style='color:#6b7c95'>Ajoutez des blocs pour afficher le CdG.</i>"
        )
        self.lbl_cdgr.setObjectName("panelRichText")
        self.lbl_cdgr.setWordWrap(True)
        self.lbl_cdgr.setTextFormat(Qt.TextFormat.RichText)
        scroll_cdgr = QScrollArea()
        scroll_cdgr.setWidget(self.lbl_cdgr)
        scroll_cdgr.setWidgetResizable(True)
        scroll_cdgr.setMaximumHeight(140)
        lay_cdgr.addWidget(scroll_cdgr)
        grp_cdgr.setLayout(lay_cdgr)
        lay_res.addWidget(grp_cdgr)

        grp_detail = QGroupBox("Détail physique & contacts")
        lay_d = QVBoxLayout(grp_detail)
        self.lbl_rapport = QLabel(
            "<i style='color:#6b7c95'>Ajoutez des blocs pour afficher le détail.</i>"
        )
        self.lbl_rapport.setObjectName("panelRichText")
        self.lbl_rapport.setWordWrap(True)
        self.lbl_rapport.setTextFormat(Qt.TextFormat.RichText)
        scroll_r = QScrollArea()
        scroll_r.setWidget(self.lbl_rapport)
        scroll_r.setWidgetResizable(True)
        scroll_r.setMinimumHeight(200)
        lay_d.addWidget(scroll_r)
        grp_detail.setLayout(lay_d)
        lay_res.addWidget(grp_detail, stretch=1)

        onglets.addTab(tab_resultats, "Résultats")

    def _toggle_gravite(self, active):
        self.canvas.activer_gravite(active)
        self.callback_physique()

    def _toggle_selection_graphe(self, active):
        self.canvas.selection_charges_au_clic = bool(active)

    def selectionner_bloc_depuis_canvas(self, index: int):
        """Appelé par le canvas : sélectionne le bloc pour l’onglet Charges."""
        if not (0 <= index < len(self.canvas.blocs)):
            return
        self.liste_blocs.setCurrentRow(index)

    def _toggle_carte_chaleur(self, active):
        """Bascule l'affichage carte de pression et relance le calcul / dessin."""
        self.canvas.activer_carte_chaleur(active)
        self.callback_physique()

    def _toggle_animer_rupture(self, active):
        self.canvas.activer_animer_rupture(bool(active))

    def _toggle_reduce_motion(self, active):
        self.canvas.activer_reduce_motion(bool(active))

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
        self.canvas.definir_surlignage_bloc(ligne if ligne >= 0 else None)
        if 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            for spin in (self.spin_force, self.spin_force_x, self.spin_pression, self.spin_moment):
                spin.blockSignals(True)
            try:
                self.spin_force.setValue(bloc["ext_force"])
                self.spin_force_x.setValue(bloc.get("ext_force_x", 0.0))
                self.spin_pression.setValue(bloc["pressure"])
                self.spin_moment.setValue(bloc["moment"])
            finally:
                for spin in (self.spin_force, self.spin_force_x, self.spin_pression, self.spin_moment):
                    spin.blockSignals(False)

    def _appliquer_charges(self):
        ligne = self._bloc_selectionne
        if ligne is not None and 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            bloc["ext_force"] = self.spin_force.value()
            bloc["ext_force_x"] = self.spin_force_x.value()
            bloc["pressure"] = self.spin_pression.value()
            bloc["moment"] = self.spin_moment.value()
            self.callback_physique(refresh_list=False)


    def rafraichir_liste(self):
        # 1. On mémorise la sélection actuelle
        mem_ligne = self.liste_blocs.currentRow()
        
        # 2. On empêche la liste d'envoyer le signal de désélection pendant qu'on la vide
        self.liste_blocs.blockSignals(True)
        
        self.liste_blocs.clear()
        for i, bloc in enumerate(self.canvas.blocs):
            libelle = f"[{i+1}] {bloc['material']}  {bloc['largeur']:.1f}×{bloc['h0']:.1f} m"
            row = _ligne_liste_bloc(self, i, libelle)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.liste_blocs.addItem(item)
            self.liste_blocs.setItemWidget(item, row)
            
        # 3. On réactive les signaux
        self.liste_blocs.blockSignals(False)
        
        # 4. On restaure la sélection
        if 0 <= mem_ligne < self.liste_blocs.count():
            self.liste_blocs.setCurrentRow(mem_ligne)
            self._bloc_selectionne = mem_ligne
        else:
            self._bloc_selectionne = None
            self.canvas.definir_surlignage_bloc(None)

    def afficher_rapport_detail(self, html):
        self.lbl_rapport.setText(html)

    def afficher_cdgr(self, html):
        self.lbl_cdgr.setText(html)

    def _infobulle_contact_assuree(self):
        """Cree l'infobulle au premier besoin (parent = canvas)."""
        if self._infobulle_contact is None:
            self._infobulle_contact = ContactTooltip(self.canvas)
        return self._infobulle_contact

    def _html_infobulle_contact(self, d):
        """HTML pour i_bot, i_top, frac, F_c."""
        ib, it = d["i_bot"], d["i_top"]
        frac, fc = d["frac"], d["F_c"]
        return (
            "<b style='color:#bf360c'>Surface de contact</b><br>"
            f"Bloc supérieur <b>{it + 1}</b> → bloc inférieur <b>{ib + 1}</b><br>"
            f"Effort transmis <b>Fc = {fc:.0f} N</b><br>"
            f"Recouvrement : <b>{frac * 100:.0f} %</b> "
        )

    def _placer_infobulle_contact(self, tip, centre_contact_global: QPoint):
        """Centre horizontalement au-dessus du point de contact."""
        tip.adjustSize()
        gap_px = 6
        w, h = tip.width(), tip.height()
        x = centre_contact_global.x() - w // 2
        y = centre_contact_global.y() - h - gap_px
        tip.move(tip._clamp_top_left(QPoint(x, y)))

    def on_contact_pick(self, d):
        """Appelé par le canvas : affiche l'infobulle pour le contact d."""
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
        """Met a jour le texte si la geometrie a change ; sinon masque."""
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
                tip.set_rich_text(self._html_infobulle_contact({"i_bot": ib, "i_top": it, "frac": frac, "F_c": fc}))
                tip.adjustSize()
                self.canvas.rafraichir_position_infobulle_contact(tip)
                return
        self._masquer_infobulle_contact()
