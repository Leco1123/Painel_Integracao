import json
import uuid
from database import conectar

# Nome do arquivo JSON com os dados que você me mandou
# Salva aquele JSON que você me passou como "empresas_integracao.json"
ARQUIVO_JSON = "empresas_integracao.json"

# Nome do banco que você criou
NOME_DB = "sistema_integracao"


def importar_json():
    # 1. Ler o arquivo JSON
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            empresas_data = json.load(f)
    except Exception as e:
        print("❌ Erro lendo o JSON:", e)
        return

    print(f"📂 Carregadas {len(empresas_data)} empresas do JSON")

    # 2. Conectar no banco
    try:
        conn = conectar()
    except Exception as e:
        print("❌ Erro conectando no banco via conectar():", e)
        return

    try:
        cur = conn.cursor()

        # 2.1 Garantir que estamos usando o banco certo
        cur.execute(f"USE {NOME_DB};")

        # 3. Inserir cada empresa e suas tarefas
        for empresa in empresas_data:
            empresa_id = empresa.get("id") or str(uuid.uuid4())
            nome_empresa = (empresa.get("empresa") or "").strip()
            cod = (empresa.get("cod") or "").strip()
            cod_athenas = (empresa.get("cod_athenas") or "").strip()
            top10_flag = 1 if empresa.get("top10", False) else 0
            prioridade_empresa = (empresa.get("prioridade") or "Média").strip()

            # 3.1 Inserir empresa
            # OBS: Se a empresa já existir (mesmo id), a gente ignora o erro e segue
            try:
                cur.execute("""
                    INSERT INTO empresas_integracao
                    (id, empresa, cod, cod_athenas, top10, prioridade_empresa)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    empresa_id,
                    nome_empresa,
                    cod,
                    cod_athenas,
                    top10_flag,
                    prioridade_empresa
                ))
            except Exception as e:
                print(f"⚠️ Aviso: não consegui inserir empresa '{nome_empresa}' ({empresa_id}). "
                      f"Pode já existir. Detalhe: {e}")

            # 3.2 Inserir tarefas dessa empresa
            tarefas = empresa.get("tarefas", [])
            for tarefa in tarefas:
                p1 = (tarefa.get("p1") or "").strip()
                p2 = (tarefa.get("p2") or "").strip()
                tipo = (tarefa.get("tipo") or "").strip()            # Ex: "LFS"
                status = (tarefa.get("status") or "Pendente").strip()  # Ex: "Pendente"
                prioridade_tarefa = (tarefa.get("prioridade") or "Média").strip()  # Ex: "TOP 10"
                mes = (tarefa.get("mes") or "").strip()               # Ex: "2025-10" (ou vazio no JSON)

                if tipo == "":
                    print(f"⚠️ Pulando tarefa sem tipo para empresa {nome_empresa}")
                    continue

                cur.execute("""
                    INSERT INTO tarefas_integracao
                    (empresa_id, p1, p2, tipo, status, prioridade_tarefa, mes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    empresa_id,
                    p1,
                    p2,
                    tipo,
                    status,
                    prioridade_tarefa,
                    mes
                ))

        # 4. Confirmar
        conn.commit()
        print("✅ Importação concluída e salva no banco!")

    except Exception as e:
        print("💥 Erro geral durante a importação:", e)
        conn.rollback()

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


if __name__ == "__main__":
    importar_json()
