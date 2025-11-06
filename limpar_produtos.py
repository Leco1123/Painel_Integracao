from database import conectar

def limpar_produtos():
    """Remove módulos duplicados sem data e garante que existam apenas os 6 fixos."""
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
        cursor = conn.cursor()

        # Remove registros duplicados ou sem data
        cursor.execute("""
            DELETE FROM produtos
            WHERE ultimo_acesso IS NULL
              AND nome IN (
                'Controle da Integração',
                'Macro da Regina',
                'Macro da Folha',
                'Macro do Fiscal',
                'Formatador de Balancete',
                'Manuais'
              );
        """)
        conn.commit()

        # Garante que todos os 6 módulos fixos existam
        for nome in modulos_fixos:
            cursor.execute("SELECT COUNT(*) FROM produtos WHERE nome = %s", (nome,))
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute(
                    "INSERT INTO produtos (nome, status, ultimo_acesso) VALUES (%s, 'Pronto', NOW())",
                    (nome,),
                )
                print(f"✅ Criado módulo ausente: {nome}")

        conn.commit()

        # Cria índice único no nome (impede duplicação futura)
        try:
            cursor.execute("ALTER TABLE produtos ADD UNIQUE INDEX idx_nome_unico (nome);")
            conn.commit()
            print("🔒 Índice único criado com sucesso (nome).")
        except Exception as e:
            if "Duplicate key name" in str(e):
                print("ℹ️ Índice único já existe, tudo certo.")
            else:
                raise e

        cursor.close()
        conn.close()
        print("\n🧹 Limpeza concluída com sucesso! Módulos duplicados removidos e estrutura protegida.")

    except Exception as e:
        print(f"❌ Erro ao limpar produtos: {e}")


if __name__ == "__main__":
    limpar_produtos()
