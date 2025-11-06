from __future__ import annotations

import logging
from typing import Callable

from PySide6 import QtWidgets
from PySide6.QtCore import Qt


class BasePainelCards(QtWidgets.QMainWindow):
    """Janela base com layout e estilo compartilhados pelos painéis."""

    GRID_COLUMNS = 3
    STYLE_SHEET = """
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
        self.setWindowTitle(title)
        self.setGeometry(400, 150, 1100, 650)
        self.setStyleSheet(self.STYLE_SHEET)
        self._build_base_ui()

    def _build_base_ui(self) -> None:
        container = QtWidgets.QWidget()
        layout_root = QtWidgets.QVBoxLayout(container)

        saudacao = QtWidgets.QLabel(f"Olá, {self.user['nome']}!")
        saudacao.setObjectName("Saudacao")
        saudacao.setAlignment(Qt.AlignCenter)
        layout_root.addWidget(saudacao)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(20)
        layout_root.addLayout(self.grid)

        rodape = QtWidgets.QLabel("🟢 Conectado ao sistema_login (MariaDB)")
        rodape.setObjectName("RodapeStatus")
        rodape.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        layout_root.addWidget(rodape)

        self.setCentralWidget(container)

    # ===============================================================
    # Utilidades de layout
    # ===============================================================
    def limpar_grade(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def posicionar_card(self, card: QtWidgets.QWidget, indice: int) -> None:
        row, col = divmod(indice, self.GRID_COLUMNS)
        self.grid.addWidget(card, row, col)

    def preencher_grade(self, produtos: list, builder: Callable[[dict], QtWidgets.QWidget]) -> None:
        self.limpar_grade()
        for indice, produto in enumerate(produtos):
            self.posicionar_card(builder(produto), indice)

    # ===============================================================
    # Utilidades gerais
    # ===============================================================
    @staticmethod
    def formatar_data(valor) -> str:
        if not valor:
            return "-"
        try:
            from datetime import datetime

            if isinstance(valor, datetime):
                return valor.strftime("%d/%m/%Y %H:%M")
            return datetime.fromisoformat(str(valor).replace("Z", "").split(".")[0]).strftime(
                "%d/%m/%Y %H:%M"
            )
        except Exception:  # pragma: no cover - fallback defensivo
            return str(valor)

