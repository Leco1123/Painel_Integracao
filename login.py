import os
os.environ["QT_OPENGL"] = "software"  # evita crash de GPU

from PySide6 import QtWidgets, QtCore, QtGui
from database import conectar
import bcrypt


class TelaLogin(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login - Sistema de Painéis")
        self.setGeometry(600, 300, 420, 320)
        self.setFixedSize(420, 320)
        self.setWindowIcon(QtGui.QIcon())

        # ======= Estilo =======
        self.setStyleSheet("""
            QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
            QLabel#Titulo { font-size: 22px; font-weight: bold; color: #4ecca3; }
            QLineEdit {
                background-color: #1b1e2b;
                border: 1px solid #3a3f58;
                border-radius: 6px;
                padding: 8px;
                color: white;
                selection-background-color: #4ecca3;
            }
            QPushButton {
                background-color: #4ecca3;
                color: black;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #6eecc1; }
            QToolButton {
                border: none;
                background: transparent;
            }
        """)
        self.setup_ui()

    # ==============================
    # Interface
    # ==============================
    def setup_ui(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        # título
        titulo = QtWidgets.QLabel("Acesso ao Sistema")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)
        layout.addSpacing(25)

        # Campo Usuário
        self.input_usuario = QtWidgets.QLineEdit()
        self.input_usuario.setPlaceholderText("Usuário")
        layout.addWidget(self.input_usuario)

        # Campo Senha + botão mostrar
        senha_layout = QtWidgets.QHBoxLayout()
        self.input_senha = QtWidgets.QLineEdit()
        self.input_senha.setPlaceholderText("Senha")
        self.input_senha.setEchoMode(QtWidgets.QLineEdit.Password)

        self.btn_toggle_senha = QtWidgets.QToolButton()
        self.btn_toggle_senha.setIcon(QtGui.QIcon.fromTheme("view-password"))
        self.btn_toggle_senha.setToolTip("Mostrar/Ocultar senha")
        self.btn_toggle_senha.setCheckable(True)
        self.btn_toggle_senha.setIcon(QtGui.QIcon(""))

        # Ícone manual (caso não tenha tema do sistema)
        icon = QtGui.QPixmap(16, 16)
        icon.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(icon)
        painter.setPen(QtGui.QPen(QtGui.QColor("#4ecca3"), 2))
        painter.drawEllipse(2, 4, 12, 8)
        painter.end()
        self.btn_toggle_senha.setIcon(QtGui.QIcon(icon))

        self.btn_toggle_senha.clicked.connect(self.toggle_senha)

        senha_layout.addWidget(self.input_senha)
        senha_layout.addWidget(self.btn_toggle_senha)
        layout.addLayout(senha_layout)

        layout.addSpacing(15)

        # Botão de login
        self.botao_login = QtWidgets.QPushButton("Entrar")
        layout.addWidget(self.botao_login)

        container.setLayout(layout)
        self.setCentralWidget(container)

        # ======== Funções ========
        self.botao_login.clicked.connect(self.validar_login)
        self.input_usuario.setFocus()

        # ENTER em qualquer campo faz login
        self.input_usuario.returnPressed.connect(self.validar_login)
        self.input_senha.returnPressed.connect(self.validar_login)

    # ==============================
    # Mostrar/Ocultar Senha
    # ==============================
    def toggle_senha(self):
        """Alterna entre mostrar e esconder a senha"""
        if self.input_senha.echoMode() == QtWidgets.QLineEdit.Password:
            self.input_senha.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.btn_toggle_senha.setStyleSheet("color: #4ecca3;")
        else:
            self.input_senha.setEchoMode(QtWidgets.QLineEdit.Password)
            self.btn_toggle_senha.setStyleSheet("color: white;")

    # ==============================
    # Captura de Teclas Globais (ENTER)
    # ==============================
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Aceita ENTER em qualquer lugar da janela"""
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.validar_login()
        else:
            super().keyPressEvent(event)

    # ==============================
    # Validação de Login
    # ==============================
    def validar_login(self):
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()

        if not usuario or not senha:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Preencha todos os campos.")
            return

        try:
            print("🔗 Tentando conectar ao banco...")
            conn = conectar()
            print("✅ Conectado!")

            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if not user:
                QtWidgets.QMessageBox.warning(self, "Erro", "Usuário não encontrado.")
                return

            if bcrypt.checkpw(senha.encode("utf-8"), user["senha_hash"].encode("utf-8")):
                QtWidgets.QMessageBox.information(self, "Sucesso", f"Bem-vindo, {user['nome']}!")
                self.abrir_painel(user)
            else:
                QtWidgets.QMessageBox.warning(self, "Erro", "Senha incorreta.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao validar login:\n{repr(e)}")

    # ==============================
    # Abertura de Painel
    # ==============================
    def abrir_painel(self, user):
        """Carrega o painel admin ou user"""
        try:
            self.hide()
            tipo = user.get("tipo", "").lower()
            if tipo == "admin":
                from painel_admin import PainelAdmin
                self.painel = PainelAdmin(user)
            else:
                from painel_user import PainelUser
                self.painel = PainelUser(user)

            self.painel.show()
            self.painel.closeEvent = lambda event: self.voltar_para_login(event)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao abrir painel:\n{e}")

    def voltar_para_login(self, event):
        """Volta para o login ao fechar o painel"""
        self.show()
        event.accept()


# ===============================
# Execução direta do login
# ===============================
if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon())

    janela = TelaLogin()
    janela.show()

    app.exec()
