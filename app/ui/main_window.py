from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from app.logic import secure_logic

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 + Cython Demo")

        self.label = QLabel("Click to check license")
        self.button = QPushButton("Check License")
        self.button.clicked.connect(self.check_license)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def check_license(self):
        if secure_logic.check_license("SECRET-KEY-123"):
            self.label.setText("License Valid ✅")
        else:
            self.label.setText("License Invalid ❌")
