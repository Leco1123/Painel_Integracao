# controle_integracao/integracao_db.py
from database import conectar
import uuid

DB_NAME = "sistema_login"


def _exec(query, params=None, fetch="none", many=False):
    """
    Executa query no banco.
    fetch:
      - "none": só executa
      - "one": retorna uma linha (dict ou None)
      - "all": retorna lista de linhas (list[dict])
    """
    conn = conectar()
    cur = conn.cursor(dictionary=True)

    # garante que estamos no banco certo
    cur.execute(f"USE {DB_NAME};")

    if many:
        cur.executemany(query, params or [])
    else:
        cur.execute(query, params or [])

    data = None
    if fetch == "one":
        data = cur.fetchone()
    elif fetch == "all":
        data = cur.fetchall()

    conn.commit()
    cur.close()
    conn.close()
    return data


# =========================
# EMPRESAS
# =========================

def listar_empresas():
    """Retorna todas as empresas para preencher combos e painel."""
    return _exec("""
        SELECT id, empresa, cod, cod_athenas, top10, prioridade_empresa
        FROM empresas_integracao
        ORDER BY empresa ASC;
    """, fetch="all")


def get_empresa_por_nome_cod(empresa_nome, cod):
    return _exec("""
        SELECT id, empresa, cod, cod_athenas, top10, prioridade_empresa
        FROM empresas_integracao
        WHERE empresa = %s AND cod = %s
        LIMIT 1;
    """, (empresa_nome, cod), fetch="one")


def garantir_empresa(empresa_nome, cod, cod_athenas, prioridade_empresa, top10_flag):
    """
    Se a empresa já existir (mesmo nome+cod) -> atualiza infos essenciais.
    Senão -> cria uma nova.
    Retorna empresa_id final.
    """
    existente = get_empresa_por_nome_cod(empresa_nome, cod)
    if existente:
        empresa_id = existente["id"]
        _exec("""
            UPDATE empresas_integracao
            SET cod_athenas = %s,
                prioridade_empresa = %s,
                top10 = %s
            WHERE id = %s
        """, (cod_athenas, prioridade_empresa, top10_flag, empresa_id))
        return empresa_id
    else:
        empresa_id = str(uuid.uuid4())
        _exec("""
            INSERT INTO empresas_integracao
            (id, empresa, cod, cod_athenas, top10, prioridade_empresa, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (empresa_id, empresa_nome, cod, cod_athenas, top10_flag, prioridade_empresa))
        return empresa_id


# =========================
# TAREFAS
# =========================

def listar_tarefas(f_empresa=None, f_mes=None, f_status=None, f_tipo=None):
    """
    Carrega as tarefas com dados da empresa.
    """
    sql = """
        SELECT
            t.id              AS tarefa_id,
            t.empresa_id      AS empresa_id,
            e.empresa         AS empresa,
            e.cod             AS cod,
            e.cod_athenas     AS cod_athenas,
            e.top10           AS top10,
            t.mes             AS mes,
            t.tipo            AS tipo,
            t.p1              AS p1,
            t.p2              AS p2,
            t.prioridade_tarefa AS prioridade,
            t.status          AS status,
            t.atualizado_em   AS atualizado_em
        FROM tarefas_integracao t
        JOIN empresas_integracao e ON e.id = t.empresa_id
        WHERE 1=1
    """
    params = []

    if f_empresa:
        sql += " AND e.empresa LIKE %s"
        params.append(f"%{f_empresa}%")
    if f_mes:
        sql += " AND t.mes = %s"
        params.append(f_mes)
    if f_status:
        sql += " AND t.status = %s"
        params.append(f_status)
    if f_tipo:
        sql += " AND t.tipo = %s"
        params.append(f_tipo)

    sql += " ORDER BY e.empresa ASC, t.mes DESC, t.tipo ASC;"

    return _exec(sql, tuple(params), fetch="all")


def inserir_tarefa(empresa_id, mes, tipo, p1, p2, prioridade_tarefa, status):
    _exec("""
        INSERT INTO tarefas_integracao
        (empresa_id, p1, p2, tipo, status, prioridade_tarefa, mes, atualizado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """, (empresa_id, p1, p2, tipo, status, prioridade_tarefa, mes))


def get_tarefa(tarefa_id):
    return _exec("""
        SELECT
            t.id              AS tarefa_id,
            t.empresa_id      AS empresa_id,
            e.empresa         AS empresa,
            e.cod             AS cod,
            e.cod_athenas     AS cod_athenas,
            e.top10           AS top10,
            e.prioridade_empresa AS prioridade_empresa,
            t.mes             AS mes,
            t.tipo            AS tipo,
            t.p1              AS p1,
            t.p2              AS p2,
            t.prioridade_tarefa AS prioridade_tarefa,
            t.status          AS status
        FROM tarefas_integracao t
        JOIN empresas_integracao e ON e.id = t.empresa_id
        WHERE t.id = %s
        LIMIT 1;
    """, (tarefa_id,), fetch="one")


def atualizar_tarefa(tarefa_id, empresa_id, mes, tipo, p1, p2, prioridade_tarefa, status, usuario_responsavel=None):
    _exec("""
        UPDATE tarefas_integracao
        SET empresa_id = %s,
            mes = %s,
            tipo = %s,
            p1 = %s,
            p2 = %s,
            prioridade_tarefa = %s,
            status = %s,
            atualizado_em = NOW()
        WHERE id = %s
    """, (empresa_id, mes, tipo, p1, p2, prioridade_tarefa, status, tarefa_id))

    # log de auditoria (opcional, não quebra se falhar)
    _exec("""
        INSERT INTO tarefas_integracao_log (tarefa_id, empresa_id, acao, usuario_responsavel, timestamp)
        VALUES (%s, %s, %s, %s, NOW())
    """, (
        tarefa_id,
        empresa_id,
        f"Edição de tarefa: status={status}, prioridade={prioridade_tarefa}",
        usuario_responsavel or ""
    ))


def listar_meses_existentes():
    rows = _exec("""
        SELECT DISTINCT mes
        FROM tarefas_integracao
        WHERE mes <> ''
        ORDER BY mes DESC;
    """, fetch="all")
    return [r["mes"] for r in rows]


def listar_tipos_existentes():
    rows = _exec("""
        SELECT DISTINCT tipo
        FROM tarefas_integracao
        ORDER BY tipo ASC;
    """, fetch="all")
    return [r["tipo"] for r in rows]


def listar_responsaveis():
    # pega da tabela usuarios (que você já tem no login)
    rows = _exec("""
        SELECT nome
        FROM usuarios
        ORDER BY nome ASC;
    """, fetch="all")
    return [r["nome"] for r in rows]


def export_raw(filtro_mes=None):
    sql = """
        SELECT
            e.empresa,
            e.cod,
            e.cod_athenas,
            t.mes,
            t.tipo,
            t.p1,
            t.p2,
            t.prioridade_tarefa AS prioridade,
            t.status,
            t.atualizado_em
        FROM tarefas_integracao t
        JOIN empresas_integracao e ON e.id = t.empresa_id
        WHERE 1=1
    """
    params = []
    if filtro_mes:
        sql += " AND t.mes = %s"
        params.append(filtro_mes)

    sql += " ORDER BY e.empresa ASC, t.mes DESC, t.tipo ASC;"

    return _exec(sql, tuple(params), fetch="all")
