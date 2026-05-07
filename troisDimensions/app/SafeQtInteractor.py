# SafeQtInteractor.py
import platform
from pyvistaqt import QtInteractor
from PySide6.QtCore import QTimer

if platform.system() == "Darwin":
    class SafeQtInteractor(QtInteractor):
        _render_deferred = False

        def paintEvent(self, ev):
            if not self._render_deferred:
                self._render_deferred = True
                QTimer.singleShot(0, self._deferred_render)

        def _deferred_render(self):
            # Évite Render() sur un interactor déjà détruit (fermeture / switch de mode).
            try:
                if self.isVisible() and getattr(self, "_Iren", None) is not None:
                    self._Iren.Render()
            except Exception:
                pass
            finally:
                self._render_deferred = False
else:
    SafeQtInteractor = QtInteractor