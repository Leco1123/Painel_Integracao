from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt
from datetime import datetime
from database import conectar
from manuais_bridge import abrir_manuais_via_qt
from controle_integracao.controle_integracao import ControleIntegracao  # 🔗 integração total


class PainelUser(QtWidgets.QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user  # dict com nome, usuario, tipo

        self.setWindowTitle("Painel do Usuário")
        self.setGeometry(400, 150, 1100, 650)

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
        self._preencher_cards()

        # Atualização automática dos cards
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._preencher_cards)
        self.timer.start(3000)

    # ===============================================================
    # Construção da interface
    # ===============================================================
    def _build_ui(self):
        container = QtWidgets.QWidget()
        layout_root = QtWidgets.QVBoxLayout(container)

        # Saudação no topo
        saudacao = QtWidgets.QLabel(f"Olá, {self.user['nome']}!")
        saudacao.setObjectName("Saudacao")
        saudacao.setAlignment(Qt.AlignCenter)
        layout_root.addWidget(saudacao)

        # Grade 2 colunas × 3 linhas
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(20)
        layout_root.addLayout(self.grid)

        # Rodapé
        rodape = QtWidgets.QLabel("🟢 Conectado ao sistema_login (MariaDB)")
        rodape.setObjectName("RodapeStatus")
        rodape.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        layout_root.addWidget(rodape)

        self.setCentralWidget(container)

    # ===============================================================
    # Atualiza os cards
    # ===============================================================
    def _preencher_cards(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        produtos = self._buscar_produtos_fixos()

        for idx, produto in enumerate(produtos):
            row = idx // 3
            col = idx % 3
            card = self._criar_card(produto)
            self.grid.addWidget(card, row, col)

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
            conn = conectar()
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
            cursor.close()
            conn.close()

            nomes_ja_no_banco = [p["nome"] for p in produtos]
            faltando = [n for n in nomes_fixos if n not in nomes_ja_no_banco]
            if faltando:
                conn = conectar()
                cursor = conn.cursor()
                for nome_modulo in faltando:
                    cursor.execute(
                        "INSERT INTO produtos (nome, status, ultimo_acesso) VALUES (%s, 'Pronto', NULL)",
                        (nome_modulo,)
                    )
                conn.commit()
                cursor.close()
                conn.close()
                return self._buscar_produtos_fixos()

            return produtos
        except Exception as e:
            print("Erro ao buscar produtos:", e)
            return []

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
        ultimo = produto["ultimo_acesso"]
        data_fmt = datetime.strftime(ultimo, "%d/%m/%Y %H:%M") if ultimo else "-"
        lbl_acesso = QtWidgets.QLabel(f"Último acesso: {data_fmt}")
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
        print(f"[PainelUser] Clicou em '{nome_modulo}' (status={status_modulo})")

        # Log de acesso
        try:
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("UPDATE produtos SET ultimo_acesso = NOW() WHERE id = %s", (produto["id"],))
            cursor.execute(
                "INSERT INTO acessos (usuario, produto_id) VALUES (%s, %s)",
                (self.user["usuario"], produto["id"])
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao registrar acesso:\n{e}")
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
