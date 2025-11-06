from PySide6 import QtWidgets, QtCore

from painel_base import BasePainelCards
from manuais_bridge import abrir_manuais_via_qt
from controle_integracao.controle_integracao import ControleIntegracao  # 🔗 integração total
from services.produtos_service import obter_produtos_principais, registrar_acesso_produto


class PainelUser(BasePainelCards):
    def __init__(self, user):
        super().__init__(user, "Painel do Usuário")
        self.logger.info("Painel do Usuário inicializado para %s", self.user["usuario"])
        self._preencher_cards()

        # Atualização automática dos cards
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._preencher_cards)
        self.timer.start(3000)

    # ===============================================================
    # Atualiza os cards
    # ===============================================================
    def _preencher_cards(self):
        try:
            produtos = obter_produtos_principais()
        except Exception as exc:
            self.logger.exception("Falha ao carregar produtos no painel do usuário.")
            QtWidgets.QMessageBox.critical(
                self,
                "Erro ao buscar produtos",
                f"Não foi possível carregar os produtos:\n{exc}",
            )
            produtos = []

        self.preencher_grade(produtos, self._criar_card)

    # ===============================================================
    # Criação dos cards
    # ===============================================================
    def _criar_card(self, produto):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Card")
        lay = QtWidgets.QVBoxLayout(frame)
        lay.setSpacing(6)

        # Nome
        lbl_nome = QtWidgets.QLabel(produto["nome"])
        lbl_nome.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        lay.addWidget(lbl_nome)

        # Status
        status_texto = produto["status"] or "Desconhecido"
        cor_status = {
            "Em Desenvolvimento": "#ff5555",
            "Atualizando": "#ffaa00",
            "Pronto": "#4ecca3",
        }.get(status_texto, "#888888")

        lbl_status = QtWidgets.QLabel(f"Status: {status_texto}")
        lbl_status.setObjectName("StatusLabel")
        lbl_status.setStyleSheet(f"color: {cor_status}; font-weight:bold;")
        lay.addWidget(lbl_status)

        # Último acesso
        lbl_acesso = QtWidgets.QLabel(
            f"Último acesso: {self.formatar_data(produto.get('ultimo_acesso'))}"
        )
        lay.addWidget(lbl_acesso)

        # Botão
        btn_abrir = QtWidgets.QPushButton("Abrir")
        status_norm = status_texto.strip().lower()

        if status_norm != "pronto":
            btn_abrir.setEnabled(False)
            btn_abrir.setStyleSheet("background-color:#ff5555; color:white; border-radius:6px; padding:6px;")
        else:
            btn_abrir.setStyleSheet(f"background-color:{cor_status}; color:black; border-radius:6px; padding:6px;")

        btn_abrir.clicked.connect(lambda _, p=produto: self._abrir_modulo(p))
        lay.addWidget(btn_abrir)
        return frame

    # ===============================================================
    # Roteamento dos módulos
    # ===============================================================
    def _abrir_modulo(self, produto):
        nome_modulo = produto["nome"]
        status_modulo = (produto["status"] or "").strip().lower()
        self.logger.info("Usuário solicitou módulo '%s' (status=%s)", nome_modulo, status_modulo)

        # Log de acesso
        try:
            registrar_acesso_produto(produto["id"], self.user["usuario"])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao registrar acesso:\n{e}")
            self.logger.exception(
                "Falha ao registrar acesso do usuário %s ao produto %s",
                self.user["usuario"],
                produto.get("id"),
            )
            return

        # Abre os módulos
        if nome_modulo == "Manuais":
            abrir_manuais_via_qt(self)
            return

        if nome_modulo == "Controle da Integração":
            self.janela_integracao = ControleIntegracao(self.user)
            self.janela_integracao.show()
            return

        QtWidgets.QMessageBox.information(
            self, "Ainda não implementado",
            f"O módulo '{nome_modulo}' ainda não foi conectado."
        )
