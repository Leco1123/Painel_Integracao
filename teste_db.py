from database import conectar

conn = conectar()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM produtos;")
print("Conectado com sucesso! Total de produtos:", cursor.fetchone()[0])
cursor.close()
conn.close()
