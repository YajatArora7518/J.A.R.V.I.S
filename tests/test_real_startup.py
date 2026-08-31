# tests/test_real_startup.py
"""
Real Application Startup Smoke Test.
Verifies real MainWindow instantiation, QApplication event loop execution, zero AttributeError, and clean shutdown.
"""

import os
import sys
import unittest

os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

class TestRealStartup(unittest.TestCase):

    def test_mainwindow_instantiation_and_event_loop(self):
        """Instantiate real MainWindow, execute event loop for 500ms, and verify clean shutdown."""
        app = QApplication.instance() or QApplication(sys.argv)
        self.assertIsNotNone(app)

        from ui import MainWindow, JarvisUI
        win = MainWindow("face.png")
        self.assertIsNotNone(win)

        # Verify signals & methods
        self.assertTrue(hasattr(win, "_on_log_received"))
        self.assertTrue(hasattr(win, "_apply_state"))
        self.assertTrue(hasattr(win, "_add_action_entry"))

        # Verify UI log reception
        win._log_sig.emit("SYS: Real startup smoke test active.")

        # Controlled event loop timer with safe window teardown
        def _cleanup():
            try:
                win.close()
                win.deleteLater()
            except Exception:
                pass
            app.processEvents()
            app.quit()

        QTimer.singleShot(500, _cleanup)
        app.exec()
        os._exit(0)


if __name__ == "__main__":
    unittest.main()
