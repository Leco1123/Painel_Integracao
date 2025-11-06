import tkinter as tk
from tkinter import messagebox
from database import conectar
import os
import subprocess


# === ESTILO GLOBAL ===
BG_MAIN = "#10121B"
BG_CARD = "#1b1e2b"
BORDER_CARD = "#2a2a4a"
TXT_NORMAL = "#ffffff"
TXT_TITLE = "#4ecca3"
BTN_BG_OK = "#4ecca3"
BTN_BG_HOVER = "#6eecc1"
BTN_TXT_DARK = "#000000"

FONT_NORMAL = ("Segoe UI", 11)
FONT_BOLD = ("Segoe UI", 12, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")


def abrir_manuais(parent_qt):
    """
    Janela principal do módulo Manuais.
    - Garante que o módulo está com status 'Pronto'
    - Abre botões: CFOP, Lanç. Fiscal, Manual da Integração (PDF)
    - Cada botão abre uma subjanela com divisor arrastável e scrollbars
    """

    # 1. checar status "Manuais"
    try:
        conn = conectar()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT status FROM produtos WHERE nome = 'Manuais'")
        row = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        print("ERRO DB abrir_manuais status:", e)
        messagebox.showerror("Erro", f"Erro ao verificar status do módulo:\n{e}")
        return

    if not row:
        messagebox.showerror("Erro", "Módulo 'Manuais' não encontrado no banco.")
        return

    status_mod = (row["status"] or "").strip().lower()
    if status_mod != "pronto":
        messagebox.showwarning(
            "Acesso bloqueado",
            f"O módulo 'Manuais' está com status '{row['status']}'.\n"
            "Ele só pode ser aberto quando estiver marcado como 'Pronto'."
        )
        return

    # ==========================
    # 2. janela principal
    # ==========================
    root = tk.Toplevel()
    root.title("📚 Manuais do Sistema")
    root.geometry("750x650")
    root.configure(bg=BG_MAIN)
    root.resizable(False, False)

    tk.Label(
        root,
        text="Manuais e Materiais de Apoio",
        font=FONT_TITLE,
        fg=TXT_TITLE,
        bg=BG_MAIN
    ).pack(pady=(20, 5))

    tk.Label(
        root,
        text="Escolha o material que deseja consultar",
        font=("Segoe UI", 10),
        fg=TXT_NORMAL,
        bg=BG_MAIN
    ).pack(pady=(0, 15))

    # ==========================
    # FUNÇÕES AUXILIARES GERAIS
    # ==========================

    def registrar_acesso(item_nome, categoria):
        """Salva/atualiza histórico de uso por item."""
        try:
            conn_h = conectar()
            cur_h = conn_h.cursor()
            cur_h.execute("""
                INSERT INTO historico_manuais (nome_item, tipo, acessos, ultimo_acesso)
                VALUES (%s, %s, 1, NOW())
                ON DUPLICATE KEY UPDATE acessos = acessos + 1, ultimo_acesso = NOW();
            """, (item_nome, categoria))
            conn_h.commit()
            cur_h.close()
            conn_h.close()
        except Exception as e:
            print("ERRO registrar_acesso:", e)
            messagebox.showerror("Erro", f"Erro ao registrar acesso:\n{e}")

    def carregar_top_usados(categoria):
        """Retorna lista de dicts {nome_item, acessos} ordenada."""
        try:
            conn_t = conectar()
            cur_t = conn_t.cursor(dictionary=True)
            cur_t.execute("""
                SELECT nome_item, acessos
                FROM historico_manuais
                WHERE tipo = %s
                ORDER BY acessos DESC, ultimo_acesso DESC
                LIMIT 10;
            """, (categoria,))
            dados = cur_t.fetchall()
            cur_t.close()
            conn_t.close()
            return dados
        except Exception as e:
            print("ERRO carregar_top_usados:", e)
            messagebox.showerror("Erro", f"Erro ao carregar Top Usados:\n{e}")
            return []

    def limpar_top_usados(categoria):
        try:
            conn_d = conectar()
            cur_d = conn_d.cursor()
            cur_d.execute("DELETE FROM historico_manuais WHERE tipo = %s", (categoria,))
            conn_d.commit()
            cur_d.close()
            conn_d.close()
            messagebox.showinfo("Limpeza concluída", f"Top usados de '{categoria}' limpo!")
        except Exception as e:
            print("ERRO limpar_top_usados:", e)
            messagebox.showerror("Erro", f"Erro ao limpar Top Usados:\n{e}")

    # ==========================
    # FUNÇÃO: abrir categoria (CFOP / Lanç. Fiscal)
    # ==========================

    def abrir_categoria_window(titulo, categoria_db):
        """
        Cria uma janela:
        - lado esquerdo: busca + resultados (scroll Y e X)
        - lado direito: Top usados (scroll Y)
        - rodapé: Voltar + Limpar Top Usados
        - divisor arrastável (PanedWindow)
        """

        print(f"[DEBUG] Abrindo categoria {categoria_db}...")

        # Carrega dados da categoria (manuais_conteudo)
        try:
            conn_c = conectar()
            cur_c = conn_c.cursor(dictionary=True)
            cur_c.execute("""
                SELECT campo1, campo2, campo3, campo4, campo5
                FROM manuais_conteudo
                WHERE categoria = %s
                ORDER BY id ASC;
            """, (categoria_db,))
            registros = cur_c.fetchall()
            cur_c.close()
            conn_c.close()
        except Exception as e:
            print("ERRO abrir_categoria_window SELECT manuais_conteudo:", e)
            messagebox.showerror("Erro", f"Erro ao carregar dados do banco:\n{e}")
            return

        # Cria subjanela
        sub = tk.Toplevel(root)
        sub.title(titulo)
        sub.geometry("1100x720")
        sub.configure(bg=BG_MAIN)
        # permitir redimensionar essa janela
        sub.resizable(True, True)

        # PanedWindow com divisor arrastável
        paned = tk.PanedWindow(
            sub,
            orient="horizontal",
            sashrelief="raised",
            sashwidth=6,
            bg=BG_MAIN,
            bd=0,
            relief="flat",
            opaqueresize=False
        )
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # LEFT - Lista principal
        left_frame_outer = tk.Frame(
            paned,
            bg=BG_CARD,
            highlightbackground=BORDER_CARD,
            highlightthickness=1,
            bd=0,
            relief="flat"
        )
        paned.add(left_frame_outer, minsize=400)  # minsize protege de fechar demais

        # RIGHT - Top usados
        right_frame_outer = tk.Frame(
            paned,
            bg=BG_CARD,
            highlightbackground=BORDER_CARD,
            highlightthickness=1,
            bd=0,
            relief="flat"
        )
        paned.add(right_frame_outer, minsize=300)

        # -----------------------
        # LEFT CONTENT
        # -----------------------
        tk.Label(
            left_frame_outer,
            text=titulo,
            font=FONT_BOLD,
            fg=TXT_TITLE,
            bg=BG_CARD
        ).pack(pady=(10, 5), padx=10, anchor="w")

        entry_busca = tk.Entry(
            left_frame_outer,
            font=FONT_NORMAL,
            bg="#1f2333",
            fg=TXT_NORMAL,
            insertbackground=TXT_NORMAL,
            relief="flat"
        )
        entry_busca.pack(fill="x", padx=10, pady=(5, 8))

        # frame que segura listbox + scrollbars
        frame_lista = tk.Frame(left_frame_outer, bg=BG_CARD)
        frame_lista.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        scroll_y = tk.Scrollbar(frame_lista, orient="vertical")
        scroll_x = tk.Scrollbar(frame_lista, orient="horizontal")

        listbox = tk.Listbox(
            frame_lista,
            bg="#1f2333",
            fg=TXT_NORMAL,
            font=("Segoe UI", 10),
            selectbackground=TXT_TITLE,
            selectforeground="#000000",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_CARD,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            activestyle="none"
        )
        # pack listbox first so we can attach scrollbars
        listbox.pack(fill="both", expand=True)

        # agora empacota as scrollbars
        scroll_y.config(command=listbox.yview)
        scroll_y.pack(side="right", fill="y")

        scroll_x.config(command=listbox.xview)
        scroll_x.pack(side="bottom", fill="x")

        # Montar linhas em texto
        def montar_texto(row_dict):
            partes = []
            for campo in ["campo1", "campo2", "campo3", "campo4", "campo5"]:
                valor = row_dict.get(campo)
                if valor and str(valor).strip():
                    partes.append(str(valor))
            return " | ".join(partes)

        itens_formatados = [montar_texto(r) for r in registros]

        def atualizar_lista(*_):
            termo = entry_busca.get().lower()
            listbox.delete(0, tk.END)
            for item in itens_formatados:
                if termo in item.lower():
                    listbox.insert(tk.END, item)

        entry_busca.bind("<KeyRelease>", atualizar_lista)
        atualizar_lista()

        def on_double_click(_evt):
            if not listbox.curselection():
                return
            escolhido = listbox.get(listbox.curselection()[0])
            registrar_acesso(escolhido, categoria_db)
            atualizar_top()

        listbox.bind("<Double-Button-1>", on_double_click)

        # -----------------------
        # RIGHT CONTENT (Top usados)
        # -----------------------
        tk.Label(
            right_frame_outer,
            text="Top usados",
            font=FONT_BOLD,
            fg=TXT_TITLE,
            bg=BG_CARD
        ).pack(pady=(10, 5), padx=10, anchor="w")

        frame_top = tk.Frame(right_frame_outer, bg=BG_CARD)
        frame_top.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        scroll_top_y = tk.Scrollbar(frame_top, orient="vertical")
        scroll_top_y.pack(side="right", fill="y")

        list_top = tk.Listbox(
            frame_top,
            bg="#1f2333",
            fg=TXT_NORMAL,
            font=("Segoe UI", 10),
            selectbackground=TXT_TITLE,
            selectforeground="#000000",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_CARD,
            yscrollcommand=scroll_top_y.set,
            activestyle="none"
        )
        list_top.pack(fill="both", expand=True)
        scroll_top_y.config(command=list_top.yview)

        def atualizar_top():
            list_top.delete(0, tk.END)
            rows_top = carregar_top_usados(categoria_db)
            if not rows_top:
                list_top.insert(tk.END, "Nenhum acesso ainda")
            else:
                for r in rows_top:
                    list_top.insert(tk.END, f"{r['nome_item']} ({r['acessos']}x)")

        atualizar_top()

        # -----------------------
        # FOOTER (Voltar / Limpar)
        # -----------------------
        footer = tk.Frame(sub, bg=BG_MAIN)
        footer.pack(fill="x", pady=(0, 12))

        def voltar():
            sub.destroy()

        btn_voltar = tk.Button(
            footer,
            text="Voltar",
            font=FONT_BOLD,
            fg=BTN_TXT_DARK,
            bg=BTN_BG_OK,
            activebackground=BTN_BG_HOVER,
            bd=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=voltar
        )
        btn_voltar.pack(side="right", padx=10)

        btn_limpar = tk.Button(
            footer,
            text="Limpar Top Usados",
            font=FONT_BOLD,
            fg="white",
            bg="#d63031",
            activebackground="#ff4d4d",
            bd=0,
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=lambda: [limpar_top_usados(categoria_db), atualizar_top()]
        )
        btn_limpar.pack(side="right", padx=10)

    # ==========================
    # ABERTURAS PRINCIPAIS
    # ==========================

    def abrir_manual_integracao():
        pdf_path = os.path.join(os.path.dirname(__file__), "Manual_Integracao.pdf")
        if os.path.exists(pdf_path):
            try:
                if os.name == "nt":
                    os.startfile(pdf_path)
                else:
                    subprocess.Popen(["xdg-open", pdf_path])
            except Exception as e:
                print("ERRO abrir_manual_integracao:", e)
                messagebox.showerror("Erro", f"Erro ao abrir manual:\n{e}")
        else:
            messagebox.showerror("Erro", "Manual_Integracao.pdf não encontrado.")

    def botao(nome_exibido, comando, cor=BTN_BG_OK):
        btn = tk.Button(
            root,
            text=nome_exibido,
            font=FONT_BOLD,
            fg=BTN_TXT_DARK,
            bg=cor,
            activebackground=BTN_BG_HOVER,
            bd=0,
            relief="flat",
            width=30,
            pady=8,
            cursor="hand2",
            command=comando
        )
        btn.pack(pady=8)
        return btn

    botao("CFOP", lambda: abrir_categoria_window("CFOP", "CFOP"))
    botao("Lanç. Fiscal", lambda: abrir_categoria_window("Lanç. Fiscal", "LANC_FISCAL"))
    botao("Manual da Integração (PDF)", abrir_manual_integracao, cor="#0984e3")

    # ================================================================
    # 🔙 BOTÃO VOLTAR PARA O PAINEL PRINCIPAL
    # ================================================================
    def voltar_para_painel():
        """Fecha o módulo Manuais e volta para o painel principal."""
        try:
            root.destroy()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao voltar para o painel:\n{e}")

    btn_voltar = tk.Button(
        root,
        text="⬅ Voltar ao Painel Principal",
        font=FONT_BOLD,
        fg="white",
        bg="#d63031",
        activebackground="#ff4d4d",
        bd=0,
        relief="flat",
        width=30,
        pady=8,
        cursor="hand2",
        command=voltar_para_painel
    )
    btn_voltar.pack(pady=(20, 10))


    # Status rodapé
    tk.Label(
        root,
        text="🟢 Conectado • Dados do banco",
        font=("Segoe UI", 9),
        fg=TXT_NORMAL,
        bg=BG_MAIN
    ).pack(side="bottom", pady=10)
