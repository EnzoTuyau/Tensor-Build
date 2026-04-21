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
    btn.setFixedSize(22, 22)
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
    QFrame        { background: #f5f5f5; }
    QGroupBox     { color:#1565c0; border:1px solid #bbdefb; margin-top:8px;
                    padding-top:6px; border-radius:4px; font-weight:bold; }
    QGroupBox::title { subcontrol-origin:margin; left:8px; }
    QLabel        { color:#333; }

    QPushButton   { background:#1565c0; color:white; border:none;
                    border-radius:4px; padding:7px; font-weight:bold; }
    QPushButton:hover { background:#1976d2; }
    QListWidget   { background:white; color:#222; border:1px solid #bbdefb; }
    QComboBox     { background:white; color:#222; border:1px solid #90caf9;
                    border-radius:3px; padding:2px; }
    QTabWidget::pane { border:1px solid #bbdefb; background:white; }
    QTabBar::tab  { background:#e3f2fd; color:#555; padding:6px 14px; }
    QTabBar::tab:selected { background:white; color:#1565c0; font-weight:bold; }
    QScrollArea   { border:none; }
    QCheckBox     { color:#1565c0; spacing: 6px; }
    QCheckBox::indicator { width: 18px; height: 18px; }
    QCheckBox::indicator:unchecked {
        background: white;
        border: 2px solid #90caf9;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        background: #1565c0;
        border: 2px solid #1565c0;
        border-radius: 3px;
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

    def _construire_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        self.btn_switch_3d = QPushButton("🧊  Passer en mode 3D")
        self.btn_switch_3d.setStyleSheet(
            "background-color: #ef6c00; color: white; font-size: 12px; padding: 8px;"
        )
        layout.addWidget(self.btn_switch_3d)

        grp_gravite = QGroupBox("Simulation physique")
        lay_grav = QVBoxLayout(grp_gravite)

        self.chk_gravite = QCheckBox("🌍  Activer la gravité")
        self.chk_gravite.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.chk_gravite.toggled.connect(self._toggle_gravite)
        lay_grav.addWidget(self.chk_gravite)

        self.chk_carte_chaleur = QCheckBox("Carte de pression (Pa)")
        self.chk_carte_chaleur.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.chk_carte_chaleur.setToolTip(
            "Grille de couleurs sur chaque bloc selon la pression (pascals) ; decoratif."
        )
        self.chk_carte_chaleur.toggled.connect(self._toggle_carte_chaleur)
        lay_grav.addWidget(self.chk_carte_chaleur)

        info_gravite = QLabel(
            "Quand la gravité est activée : les nouveaux blocs\n"
            "tombent et s'empilent. Les blocs ne se traversent pas."
        )
        info_gravite.setStyleSheet("color: #555; font-size: 8px;")
        lay_grav.addWidget(info_gravite)

        grp_gravite.setLayout(lay_grav)
        layout.addWidget(grp_gravite)

        lbl_hint = QLabel(
            "<span style='color:#888;font-size:8px'>"
            "Cliquez sur une surface de contact pour afficher les détails.</span>"
        )
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

        onglets = QTabWidget()

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

        btn_ajouter = QPushButton("➕  Ajouter bloc")
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

        tab_charges = QWidget()
        lay_charges = QVBoxLayout(tab_charges)
        grp_charges = QGroupBox("Charges — bloc sélectionné")
        form_charges = QFormLayout()

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

        form_charges.addRow("Force ponctuelle:", self.spin_force)
        form_charges.addRow("Pression dist.:", self.spin_pression)
        form_charges.addRow("Moment fléch.:", self.spin_moment)
        grp_charges.setLayout(form_charges)
        lay_charges.addWidget(grp_charges)

        btn_appliquer = QPushButton("✅  Appliquer charges")
        btn_appliquer.clicked.connect(self._appliquer_charges)
        lay_charges.addWidget(btn_appliquer)
        lay_charges.addStretch()
        onglets.addTab(tab_charges, "Charges")

        tab_resultats = QWidget()
        lay_res = QVBoxLayout(tab_resultats)
        lay_res.setContentsMargins(4, 4, 4, 4)
        lay_res.setSpacing(8)

        grp_cdgr = QGroupBox("Centre de gravité")
        lay_cdgr = QVBoxLayout(grp_cdgr)
        self.lbl_cdgr = QLabel("<i style='color:#888'>Ajoutez des blocs pour afficher le CdG.</i>")
        self.lbl_cdgr.setWordWrap(True)
        self.lbl_cdgr.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_cdgr.setStyleSheet("font-family: Consolas; font-size: 9px; color: #222;")
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
            "<i style='color:#888'>Ajoutez des blocs pour afficher le détail.</i>"
        )
        self.lbl_rapport.setWordWrap(True)
        self.lbl_rapport.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_rapport.setStyleSheet("font-family: Consolas; font-size: 9px; color: #222;")
        scroll_r = QScrollArea()
        scroll_r.setWidget(self.lbl_rapport)
        scroll_r.setWidgetResizable(True)
        scroll_r.setMinimumHeight(200)
        lay_d.addWidget(scroll_r)
        grp_detail.setLayout(lay_d)
        lay_res.addWidget(grp_detail, stretch=1)

        onglets.addTab(tab_resultats, "Résultats")

        layout.addWidget(onglets)
        self.setStyleSheet(PANEL_QSS)

    def _toggle_gravite(self, active):
        self.canvas.activer_gravite(active)

    def _toggle_carte_chaleur(self, active):
        """Bascule l'affichage carte de pression et relance le calcul / dessin."""
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
            self.spin_force.setValue(bloc["ext_force"])
            self.spin_pression.setValue(bloc["pressure"])
            self.spin_moment.setValue(bloc["moment"])

    def _appliquer_charges(self):
        ligne = self._bloc_selectionne
        if ligne is not None and 0 <= ligne < len(self.canvas.blocs):
            bloc = self.canvas.blocs[ligne]
            bloc["ext_force"] = self.spin_force.value()
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
            patch = bloc["patch"]
            libelle = f"[{i+1}] {bloc['material']}  {patch.get_width():.1f}×{patch.get_height():.1f} m"
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

    def afficher_cdgr(self, html):
        self.lbl_cdgr.setText(html)

    def afficher_rapport_detail(self, html):
        self.lbl_rapport.setText(html)

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
