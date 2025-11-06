# manuais_bridge.py

import threading
from PySide6 import QtWidgets
from database import conectar
from tkinter import messagebox, Tk
import manuais  # seu módulo que tem abrir_manuais()


def checar_status_modulo(nome_modulo: str) -> str | None:
    """
    Retorna o status atual do módulo no banco ou None se não achar.
    """
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT status FROM produtos WHERE nome = %s", (nome_modulo,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return None
        return row["status"]
    except Exception as e:
        print(f"Erro ao checar status do módulo {nome_modulo}: {e}")
        return None


def abrir_manuais_via_qt(parent_qt_widget: QtWidgets.QWidget):
    """
    Chamado pelo botão 'Manuais' do painel (Qt).
    - Valida status no banco.
    - Se ok, abre o Tkinter em uma thread separada.
    - Se não ok, avisa pro usuário no próprio Qt.
    """

    status = checar_status_modulo("Manuais")
    print(f"[bridge] Status do módulo 'Manuais' = {status}")

    if status is None:
        QtWidgets.QMessageBox.critical(
            parent_qt_widget,
            "Erro",
            "Módulo 'Manuais' não encontrado no banco."
        )
        return

    if status.strip().lower() != "pronto":
        # se não estiver pronto -> mostra aviso estilo sistema
        QtWidgets.QMessageBox.warning(
            parent_qt_widget,
            "Acesso bloqueado",
            (
                f"O módulo 'Manuais' está com status:\n"
                f"{status}\n\n"
                "Ele só pode ser aberto quando estiver marcado como 'Pronto'."
            )
        )
        return

    # Se chegou aqui = pode abrir
    # Agora vem o pulo do gato:
    # - Tkinter precisa rodar seu próprio mainloop.
    # - Se a gente rodar direto, ele congela o PySide6.
    # -> Solução: rodar Tkinter em outra thread.
    def run_tk():
        # cria raiz Tk só se ainda não existir
        root = Tk()
        root.withdraw()  # esconde a janela raiz
        # abre a janela de manuais usando o Tk root como parent
        manuais.abrir_manuais(root)
        root.mainloop()

    threading.Thread(target=run_tk, daemon=True).start()
