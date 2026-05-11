# SafeQtInteractor.py

import platform
import shiboken6
from pyvistaqt import QtInteractor
from PySide6.QtCore import QTimer


#1. Vérifie si le système utilisé est macOS
if platform.system() == "Darwin":

    #2. Classe personnalisée sécurisée pour QtInteractor
    class SafeQtInteractor(QtInteractor):

        # Variable utilisée pour éviter plusieurs rendus simultanés
        _render_deferred = False

        #3. Création du timer utilisé pour différer le rendu
        def _deferred_vtk_timer(self) -> QTimer:

            # Vérifie si le timer existe déjà
            t = getattr(self, "_deferred_vtk_qtimer", None)

            # Création du timer si inexistant
            if t is None:

                # QTimer enfant = annulé à la destruction du widget
                # contrairement à QTimer.singleShot(0) sans parent
                # qui peut rendre après teardown

                t = QTimer(self)

                # Le timer ne s’exécute qu’une seule fois
                t.setSingleShot(True)

                # Appelle la méthode de rendu différé à la fin du timer
                t.timeout.connect(self._deferred_render)

                # Sauvegarde du timer
                self._deferred_vtk_qtimer = t

            return t

        #4. Gestion de l’événement de dessin
        def paintEvent(self, ev):

            # Vérifie qu’un rendu n’est pas déjà prévu
            if not self._render_deferred:

                # Active l’état de rendu différé
                self._render_deferred = True

                # Lance le timer immédiatement
                self._deferred_vtk_timer().start(0)

        #5. Exécution du rendu différé
        def _deferred_render(self):

            # Réinitialise l’état du rendu
            self._render_deferred = False

            # Vérifie que l’objet Qt existe encore
            if not shiboken6.isValid(self):
                return

            try:

                # Effectue le rendu VTK
                self._Iren.Render()

            # Ignore les erreurs si le widget est détruit
            except RuntimeError:
                return


#6. Sur les autres systèmes, utilise QtInteractor normal
else:
    SafeQtInteractor = QtInteractor