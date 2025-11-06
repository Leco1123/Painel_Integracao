from PySide6.QtWidgets import QApplication, QLabel
import os
os.environ["QT_OPENGL"] = "software"

app = QApplication([])
label = QLabel("✅ PySide6 funcionando — substituto do PyQt5")
label.resize(320, 120)
label.show()
app.exec()
