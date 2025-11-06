import os, sys, logging
from datetime import datetime
import pandas as pd
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QVBoxLayout, QWidget, QDialog, QLabel,
    QComboBox, QMessageBox, QFileDialog
)
from controle_integracao.dao import TarefasDAO

# Caminho absoluto da pasta atual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Garante a existência da pasta de logs
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

# Configuração global de log
logging.basicConfig(
    filename=os.path.join(BASE_DIR, "logs", "integracao.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --------------------------
# THREAD DE CARREGAMENTO
# --------------------------
class LoaderThread(QThread):
    data_loaded = Signal(list)

    def run(self):
        try:
            dados = TarefasDAO.listar_tarefas()
            self.data_loaded.emit(dados)
        except Exception as e:
            logging.error(f"Erro ao carregar tarefas: {e}")
            self.data_loaded.emit([])


# --------------------------
# POPUP DE FILTROS
# --------------------------
class FiltroDialog(QDialog):
    def __init__(self, parent=None, empresas=None, meses=None):
        super().__init__(parent)
        self.setWindowTitle("Filtrar Tarefas")

        # Aplica estilo
        style_path = os.path.join(BASE_DIR, "styles.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            self.setStyleSheet("""
                QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
                QPushButton { background-color: #4ecca3; color: black; font-weight: bold; border-radius: 6px; }
                QLabel { color: #4ecca3; font-weight: bold; }
            """)

        layout = QVBoxLayout(self)

        def linha_rotulo(texto, widget):
            row = QHBoxLayout()
            row.addWidget(QLabel(texto))
            row.addWidget(widget)
            layout.addLayout(row)

        self.cb_empresa = QComboBox()
        self.cb_empresa.addItem("Todos", userData="Todos")
        for emp in empresas:
            self.cb_empresa.addItem(f"{emp['empresa']} ({emp['cod']})", userData=emp["id"])

        self.cb_status = QComboBox()
        self.cb_status.addItems(["Todos", "Pendente", "Concluída"])

        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(["Todos", "LFS", "GPS", "TRI"])

        self.cb_mes = QComboBox()
        self.cb_mes.addItem("Todos", userData="Todos")
        for m in meses:
            self.cb_mes.addItem(m, userData=m)

        linha_rotulo("Empresa:", self.cb_empresa)
        linha_rotulo("Status:", self.cb_status)
        linha_rotulo("Tipo:", self.cb_tipo)
        linha_rotulo("Mês:", self.cb_mes)

        btns = QHBoxLayout()
        btn_voltar = QPushButton("Voltar")
        btn_voltar.setObjectName("Secondary")
        btn_aplicar = QPushButton("Aplicar")
        btns.addStretch()
        btns.addWidget(btn_voltar)
        btns.addWidget(btn_aplicar)
        layout.addLayout(btns)

        btn_voltar.clicked.connect(self.reject)
        btn_aplicar.clicked.connect(self.accept)

    def get_filtros(self):
        return {
            "empresa_id": self.cb_empresa.currentData(),
            "status": self.cb_status.currentText(),
            "tipo": self.cb_tipo.currentText(),
            "mes": self.cb_mes.currentData()
        }

    class AdicionarDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Adicionar Tarefa")
            self.setModal(True)
            self._ok = False
            self._dados = None

            # estilo
            style_path = os.path.join(os.path.dirname(__file__), "styles.qss")
            if os.path.exists(style_path):
                with open(style_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            else:
                self.setStyleSheet("""
                    QDialog { background-color: #10121B; color: white; }
                    QLabel { color: #4ecca3; font-weight: bold; }
                    QComboBox { background-color: #10121B; color: white; border: 1px solid #3a3f58; border-radius: 6px; padding: 6px; }
                    QPushButton { background-color: #4ecca3; color: black; font-weight: bold; border-radius: 6px; padding: 6px 10px; }
                    QPushButton#Voltar { background-color: #2a2f3a; color: white; border: 1px solid #3a3f58; }
                """)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 16)
            layout.setSpacing(10)

            # --- Campos (empresas / meses / usuarios) ---
            empresas = TarefasDAO.listar_empresas()
            meses_existentes = TarefasDAO.listar_meses()
            usuarios = TarefasDAO.listar_usuarios()

            # Empresa
            row_emp = QHBoxLayout()
            row_emp.addWidget(QLabel("Empresa:"))
            self.cb_empresa = QComboBox()
            for emp in empresas:
                self.cb_empresa.addItem(f"{emp['empresa']} ({emp['cod']})", emp)
            row_emp.addWidget(self.cb_empresa)
            layout.addLayout(row_emp)

            # Mês (YYYY-MM)
            from datetime import datetime
            mes_atual = datetime.now().strftime("%Y-%m")
            meses_combo = [mes_atual] + [m for m in meses_existentes if m != mes_atual]

            row_mes = QHBoxLayout()
            row_mes.addWidget(QLabel("Mês (YYYY-MM):"))
            self.cb_mes = QComboBox()
            for m in meses_combo:
                self.cb_mes.addItem(m)
            row_mes.addWidget(self.cb_mes)
            layout.addLayout(row_mes)

            # P1 / P2
            row_p1 = QHBoxLayout()
            row_p1.addWidget(QLabel("P1:"))
            self.cb_p1 = QComboBox();
            self.cb_p1.addItems(usuarios)
            row_p1.addWidget(self.cb_p1)
            layout.addLayout(row_p1)

            row_p2 = QHBoxLayout()
            row_p2.addWidget(QLabel("P2:"))
            self.cb_p2 = QComboBox();
            self.cb_p2.addItems(usuarios)
            row_p2.addWidget(self.cb_p2)
            layout.addLayout(row_p2)

            # Tipo
            row_tipo = QHBoxLayout()
            row_tipo.addWidget(QLabel("Tipo / Obrigação:"))
            self.cb_tipo = QComboBox();
            self.cb_tipo.addItems(["GPS", "LFS", "TRI"])
            row_tipo.addWidget(self.cb_tipo)
            layout.addLayout(row_tipo)

            # Prioridade
            row_pri = QHBoxLayout()
            row_pri.addWidget(QLabel("Prioridade:"))
            self.cb_prioridade = QComboBox();
            self.cb_prioridade.addItems(["TOP 10", "Alta", "Média", "Baixa"])
            self.cb_prioridade.setCurrentText("Média")
            row_pri.addWidget(self.cb_prioridade)
            layout.addLayout(row_pri)

            # Botões
            btns = QHBoxLayout()
            self.btn_voltar = QPushButton("Voltar");
            self.btn_voltar.setObjectName("Voltar")
            self.btn_salvar = QPushButton("Salvar")
            btns.addStretch();
            btns.addWidget(self.btn_voltar);
            btns.addWidget(self.btn_salvar)
            layout.addLayout(btns)

            self.btn_voltar.clicked.connect(self.reject)
            self.btn_salvar.clicked.connect(self._on_salvar)

        def _on_salvar(self):
            emp_info = self.cb_empresa.currentData()
            if not emp_info:
                QMessageBox.warning(self, "Aviso", "Selecione a empresa.")
                return

            dados = {
                "empresa_id": emp_info["id"],
                "mes": self.cb_mes.currentText().strip(),
                "p1": self.cb_p1.currentText().strip(),
                "p2": self.cb_p2.currentText().strip(),
                "tipo": self.cb_tipo.currentText().strip(),
                "prioridade": self.cb_prioridade.currentText().strip(),
                "status": "Pendente"
            }
            if not dados["mes"]:
                QMessageBox.warning(self, "Aviso", "Informe o mês (YYYY-MM).")
                return

            self._ok = True
            self._dados = dados
            self.accept()

        def result_ok(self):
            return self._ok, self._dados


# --------------------------
# JANELA PRINCIPAL
# --------------------------
class ControleIntegracao(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.filtros_atuais = None
        self.linhas_ids = []

        self.setWindowTitle("Controle da Integração")
        self.setGeometry(250, 150, 1100, 600)

        # Aplica estilo dark
        style_path = os.path.join(BASE_DIR, "styles.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            self.setStyleSheet("""
                QWidget { background-color: #10121B; color: white; font-family: 'Segoe UI'; }
                QPushButton { background-color: #4ecca3; color: black; font-weight: bold; border-radius: 6px; }
                QLabel { color: #4ecca3; font-weight: bold; }
            """)

        self._build_ui()
        self._load_data_async()

    # --------------------------
    # THREAD DE CARREGAMENTO
    # --------------------------
    def _load_data_async(self):
        self.thread = LoaderThread()
        self.thread.data_loaded.connect(self._populate_table)
        self.thread.start()

    # --------------------------
    # TABELA
    # --------------------------
    def _populate_table(self, tarefas):
        self.tabela.setRowCount(0)
        self.linhas_ids.clear()

        for t in tarefas:
            row = self.tabela.rowCount()
            self.tabela.insertRow(row)
            empresa_item = QTableWidgetItem(t["empresa"])
            empresa_item.setData(Qt.UserRole, t["tarefa_id"])
            self.linhas_ids.append(t["empresa_id"])

            cols = [
                empresa_item,
                QTableWidgetItem(t["cod_athenas"] or ""),
                QTableWidgetItem(t["prioridade"] or ""),
                QTableWidgetItem(t["p1"] or ""),
                QTableWidgetItem(t["p2"] or "")
            ]
            for col, item in enumerate(cols):
                self.tabela.setItem(row, col, item)

            # GPS, LFS, TRI coloridos
            for i, tipo in enumerate(["GPS", "LFS", "TRI"], start=5):
                status = "Concluída" if t["tipo"] == tipo and t["status"] == "Concluída" else "Pendente"
                cor = QtGui.QColor("#4ecca3") if status == "Concluída" else QtGui.QColor("#ff5555")
                item = QTableWidgetItem(status)
                item.setForeground(QtGui.QBrush(cor))
                self.tabela.setItem(row, i, item)

        logging.info(f"{len(tarefas)} tarefas carregadas.")
        self.tabela.resizeColumnsToContents()

    # --------------------------
    # FUNÇÕES DE BANCO
    # --------------------------
    def abrir_filtro(self):
        dlg = FiltroDialog(
            parent=self,
            empresas=TarefasDAO.listar_empresas(),
            meses=TarefasDAO.listar_meses()
        )
        if dlg.exec() == QDialog.Accepted:
            self.filtros_atuais = dlg.get_filtros()
            tarefas = TarefasDAO.listar_tarefas(self.filtros_atuais)
            self._populate_table(tarefas)

    def limpar_filtros(self):
        self.filtros_atuais = None
        self._load_data_async()

    def exportar_excel(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar planilha", "controle_integracao.xlsx", "Excel (*.xlsx)"
        )
        if not caminho:
            return
        tarefas = TarefasDAO.listar_tarefas(self.filtros_atuais)
        try:
            pd.DataFrame(tarefas).to_excel(caminho, index=False)
            QMessageBox.information(self, "Sucesso", "Planilha exportada!")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            logging.error(f"Erro exportar_excel: {e}")

    def concluir_tarefa(self):
        linha = self.tabela.currentRow()
        col = self.tabela.currentColumn()
        if linha < 0 or col not in [5, 6, 7]:
            QMessageBox.warning(self, "Aviso", "Selecione GPS, LFS ou TRI.")
            return
        empresa_id = self.linhas_ids[linha]
        tipo = {5: "GPS", 6: "LFS", 7: "TRI"}[col]
        if QMessageBox.question(self, "Confirmar", f"Concluir {tipo}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            TarefasDAO.concluir_tarefa(empresa_id, tipo)
            self._load_data_async()

    def concluir_todas(self):
        linha = self.tabela.currentRow()
        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma empresa.")
            return
        empresa_id = self.linhas_ids[linha]
        if QMessageBox.question(self, "Confirmar", "Concluir todas as obrigações?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            for tipo in ["GPS", "LFS", "TRI"]:
                TarefasDAO.concluir_tarefa(empresa_id, tipo)
            self._load_data_async()

    def excluir_tarefa(self):
        linha = self.tabela.currentRow()
        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione uma tarefa para excluir.")
            return
        tarefa_id = self.tabela.item(linha, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Confirmar", "Excluir esta tarefa?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            linhas = TarefasDAO.excluir_tarefa(tarefa_id)
            if linhas:
                QMessageBox.information(self, "Sucesso", "Tarefa excluída.")
            self._load_data_async()

    # --------------------------
    # Adicionar nova tarefa
    # --------------------------
    def abrir_add(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Adicionar Tarefa")
        dlg.setModal(True)
        dlg.resize(400, 300)

        style_path = os.path.join(os.path.dirname(__file__), "styles.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                dlg.setStyleSheet(f.read())
        else:
            dlg.setStyleSheet("""
                QDialog { background-color: #10121B; color: white; }
                QLabel { color: #4ecca3; font-weight: bold; }
                QPushButton { background-color: #4ecca3; color: black; font-weight: bold; border-radius: 6px; }
            """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 15)

        # ===== CAMPOS =====
        lbl_empresa = QLabel("Empresa:")
        cb_empresa = QComboBox()
        empresas = TarefasDAO.listar_empresas()
        for emp in empresas:
            cb_empresa.addItem(f"{emp['empresa']} ({emp['cod']})", emp["id"])

        lbl_prioridade = QLabel("Prioridade:")
        cb_prioridade = QComboBox()
        cb_prioridade.addItems(["Baixa", "Média", "Alta", "TOP 10"])

        lbl_p1 = QLabel("Responsável P1:")
        txt_p1 = QtWidgets.QLineEdit()
        lbl_p2 = QLabel("Responsável P2:")
        txt_p2 = QtWidgets.QLineEdit()

        lbl_tipo = QLabel("Tipo:")
        cb_tipo = QComboBox()
        cb_tipo.addItems(["GPS", "LFS", "TRI"])

        for w in [lbl_empresa, cb_empresa, lbl_prioridade, cb_prioridade,
                  lbl_p1, txt_p1, lbl_p2, txt_p2, lbl_tipo, cb_tipo]:
            layout.addWidget(w)

        # ===== BOTÕES =====
        btns = QHBoxLayout()
        btn_voltar = QPushButton("Voltar")
        btn_salvar = QPushButton("Salvar")
        btns.addStretch()
        btns.addWidget(btn_voltar)
        btns.addWidget(btn_salvar)
        layout.addLayout(btns)

        btn_voltar.clicked.connect(dlg.reject)

        def salvar():
            empresa_id = cb_empresa.currentData()
            prioridade = cb_prioridade.currentText()
            p1 = txt_p1.text().strip()
            p2 = txt_p2.text().strip()
            tipo = cb_tipo.currentText()

            if not empresa_id or not p1 or not p2:
                QMessageBox.warning(dlg, "Aviso", "Preencha todos os campos obrigatórios!")
                return

            try:
                TarefasDAO.adicionar_tarefa(empresa_id, prioridade, p1, p2, tipo)
                QMessageBox.information(dlg, "Sucesso", "Tarefa adicionada com sucesso!")
                dlg.accept()
                self._load_data_async()
            except Exception as e:
                logging.error(f"Erro ao adicionar tarefa: {e}")
                QMessageBox.critical(dlg, "Erro", str(e))

        btn_salvar.clicked.connect(salvar)

        dlg.exec()

    # --------------------------
    # INTERFACE
    # --------------------------
    def _build_ui(self):
        root = QWidget()
        main_layout = QVBoxLayout(root)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 12)

        # ===== TÍTULO =====
        titulo = QLabel(f"Controle da Integração — {self.user['nome']}")
        titulo.setObjectName("Titulo")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            QLabel#Titulo {
                color: #4ecca3;
                font-size: 18px;
                font-weight: bold;
                padding-bottom: 8px;
            }
        """)
        main_layout.addWidget(titulo)

        # ===== WRAPPER DA TABELA =====
        tabela_container = QWidget()
        tabela_container.setStyleSheet("""
            QWidget {
                background-color: #1b1e2b;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
        """)
        tabela_layout = QVBoxLayout(tabela_container)
        tabela_layout.setContentsMargins(8, 8, 8, 8)
        tabela_layout.setSpacing(0)

        # Tabela em si
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(8)
        self.tabela.setHorizontalHeaderLabels([
            "Empresa", "Cód Athenas", "Prioridade", "P1", "P2", "GPS", "LFS", "TRI"
        ])
        self.tabela.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tabela.setStyleSheet("""
            QTableWidget {
                background-color: #1b1e2b;
                gridline-color: #2a2a4a;
                color: white;
                font-size: 12px;
                selection-background-color: #4ecca3;
                selection-color: black;
            }
            QHeaderView::section {
                background-color: #2a2f3a;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #3a3f58;
            }
        """)
        tabela_layout.addWidget(self.tabela)

        # adiciona a tabela dentro do container estilizado
        main_layout.addWidget(tabela_container, stretch=1)

        # ===== FOOTER =====
        footer_container = QWidget()
        footer_container.setStyleSheet("""
            QWidget {
                background-color: #1b1e2b;
                border: 1px solid #2a2a4a;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #4ecca3;
                color: #000;
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                filter: brightness(1.1);
            }
        """)
        footer_layout_outer = QVBoxLayout(footer_container)
        footer_layout_outer.setContentsMargins(10, 10, 10, 10)
        footer_layout_outer.setSpacing(6)

        # linha com botões (2 grupos)
        botoes_layout = QHBoxLayout()
        botoes_layout.setSpacing(10)

        # Grupo ESQUERDA = ações sobre tarefas
        grupo_esq = QHBoxLayout()
        grupo_esq.setSpacing(8)

        def botao(texto, icone=None, danger=False):
            btn = QPushButton(f"{icone + ' ' if icone else ''}{texto}")
            btn.setFixedHeight(32)
            if danger:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ff5555;
                        color: white;
                        font-weight: 600;
                        border-radius: 6px;
                        padding: 6px 10px;
                    }
                    QPushButton:hover {
                        background-color: #ff6b6b;
                    }
                """)
            return btn

        self.btn_add = botao("Adicionar", "➕")
        self.btn_edit = botao("Editar", "✏️")
        self.btn_concluir = botao("Concluir", "✅")
        self.btn_concluir_todas = botao("Concluir Todas", "✅")
        self.btn_excluir = botao("Excluir", "🗑️", danger=True)

        for b in [
            self.btn_add,
            self.btn_edit,
            self.btn_concluir,
            self.btn_concluir_todas,
            self.btn_excluir
        ]:
            grupo_esq.addWidget(b)

        # Grupo DIREITA = utilidade
        grupo_dir = QHBoxLayout()
        grupo_dir.setSpacing(8)

        self.btn_export = botao("Exportar Excel", "📊")
        self.btn_filtro = botao("Filtros", "🔍")
        self.btn_limpar = botao("Limpar", "🧹")
        self.btn_atualizar = botao("Atualizar", "🔄")

        for b in [
            self.btn_export,
            self.btn_filtro,
            self.btn_limpar,
            self.btn_atualizar
        ]:
            grupo_dir.addWidget(b)

        botoes_layout.addLayout(grupo_esq)
        botoes_layout.addStretch()
        botoes_layout.addLayout(grupo_dir)

        footer_layout_outer.addLayout(botoes_layout)

        # linha de status
        status_line = QHBoxLayout()
        status_line.addStretch()
        status_label = QLabel("🟢 Conectado ao Controle da Integração (MariaDB)")
        status_label.setStyleSheet("color: #888; font-size: 11px;")
        status_line.addWidget(status_label)
        footer_layout_outer.addLayout(status_line)

        # footer no layout principal
        main_layout.addWidget(footer_container)

        # ===== aplica no QMainWindow =====
        self.setCentralWidget(root)

        # liga sinais
        self.btn_add.clicked.connect(self.abrir_add)
        # opcional, se já tiver editar implementado:
        # self.btn_edit.clicked.connect(self.abrir_editar)

        self.btn_concluir.clicked.connect(self.concluir_tarefa)
        self.btn_concluir_todas.clicked.connect(self.concluir_todas)
        self.btn_excluir.clicked.connect(self.excluir_tarefa)
        self.btn_export.clicked.connect(self.exportar_excel)
        self.btn_filtro.clicked.connect(self.abrir_filtro)
        self.btn_limpar.clicked.connect(self.limpar_filtros)
        self.btn_atualizar.clicked.connect(self._load_data_async)
