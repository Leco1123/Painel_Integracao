import mysql.connector
from mysql.connector import errorcode

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="int123!"
    )
    print("✅ Conexão com o servidor MySQL OK!")
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION();")
    print("Versão do MySQL:", cursor.fetchone()[0])
    conn.close()
except mysql.connector.Error as err:
    print("❌ Erro MySQL:", err)

