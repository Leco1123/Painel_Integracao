from PySide6 import QtWidgets, QtCore
from database import conectar
import bcrypt
from datetime import datetime


class PainelAdministracao(QtWidgets.QTabWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Painel de Administração")
        self.setGeometry(450, 200, 800, 500)
        self.setStyleSheet("""
            QWidget { background-color: #1b1b2f; color: white; font-family: 'Segoe UI'; }
            QLabel { font-size: 14px; color: #4ecca3; font-weight: bold; }
            QTableWidget {
                background-color: #12121c;
                color: white;
                border: 1px solid #2a2a4a;
                gridline-color: #2a2a4a;
                selection-background-color: #4ecca3;
            }
            QPushButton {
                background-color: #4ecca3;
                color: black;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #6eecc1; }
            QComboBox {
                background-color: #2b2b3c;
                color: white;
                border-radius: 5px;
                padding: 3px;
            }
        """)
        self.initUI()

    # ============================================================
    # 🧠 INTERFACE PRINCIPAL
    # ============================================================
    def initUI(self):
        self.tab_usuarios = QtWidgets.QWidget()
        self.tab_status = QtWidgets.QWidget()

        self.addTab(self.tab_usuarios, "Usuários")
        self.addTab(self.tab_status, "Status dos Módulos")

        self.init_tab_usuarios()
        self.init_tab_status()

    # ============================================================
    # 🧍‍♂️ ABA DE USUÁRIOS (CRUD)
    # ============================================================
    def init_tab_usuarios(self):
        layout = QtWidgets.QVBoxLayout(self.tab_usuarios)

        titulo = QtWidgets.QLabel("Gerenciamento de Usuários")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)

        self.tabela = QtWidgets.QTableWidget()
        self.tabela.setColumnCount(4)
        self.tabela.setHorizontalHeaderLabels(["Usuário", "Nome", "Permissão", "Criado em"])
        self.tabela.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela)

        botoes = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("➕ Cadastrar Usuário")
        btn_edit = QtWidgets.QPushButton("✏️ Editar Usuário")
        btn_del = QtWidgets.QPushButton("🗑️ Excluir Usuário")
        btn_refresh = QtWidgets.QPushButton("🔄 Atualizar")

        botoes.addWidget(btn_add)
        botoes.addWidget(btn_edit)
        botoes.addWidget(btn_del)
        botoes.addStretch()
        botoes.addWidget(btn_refresh)
        layout.addLayout(botoes)

        btn_add.clicked.connect(self.cadastrar_usuario)
        btn_edit.clicked.connect(self.editar_usuario)
        btn_del.clicked.connect(self.excluir_usuario)
        btn_refresh.clicked.connect(self.carregar_usuarios)

        self.carregar_usuarios()

    def carregar_usuarios(self):
        try:
            conn = conectar()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT usuario, nome, tipo, data_criacao FROM usuarios ORDER BY data_criacao DESC;")
            usuarios = cursor.fetchall()
            cursor.close()
            conn.close()

            self.tabela.setRowCount(len(usuarios))
            for i, user in enumerate(usuarios):
                self.tabela.setItem(i, 0, QtWidgets.QTableWidgetItem(user["usuario"]))
                self.tabela.setItem(i, 1, QtWidgets.QTableWidgetItem(user["nome"]))
                self.tabela.setItem(i, 2, QtWidgets.QTableWidgetItem(user["tipo"].capitalize()))
                data = user["data_criacao"].strftime("%d/%m/%Y %H:%M") if user["data_criacao"] else "-"
                self.tabela.setItem(i, 3, QtWidgets.QTableWidgetItem(data))

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao carregar usuários:\n{e}")

    def cadastrar_usuario(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Cadastrar Novo Usuário")
        dialog.resize(400, 250)
        layout = QtWidgets.QFormLayout(dialog)

        nome = QtWidgets.QLineEdit()
        usuario = QtWidgets.QLineEdit()
        senha = QtWidgets.QLineEdit()
        senha.setEchoMode(QtWidgets.QLineEdit.Password)
        tipo = QtWidgets.QComboBox()
        tipo.addItems(["admin", "user"])

        layout.addRow("Nome:", nome)
        layout.addRow("Usuário:", usuario)
        layout.addRow("Senha:", senha)
        layout.addRow("Permissão:", tipo)

        btn_salvar = QtWidgets.QPushButton("Salvar")
        layout.addRow(btn_salvar)

        def salvar():
            nome_v = nome.text().strip()
            usuario_v = usuario.text().strip()
            senha_v = senha.text().strip()
            tipo_v = tipo.currentText()

            if not nome_v or not usuario_v or not senha_v:
                QtWidgets.QMessageBox.warning(dialog, "Aviso", "Preencha todos os campos.")
                return

            hash_senha = bcrypt.hashpw(senha_v.encode(), bcrypt.gensalt()).decode()

            try:
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO usuarios (nome, usuario, senha_hash, tipo, data_criacao)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (nome_v, usuario_v, hash_senha, tipo_v))
                conn.commit()
                cursor.close()
                conn.close()
                QtWidgets.QMessageBox.information(dialog, "Sucesso", "Usuário cadastrado com sucesso!")
                dialog.accept()
                self.carregar_usuarios()
            except Exception as e:
                QtWidgets.QMessageBox.critical(dialog, "Erro", f"Erro ao cadastrar:\n{e}")

        btn_salvar.clicked.connect(salvar)
        dialog.exec()

    def editar_usuario(self):
        linha = self.tabela.currentRow()
        if linha < 0:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Selecione um usuário para editar.")
            return

        usuario = self.tabela.item(linha, 0).text()
        nome = self.tabela.item(linha, 1).text()
        tipo_atual = self.tabela.item(linha, 2).text().lower()

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Editar Usuário — {nome}")
        dialog.resize(400, 220)
        layout = QtWidgets.QFormLayout(dialog)

        tipo = QtWidgets.QComboBox()
        tipo.addItems(["admin", "user"])
        tipo.setCurrentText(tipo_atual)

        senha = QtWidgets.QLineEdit()
        senha.setEchoMode(QtWidgets.QLineEdit.Password)
        senha.setPlaceholderText("Deixe em branco para não alterar")

        layout.addRow("Permissão:", tipo)
        layout.addRow("Nova Senha:", senha)

        btn_salvar = QtWidgets.QPushButton("Salvar Alterações")
        layout.addRow(btn_salvar)

        def salvar():
            tipo_v = tipo.currentText()
            senha_v = senha.text().strip()

            try:
                conn = conectar()
                cursor = conn.cursor()
                if senha_v:
                    hash_senha = bcrypt.hashpw(senha_v.encode(), bcrypt.gensalt()).decode()
                    cursor.execute(
                        "UPDATE usuarios SET tipo=%s, senha_hash=%s WHERE usuario=%s",
                        (tipo_v, hash_senha, usuario),
                    )
                else:
                    cursor.execute("UPDATE usuarios SET tipo=%s WHERE usuario=%s", (tipo_v, usuario))
                conn.commit()
                cursor.close()
                conn.close()
                QtWidgets.QMessageBox.information(dialog, "Sucesso", "Usuário atualizado!")
                dialog.accept()
                self.carregar_usuarios()
            except Exception as e:
                QtWidgets.QMessageBox.critical(dialog, "Erro", f"Erro ao editar:\n{e}")

        btn_salvar.clicked.connect(salvar)
        dialog.exec()

    def excluir_usuario(self):
        linha = self.tabela.currentRow()
        if linha < 0:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Selecione um usuário para excluir.")
            return

        usuario = self.tabela.item(linha, 0).text()
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Tem certeza que deseja excluir o usuário '{usuario}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )

        if confirm == QtWidgets.QMessageBox.Yes:
            try:
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM usuarios WHERE usuario = %s", (usuario,))
                conn.commit()
                cursor.close()
                conn.close()
                QtWidgets.QMessageBox.information(self, "Sucesso", "Usuário excluído!")
                self.carregar_usuarios()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao excluir:\n{e}")

    # ============================================================
    # 🧩 ABA DE STATUS DOS 6 MÓDULOS FIXOS
    # ============================================================
    def init_tab_status(self):
        layout = QtWidgets.QVBoxLayout(self.tab_status)
        titulo = QtWidgets.QLabel("Gerenciar Status dos 6 Módulos")
        titulo.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(titulo)

        self.tabela_modulos = QtWidgets.QTableWidget()
        self.tabela_modulos.setColumnCount(3)
        self.tabela_modulos.setHorizontalHeaderLabels(["Módulo", "Status Atual", "Último Acesso"])
        self.tabela_modulos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_modulos)

        btn_atualizar = QtWidgets.QPushButton("🔄 Atualizar Lista")
        btn_atualizar.clicked.connect(self.carregar_modulos)
        layout.addWidget(btn_atualizar)

        self.carregar_modulos()

    def carregar_modulos(self):
        """Carrega apenas os 6 módulos principais (sem duplicar)"""
        modulos_fixos = [
            "Controle da Integração",
            "Macro da Regina",
            "Macro da Folha",
            "Macro do Fiscal",
            "Formatador de Balancete",
            "Manuais",
        ]

        try:
            conn = conectar()
            cursor = conn.cursor(dictionary=True)

            # Busca todos os produtos existentes
            cursor.execute("SELECT id, nome, status, ultimo_acesso FROM produtos;")
            existentes = cursor.fetchall()
            nomes_existentes = [p["nome"] for p in existentes]

            # Cria apenas os que ainda não existem
            faltantes = [m for m in modulos_fixos if m not in nomes_existentes]
            for nome in faltantes:
                cursor.execute(
                    "INSERT INTO produtos (nome, status, ultimo_acesso) VALUES (%s, 'Pronto', NULL)",
                    (nome,),
                )
            if faltantes:
                conn.commit()

            # Agora busca apenas os 6 fixos
            cursor.execute("""
                SELECT id, nome, status, ultimo_acesso
                FROM produtos
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

            # Limpa e exibe
            self.tabela_modulos.setRowCount(len(produtos))
            for i, p in enumerate(produtos):
                self.tabela_modulos.setItem(i, 0, QtWidgets.QTableWidgetItem(p["nome"]))

                combo = QtWidgets.QComboBox()
                combo.addItems(["Pronto", "Atualizando", "Em Desenvolvimento"])
                combo.setCurrentText(p["status"])
                combo.currentTextChanged.connect(lambda status, pid=p["id"]: self.atualizar_status(pid, status))
                self.tabela_modulos.setCellWidget(i, 1, combo)

                data_fmt = datetime.strftime(p["ultimo_acesso"], "%d/%m/%Y %H:%M") if p["ultimo_acesso"] else "-"
                self.tabela_modulos.setItem(i, 2, QtWidgets.QTableWidgetItem(data_fmt))

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao carregar módulos:\n{e}")

    def atualizar_status(self, produto_id, novo_status):
        try:
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("UPDATE produtos SET status=%s WHERE id=%s", (novo_status, produto_id))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao atualizar status:\n{e}")
