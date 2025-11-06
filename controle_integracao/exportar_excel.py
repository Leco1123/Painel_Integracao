# controle_integracao/exportar_excel.py
import pandas as pd
from PySide6 import QtWidgets
from . import integracao_db

def exportar_excel(parent=None, filtro_mes=None):
    dados = integracao_db.export_raw(filtro_mes=filtro_mes)
    if not dados:
        QtWidgets.QMessageBox.information(parent, "Exportar", "Não há dados para exportar.")
        return

    df = pd.DataFrame(dados)

    caminho, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent,
        "Salvar Relatório Excel",
        "relatorio_integracao.xlsx",
        "Planilha Excel (*.xlsx)"
    )
    if not caminho:
        return

    try:
        df.to_excel(caminho, index=False)
        QtWidgets.QMessageBox.information(parent, "Exportar", "Relatório exportado com sucesso!")
    except Exception as e:
        QtWidgets.QMessageBox.critical(parent, "Erro", f"Erro ao salvar Excel:\n{e}")
