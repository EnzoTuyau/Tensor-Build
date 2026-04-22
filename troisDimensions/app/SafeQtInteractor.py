# SafeQtInteractor.py
import platform
import shiboken6
from pyvistaqt import QtInteractor
from PySide6.QtCore import QTimer

if platform.system() == "Darwin":
    class SafeQtInteractor(QtInteractor):
        _render_deferred = False

        def _deferred_vtk_timer(self) -> QTimer:
            t = getattr(self, "_deferred_vtk_qtimer", None)
            if t is None:
                # QTimer enfant = annulé à la destruction du widget (contrairement à
                # QTimer.singleShot(0) sans parent, qui peut rendre après teardown).
                t = QTimer(self)
                t.setSingleShot(True)
                t.timeout.connect(self._deferred_render)
                self._deferred_vtk_qtimer = t
            return t

        def paintEvent(self, ev):
            if not self._render_deferred:
                self._render_deferred = True
                self._deferred_vtk_timer().start(0)

        def _deferred_render(self):
            self._render_deferred = False
            if not shiboken6.isValid(self):
                return
            try:
                self._Iren.Render()
            except RuntimeError:
                return
else:
    SafeQtInteractor = QtInteractor
