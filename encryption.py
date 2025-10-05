
from cryptography.fernet import Fernet
import os

# Generate a key for encryption
def generate_key():
    return Fernet.generate_key()

# Encrypt a file
def encrypt_file(file_path, key):
    fernet = Fernet(key)
    with open(file_path, "rb") as file:
        file_data = file.read()
    encrypted_data = fernet.encrypt(file_data)
    with open(file_path + ".enc", "wb") as file:
        file.write(encrypted_data)
    os.remove(file_path)

# Decrypt a file
def decrypt_file(file_path, key):
    fernet = Fernet(key)
    with open(file_path, "rb") as file:
        encrypted_data = file.read()
    decrypted_data = fernet.decrypt(encrypted_data)
    return decrypted_data.decode()
