"""Fenetre principale et orchestration du mode 2D."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QHBoxLayout, QMainWindow, QWidget

from deuxDimensions.physics.calculs import calculer_donnees_physiques
from deuxDimensions.rendering.canvas2d import Canvas2D
from deuxDimensions.ui.panneau_controle import PanneauControle


class MaterialSimulationApp(QMainWindow):
    """
    Fenetre principale de la simulation 2D.
    Assemble le canvas et le panneau de controle,
    et orchestre les calculs physiques.
    """

    def __init__(self, mode="2D", switch_callback=None):
        super().__init__()
        self.setWindowTitle("Tensor Build — Simulateur de Résistance des Matériaux")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        mise_en_page = QHBoxLayout(central)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)

        self.canvas = Canvas2D(central, on_blocs_changes=self._on_changed)
        mise_en_page.addWidget(self.canvas, stretch=1)

        self.panneau = PanneauControle(self.canvas, self._on_changed)
        self.canvas.set_callback_contact_clic(self.panneau.on_contact_pick)

        if switch_callback:
            self.panneau.btn_switch_3d.clicked.connect(switch_callback)

        dock = QDockWidget("Contrôles", self)
        dock.setWidget(self.panneau)
        dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _on_changed(self, *, refresh_list=True):
        """Recalcule la physique et redessine ; met a jour la liste si demande."""
        if refresh_list:
            self.panneau.rafraichir_liste()
        donnees_stress, paires = self._calculer_physique()
        self.canvas.dessiner_contraintes(donnees_stress, paires)
        self.panneau.rafraichir_infobulle_contact(paires, donnees_stress)

    def _calculer_physique(self):
        """
        Calcule et met a jour les zones de resultats HTML du panneau.
        Retourne les donnees de stress et les paires de contact.
        """
        resultats = calculer_donnees_physiques(self.canvas.blocs)
        self.panneau.afficher_rapport_detail(resultats["html_rapport"])
        self.panneau.afficher_cdgr(resultats["html_cdgr"])
        if not self.canvas.blocs:
            self.panneau._masquer_infobulle_contact()
        return resultats["donnees_stress"], resultats["paires"]


def lancer_application():
    """Point d'entree d'execution locale de la fenetre 2D."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    fenetre = MaterialSimulationApp()
    fenetre.show()
    return sys.exit(app.exec())

