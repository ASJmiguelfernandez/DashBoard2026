# -*- coding: utf-8 -*-
"""
explorar_bd.py
--------------
Script de diagnostico: lista todas las tablas de la BD ACUE
y muestra las primeras filas de cada una.

Ejecutar con:  python explorar_bd.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pyodbc

# Cadena de conexión
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=172.16.130.5;"
    "DATABASE=ACUE;"
    "UID=acue;"
    "PWD=Acue2005@!;"
)

def main():
    print("Conectando a SQL Server...")
    try:
        conn = pyodbc.connect(CONN_STR, timeout=10)
        print("✅ Conexión exitosa!\n")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("\nAsegúrate de tener instalado 'ODBC Driver 17 for SQL Server'.")
        print("Descarga: https://aka.ms/downloadmsodbcsql")
        return

    cursor = conn.cursor()

    # Listar todas las tablas de usuario
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)
    tablas = cursor.fetchall()

    if not tablas:
        print("⚠️  No se encontraron tablas en la base de datos.")
        return

    print(f"📋 TABLAS DISPONIBLES EN '{CONN_STR.split('DATABASE=')[1].split(';')[0]}' ({len(tablas)} tablas):")
    print("=" * 60)
    for schema, tabla in tablas:
        print(f"  [{schema}].[{tabla}]")

    print("\n" + "=" * 60)
    print("📊 COLUMNAS POR TABLA:")
    print("=" * 60)

    for schema, tabla in tablas:
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """, schema, tabla)
        columnas = cursor.fetchall()

        print(f"\n▶ [{schema}].[{tabla}]")
        for col_name, data_type, max_len in columnas:
            len_str = f"({max_len})" if max_len else ""
            print(f"    - {col_name}: {data_type}{len_str}")

        # Mostrar primeras 3 filas como muestra
        try:
            cursor.execute(f"SELECT TOP 3 * FROM [{schema}].[{tabla}]")
            rows = cursor.fetchall()
            if rows:
                col_names = [desc[0] for desc in cursor.description]
                print(f"    Ejemplo (3 filas):")
                print(f"    {col_names}")
                for row in rows:
                    print(f"    {list(row)}")
        except Exception as ex:
            print(f"    (No se pudo leer datos: {ex})")

    conn.close()
    print("\n✅ Exploración completada.")

if __name__ == "__main__":
    main()
