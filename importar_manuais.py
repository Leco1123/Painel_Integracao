import csv
from database import conectar

# Ajuste aqui os nomes dos arquivos que você já tem
ARQUIVOS = [
    {
        "categoria": "CFOP",
        "arquivo": "Tabela_CFOP.csv"
    },
    {
        "categoria": "LANC_FISCAL",
        "arquivo": "Tabela_Lanc_Fisc.csv"
    }
]


def importar_csv_para_banco():
    conn = conectar()
    cursor = conn.cursor()

    for item in ARQUIVOS:
        categoria = item["categoria"]
        caminho = item["arquivo"]

        print(f"📥 Importando '{caminho}' como categoria '{categoria}'")

        # apaga dados antigos dessa categoria pra não duplicar
        cursor.execute("DELETE FROM manuais_conteudo WHERE categoria = %s", (categoria,))

        with open(caminho, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                # row é uma lista com as colunas do CSV.
                # vamos enfiar até 5 colunas por linha, completando com None
                c1 = row[0] if len(row) > 0 else None
                c2 = row[1] if len(row) > 1 else None
                c3 = row[2] if len(row) > 2 else None
                c4 = row[3] if len(row) > 3 else None
                c5 = row[4] if len(row) > 4 else None

                cursor.execute(
                    """
                    INSERT INTO manuais_conteudo
                    (categoria, campo1, campo2, campo3, campo4, campo5)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (categoria, c1, c2, c3, c4, c5)
                )

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Importação finalizada com sucesso!")


if __name__ == "__main__":
    importar_csv_para_banco()
