# crittr/app.py
from __future__ import annotations
import sys
from crittr.qt import QtWidgets, QtGui, QtCore
from app_config import ensure_app_dirs, apply_qsettings_org, banner
from crittr.core.logging import setup_logging
from crittr.ui.main_window import MainWindow
from crittr.ui.theme import apply_fusion_theme
import logging


def _apply_dark_fusion(app: QtWidgets.QApplication) -> None:
    # Use Fusion for consistent cross-platform styling
    app.setStyle("Fusion")

    # Build a dark palette
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(37, 37, 38))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText, QtCore.Qt.GlobalColor.white)
    pal.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(30, 30, 30))
    pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(45, 45, 48))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtCore.Qt.GlobalColor.white)
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtCore.Qt.GlobalColor.white)
    pal.setColor(QtGui.QPalette.ColorRole.Text, QtCore.Qt.GlobalColor.white)
    pal.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(45, 45, 48))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QtCore.Qt.GlobalColor.white)
    pal.setColor(QtGui.QPalette.ColorRole.BrightText, QtCore.Qt.GlobalColor.red)
    pal.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(56, 117, 215))
    pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.white)

    # Disabled state tweaks
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor(127, 127, 127))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(127, 127, 127))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(127, 127, 127))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(70, 70, 70))
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(180, 180, 180))

    app.setPalette(pal)

    # Small stylesheet for tooltips and splitter grips, etc.
    app.setStyleSheet("""
        QToolTip {
            color: #ffffff;
            background-color: #2d2d2e;
            border: 1px solid #3a3a3b;
        }
        QSplitter::handle {
            background-color: #3a3a3b;
        }
        QMenuBar, QMenu {
            background-color: #2d2d2e;
            color: #ffffff;
        }
        QMenu::item:selected {
            background-color: #3875d7;
        }
        QScrollBar:vertical, QScrollBar:horizontal {
            background: #2d2d2e;
        }
    """)

def main() -> int:
    ensure_app_dirs()
    apply_qsettings_org()
    logger = setup_logging(level=logging.DEBUG)


    app = QtWidgets.QApplication(sys.argv)
    logger.info(banner())

    # Apply dark Fusion theme
    #_apply_dark_fusion(app)
    apply_fusion_theme(app)
    mw = MainWindow()
    mw.show()

    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
