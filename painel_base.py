"""Componentes base compartilhados entre os painéis de usuário e administrador."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Dict, Sequence

from PySide6 import QtCore, QtWidgets

from services.produtos_service import Produto


STATUS_COLORS = {
    "Em Desenvolvimento": "#ff5555",
    "Atualizando": "#ffaa00",
    "Pronto": "#4ecca3",
}


class PainelCard(QtWidgets.QFrame):
    """Widget visual responsável por exibir um único produto."""

    activated = QtCore.Signal(Produto)

    def __init__(self, produto: Produto, *, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._produto = produto
        self._build_ui()
        self.update_from_produto(produto)

    # ------------------------------------------------------------------
    # Construção visual
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        self.lbl_nome = QtWidgets.QLabel()
        self.lbl_nome.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(self.lbl_nome)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("StatusLabel")
        layout.addWidget(self.lbl_status)

        self.lbl_acesso = QtWidgets.QLabel()
        layout.addWidget(self.lbl_acesso)

        self.btn_abrir = QtWidgets.QPushButton("Abrir")
        self.btn_abrir.clicked.connect(self._emit_activated)
        layout.addWidget(self.btn_abrir)

    # ------------------------------------------------------------------
    # Atualizações
    # ------------------------------------------------------------------
    def update_from_produto(self, produto: Produto) -> None:
        self._produto = produto
        self.lbl_nome.setText(produto.nome)
        status = (produto.status or "Desconhecido").strip()
        cor = STATUS_COLORS.get(status, "#888888")
        self.lbl_status.setText(f"Status: {status}")
        self.lbl_status.setStyleSheet(f"color: {cor}; font-weight:bold;")

        acesso = BasePainelWindow.formatar_data(produto.ultimo_acesso)
        self.lbl_acesso.setText(f"Último acesso: {acesso}")

        habilitado = status.lower() == "pronto"
        self.btn_abrir.setEnabled(habilitado)
        if habilitado:
            self.btn_abrir.setStyleSheet(f"background-color:{cor}; color:black; border-radius:6px; padding:6px;")
        else:
            self.btn_abrir.setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------
    def _emit_activated(self) -> None:
        if self.btn_abrir.isEnabled():
            self.activated.emit(self._produto)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 (Qt API)
        self._emit_activated()
        return super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @property
    def produto(self) -> Produto:
        return self._produto


class BasePainelWindow(QtWidgets.QMainWindow):
    """Janela base que encapsula layout, estilo e utilitários comuns."""

    GRID_COLUMNS = 3
    STYLE = """
        QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
        QLabel#Saudacao {
            font-size: 22px;
            font-weight: bold;
            color: #4ecca3;
            margin: 15px;
        }
        QFrame#Card {
            background-color: #1b1e2b;
            border-radius: 10px;
            border: 1px solid #2a2a4a;
            padding: 16px;
            margin: 8px;
        }
        QLabel { font-size: 13px; color: #ffffff; }
        QLabel.StatusLabel { font-size: 13px; font-weight: bold; }
        QPushButton {
            font-weight: bold;
            border-radius: 6px;
            padding: 6px;
        }
        QLabel#RodapeStatus {
            font-size: 12px;
            color: #ffffff;
        }
    """

    def __init__(self, user: dict, title: str):
        super().__init__()
        self.user = user
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cards: Dict[str, PainelCard] = {}

        self.setWindowTitle(title)
        self.setGeometry(400, 150, 1100, 650)
        self.setStyleSheet(self.STYLE)
        self._build_base_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_base_layout(self) -> None:
        container = QtWidgets.QWidget()
        layout_root = QtWidgets.QVBoxLayout(container)

        saudacao = QtWidgets.QLabel(f"Olá, {self.user.get('nome', 'usuário')}!")
        saudacao.setObjectName("Saudacao")
        saudacao.setAlignment(QtCore.Qt.AlignCenter)
        layout_root.addWidget(saudacao)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(20)
        layout_root.addLayout(self.grid)

        rodape = QtWidgets.QLabel("🟢 Conectado ao sistema_login (MariaDB)")
        rodape.setObjectName("RodapeStatus")
        rodape.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        layout_root.addWidget(rodape)

        self.setCentralWidget(container)

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------
    def renderizar_produtos(self, produtos: Sequence[Produto]) -> None:
        self._limpar_grade()
        self.cards.clear()

        for indice, produto in enumerate(produtos):
            card = self.criar_card(produto)
            self.cards[produto.cache_key] = card
            row, col = divmod(indice, self.GRID_COLUMNS)
            self.grid.addWidget(card, row, col)

    def criar_card(self, produto: Produto) -> PainelCard:
        return PainelCard(produto)

    def atualizar_card(self, produto: Produto) -> None:
        card = self.cards.get(produto.cache_key)
        if card:
            card.update_from_produto(produto)

    def _limpar_grade(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @staticmethod
    def formatar_data(valor) -> str:
        if not valor:
            return "-"
        try:
            if isinstance(valor, datetime):
                return valor.strftime("%d/%m/%Y %H:%M")
            return datetime.fromisoformat(str(valor).split(".")[0]).strftime("%d/%m/%Y %H:%M")
        except Exception:  # pragma: no cover - melhor esforço
            return str(valor)


__all__ = ["BasePainelWindow", "PainelCard", "STATUS_COLORS"]
