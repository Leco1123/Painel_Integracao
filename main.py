import os
os.environ["QT_OPENGL"] = "software"  # garante que o Qt rode sem GPU (evita erro 0xC0000005)

from PySide6 import QtWidgets, QtGui, QtCore
from database import conectar
import bcrypt

class TelaLogin(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login - Sistema de Painéis")
        self.setGeometry(600, 300, 400, 300)
        self.setStyleSheet("""
            QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
            QLabel#Titulo { font-size: 22px; font-weight: bold; color: #4ecca3; }
            QLineEdit {
                background-color: #1b1e2b; border: 1px solid #3a3f58;
                border-radius: 6px; padding: 8px; color: white;
            }
            QPushButton {
                background-color: #4ecca3; color: black; font-weight: bold;
                border-radius: 6px; padding: 6px;
            }
            QPushButton:hover { background-color: #6eecc1; }
        """)
        self.setup_ui()

    def setup_ui(self):
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        self.titulo = QtWidgets.QLabel("Acesso ao Sistema")
        self.titulo.setObjectName("Titulo")
        self.titulo.setAlignment(QtCore.Qt.AlignCenter)

        self.usuario_input = QtWidgets.QLineEdit()
        self.usuario_input.setPlaceholderText("Usuário")

        self.senha_input = QtWidgets.QLineEdit()
        self.senha_input.setPlaceholderText("Senha")
        self.senha_input.setEchoMode(QtWidgets.QLineEdit.Password)

        self.botao_login = QtWidgets.QPushButton("Entrar")
        self.botao_login.clicked.connect(self.validar_login)

        layout.addWidget(self.titulo)
        layout.addSpacing(20)
        layout.addWidget(self.usuario_input)
        layout.addWidget(self.senha_input)
        layout.addSpacing(15)
        layout.addWidget(self.botao_login)

        self.setCentralWidget(central)

    def validar_login(self):
        usuario = self.usuario_input.text().strip()
        senha = self.senha_input.text().strip()

        if not usuario or not senha:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Preencha todos os campos.")
            return

        try:
            conn = conectar()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and bcrypt.checkpw(senha.encode('utf-8'), user['senha_hash'].encode('utf-8')):
                QtWidgets.QMessageBox.information(self, "Sucesso", f"Bem-vindo, {user['nome']}!")

                self.hide()
                self.abrir_painel(user)
            else:
                QtWidgets.QMessageBox.warning(self, "Erro", "Usuário ou senha inválidos.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao validar login:\n{e}")

    def abrir_painel(self, user):
        try:
            if user['tipo'] == 'admin':
                from painel_admin import PainelAdmin
                self.painel = PainelAdmin(user)
            else:
                from painel_user import PainelUser
                self.painel = PainelUser(user)

            self.painel.show()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao abrir painel:\n{e}")

# ================================
# Execução do sistema
# ================================
if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    # Ícone opcional
    app.setWindowIcon(QtGui.QIcon())

    janela = TelaLogin()
    janela.show()

    app.exec()
