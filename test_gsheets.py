import json
import sys
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

def main():
    try:
        # 1) Lee los secretos básicos
        sheet_url = st.secrets["SHEET_STUDENTS_URL"].strip()
        sa_path   = st.secrets["SERVICE_ACCOUNT_FILE"].strip()

        print("[INFO] Usando SERVICE_ACCOUNT_FILE:", sa_path)
        print("[INFO] Usando SHEET_STUDENTS_URL:", sheet_url)

        # 2) Carga credenciales del Service Account
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(sa_path, scopes=scopes)

        # 3) Abre el sheet vía URL
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(sheet_url)

        print("[OK] Conexión exitosa al Google Sheet.")
        print("[OK] Título del documento:", sh.title)

        # 4) Lee la primera hoja
        ws = sh.get_worksheet(0)
        print("[OK] Primera hoja:", ws.title)

        # 5) Trae algunas filas como muestra
        rows = ws.get_all_values()
        print(f"[OK] Filas totales: {len(rows)}")
        for i, row in enumerate(rows[:5], start=1):
            print(f"Fila {i}: {row}")

        print("\n✅ PRUEBA SUPERADA: Se pudo leer el Google Sheet.\n")

    except KeyError as ke:
        print("\n[ERROR] Falta una clave en secrets.toml:", ke)
        print("Asegúrate de tener en .streamlit/secrets.toml estas líneas, sin comas ni espacios raros:")
        print('  SERVICE_ACCOUNT_FILE = ".streamlit/service_account.json"')
        print('  SHEET_STUDENTS_URL   = "https://docs.google.com/..."')
        sys.exit(1)

    except gspread.SpreadsheetNotFound:
        print("\n[ERROR] No se encontró el Spreadsheet.")
        print("• Verifica que la URL en SHEET_STUDENTS_URL sea correcta.")
        print("• Verifica que compartiste el Sheet con el email del service account como Editor.")
        sys.exit(1)

    except gspread.exceptions.APIError as api_e:
        print("\n[API ERROR] Google API devolvió un error:")
        print(api_e)
        print("• Suele ser permisos (compartir el Sheet) o scopes.")
        sys.exit(1)

    except FileNotFoundError:
        print("\n[ERROR] No se encuentra el archivo del Service Account en la ruta indicada.")
        print("• Revisa SERVICE_ACCOUNT_FILE en secrets.toml y que el archivo exista.")
        sys.exit(1)

    except Exception as e:
        print("\n[ERROR] Falló la prueba por un error inesperado:")
        print(type(e).__name__, "->", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
