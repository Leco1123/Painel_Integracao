# controle_integracao/editar_tarefa.py
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from . import integracao_db

DIALOG_STYLE = """
QDialog {
    background-color: #1b1e2b;
    color: white;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QLabel {
    color: #4ecca3;
    font-weight: bold;
}
QLineEdit, QComboBox {
    background-color: #10121B;
    color: #ffffff;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    padding: 4px;
}
QPushButton {
    background-color: #4ecca3;
    color: #000000;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton:hover {
    background-color: #6eecc1;
}
"""

class PopupEditarTarefa(QtWidgets.QDialog):
    def __init__(self, tarefa_id, usuario_logado, parent=None, on_save=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Editar Tarefa")
        self.setStyleSheet(DIALOG_STYLE)
        self.setFixedSize(780, 480)

        self.tarefa_id = tarefa_id
        self.usuario_logado = usuario_logado  # nome do cara logado p/ auditoria
        self.on_save = on_save

        dados = integracao_db.get_tarefa(tarefa_id)
        if not dados:
            QtWidgets.QMessageBox.critical(self, "Erro", "Tarefa não encontrada.")
            self.reject()
            return

        empresas = integracao_db.listar_empresas()
        self.meses_existentes = sorted(set(integracao_db.listar_meses_existentes() + ([dados["mes"]] if dados["mes"] else [])))
        self.responsaveis = integracao_db.listar_responsaveis()
        self.tipos_existentes = sorted(set(integracao_db.listar_tipos_existentes() + ([dados["tipo"]] if dados["tipo"] else [])))

        # map helpers iguais ao adicionar
        self.empresa_cod_map = {}
        self.map_por_cod = {}
        self.map_por_ath = {}

        for e in empresas:
            nome_emp = e["empresa"] or ""
            cod_emp = e["cod"] or ""
            ath_emp = e["cod_athenas"] or ""
            self.empresa_cod_map.setdefault(nome_emp, []).append((cod_emp, ath_emp))
            if cod_emp:
                self.map_por_cod[cod_emp] = {"empresa": nome_emp, "cod_athenas": ath_emp}
            if ath_emp:
                self.map_por_ath[ath_emp] = {"empresa": nome_emp, "cod": cod_emp}

        root = QtWidgets.QGridLayout(self)

        # coluna esquerda
        col_esq = QtWidgets.QVBoxLayout()

        lbl_empresa = QtWidgets.QLabel("Empresa:")
        self.cb_empresa = QtWidgets.QComboBox()
        self.cb_empresa.setEditable(True)
        self.cb_empresa.addItems(sorted(self.empresa_cod_map.keys()))
        self.cb_empresa.setCurrentText(dados["empresa"])

        lbl_cod = QtWidgets.QLabel("Cód:")
        self.cb_cod = QtWidgets.QComboBox()
        self.cb_cod.setEditable(True)
        self.cb_cod.addItems(sorted(self.map_por_cod.keys()))
        self.cb_cod.setCurrentText(dados["cod"] or "")

        lbl_cod_ath = QtWidgets.QLabel("Cód Athenas:")
        self.cb_cod_ath = QtWidgets.QComboBox()
        self.cb_cod_ath.setEditable(True)
        self.cb_cod_ath.addItems(sorted(self.map_por_ath.keys()))
        self.cb_cod_ath.setCurrentText(dados["cod_athenas"] or "")

        lbl_mes = QtWidgets.QLabel("Mês (YYYY-MM):")
        self.cb_mes = QtWidgets.QComboBox()
        self.cb_mes.setEditable(True)
        self.cb_mes.addItems(self.meses_existentes)
        self.cb_mes.setCurrentText(dados["mes"] or "")

        col_esq.addWidget(lbl_empresa)
        col_esq.addWidget(self.cb_empresa)
        col_esq.addWidget(lbl_cod)
        col_esq.addWidget(self.cb_cod)
        col_esq.addWidget(lbl_cod_ath)
        col_esq.addWidget(self.cb_cod_ath)
        col_esq.addWidget(lbl_mes)
        col_esq.addWidget(self.cb_mes)

        # coluna direita
        col_dir = QtWidgets.QVBoxLayout()

        lbl_p1 = QtWidgets.QLabel("P1:")
        self.cb_p1 = QtWidgets.QComboBox()
        self.cb_p1.setEditable(True)
        self.cb_p1.addItems(self.responsaveis)
        self.cb_p1.setCurrentText(dados["p1"] or "")

        lbl_p2 = QtWidgets.QLabel("P2:")
        self.cb_p2 = QtWidgets.QComboBox()
        self.cb_p2.setEditable(True)
        self.cb_p2.addItems(self.responsaveis)
        self.cb_p2.setCurrentText(dados["p2"] or "")

        lbl_tipo = QtWidgets.QLabel("Tipo / Obrigação:")
        self.cb_tipo = QtWidgets.QComboBox()
        self.cb_tipo.setEditable(True)
        self.cb_tipo.addItems(self.tipos_existentes if self.tipos_existentes else ["LFS", "GPS", "TRI"])
        self.cb_tipo.setCurrentText(dados["tipo"] or "")

        lbl_prioridade = QtWidgets.QLabel("Prioridade da Tarefa:")
        self.cb_prioridade = QtWidgets.QComboBox()
        self.cb_prioridade.addItems(["TOP 10", "Alta", "Média", "Baixa"])
        self.cb_prioridade.setCurrentText(dados["prioridade_tarefa"] or "Média")

        lbl_status = QtWidgets.QLabel("Status:")
        self.cb_status = QtWidgets.QComboBox()
        self.cb_status.addItems(["Pendente", "Concluída"])
        self.cb_status.setCurrentText(dados["status"] or "Pendente")

        col_dir.addWidget(lbl_p1)
        col_dir.addWidget(self.cb_p1)
        col_dir.addWidget(lbl_p2)
        col_dir.addWidget(self.cb_p2)
        col_dir.addWidget(lbl_tipo)
        col_dir.addWidget(self.cb_tipo)
        col_dir.addWidget(lbl_prioridade)
        col_dir.addWidget(self.cb_prioridade)
        col_dir.addWidget(lbl_status)
        col_dir.addWidget(self.cb_status)

        root.addLayout(col_esq, 0, 0)
        root.addLayout(col_dir, 0, 1)

        # rodapé
        footer = QtWidgets.QHBoxLayout()
        self.btn_cancelar = QtWidgets.QPushButton("Cancelar")
        self.btn_salvar = QtWidgets.QPushButton("💾 Salvar Alterações")
        footer.addStretch()
        footer.addWidget(self.btn_cancelar)
        footer.addWidget(self.btn_salvar)
        root.addLayout(footer, 1, 0, 1, 2)

        # binds
        self.cb_empresa.currentTextChanged.connect(self._empresa_changed)
        self.cb_cod.currentTextChanged.connect(self._cod_changed)
        self.cb_cod_ath.currentTextChanged.connect(self._ath_changed)

        self.btn_cancelar.clicked.connect(self.reject)
        self.btn_salvar.clicked.connect(self._salvar)

    def _empresa_changed(self):
        emp = self.cb_empresa.currentText().strip()
        lista = self.empresa_cod_map.get(emp)
        if not lista:
            return
        if len(lista) == 1:
            cod, ath = lista[0]
            self.cb_cod.setCurrentText(cod)
            self.cb_cod_ath.setCurrentText(ath)
        else:
            cods = [c for c, _ in lista]
            athenas_list = [a for _, a in lista]
            self.cb_cod.clear()
            self.cb_cod.addItems(cods)
            self.cb_cod.setCurrentText(cods[0] if cods else "")
            self.cb_cod_ath.clear()
            self.cb_cod_ath.addItems(athenas_list)
            self.cb_cod_ath.setCurrentText(athenas_list[0] if athenas_list else "")

    def _cod_changed(self):
        c = self.cb_cod.currentText().strip()
        info = self.map_por_cod.get(c)
        if info:
            self.cb_empresa.setCurrentText(info["empresa"])
            self.cb_cod_ath.setCurrentText(info["cod_athenas"])

    def _ath_changed(self):
        a = self.cb_cod_ath.currentText().strip()
        info = self.map_por_ath.get(a)
        if info:
            self.cb_empresa.setCurrentText(info["empresa"])
            self.cb_cod.setCurrentText(info["cod"])

    def _salvar(self):
        empresa_nome = self.cb_empresa.currentText().strip()
        cod = self.cb_cod.currentText().strip()
        cod_ath = self.cb_cod_ath.currentText().strip()
        mes = self.cb_mes.currentText().strip()
        p1 = self.cb_p1.currentText().strip()
        p2 = self.cb_p2.currentText().strip()
        tipo = self.cb_tipo.currentText().strip()
        prioridade_tarefa = self.cb_prioridade.currentText().strip()
        status = self.cb_status.currentText().strip()

        if not empresa_nome or not cod or not tipo:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Preencha pelo menos Empresa, Cód e Tipo.")
            return

        prioridade_empresa = "Média"
        top10_flag = 1 if prioridade_tarefa == "TOP 10" else 0

        empresa_id = integracao_db.garantir_empresa(
            empresa_nome=empresa_nome,
            cod=cod,
            cod_athenas=cod_ath,
            prioridade_empresa=prioridade_empresa,
            top10_flag=top10_flag
        )

        integracao_db.atualizar_tarefa(
            tarefa_id=self.tarefa_id,
            empresa_id=empresa_id,
            mes=mes,
            tipo=tipo,
            p1=p1,
            p2=p2,
            prioridade_tarefa=prioridade_tarefa,
            status=status,
            usuario_responsavel=self.usuario_logado
        )

        QtWidgets.QMessageBox.information(self, "Sucesso", "Tarefa atualizada!")
        if self.on_save:
            self.on_save()

        self.accept()
