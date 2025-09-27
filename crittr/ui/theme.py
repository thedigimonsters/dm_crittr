# crittr/ui/theme.py
from crittr.qt import QtGui, QtWidgets

NOTE_RAIL_COLOR = QtGui.QColor("#32363c")
GRIP_WIDTH_PX   = 8



class Theme:
    bg          = QtGui.QColor("#1f2124")
    panel       = QtGui.QColor("#26292e")
    panel_alt   = QtGui.QColor("#2c3036")
    stroke      = QtGui.QColor("#3a3f46")
    text        = QtGui.QColor("#d6d7d9")
    text_dim    = QtGui.QColor("#aab0b7")
    accent      = QtGui.QColor("#3fb6ff")
    accent_dim  = QtGui.QColor("#2a90cc")
    success     = QtGui.QColor("#4caf50")
    icon_idle   = QtGui.QColor("#bfc5cc")
    icon_hover  = QtGui.QColor("#e3e6ea")
    danger      = QtGui.QColor("#e57373")

    header_bg = QtGui.QColor("#26292e")  # default (panel_alt)
    header_bg_hover = QtGui.QColor("#2c3036")  # +3–4% luminance
    header_bg_active = QtGui.QColor("#2B323B")  # calm selected header

    chip_colors = [
        QtGui.QColor("#8ab4f8"),
        QtGui.QColor("#f28b82"),
        QtGui.QColor("#80cbc4"),
        QtGui.QColor("#fdd663"),
        QtGui.QColor("#cf93d9"),
    ]

def qcolor_hex(c: QtGui.QColor) -> str:
    return c.name(QtGui.QColor.HexRgb)

def apply_fusion_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, Theme.bg)
    pal.setColor(QtGui.QPalette.Base, Theme.panel)
    pal.setColor(QtGui.QPalette.AlternateBase, Theme.panel_alt)
    pal.setColor(QtGui.QPalette.Text, Theme.text)
    pal.setColor(QtGui.QPalette.WindowText, Theme.text)
    pal.setColor(QtGui.QPalette.ButtonText, Theme.text)
    pal.setColor(QtGui.QPalette.Button, Theme.panel)
    pal.setColor(QtGui.QPalette.ToolTipBase, Theme.panel)
    pal.setColor(QtGui.QPalette.ToolTipText, Theme.text)
    pal.setColor(QtGui.QPalette.Highlight, Theme.accent)
    pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#0c0d0e"))
    app.setPalette(pal)