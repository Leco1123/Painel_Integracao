"""Painel administrativo responsável por orquestrar os módulos internos."""

from __future__ import annotations

import logging
from typing import Callable, List

from PySide6 import QtCore, QtGui, QtWidgets

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from painel_base import BasePainelWindow, ProductCard
from services.produtos_service import Produto, ProdutoService, ProdutoStatus

LOGGER = logging.getLogger(__name__)


class _WorkerSignals(QtCore.QObject):
    succeeded = QtCore.Signal(list)
    failed = QtCore.Signal(object)


class _Worker(QtCore.QRunnable):
    def __init__(self, task: Callable[[], List[Produto]]):
        super().__init__()
        self._task = task
        self.signals = _WorkerSignals()

    def run(self) -> None:  # pragma: no cover - executado fora da thread principal
        try:
            resultado = list(self._task())
        except Exception as exc:  # pragma: no cover - repassado ao Qt
            LOGGER.exception("Worker de produtos falhou")
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(resultado)


class PainelAdmin(BasePainelWindow):
    REFRESH_INTERVAL_MS = 3500

    def __init__(self, usuario: dict):
        super().__init__(usuario, "Painel do Administrador")
        self._service = ProdutoService()
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._schedule_refresh)
        self._refreshing = False

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self._schedule_refresh)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

        self.logger.info("Painel administrativo inicializado para %s", self.usuario.get("usuario"))
        self._janela_admin = None
        self._janela_integracao = None

        self._schedule_refresh()
        self._timer.start()

    # ------------------------------------------------------------------
    # Atualização dos produtos
    # ------------------------------------------------------------------
    def _schedule_refresh(self) -> None:
        if self._refreshing:
            return
        worker = _Worker(self._service.listar_principais)
        worker.signals.succeeded.connect(self._on_refresh_success)
        worker.signals.failed.connect(self._on_refresh_error)
        self.atualizar_rodape("🔄 Atualizando lista de produtos...")
        self._refreshing = True
        self._thread_pool.start(worker)

    @QtCore.Slot(list)
    def _on_refresh_success(self, produtos: List[Produto]) -> None:
        lista = list(produtos)
        if not any(prod.nome == "Painel de Administração" for prod in lista):
            lista.append(Produto(id=None, nome="Painel de Administração", status=ProdutoStatus.PRONTO.value, ultimo_acesso=None))
        self.renderizar_produtos(lista)
        self.atualizar_rodape("🟢 Conectado ao banco de dados")
        self._refreshing = False

    @QtCore.Slot(object)
    def _on_refresh_error(self, erro: Exception) -> None:
        self.logger.exception("Erro ao atualizar produtos", exc_info=erro)
        self.atualizar_rodape("🔴 Falha ao consultar produtos")
        QtWidgets.QMessageBox.critical(
            self,
            "Erro ao buscar produtos",
            f"Não foi possível carregar os produtos:\n{erro}",
        )
        self._refreshing = False

    # ------------------------------------------------------------------
    # Personalização dos cards
    # ------------------------------------------------------------------
    def criar_card(self, produto: Produto) -> ProductCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        card.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda pos, c=card: self._mostrar_menu_status(c, pos))
        if produto.nome == "Painel de Administração":
            card.btn_abrir.setStyleSheet("background-color: #38bdf8; color: black; font-weight: bold; border-radius: 6px; padding: 8px;")
        return card

    # ------------------------------------------------------------------
    # Manipulação de status
    # ------------------------------------------------------------------
    def _mostrar_menu_status(self, card: ProductCard, pos: QtCore.QPoint) -> None:
        produto = card.produto
        if produto.id is None:
            return

        menu = QtWidgets.QMenu(card)
        for status in ProdutoStatus.ordenados():
            action = menu.addAction(status)
            action.triggered.connect(lambda _checked=False, s=status, p=produto: self._alterar_status(p, s))
        menu.exec(card.mapToGlobal(pos))

    def _alterar_status(self, produto: Produto, novo_status: str) -> None:
        try:
            self._service.atualizar_status(produto.id, novo_status)  # type: ignore[arg-type]
        except Exception as exc:
            self.logger.exception("Falha ao alterar status do produto %s", produto.id)
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao atualizar status",
                f"Não foi possível atualizar o status:\n{exc}",
            )
        else:
            self._schedule_refresh()

    # ------------------------------------------------------------------
    # Navegação entre módulos
    # ------------------------------------------------------------------
    def _registrar_acesso(self, produto: Produto) -> None:
        if produto.id is None:
            return
        try:
            self._service.registrar_acesso(produto.id, self.usuario.get("usuario", ""))
        except Exception:
            self.logger.exception("Não foi possível registrar acesso ao produto %s", produto.id)

    def _abrir_modulo(self, produto: Produto) -> None:
        self.logger.info("Abrindo módulo %s", produto.nome)
        self._registrar_acesso(produto)

        if produto.nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif produto.nome == "Painel de Administração":
            self._abrir_painel_administracao()
        elif produto.nome == "Controle da Integração":
            self._abrir_controle_integracao()
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{produto.nome}' ainda não foi conectado.",
            )

    def _abrir_painel_administracao(self) -> None:
        janela = PainelAdministracao()
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_admin = janela

    def _abrir_controle_integracao(self) -> None:
        janela = ControleIntegracao(self.usuario)
        janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        janela.show()
        self._janela_integracao = janela

    # ------------------------------------------------------------------
    # Ciclo de vida da janela
    # ------------------------------------------------------------------
    def event(self, event):  # noqa: D401 - assinatura Qt
        if event.type() == QtCore.QEvent.WindowActivate and not self._timer.isActive():
            self._timer.start(self.REFRESH_INTERVAL_MS)
        elif event.type() == QtCore.QEvent.WindowDeactivate and self._timer.isActive():
            self._timer.stop()
        return super().event(event)


__all__ = ["PainelAdmin"]
