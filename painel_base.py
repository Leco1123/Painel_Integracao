"""Widgets base compartilhados pelos painéis da aplicação."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Dict, Iterable, Sequence

from PySide6 import QtCore, QtWidgets

from services.produtos_service import Produto, ProdutoStatus


STATUS_COLORS = {
    ProdutoStatus.EM_DESENVOLVIMENTO.value: "#f87171",
    ProdutoStatus.ATUALIZANDO.value: "#fbbf24",
    ProdutoStatus.PRONTO.value: "#4ade80",
}


class ProductCard(QtWidgets.QFrame):
    """Cartão visual que representa um único produto."""

    activated = QtCore.Signal(Produto)

    def __init__(self, produto: Produto, *, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._produto = produto
        self._build()
        self.update_from_produto(produto)

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self.lbl_nome = QtWidgets.QLabel()
        self.lbl_nome.setObjectName("CardTitle")
        layout.addWidget(self.lbl_nome)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setObjectName("CardStatus")
        layout.addWidget(self.lbl_status)

        self.lbl_ultimo_acesso = QtWidgets.QLabel()
        layout.addWidget(self.lbl_ultimo_acesso)

        layout.addStretch(1)

        self.btn_abrir = QtWidgets.QPushButton("Abrir módulo")
        self.btn_abrir.clicked.connect(self._emit_activated)
        layout.addWidget(self.btn_abrir)

    def mouseDoubleClickEvent(self, event):  # noqa: D401 - API Qt
        self._emit_activated()
        return super().mouseDoubleClickEvent(event)

    def _emit_activated(self) -> None:
        if self.btn_abrir.isEnabled():
            self.activated.emit(self._produto)

    def update_from_produto(self, produto: Produto) -> None:
        self._produto = produto
        self.lbl_nome.setText(produto.nome)

        status = (produto.status or "Desconhecido").strip()
        cor = STATUS_COLORS.get(status, "#94a3b8")
        self.lbl_status.setText(f"Status: {status}")
        self.lbl_status.setStyleSheet(f"color: {cor}; font-weight: bold;")

        ultimo_acesso = BasePainelWindow.formatar_data(produto.ultimo_acesso)
        self.lbl_ultimo_acesso.setText(f"Último acesso: {ultimo_acesso}")

        habilitado = status.lower() == ProdutoStatus.PRONTO.value.lower()
        self.btn_abrir.setEnabled(habilitado)
        if habilitado:
            self.btn_abrir.setStyleSheet(
                f"background-color: {cor}; color: black; font-weight: bold; border-radius: 6px; padding: 8px;"
            )
        else:
            self.btn_abrir.setStyleSheet(
                "background-color: #ef4444; color: white; font-weight: bold; border-radius: 6px; padding: 8px;"
            )

    @property
    def produto(self) -> Produto:
        return self._produto


class ProductGrid(QtWidgets.QWidget):
    """Grade responsiva responsável por organizar os cartões."""

    def __init__(self, *, columns: int = 3, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._columns = max(1, columns)
        self._layout = QtWidgets.QGridLayout(self)
        self._layout.setSpacing(16)
        self._cards: Dict[str, ProductCard] = {}

    def set_products(self, produtos: Sequence[Produto], *, factory) -> None:
        self.clear()
        for index, produto in enumerate(produtos):
            card = factory(produto)
            self._cards[produto.cache_key] = card
            row, column = divmod(index, self._columns)
            self._layout.addWidget(card, row, column)

    def update_product(self, produto: Produto) -> None:
        card = self._cards.get(produto.cache_key)
        if card:
            card.update_from_produto(produto)

    def clear(self) -> None:
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()
        while self._layout.count():
            self._layout.takeAt(0)

    def cards(self) -> Iterable[ProductCard]:
        return self._cards.values()


class BasePainelWindow(QtWidgets.QMainWindow):
    """Janela base compartilhada entre os painéis do sistema."""

    GRID_COLUMNS = 3
    STYLE = """
        QWidget { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI'; }
        QLabel#TituloPainel { font-size: 24px; font-weight: bold; color: #38bdf8; }
        QLabel#RodapeStatus { font-size: 12px; color: #94a3b8; }
        QFrame#Card {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
        }
        QLabel#CardTitle { font-size: 16px; font-weight: 600; color: #e2e8f0; }
        QLabel#CardStatus { font-size: 13px; }
    """

    def __init__(self, usuario: dict, titulo: str):
        super().__init__()
        self.usuario = usuario
        self.logger = logging.getLogger(self.__class__.__name__)
        self._grid = ProductGrid(columns=self.GRID_COLUMNS)

        self.setWindowTitle(titulo)
        self.setMinimumSize(1100, 650)
        self.setStyleSheet(self.STYLE)
        self._build_layout()

    def _build_layout(self) -> None:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        titulo = QtWidgets.QLabel(f"Olá, {self.usuario.get('nome', 'usuário')}!")
        titulo.setObjectName("TituloPainel")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        scroll_layout.addWidget(self._grid)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        self._rodape = QtWidgets.QLabel("🔌 Aguardando conexão...")
        self._rodape.setObjectName("RodapeStatus")
        self._rodape.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        layout.addWidget(self._rodape)

        self.setCentralWidget(container)

    # ------------------------------------------------------------------
    # API de atualização
    # ------------------------------------------------------------------
    def renderizar_produtos(self, produtos: Sequence[Produto]) -> None:
        self._grid.set_products(produtos, factory=self.criar_card)

    def criar_card(self, produto: Produto) -> ProductCard:
        return ProductCard(produto)

    def atualizar_card(self, produto: Produto) -> None:
        self._grid.update_product(produto)

    def atualizar_rodape(self, mensagem: str) -> None:
        self._rodape.setText(mensagem)

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


__all__ = ["BasePainelWindow", "ProductCard", "ProductGrid", "STATUS_COLORS"]
