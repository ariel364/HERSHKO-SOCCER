
def xor_encrypt_decrypt(data: bytes, key: bytes) -> bytes:
    key_length = len(key)
    return bytes([data[i] ^ key[i % key_length] for i in range(len(data))])

# מפתח הצפנה - חשוב שיהיה זהה גם לשרת וגם ללקוח
SECRET_KEY = b'SuperSecret123'  
# אתה יכול לשנות אבל תשמור אותו זהה גם בלקוח וגם בשרת
