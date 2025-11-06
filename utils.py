import logging

import bcrypt

from database import conectar

LOGGER = logging.getLogger(__name__)

def verificar_login(usuario, senha):
    try:
        with conectar() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
                user = cursor.fetchone()
            finally:
                cursor.close()

        if user and bcrypt.checkpw(senha.encode("utf-8"), user["senha_hash"].encode("utf-8")):
            registrar_acesso(user["usuario"])
            return user
    except Exception:
        LOGGER.exception("Erro ao verificar login do usuário '%s'", usuario)
        raise

    return None

def registrar_acesso(usuario):
    """Atualiza o último acesso de todos os produtos e registra o log."""

    try:
        with conectar() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE produtos SET ultimo_acesso = NOW()")
                cursor.execute(
                    "INSERT INTO acessos (usuario, produto_id) SELECT %s, id FROM produtos",
                    (usuario,),
                )
                conn.commit()
            finally:
                cursor.close()
    except Exception:
        LOGGER.exception("Erro ao registrar acesso em massa do usuário '%s'", usuario)
        raise
