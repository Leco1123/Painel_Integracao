from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QPoint
from datetime import datetime
from database import conectar
from manuais_bridge import abrir_manuais_via_qt
from painel_administracao import PainelAdministracao
from controle_integracao.controle_integracao import ControleIntegracao


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

    def run(self):
        try:
            produtos = self.fetch_fn()
            self.signals.done.emit(produtos)
        except Exception as e:
            self.signals.error.emit(str(e))


class PainelAdmin(QtWidgets.QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user  # dict com nome, usuario, tipo
        self._card_cache = {}  # {nome: {"frame":..., "lbl_status":..., "lbl_acesso":..., "btn":...}}
        self.setWindowTitle("Painel do Administrador")
        self.setGeometry(400, 150, 1100, 650)

        # Pool global para os workers
        self.pool = QThreadPool.globalInstance()

        # === Estilo padrão ===
        self.setStyleSheet("""
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
        """)

        self._build_ui()

        # Primeira carga (assíncrona)
        self._agendar_refresh_async(first_build=True)

        # Atualização automática dos cards (assíncrona)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._agendar_refresh_async)
        self.timer.start(3000)

    # ===============================================================
    # Interface
    # ===============================================================
    def _build_ui(self):
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

        # 3) Atalhos
        QtWidgets.QShortcut(QtCore.QKeySequence("Ctrl+R"), self, self._agendar_refresh_async)
        QtWidgets.QShortcut(QtCore.QKeySequence("Esc"), self, self.close)

        self.setCentralWidget(container)

    # ===============================================================
    # 1) Refresh assíncrono
    # ===============================================================
    def _agendar_refresh_async(self, first_build: bool = False):
        worker = ProdutosFetcher(self._buscar_produtos_fixos)
        worker.signals.done.connect(lambda produtos: self._aplicar_produtos(produtos, first_build))
        worker.signals.error.connect(lambda msg: print("[PainelAdmin] Erro no fetch:", msg))
        self.pool.start(worker)

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
        nomes_fixos = [
            "Controle da Integração",
            "Macro da Regina",
            "Macro da Folha",
            "Macro do Fiscal",
            "Formatador de Balancete",
            "Manuais"
        ]
        try:
            with conectar() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT id, nome, status, ultimo_acesso FROM produtos
                    WHERE nome IN (
                        'Controle da Integração',
                        'Macro da Regina',
                        'Macro da Folha',
                        'Macro do Fiscal',
                        'Formatador de Balancete',
                        'Manuais'
                    )
                    ORDER BY FIELD(nome,
                        'Controle da Integração',
                        'Macro da Regina',
                        'Macro da Folha',
                        'Macro do Fiscal',
                        'Formatador de Balancete',
                        'Manuais');
                """)
                produtos = cursor.fetchall()

                # insere faltantes de uma vez
                nomes_banco = {p["nome"] for p in produtos}
                faltando = [n for n in nomes_fixos if n not in nomes_banco]
                if faltando:
                    cur2 = conn.cursor()
                    for nome_modulo in faltando:
                        cur2.execute(
                            "INSERT IGNORE INTO produtos (nome, status, ultimo_acesso) VALUES (%s, 'Pronto', NULL)",
                            (nome_modulo,)
                        )
                    conn.commit()
                    cur2.close()

                    cursor.execute("""
                        SELECT id, nome, status, ultimo_acesso FROM produtos
                        WHERE nome IN (
                            'Controle da Integração',
                            'Macro da Regina',
                            'Macro da Folha',
                            'Macro do Fiscal',
                            'Formatador de Balancete',
                            'Manuais'
                        )
                        ORDER BY FIELD(nome,
                            'Controle da Integração',
                            'Macro da Regina',
                            'Macro da Folha',
                            'Macro do Fiscal',
                            'Formatador de Balancete',
                            'Manuais');
                    """)
                    produtos = cursor.fetchall()

                cursor.close()
                return produtos
        except Exception as e:
            print("[PainelAdmin] Erro ao buscar produtos:", e)
            return []

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

        lbl_acesso = QtWidgets.QLabel(f"Último acesso: {self._formatar_data(produto.get('ultimo_acesso'))}")
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
        card["lbl_acesso"].setText(f"Último acesso: {self._formatar_data(produto.get('ultimo_acesso'))}")

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
            with conectar() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE produtos SET status=%s WHERE id=%s", (novo_status, produto["id"]))
                conn.commit()
                cur.close()
            # feedback visual imediato
            produto["status"] = novo_status
            card = self._card_cache.get(produto["nome"])
            if card:
                self._atualizar_card(card, produto)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Não foi possível atualizar o status:\n{e}")

    # ===============================================================
    # Utils
    # ===============================================================
    def _formatar_data(self, valor):
        if not valor:
            return "-"
        if isinstance(valor, datetime):
            return valor.strftime("%d/%m/%Y %H:%M")
        try:
            return datetime.fromisoformat(str(valor).replace("Z", "").split(".")[0]).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(valor)

    # ===============================================================
    # Roteamento
    # ===============================================================
    def _abrir_modulo(self, produto):
        nome = produto["nome"]
        print(f"[PainelAdmin] Clicou em '{nome}'")

        try:
            if produto.get("id", -1) != -1:
                with conectar() as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE produtos SET ultimo_acesso = NOW() WHERE id = %s", (produto["id"],))
                    cur.execute("INSERT INTO acessos (usuario, produto_id) VALUES (%s, %s)",
                                (self.user["usuario"], produto["id"]))
                    conn.commit()
                    cur.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao registrar acesso:\n{e}")
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
