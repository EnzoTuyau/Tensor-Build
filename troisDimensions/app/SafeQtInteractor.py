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
            self._Iren.Render()
            self._render_deferred = False
else:
    SafeQtInteractor = QtInteractor