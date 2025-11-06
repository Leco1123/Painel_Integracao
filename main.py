"""Ponto de entrada principal da aplicação PySide6."""

from __future__ import annotations

import os
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from painel_admin import PainelAdmin
from painel_user import PainelUser
from utils import AuthService, Usuario

os.environ.setdefault("QT_OPENGL", "software")


class LoginWindow(QtWidgets.QMainWindow):
    """Tela inicial responsável pelo fluxo de autenticação."""

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service or AuthService()
        self._painel_aberto: Optional[QtWidgets.QWidget] = None

        self.setWindowTitle("Painel de Integração - Login")
        self.setFixedSize(460, 340)
        self.setWindowIcon(QtGui.QIcon())
        self._configurar_estilos()
        self._montar_interface()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _configurar_estilos(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI'; }
            QLabel#Titulo { font-size: 24px; font-weight: bold; color: #38bdf8; }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px;
                color: #e2e8f0;
            }
            QPushButton {
                background-color: #38bdf8;
                color: #020617;
                font-weight: 600;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton:hover { background-color: #0ea5e9; }
            QLabel#StatusMensagem { color: #f87171; font-size: 12px; }
            QToolButton { border: none; background: transparent; }
            """
        )

    def _montar_interface(self) -> None:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(14)

        titulo = QtWidgets.QLabel("Acesse o sistema")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)

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
        self.btn_toggle_senha.setToolTip("Mostrar/ocultar senha")
        self.btn_toggle_senha.clicked.connect(self._alternar_senha)
        senha_layout.addWidget(self.btn_toggle_senha)
        layout.addLayout(senha_layout)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("StatusMensagem")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.btn_login = QtWidgets.QPushButton("Entrar")
        self.btn_login.clicked.connect(self._tentar_login)
        layout.addWidget(self.btn_login)

        layout.addStretch(1)
        self.setCentralWidget(container)

        self.input_usuario.returnPressed.connect(self._tentar_login)
        self.input_senha.returnPressed.connect(self._tentar_login)
        self.input_usuario.setFocus()

    # ------------------------------------------------------------------
    # Eventos e interações
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: D401 - assinatura Qt
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._tentar_login()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._painel_aberto is not None:
            self._painel_aberto.close()
        event.accept()

    def _alternar_senha(self) -> None:
        modo = self.input_senha.echoMode()
        self.input_senha.setEchoMode(
            QtWidgets.QLineEdit.Normal if modo == QtWidgets.QLineEdit.Password else QtWidgets.QLineEdit.Password
        )

    def _icone_senha(self) -> QtGui.QIcon:
        pixmap = QtGui.QPixmap(18, 18)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#38bdf8"), 2))
        painter.drawEllipse(2, 5, 14, 8)
        painter.end()
        return QtGui.QIcon(pixmap)

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------
    def _tentar_login(self) -> None:
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()

        if not usuario or not senha:
            self._exibir_status("Informe usuário e senha.", erro=True)
            return

        self.btn_login.setEnabled(False)
        self._exibir_status("Validando credenciais...", erro=False)

        try:
            autenticado = self._auth.authenticate(usuario, senha)
        except ValueError as exc:
            self._exibir_status(str(exc), erro=True)
            self.btn_login.setEnabled(True)
            return
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Falha ao autenticar:\n{exc}")
            self._exibir_status("Não foi possível concluir o login.", erro=True)
            self.btn_login.setEnabled(True)
            return

        if not autenticado:
            self._exibir_status("Usuário ou senha inválidos.", erro=True)
            self.btn_login.setEnabled(True)
            return

        self._abrir_painel(autenticado)
        self.btn_login.setEnabled(True)

    def _exibir_status(self, mensagem: str, *, erro: bool) -> None:
        self.lbl_status.setText(mensagem)
        cor = "#f87171" if erro else "#38bdf8"
        self.lbl_status.setStyleSheet(f"color: {cor};")

    def _abrir_painel(self, usuario: Usuario) -> None:
        if self._painel_aberto is not None:
            self._painel_aberto.close()

        painel: QtWidgets.QWidget
        destino = usuario.tipo.lower()
        if destino == "admin":
            painel = PainelAdmin(usuario.to_dict())
        else:
            painel = PainelUser(usuario.to_dict())

        painel.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        painel.show()
        painel.closeEvent = self._retornar_para_login  # type: ignore[assignment]

        self._painel_aberto = painel
        self.hide()
        QtWidgets.QMessageBox.information(self, "Login realizado", f"Bem-vindo, {usuario.nome}!")

    def _retornar_para_login(self, event: QtGui.QCloseEvent) -> None:
        self._painel_aberto = None
        self.show()
        self._exibir_status("Sessão encerrada. Faça login novamente.", erro=False)
        event.accept()


def run() -> None:
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon())
    janela = LoginWindow()
    janela.show()
    app.exec()


if __name__ == "__main__":
    run()
