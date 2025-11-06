import mysql.connector
from mysql.connector import errorcode

# 🔧 CONFIGURAÇÃO — ajuste se necessário
CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "int123!",
    "database": "sistema_login",
    "port": 3306
}


def testar_conexao():
    print("🔍 Testando conexão com o MySQL...")
    try:
        conn = mysql.connector.connect(**CONFIG)
        cursor = conn.cursor()
        print("✅ Conexão estabelecida com sucesso!")
        print(f"Servidor: {CONFIG['host']}:{CONFIG['port']}")

        # Mostra a versão do servidor
        cursor.execute("SELECT VERSION();")
        versao = cursor.fetchone()[0]
        print(f"MySQL versão: {versao}")

        # Mostra o banco atual
        cursor.execute("SELECT DATABASE();")
        db = cursor.fetchone()[0]
        print(f"Banco selecionado: {db}")

        # Lista tabelas disponíveis
        cursor.execute("SHOW TABLES;")
        tabelas = cursor.fetchall()
        if tabelas:
            print("\n📋 Tabelas encontradas:")
            for t in tabelas:
                print(f"  • {t[0]}")
        else:
            print("\n⚠️ Nenhuma tabela encontrada no banco.")

        cursor.close()
        conn.close()
        print("\n✅ Teste concluído com sucesso!")

    except mysql.connector.Error as err:
        print("\n❌ Ocorreu um erro ao conectar:")
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("→ Usuário ou senha incorretos.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("→ Banco de dados não encontrado.")
        elif err.errno == 2003:
            print("→ Servidor MySQL inacessível. Verifique se está em execução (porta 3306).")
        else:
            print(f"→ Erro desconhecido: {err}")

    except Exception as e:
        print(f"\n⚠️ Erro inesperado: {e}")


if __name__ == "__main__":
    testar_conexao()
