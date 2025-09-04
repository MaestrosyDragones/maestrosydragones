# data_layer.py
import os
import pandas as pd
import streamlit as st

DEV_MODE = os.getenv("DEV_MODE", "0") == "1"   # En local: set DEV_MODE=1

# ---- CONFIG ----
CSV_STUDENTS = "students.csv"
CSV_LOGS     = "logs.csv"
CSV_ATT      = "asistencia.csv"

# ---- HELPERS ----
def _ensure_csv(path: str, cols: list[str]) -> None:
    """Crea CSV vacío con columnas si no existe."""
    import os
    if not os.path.exists(path):
        pd.DataFrame(columns=cols).to_csv(path, index=False, encoding="utf-8")

@st.cache_resource
def _open_sheet():
    """Devuelve el spreadsheet (objeto gspread) SOLO en producción (nube)."""
    if DEV_MODE:
        return None
    import gspread
    from google.oauth2.service_account import Credentials
    # En la nube (Streamlit Cloud) debes tener en secrets:
    # SERVICE_ACCOUNT_FILE = ".streamlit/service-account.json" (o la ruta que uses)
    # SHEET_STUDENTS_URL   = "https://docs.google.com/......"
    sa_file = st.secrets["SERVICE_ACCOUNT_FILE"]
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(sa_file, scopes=scope)
    gc = gspread.authorize(creds)
    return gc.open_by_url(st.secrets["SHEET_STUDENTS_URL"])

# ===================== LECTURAS =====================
@st.cache_data(ttl=60, show_spinner=False)
def load_students() -> pd.DataFrame:
    if DEV_MODE:
        _ensure_csv(CSV_STUDENTS,
                    ["id","name","grupo","xp","colegio_id","phone","teacher",
                     "xp_delta","xp_reason","avatar","trinket","trinket_desc"])
        df = pd.read_csv(CSV_STUDENTS)
        return df
    ws = _open_sheet().worksheet("students")
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=60, show_spinner=False)
def load_logs() -> pd.DataFrame:
    if DEV_MODE:
        _ensure_csv(CSV_LOGS, ["timestamp","id","name","delta_xp","reason"])
        return pd.read_csv(CSV_LOGS)
    ws = _open_sheet().worksheet("logs")
    return pd.DataFrame(ws.get_all_records())

@st.cache_data(ttl=60, show_spinner=False)
def load_attendance() -> pd.DataFrame:
    if DEV_MODE:
        _ensure_csv(CSV_ATT, ["id","date","status"])
        return pd.read_csv(CSV_ATT)
    ws = _open_sheet().worksheet("attendance")
    return pd.DataFrame(ws.get_all_records())

# ===================== ESCRITURAS =====================
def save_students(df: pd.DataFrame) -> None:
    """Sobrescribe estudiantes (CSV en dev, Sheet en prod)."""
    if DEV_MODE:
        df.to_csv(CSV_STUDENTS, index=False, encoding="utf-8")
        load_students.clear()
        return
    # Producción: reemplazo total de la hoja "students"
    sh = _open_sheet()
    ws = sh.worksheet("students")
    # Limpia y sube con encabezados
    ws.clear()
    if df.empty:
        return
    ws.update([df.columns.tolist()] + df.astype(str).values.tolist())
    load_students.clear()

def append_log(student_id: int, name: str, delta: int, reason: str) -> None:
    """Agrega UNA fila al log."""
    from datetime import datetime
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "id": int(student_id),
        "name": str(name),
        "delta_xp": int(delta),
        "reason": (reason or "")
    }
    if DEV_MODE:
        _ensure_csv(CSV_LOGS, ["timestamp","id","name","delta_xp","reason"])
        header_needed = False
        try:
            header_needed = (pd.read_csv(CSV_LOGS).shape[0] == 0)
        except Exception:
            header_needed = True
        pd.DataFrame([row]).to_csv(
            CSV_LOGS, mode="a", header=header_needed, index=False, encoding="utf-8"
        )
        load_logs.clear()
        return
    # Producción: append a la hoja "logs"
    sh = _open_sheet()
    ws = sh.worksheet("logs")
    ws.append_row([row["timestamp"], str(row["id"]), row["name"],
                   str(row["delta_xp"]), row["reason"]], value_input_option="USER_ENTERED")
    load_logs.clear()

def save_attendance(df: pd.DataFrame) -> None:
    if DEV_MODE:
        df.to_csv(CSV_ATT, index=False, encoding="utf-8")
        load_attendance.clear()
        return
    sh = _open_sheet()
    ws = sh.worksheet("attendance")
    ws.clear()
    if df.empty:
        return
    ws.update([df.columns.tolist()] + df.astype(str).values.tolist())
    load_attendance.clear()