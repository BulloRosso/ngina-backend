import bcrypt

# Create hash for password 'demo123'
password = 'demo123'
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print("Hashed password:", hashed.decode('utf-8'))