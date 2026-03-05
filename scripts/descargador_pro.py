import csv
import base64
import hashlib
import hmac
import requests
import os
from Crypto.Cipher import AES

# --- CONFIGURACIÓN DE RUTAS ---
# Esto creará las carpetas en la memoria de tu celular
BASE_PATH = "/sdcard/Download/WhatsApp_Recuperado"
os.makedirs(f"{BASE_PATH}/Fotos", exist_ok=True)
os.makedirs(f"{BASE_PATH}/Videos", exist_ok=True)

def hkdf_expand(key, length, info):
    """Derivación de llaves estándar de WhatsApp."""
    key = hmac.new(b"\x00"*32, key, hashlib.sha256).digest()
    key_stream = b""
    key_block = b""
    for i in range(1, (length + 31) // 32 + 1):
        key_block = hmac.new(key, key_block + info.encode() + bytes([i]), hashlib.sha256).digest()
        key_stream += key_block
    return key_stream[:length]

def descargar_y_descifrar(row):
    try:
        url = row['message_url']
        # Detectar si es imagen o video
        es_video = "video" in row['mime_type'].lower()
        tipo_llave = "WhatsApp Video Keys" if es_video else "WhatsApp Image Keys"
        extension = ".mp4" if es_video else ".jpg"
        subcarpeta = "Videos" if es_video else "Fotos"
        
        # Nombre del archivo usando el ID de la base de datos
        nombre_archivo = f"WA_MSG_{row['message_row_id']}{extension}"
        ruta_guardado = os.path.join(BASE_PATH, subcarpeta, nombre_archivo)

        print(f"[*] Descargando: {nombre_archivo}...", end="\r")
        
        # 1. Descargar el archivo .enc
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"[!] Error {r.status_code} en ID {row['message_row_id']} (Archivo caducado)")
            return False
            
        media_data = r.content
        
        # 2. Preparar llaves
        media_key = bytes.fromhex(row['media_key_hex'])
        expanded_key = hkdf_expand(media_key, 112, tipo_llave)
        iv = expanded_key[:16]
        cipher_key = expanded_key[16:48]

        # 3. Descifrado AES-CBC (quitando los 10 bytes del MAC)
        enc_data = media_data[:-10]
        # Ajustar al límite de bloque de 16 bytes
        enc_data = enc_data[:(len(enc_data) // 16) * 16]
        
        cipher = AES.new(cipher_key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(enc_data)

        # 4. Limpieza específica para imágenes JPG
        if not es_video:
            eoi = decrypted_data.find(b'\xff\xd9')
            if eoi != -1:
                decrypted_data = decrypted_data[:eoi + 2]

        # 5. Guardar en la memoria del celular
        with open(ruta_guardado, "wb") as f:
            f.write(decrypted_data)
        
        return True

    except Exception as e:
        print(f"\n[!] Error procesando ID {row.get('message_row_id')}: {e}")
        return False

# --- EJECUCIÓN PRINCIPAL ---
csv_input = "datos_finales.csv"

if not os.path.exists(csv_input):
    print(f"Error: No se encuentra el archivo '{csv_input}'")
    print("Asegúrate de ejecutar el comando sqlite3 primero.")
else:
    print(f"[*] Iniciando recuperación en: {BASE_PATH}")
    with open(csv_input, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_exitos = 0
        total_filas = 0
        
        for fila in reader:
            total_filas += 1
            if descargar_y_descifrar(fila):
                total_exitos += 1
    
    print(f"\n\n--- PROCESO FINALIZADO ---")
    print(f"[+] Archivos encontrados en CSV: {total_filas}")
    print(f"[+] Archivos recuperados con éxito: {total_exitos}")
    print(f"[+] Revisa tu galería en la carpeta: WhatsApp_Recuperado")
