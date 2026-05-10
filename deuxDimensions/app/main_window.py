"""Fenetre principale et orchestration du mode 2D."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from deuxDimensions.physics.calculs import calculer_donnees_physiques
from deuxDimensions.rendering.canvas2d import Canvas2D
from deuxDimensions.ui.panneau_controle import PanneauControle


class MaterialSimulationApp(QMainWindow):
    """
    Fenetre principale de la simulation 2D.
    Assemble le canvas et le panneau de controle,
    et orchestre les calculs physiques (physique → ruptures / latch → dessin).
    """

    def __init__(self, mode="2D", switch_callback=None):
        super().__init__()
        self.setWindowTitle("Tensor Build — Simulateur de Résistance des Matériaux")
        self.resize(1400, 900)

        self._bandeau_rupture = QFrame()
        self._bandeau_rupture.setObjectName("ruptureBanner")
        self._bandeau_rupture.setVisible(False)
        self._bandeau_rupture.setStyleSheet(
            """
            #ruptureBanner {
                background-color: #6a1b1b;
                border-bottom: 2px solid #c62828;
            }
            """
        )
        lay_band = QHBoxLayout(self._bandeau_rupture)
        lay_band.setContentsMargins(14, 10, 14, 10)
        self._label_bandeau_rupture = QLabel("")
        self._label_bandeau_rupture.setWordWrap(True)
        self._label_bandeau_rupture.setStyleSheet(
            "color: #ffebee; font-weight: 600; font-size: 13px;"
        )
        lay_band.addWidget(self._label_bandeau_rupture)
        self._timer_bandeau_rupture = QTimer(self)
        self._timer_bandeau_rupture.setSingleShot(True)
        self._timer_bandeau_rupture.timeout.connect(self._masquer_bandeau_rupture)

        central = QWidget()
        layout_vert = QVBoxLayout(central)
        layout_vert.setContentsMargins(0, 0, 0, 0)
        layout_vert.setSpacing(0)
        layout_vert.addWidget(self._bandeau_rupture)

        zone_principale = QWidget()
        mise_en_page = QHBoxLayout(zone_principale)
        mise_en_page.setContentsMargins(0, 0, 0, 0)
        mise_en_page.setSpacing(0)
        layout_vert.addWidget(zone_principale, stretch=1)

        self.setCentralWidget(central)

        self.canvas = Canvas2D(
            zone_principale,
            on_blocs_changes=self._on_changed,
            on_rupture_message=self._message_rupture_bloc,
        )
        mise_en_page.addWidget(self.canvas, stretch=1)

        self.panneau = PanneauControle(self.canvas, self._on_changed)
        self.canvas.set_callback_contact_clic(self.panneau.on_contact_pick)

        if switch_callback:
            self.panneau.btn_switch_3d.clicked.connect(switch_callback)

        dock = QDockWidget("Contrôles", self)
        dock.setWidget(self.panneau)
        dock.setMinimumWidth(320)
        dock.setStyleSheet(
            """
            QDockWidget {
                background-color: #050607;
                color: #eaf2ff;
            }
            QDockWidget::title {
                background-color: #06080c;
                padding: 10px 14px;
                border-bottom: 1px solid #223753;
                font-weight: bold;
                color: #9ec8ff;
            }
            """
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _masquer_bandeau_rupture(self):
        self._bandeau_rupture.setVisible(False)

    def _message_rupture_bloc(self, message: str):
        self._label_bandeau_rupture.setText(message)
        self._bandeau_rupture.setVisible(True)
        self._timer_bandeau_rupture.start(9000)
        self.statusBar().showMessage(message, 6500)

    def _on_changed(self, *, refresh_list=True):
        """Recalcule la physique et redessine ; met a jour la liste si demande."""
        if refresh_list:
            self.panneau.rafraichir_liste()
        donnees_stress, paires = self._calculer_physique()
        self.canvas.verifier_ruptures_apres_physique(donnees_stress)
        self.canvas.dessiner_contraintes(donnees_stress, paires)
        self.panneau.rafraichir_infobulle_contact(paires, donnees_stress)

    def _calculer_physique(self):
        """
        Calcule et met a jour les zones de resultats HTML du panneau.
        Retourne les donnees de stress et les paires de contact.
        """
        resultats = calculer_donnees_physiques(
            self.canvas.blocs, gravite_active=self.canvas.gravite_active
        )
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

