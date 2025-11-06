"""Painel destinado aos usuários finais com consulta periódica dos produtos."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from controle_integracao.controle_integracao import ControleIntegracao
from manuais_bridge import abrir_manuais_via_qt
from painel_base import BasePainelWindow, PainelCard
from services.produtos_service import Produto, ProdutoService


class PainelUser(BasePainelWindow):
    REFRESH_INTERVAL_MS = 3000

    def __init__(self, user: dict):
        super().__init__(user, "Painel do Usuário")
        self._service = ProdutoService()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh_produtos)

        self.logger.info("Painel do Usuário inicializado para %s", self.user.get("usuario"))
        self._janela_integracao = None
        self._refresh_produtos()
        self._timer.start()

    def criar_card(self, produto: Produto) -> PainelCard:
        card = super().criar_card(produto)
        card.activated.connect(self._abrir_modulo)
        return card

    def _refresh_produtos(self) -> None:
        try:
            produtos = self._service.listar_principais()
        except Exception as exc:
            self.logger.exception("Falha ao carregar produtos no painel do usuário.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao buscar produtos",
                f"Não foi possível carregar os produtos:\n{exc}",
            )
            return

        self.renderizar_produtos(produtos)

    def _abrir_modulo(self, produto: Produto) -> None:
        nome = produto.nome
        self.logger.info("Usuário acionou módulo %s", nome)

        if produto.id is not None:
            try:
                self._service.registrar_acesso(produto.id, self.user.get("usuario", ""))
            except Exception:
                self.logger.exception(
                    "Falha ao registrar acesso do usuário %s ao produto %s",
                    self.user.get("usuario"),
                    produto.id,
                )
                return

        if nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif nome == "Controle da Integração":
            janela = ControleIntegracao(self.user)
            janela.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            janela.show()
            self._janela_integracao = janela
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Módulo não disponível",
                f"O módulo '{nome}' ainda não foi conectado.",
            )


__all__ = ["PainelUser"]
