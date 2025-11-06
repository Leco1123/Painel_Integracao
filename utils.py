import bcrypt
from database import conectar

def verificar_login(usuario, senha):
    conn = conectar()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
    user = cursor.fetchone()

    if user and bcrypt.checkpw(senha.encode('utf-8'), user['senha_hash'].encode('utf-8')):
        registrar_acesso(user['usuario'])
        cursor.close()
        conn.close()
        return user
    cursor.close()
    conn.close()
    return None

def registrar_acesso(usuario):
    """Atualiza o último acesso de todos os produtos e registra o log."""
    conn = conectar()
    cursor = conn.cursor()
    # atualiza campo ultimo_acesso em todos os produtos
    cursor.execute("UPDATE produtos SET ultimo_acesso = NOW()")
    # grava log de acesso
    cursor.execute("INSERT INTO acessos (usuario, produto_id) SELECT %s, id FROM produtos", (usuario,))
    conn.commit()
    cursor.close()
    conn.close()
