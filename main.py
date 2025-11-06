"""Ponto de entrada da aplicação PySide6 responsável pelo fluxo de login."""

from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from painel_admin import PainelAdmin
from painel_user import PainelUser
from utils import AuthService, Usuario

os.environ.setdefault("QT_OPENGL", "software")


class LoginWindow(QtWidgets.QMainWindow):
    """Janela de autenticação que direciona o usuário para o painel adequado."""

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self.auth_service = auth_service or AuthService()
        self._painel_atual: Optional[QtWidgets.QWidget] = None

        self.setWindowTitle("Login - Sistema de Painéis")
        self.setFixedSize(420, 320)
        self.setWindowIcon(QtGui.QIcon())
        self._configurar_estilos()
        self._construir_interface()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _configurar_estilos(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
            QLabel#Titulo { font-size: 22px; font-weight: bold; color: #4ecca3; }
            QLineEdit {
                background-color: #1b1e2b;
                border: 1px solid #3a3f58;
                border-radius: 6px;
                padding: 8px;
                color: white;
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
            """
        )

    def _construir_interface(self) -> None:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        titulo = QtWidgets.QLabel("Acesso ao Sistema")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)
        layout.addSpacing(20)

        self.input_usuario = QtWidgets.QLineEdit()
        self.input_usuario.setPlaceholderText("Usuário")
        layout.addWidget(self.input_usuario)

        senha_layout = QtWidgets.QHBoxLayout()
        self.input_senha = QtWidgets.QLineEdit()
        self.input_senha.setPlaceholderText("Senha")
        self.input_senha.setEchoMode(QtWidgets.QLineEdit.Password)
        senha_layout.addWidget(self.input_senha)

        self.btn_toggle_senha = QtWidgets.QToolButton()
        self.btn_toggle_senha.setIcon(self._icone_senha())
        self.btn_toggle_senha.setCheckable(True)
        self.btn_toggle_senha.setToolTip("Mostrar/Ocultar senha")
        self.btn_toggle_senha.clicked.connect(self._alternar_senha)
        senha_layout.addWidget(self.btn_toggle_senha)
        layout.addLayout(senha_layout)

        layout.addSpacing(20)

        self.btn_login = QtWidgets.QPushButton("Entrar")
        self.btn_login.clicked.connect(self._executar_login)
        layout.addWidget(self.btn_login)

        self.setCentralWidget(container)

        self.input_usuario.returnPressed.connect(self._executar_login)
        self.input_senha.returnPressed.connect(self._executar_login)
        self.input_usuario.setFocus()

    # ------------------------------------------------------------------
    # Eventos de UI
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: D401 - assinatura Qt
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._executar_login()
        else:
            super().keyPressEvent(event)

    def _alternar_senha(self) -> None:
        if self.input_senha.echoMode() == QtWidgets.QLineEdit.Password:
            self.input_senha.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.input_senha.setEchoMode(QtWidgets.QLineEdit.Password)

    def _icone_senha(self) -> QtGui.QIcon:
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#4ecca3"), 2))
        painter.drawEllipse(2, 4, 12, 8)
        painter.end()
        return QtGui.QIcon(pixmap)

    # ------------------------------------------------------------------
    # Lógica de autenticação
    # ------------------------------------------------------------------
    def _executar_login(self) -> None:
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()

        if not usuario or not senha:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Preencha todos os campos.")
            return

        try:
            autenticado = self.auth_service.authenticate(usuario, senha)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Dados inválidos", str(exc))
            return
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao validar login:\n{exc}")
            return

        if not autenticado:
            QtWidgets.QMessageBox.warning(self, "Erro", "Usuário ou senha inválidos.")
            return

        QtWidgets.QMessageBox.information(self, "Sucesso", f"Bem-vindo, {autenticado.nome}!")
        self._abrir_painel(autenticado)

    def _abrir_painel(self, usuario: Usuario) -> None:
        if self._painel_atual is not None:
            self._painel_atual.close()

        painel: QtWidgets.QWidget
        if usuario.tipo.lower() == "admin":
            painel = PainelAdmin(usuario.to_dict())
        else:
            painel = PainelUser(usuario.to_dict())

        painel.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        painel.show()
        painel.closeEvent = self._retornar_para_login  # type: ignore[assignment]

        self._painel_atual = painel
        self.hide()

    def _retornar_para_login(self, event: QtGui.QCloseEvent) -> None:
        self._painel_atual = None
        self.show()
        event.accept()


def run() -> None:
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon())

    janela = LoginWindow()
    janela.show()

    app.exec()


if __name__ == "__main__":
    run()
