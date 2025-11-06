import bcrypt

senha = "1234".encode()
hash_novo = bcrypt.hashpw(senha, bcrypt.gensalt())
print("Hash gerado:", hash_novo.decode())
