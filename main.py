# crittr/app.py
from __future__ import annotations
import sys
from crittr.qt import QtWidgets, QtGui, QtCore
from app_config import ensure_app_dirs, apply_qsettings_org, banner
from crittr.core.logging import setup_logging
from crittr.ui.main_window import MainWindow
from crittr.ui.theme import apply_fusion_theme
import logging


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
