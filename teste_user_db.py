from database import conectar

conn = conectar()
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT * FROM usuarios;")
for u in cursor.fetchall():
    print(u)
cursor.close()
conn.close()
