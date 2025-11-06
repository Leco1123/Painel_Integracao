"""Painel destinado aos usuários finais do sistema."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_base import BasePainelWindow, ProductCard
from services.produtos_service import Produto, ProdutoService


class PainelUser(BasePainelWindow):
    REFRESH_INTERVAL_MS = 4000

    def __init__(self, usuario: dict):
        super().__init__(usuario, "Painel do Usuário")
        self._service = ProdutoService()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._atualizar_produtos)

        self.logger.info("Painel do usuário inicializado para %s", self.usuario.get("usuario"))
        self._janela_integracao = None
        self._atualizar_produtos()
        self._timer.start()

    def criar_card(self, produto: Produto) -> ProductCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        return card

    def _atualizar_produtos(self) -> None:
        try:
            produtos = self._service.listar_principais()
        except Exception as exc:
            self.logger.exception("Falha ao carregar produtos no painel do usuário.")
            self.atualizar_rodape("🔴 Falha ao buscar produtos")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao buscar produtos",
                f"Não foi possível carregar os produtos:\n{exc}",
            )
            return

        self.renderizar_produtos(produtos)
        self.atualizar_rodape("🟢 Conectado ao banco de dados")

    def _registrar_acesso(self, produto: Produto) -> None:
        if produto.id is None:
            return
        try:
            self._service.registrar_acesso(produto.id, self.usuario.get("usuario", ""))
        except Exception:
            self.logger.exception(
                "Falha ao registrar acesso do usuário %s ao produto %s",
                self.usuario.get("usuario"),
                produto.id,
            )

    def _abrir_modulo(self, produto: Produto) -> None:
        self.logger.info("Usuário acionou módulo %s", produto.nome)
        self._registrar_acesso(produto)

        if produto.nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif produto.nome == "Controle da Integração":
            janela = ControleIntegracao(self.usuario)
            janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            janela.show()
            self._janela_integracao = janela
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{produto.nome}' ainda não foi conectado.",
            )


__all__ = ["PainelUser"]
