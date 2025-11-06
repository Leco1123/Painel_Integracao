import logging

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QPoint

from painel_base import BasePainelCards
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from controle_integracao.controle_integracao import ControleIntegracao
from services.produtos_service import (
    atualizar_status_produto,
    obter_produtos_principais,
    registrar_acesso_produto,
)


# ==========================
# 1) Worker assíncrono (fetch do DB)
# ==========================
class ProdutosFetcherSignals(QObject):
    done = Signal(list)
    error = Signal(str)

class ProdutosFetcher(QRunnable):
    def __init__(self, fetch_fn):
        super().__init__()
        self.fetch_fn = fetch_fn
        self.signals = ProdutosFetcherSignals()
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        try:
            produtos = self.fetch_fn()
            self.signals.done.emit(produtos)
        except Exception as e:
            self.logger.exception("Falha ao buscar produtos no worker.")
            self.signals.error.emit(str(e))


class PainelAdmin(BasePainelCards):
    def __init__(self, user):
        super().__init__(user, "Painel do Administrador")
        self._card_cache = {}  # {nome: {"frame":..., "lbl_status":..., "lbl_acesso":..., "btn":...}}

        # Pool global para os workers
        self.pool = QThreadPool.globalInstance()

        # 3) Atalhos
        QtWidgets.QShortcut(QtCore.QKeySequence("Ctrl+R"), self, self._agendar_refresh_async)
        QtWidgets.QShortcut(QtCore.QKeySequence("Esc"), self, self.close)

        self.logger.info("Painel do Administrador inicializado para %s", self.user["usuario"])
        # Primeira carga (assíncrona)
        self._agendar_refresh_async(first_build=True)

        # Atualização automática dos cards (assíncrona)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._agendar_refresh_async)
        self.timer.start(3000)

    # ===============================================================
    # 1) Refresh assíncrono
    # ===============================================================
    def _agendar_refresh_async(self, first_build: bool = False):
        self.logger.debug("Agendando refresh dos produtos (first_build=%s)", first_build)
        worker = ProdutosFetcher(self._buscar_produtos_fixos)
        worker.signals.done.connect(lambda produtos: self._aplicar_produtos(produtos, first_build))
        worker.signals.error.connect(self._exibir_erro_fetch)
        self.pool.start(worker)

    def _exibir_erro_fetch(self, mensagem: str) -> None:
        self.logger.error("Erro ao atualizar lista de produtos: %s", mensagem)
        QtWidgets.QMessageBox.critical(
            self,
            "Erro ao buscar produtos",
            f"Não foi possível carregar os produtos:\n{mensagem}",
        )

    def _aplicar_produtos(self, produtos: list, first_build: bool = False):
        # Garante o "Painel de Administração"
        if not any((p.get("nome", "").lower() == "painel de administração") for p in produtos):
            produtos.append({
                "id": -1,
                "nome": "Painel de Administração",
                "status": "Pronto",
                "ultimo_acesso": None
            })

        if first_build or not self._card_cache:
            # Limpa grade e monta do zero
            while self.grid.count():
                item = self.grid.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._card_cache.clear()

            for idx, produto in enumerate(produtos):
                row, col = divmod(idx, 3)
                card_info = self._criar_card(produto)
                self._card_cache[produto["nome"]] = card_info
                self.grid.addWidget(card_info["frame"], row, col)
            return

        # Atualização incremental
        for produto in produtos:
            nome = produto["nome"]
            if nome in self._card_cache:
                self._atualizar_card(self._card_cache[nome], produto)
            else:
                idx = len(self._card_cache)
                row, col = divmod(idx, 3)
                card_info = self._criar_card(produto)
                self._card_cache[nome] = card_info
                self.grid.addWidget(card_info["frame"], row, col)

    # ===============================================================
    # 4) Buscar produtos (compatível com pool em database.conectar)
    # ===============================================================
    def _buscar_produtos_fixos(self):
        return obter_produtos_principais()

    # ===============================================================
    # Cards + 2) Menu de contexto
    # ===============================================================
    def _criar_card(self, produto):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Card")
        lay = QtWidgets.QVBoxLayout(frame)
        lay.setSpacing(6)

        lbl_nome = QtWidgets.QLabel(produto["nome"])
        lbl_nome.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        lay.addWidget(lbl_nome)

        status = (produto["status"] or "Desconhecido").strip()
        cor_status = {"Em Desenvolvimento": "#ff5555", "Atualizando": "#ffaa00", "Pronto": "#4ecca3"}.get(status, "#888")
        lbl_status = QtWidgets.QLabel(f"Status: {status}")
        lbl_status.setObjectName("StatusLabel")
        lbl_status.setStyleSheet(f"color:{cor_status}; font-weight:bold;")
        lay.addWidget(lbl_status)

        lbl_acesso = QtWidgets.QLabel(
            f"Último acesso: {self.formatar_data(produto.get('ultimo_acesso'))}"
        )
        lay.addWidget(lbl_acesso)

        btn = QtWidgets.QPushButton("Abrir")
        if status.lower() != "pronto" and produto["nome"].lower() != "painel de administração":
            btn.setEnabled(False)
            btn.setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")
        else:
            cor = "#00aaff" if produto["nome"].lower() == "painel de administração" else cor_status
            btn.setStyleSheet(f"background-color:{cor}; color:black; border-radius:6px; padding:6px;")
        btn.clicked.connect(lambda _, p=produto: self._abrir_modulo(p))
        lay.addWidget(btn)

        # Duplo clique abre
        frame.mouseDoubleClickEvent = lambda ev, p=produto: self._abrir_modulo(p)

        # 2) Menu de contexto
        frame.setContextMenuPolicy(Qt.CustomContextMenu)
        frame.customContextMenuRequested.connect(lambda pos, p=produto, f=frame: self._abrir_menu_card(f, p))

        return {"frame": frame, "lbl_status": lbl_status, "lbl_acesso": lbl_acesso, "btn": btn}

    def _abrir_menu_card(self, widget, produto):
        menu = QtWidgets.QMenu(widget)
        for novo in ["Em Desenvolvimento", "Atualizando", "Pronto"]:
            action = menu.addAction(novo)
            action.triggered.connect(lambda _, n=novo, p=produto: self._atualizar_status_produto(p, n))
        # abre no canto superior do card (ponto fixo evita problemas de layout)
        menu.exec(widget.mapToGlobal(QPoint(10, 10)))

    def _atualizar_card(self, card, produto):
        status = (produto["status"] or "Desconhecido").strip()
        cor_status = {"Em Desenvolvimento": "#ff5555", "Atualizando": "#ffaa00", "Pronto": "#4ecca3"}.get(status, "#888")
        card["lbl_status"].setText(f"Status: {status}")
        card["lbl_status"].setStyleSheet(f"color:{cor_status}; font-weight:bold;")
        card["lbl_acesso"].setText(
            f"Último acesso: {self.formatar_data(produto.get('ultimo_acesso'))}"
        )

        if status.lower() != "pronto" and produto["nome"].lower() != "painel de administração":
            card["btn"].setEnabled(False)
            card["btn"].setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")
        else:
            cor = "#00aaff" if produto["nome"].lower() == "painel de administração" else cor_status
            card["btn"].setEnabled(True)
            card["btn"].setStyleSheet(f"background-color:{cor}; color:black; border-radius:6px; padding:6px;")

    def _atualizar_status_produto(self, produto, novo_status):
        try:
            if produto.get("id", -1) == -1:
                QtWidgets.QMessageBox.information(self, "Aviso", "Este card é virtual e não possui ID no banco.")
                return
            atualizar_status_produto(produto["id"], novo_status)
            # feedback visual imediato
            produto["status"] = novo_status
            card = self._card_cache.get(produto["nome"])
            if card:
                self._atualizar_card(card, produto)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Não foi possível atualizar o status:\n{e}")
            self.logger.exception("Falha ao atualizar status do produto %s", produto.get("id"))

    # ===============================================================
    # Roteamento
    # ===============================================================
    def _abrir_modulo(self, produto):
        nome = produto["nome"]
        self.logger.info("Ação de abrir módulo: %s", nome)

        try:
            if produto.get("id", -1) != -1:
                registrar_acesso_produto(produto["id"], self.user["usuario"])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao registrar acesso:\n{e}")
            self.logger.exception("Falha ao registrar acesso do módulo %s", produto.get("id"))
            return

        if nome == "Manuais":
            abrir_manuais_via_qt(self)
        elif nome == "Painel de Administração":
            self.janela_admin = PainelAdministracao()
            self.janela_admin.show()
        elif nome == "Controle da Integração":
            self.janela_integracao = ControleIntegracao(self.user)
            self.janela_integracao.show()
        else:
            QtWidgets.QMessageBox.information(self, "Ainda não implementado",
                                              f"O módulo '{nome}' ainda não foi conectado.")

    # ===============================================================
    # 1) Bônus: pausa o timer quando perde foco (economiza recursos)
    # ===============================================================
    def event(self, e):
        if e.type() == QtCore.QEvent.WindowActivate:
            if not self.timer.isActive():
                self.timer.start(3000)
        elif e.type() == QtCore.QEvent.WindowDeactivate:
            if self.timer.isActive():
                self.timer.stop()
        return super().event(e)
