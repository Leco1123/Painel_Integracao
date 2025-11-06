# controle_integracao/main_integracao.py
import sys
from PySide6 import QtWidgets
from controle_integracao.controle_integracao import ControleIntegracao

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    fake_user = {"nome": "Administrador", "usuario": "admin", "tipo": "admin"}
    win = ControleIntegracao(user=fake_user)
    win.show()
    sys.exit(app.exec())
