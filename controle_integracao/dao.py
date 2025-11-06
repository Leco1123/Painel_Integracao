# dao.py
from contextlib import contextmanager
from database import conectar


# -----------------------------
# Context manager para conexão
# -----------------------------
@contextmanager
def db_cursor(dictionary=True, commit=False):
    conn = conectar()
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DAO ERRO] {e}")
        raise
    finally:
        cur.close()
        conn.close()


# -----------------------------
# Classe DAO das tarefas
# -----------------------------
class TarefasDAO:
    @staticmethod
    def listar_tarefas(filtros=None):
        base = """
            SELECT
                t.id AS tarefa_id, e.id AS empresa_id,
                e.empresa, e.cod, e.cod_athenas,
                t.prioridade_tarefa AS prioridade, t.p1, t.p2,
                t.status, t.tipo, t.mes, t.atualizado_em
            FROM tarefas_integracao t
            JOIN empresas_integracao e ON e.id = t.empresa_id
            WHERE 1=1
        """
        params = []
        if filtros:
            if filtros.get("empresa_id") and filtros["empresa_id"] != "Todos":
                base += " AND e.id = %s"; params.append(filtros["empresa_id"])
            if filtros.get("status") and filtros["status"] != "Todos":
                base += " AND t.status = %s"; params.append(filtros["status"])
            if filtros.get("tipo") and filtros["tipo"] != "Todos":
                base += " AND t.tipo = %s"; params.append(filtros["tipo"])
            if filtros.get("mes") and filtros["mes"] != "Todos":
                base += " AND t.mes = %s"; params.append(filtros["mes"])
        base += " ORDER BY t.atualizado_em DESC"

        with db_cursor() as cur:
            cur.execute(base, params)
            return cur.fetchall()

    @staticmethod
    def listar_empresas():
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, empresa, cod, cod_athenas,
                       prioridade_empresa, top10
                FROM empresas_integracao
                ORDER BY empresa ASC
            """)
            return cur.fetchall()

    @staticmethod
    def listar_usuarios():
        with db_cursor() as cur:
            cur.execute("SELECT nome FROM usuarios ORDER BY nome ASC")
            return [r["nome"] for r in cur.fetchall()]

    @staticmethod
    def listar_meses():
        with db_cursor(dictionary=False) as cur:
            cur.execute("""
                SELECT DISTINCT mes
                FROM tarefas_integracao
                WHERE mes <> ''
                ORDER BY mes DESC
            """)
            return [m[0] for m in cur.fetchall()]

    @staticmethod
    def inserir_tarefa(dados):
        with db_cursor(commit=True, dictionary=False) as cur:
            cur.execute("""
                INSERT INTO tarefas_integracao
                (empresa_id, p1, p2, tipo, status,
                 prioridade_tarefa, mes, atualizado_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
            """, (
                dados["empresa_id"],
                dados["p1"], dados["p2"], dados["tipo"],
                dados["status"], dados["prioridade"], dados["mes"]
            ))

    @staticmethod
    def atualizar_tarefa(tarefa_id, dados):
        with db_cursor(commit=True, dictionary=False) as cur:
            cur.execute("""
                UPDATE tarefas_integracao
                SET empresa_id=%s, p1=%s, p2=%s, tipo=%s,
                    status=%s, prioridade_tarefa=%s, mes=%s,
                    atualizado_em=NOW()
                WHERE id=%s
            """, (
                dados["empresa_id"], dados["p1"], dados["p2"],
                dados["tipo"], dados["status"],
                dados["prioridade"], dados["mes"], tarefa_id
            ))

    @staticmethod
    def excluir_tarefa(tarefa_id):
        with db_cursor(commit=True, dictionary=False) as cur:
            cur.execute("DELETE FROM tarefas_integracao WHERE id = %s", (tarefa_id,))
            return cur.rowcount

    @staticmethod
    def concluir_tarefa(empresa_id, tipo):
        with db_cursor(commit=True, dictionary=False) as cur:
            cur.execute("""
                UPDATE tarefas_integracao
                SET status = 'Concluída', atualizado_em = NOW()
                WHERE empresa_id = %s AND tipo = %s
            """, (empresa_id, tipo))
            return cur.rowcount

    @staticmethod
    def adicionar_tarefa(empresa_id, prioridade, p1, p2, tipo):
        conn = Database.get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tarefas_integracao (empresa_id, prioridade_tarefa, p1, p2, tipo, status, atualizado_em)
            VALUES (%s, %s, %s, %s, %s, 'Pendente', NOW())
        """, (empresa_id, prioridade, p1, p2, tipo))
        conn.commit()
        cur.close()
        conn.close()

