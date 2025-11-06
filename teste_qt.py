from PyQt5.QtWidgets import QApplication, QLabel

app = QApplication([])
label = QLabel("✅ PyQt5 está funcionando!")
label.resize(300, 100)
label.show()
app.exec_()
