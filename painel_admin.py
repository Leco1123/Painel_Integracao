"""Painel administrativo com atualizações assíncronas e gerenciamento de produtos."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable, Iterable, List

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QPoint, QRunnable, QThreadPool

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from painel_base import BasePainelWindow, PainelCard
from services.produtos_service import Produto, ProdutoService

LOGGER = logging.getLogger(__name__)


class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)


class ServiceWorker(QRunnable):
    def __init__(self, fn: Callable[[], Iterable[Produto]]):
        super().__init__()
        self._fn = fn
        self.signals = WorkerSignals()

    def run(self) -> None:  # pragma: no cover - executado em thread de trabalho
        try:
            resultado = list(self._fn())
        except Exception as exc:  # pragma: no cover - propagado via sinal
            LOGGER.exception("Worker de serviço falhou")
            self.signals.failed.emit(str(exc))
        else:
            self.signals.finished.emit(resultado)


class PainelAdmin(BasePainelWindow):
    """Janela principal utilizada pelos administradores."""

    REFRESH_INTERVAL_MS = 3000

    def __init__(self, user: dict):
        super().__init__(user, "Painel do Administrador")
        self._service = ProdutoService()
        self._pool = QThreadPool.globalInstance()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._schedule_refresh)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self._schedule_refresh)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

        self.logger.info("Painel do Administrador inicializado para %s", self.user.get("usuario"))
        self._janela_admin = None
        self._janela_integracao = None
        self._schedule_refresh()
        self._timer.start()

    # ------------------------------------------------------------------
    # Fetch assíncrono
    # ------------------------------------------------------------------
    def _schedule_refresh(self) -> None:
        worker = ServiceWorker(self._fetch_produtos)
        worker.signals.finished.connect(self._apply_produtos)
        worker.signals.failed.connect(self._handle_error)
        self._pool.start(worker)

    def _fetch_produtos(self) -> List[Produto]:
        return self._service.listar_principais()

    def _apply_produtos(self, produtos: List[Produto]) -> None:
        itens = list(produtos)
        if not any(produto.nome == "Painel de Administração" for produto in itens):
            itens.append(Produto(id=None, nome="Painel de Administração", status="Pronto", ultimo_acesso=None))
        self.renderizar_produtos(itens)

    def _handle_error(self, mensagem: str) -> None:
        QtWidgets.QMessageBox.critical(
            self,
            "Erro ao buscar produtos",
            f"Não foi possível carregar os produtos:\n{mensagem}",
        )

    # ------------------------------------------------------------------
    # Criação e atualização dos cards
    # ------------------------------------------------------------------
    def criar_card(self, produto: Produto) -> PainelCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        card.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda _pos, c=card: self._abrir_menu(c))
        if produto.nome == "Painel de Administração":
            card.btn_abrir.setStyleSheet("background-color:#00aaff; color:black; border-radius:6px; padding:6px;")
        return card

    def atualizar_card(self, produto: Produto) -> None:
        super().atualizar_card(produto)
        card = self.cards.get(produto.cache_key)
        if card and produto.nome == "Painel de Administração":
            card.btn_abrir.setStyleSheet("background-color:#00aaff; color:black; border-radius:6px; padding:6px;")

    def _abrir_menu(self, card: PainelCard) -> None:
        produto = card.produto
        if produto.id is None:
            QtWidgets.QMessageBox.information(self, "Informação", "Este card não possui ID no banco de dados.")
            return

        menu = QtWidgets.QMenu(card)
        for status in ("Em Desenvolvimento", "Atualizando", "Pronto"):
            action = menu.addAction(status)
            action.triggered.connect(lambda _checked=False, s=status, p=produto: self._alterar_status(p, s))
        menu.exec(card.mapToGlobal(QPoint(10, 10)))

    def _alterar_status(self, produto: Produto, novo_status: str) -> None:
        try:
            if produto.id is not None:
                self._service.atualizar_status(produto.id, novo_status)
                atualizado = replace(produto, status=novo_status)
                self.atualizar_card(atualizado)
        except Exception as exc:
            self.logger.exception("Falha ao alterar status do produto %s", produto.id)
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao atualizar status",
                f"Não foi possível atualizar o status:\n{exc}",
            )

    # ------------------------------------------------------------------
    # Navegação entre módulos
    # ------------------------------------------------------------------
    def _abrir_modulo(self, produto: Produto) -> None:
        nome = produto.nome
        self.logger.info("Abrindo módulo %s", nome)

        if produto.id is not None:
            try:
                self._service.registrar_acesso(produto.id, self.user.get("usuario", ""))
            except Exception:
                self.logger.exception("Falha ao registrar acesso ao produto %s", produto.id)

        if nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif nome == "Painel de Administração":
            self._abrir_painel_administracao()
        elif nome == "Controle da Integração":
            self._abrir_controle_integracao()
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{nome}' ainda não foi conectado.",
            )

    def _abrir_painel_administracao(self) -> None:
        janela = PainelAdministracao()
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_admin = janela

    def _abrir_controle_integracao(self) -> None:
        janela = ControleIntegracao(self.user)
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_integracao = janela

    # ------------------------------------------------------------------
    # Otimizações
    # ------------------------------------------------------------------
    def event(self, event):  # noqa: D401 - assinatura Qt
        if event.type() == QtCore.QEvent.WindowActivate and not self._timer.isActive():
            self._timer.start(self.REFRESH_INTERVAL_MS)
        elif event.type() == QtCore.QEvent.WindowDeactivate and self._timer.isActive():
            self._timer.stop()
        return super().event(event)


__all__ = ["PainelAdmin"]
