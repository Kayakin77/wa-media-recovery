-- Este archivo genera el CSV necesario para el script descargador_pro.py
-- Ejecución en terminal: sqlite3 -header -csv msgstore.db < extract_media.sql > datos_finales.csv

SELECT 
    message_row_id, 
    message_url, 
    hex(media_key) AS media_key_hex, 
    mime_type 
FROM 
    message_media 
WHERE 
    message_url IS NOT NULL;
