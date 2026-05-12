"""Fenêtre 2D : canvas + dock + toasts ; boucle physique → rupture → dessin."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QMainWindow,
    QWidget,
)

from deuxDimensions.physics.calculs import calculer_donnees_physiques
from deuxDimensions.rendering.canvas2d import Canvas2D
from deuxDimensions.ui.panneau_controle import PanneauControle
from deuxDimensions.ui.toast_notifications import ToastStack


class MaterialSimulationApp(QMainWindow):
    """Simulateur RDM 2D — assemble graphe, panneau et notifications."""

    def __init__(self, mode="2D", switch_callback=None):
        super().__init__()
        self.setWindowTitle("Tensor Build — Simulateur de Résistance des Matériaux")
        self.resize(1400, 900)

        central = QWidget()
        mise_en_page = QHBoxLayout(central)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)
        self.setCentralWidget(central)

        self.canvas = Canvas2D(
            central,
            on_blocs_changes=self._on_changed,
            on_rupture=self._signaler_rupture,
        )
        mise_en_page.addWidget(self.canvas, stretch=1)

        self.panneau = PanneauControle(self.canvas, self._on_changed)
        self.canvas.set_callback_contact_clic(self.panneau.on_contact_pick)

        if switch_callback:
            self.panneau.btn_switch_3d.clicked.connect(switch_callback)

        dock = QDockWidget("CONTRÔLES", self)
        dock.setWidget(self.panneau)
        dock.setMinimumWidth(340)
        dock.setStyleSheet(
            """
            QDockWidget {
                background-color: #050607;
                color: #9eb4d9;
            }
            QDockWidget::title {
                background-color: #06080c;
                padding: 10px 14px;
                border-bottom: 1px solid #3b4b62;
                font-weight: 700;
                color: #9eb4d9;
                letter-spacing: 1.4px;
            }
            """
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._dock_controles = dock
        self.setStyleSheet(
            "QMainWindow { background: #050607; }"
            "QStatusBar { background: #06080c; color: #9eb4d9; border-top: 1px solid #3b4b62; }"
        )

        self._toasts = ToastStack(self, dock_a_eviter=self._dock_controles)

    def _signaler_rupture(self, numero: int, materiau: str, util_pct: float):
        """Toast + barre d’état quand le canvas signale une rupture."""
        titre = f"Bloc {numero} brisé"
        sous = (
            f"{materiau} — contrainte au-delà du seuil "
            f"({util_pct:.0f}% de σ_y)"
        )
        self._toasts.push(titre, sous)
        self.statusBar().showMessage(f"{titre} · {sous}", 6500)

    def _on_changed(self, *, refresh_list=True):
        """Recalcule physique, ruptures, dessin ; option liste panneau."""
        if refresh_list:
            self.panneau.rafraichir_liste()
        donnees_stress, paires = self._calculer_physique()
        self.canvas.verifier_ruptures_apres_physique(donnees_stress)
        self.canvas.dessiner_contraintes(donnees_stress, paires)
        self.panneau.rafraichir_infobulle_contact(paires, donnees_stress)

    def _calculer_physique(self):
        """HTML panneau + retour (stress, paires) pour le canvas."""
        resultats = calculer_donnees_physiques(
            self.canvas.blocs, gravite_active=self.canvas.gravite_active
        )
        self.panneau.afficher_rapport_detail(resultats["html_rapport"])
        self.panneau.afficher_cdgr(resultats["html_cdgr"])
        if not self.canvas.blocs:
            self.panneau._masquer_infobulle_contact()
        return resultats["donnees_stress"], resultats["paires"]


def lancer_application():
    """Lance Qt Fusion + fenêtre principale."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    fenetre = MaterialSimulationApp()
    fenetre.show()
    return sys.exit(app.exec())
