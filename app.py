import streamlit as st
import pandas as pd
import json, base64, os, re, calendar, mimetypes, io
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
from streamlit_image_coordinates import streamlit_image_coordinates

# ===== Finos (ajusta a gusto) =====
LABEL_OFFSET_X = 0
LABEL_OFFSET_Y = 0
TIGHT_BELOW    = -8

# ===== Paths locales (cuando NO se usa Sheets) =====
ASSETS_DIR   = "assets"
MAP_IMG      = os.path.join(ASSETS_DIR, "mi_mapa.png")
AVATARS_DIR  = os.path.join(ASSETS_DIR, "avatars")
TRINKETS_DIR = os.path.join(ASSETS_DIR, "trinkets")
AUDIO_DIR    = os.path.join(ASSETS_DIR, "audio")
BGM_FILE     = os.path.join(AUDIO_DIR, "DungeonSynth.mp3")  # <— tu pista
STU_CSV      = "students.csv"
LOG_CSV      = "logs.csv"
OBS_CSV      = "observaciones.csv"
ATT_CSV      = "asistencia.csv"
MILESTONES_JSON = "milestones.json"
COLEGIOS_CSV = "colegios.csv"

# ===== Auto-switch a Google Sheets si hay secretos =====
def _bool_secret(name, default=False):
    try:
        return bool(st.secrets.get(name, default))
    except Exception:
        return default

USE_SHEETS = _bool_secret("USE_SHEETS", False)

def _gs_client():
    import gspread
    from google.oauth2.service_account import Credentials
    raw = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("No hay GOOGLE_SERVICE_ACCOUNT_JSON en secrets.")
    info = json.loads(raw)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def _open_sheet(url):
    gc = _gs_client()
    return gc.open_by_url(url).sheet1

def _sheet_to_df(url, expected_cols=None):
    sh = _open_sheet(url)
    rows = sh.get_all_records()
    df = pd.DataFrame(rows)
    if expected_cols:
        for c in expected_cols:
            if c not in df.columns:
                df[c] = "" if c not in ["xp","colegio_id","xp_delta"] else 0
        df = df[expected_cols]
    return df

def _df_to_sheet(url, df: pd.DataFrame):
    sh = _open_sheet(url)
    sh.clear()
    # gspread prefiere listas de listas
    header = list(df.columns)
    values = [header] + df.astype(str).values.tolist()
    sh.update(values)

SHEET_STUDENTS_URL = st.secrets.get("SHEET_STUDENTS_URL", "")
SHEET_LOGS_URL     = st.secrets.get("SHEET_LOGS_URL", "")
SHEET_OBS_URL      = st.secrets.get("SHEET_OBS_URL", "")
SHEET_ATT_URL      = st.secrets.get("SHEET_ATT_URL", "")

# ===== Utils =====
def do_rerun():
    try: st.rerun()
    except AttributeError: st.experimental_rerun()

def play_positive_sound():
    # sonido corto (no el BGM)
    st.markdown("""
    <script>
    (function(){
      try{
        const A = window.AudioContext||window.webkitAudioContext;
        const c = new A(); const o = c.createOscillator(); const g = c.createGain();
        o.type='triangle'; o.frequency.value=880; o.connect(g); g.connect(c.destination);
        g.gain.setValueAtTime(0.0001,c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.25,c.currentTime+0.03);
        g.gain.exponentialRampToValueAtTime(0.0001,c.currentTime+0.25);
        o.start(); o.stop(c.currentTime+0.27);
      }catch(e){}
    })();
    </script>
    """, unsafe_allow_html=True)

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

# ===== Query params helpers =====
def get_qp():
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()

def set_qp(**kwargs):
    try:
        st.query_params.update(kwargs)
    except Exception:
        st.experimental_set_query_params(**kwargs)

# ===== Avatar & Trinket helpers =====
def discover_avatars():
    options=[]
    if os.path.isdir(AVATARS_DIR):
        for f in sorted(os.listdir(AVATARS_DIR)):
            if os.path.isfile(os.path.join(AVATARS_DIR,f)):
                options.append(f)
    return options

def discover_trinkets():
    options=[]
    if os.path.isdir(TRINKETS_DIR):
        for f in sorted(os.listdir(TRINKETS_DIR)):
            if os.path.splitext(f.lower())[1] in [".png",".jpg",".jpeg",".gif",".webp",".bmp"]:
                options.append(f)
    return options

AVATAR_OPTIONS  = discover_avatars()
TRINKET_OPTIONS = discover_trinkets()

def avatar_path_for(student_row):
    fname = (student_row.get("avatar","") if isinstance(student_row, dict) else getattr(student_row, "avatar", ""))
    fname = (fname or "").strip()
    if not fname: return None
    path = os.path.join(AVATARS_DIR, fname)
    return path if os.path.isfile(path) else None

def trinket_path_for(student_row):
    fname = (student_row.get("trinket","") if isinstance(student_row, dict) else getattr(student_row, "trinket", ""))
    fname = (fname or "").strip()
    if not fname: return None
    path = os.path.join(TRINKETS_DIR, fname)
    return path if os.path.isfile(path) else None

def render_trinket_with_tooltip(student_row, width_px=64):
    tpath = trinket_path_for(student_row)
    if not tpath: return
    tip = (student_row.get("trinket_desc","") if isinstance(student_row, dict) else getattr(student_row, "trinket_desc", "")) or ""
    mt, _ = mimetypes.guess_type(tpath)
    if not mt: mt="image/png"
    try:
        with open(tpath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        st.markdown(
            f"""
            <div class="trinket-wrap" title="{tip.replace('"','&quot;')}">
              <img class="trinket-img" style="width:{width_px}px;height:auto" src="data:{mt};base64,{b64}" alt="trinket"/>
              <div class="trinket-cap">Trinket</div>
            </div>
            """, unsafe_allow_html=True
        )
    except:
        st.image(Image.new("RGBA",(width_px,width_px),(80,80,100,255)), width=width_px, caption="Trinket")

# ===== Data IO  (CSV por defecto / Sheets si hay secrets) =====
@st.cache_data
def load_students_csv():
    if not os.path.exists(STU_CSV):
        pd.DataFrame(columns=[
            "id","name","grupo","xp","colegio_id","phone","teacher","xp_delta","xp_reason","avatar",
            "trinket","trinket_desc"
        ]).to_csv(STU_CSV, index=False)
    df = pd.read_csv(STU_CSV)
    for col in ["id","name","grupo","xp","colegio_id","phone","teacher","xp_delta","xp_reason","avatar","trinket","trinket_desc"]:
        if col not in df.columns:
            df[col] = "" if col in ["name","grupo","phone","teacher","xp_reason","avatar","trinket","trinket_desc"] else 0
    df["xp"] = pd.to_numeric(df["xp"], errors="coerce").fillna(0).astype(int)
    df["colegio_id"] = pd.to_numeric(df["colegio_id"], errors="coerce").fillna(1).astype(int)
    df["xp_delta"]   = pd.to_numeric(df["xp_delta"], errors="coerce").fillna(0).astype(int)
    for c in ["name","grupo","phone","teacher","xp_reason","avatar","trinket","trinket_desc"]:
        df[c] = df[c].fillna("").astype(str)
    return df

def save_students_csv(df):
    for col in ["phone","teacher","xp_reason","name","grupo","avatar","trinket","trinket_desc"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    for col in ["xp","colegio_id","xp_delta"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df.to_csv(STU_CSV, index=False)
    load_students_csv.clear()

@st.cache_data
def load_milestones():
    if not os.path.exists(MILESTONES_JSON):
        defaults={"milestones":[
            {"label":"Madera","threshold":0,"color":"#8b5a2b","icon":"assets/madera.png"},
            {"label":"Bronce","threshold":100,"color":"#b05c28","icon":"assets/bronce.png"},
            {"label":"Plata","threshold":250,"color":"#a0a7b8","icon":"assets/plata.png"},
            {"label":"Oro","threshold":500,"color":"#e0b63d","icon":"assets/oro.png"},
            {"label":"Platino","threshold":750,"color":"#79b8ff","icon":"assets/platino.png"},
            {"label":"Diamante","threshold":1000,"color":"#b07cff","icon":"assets/diamante.png"},
        ]}
        with open(MILESTONES_JSON,"w",encoding="utf-8") as f: json.dump(defaults,f,ensure_ascii=False,indent=2)
    with open(MILESTONES_JSON,"r",encoding="utf-8") as f:
        data=json.load(f)
    data["milestones"]=sorted(data["milestones"],key=lambda m:m["threshold"])
    return data

@st.cache_data
def load_colegios():
    if not os.path.exists(COLEGIOS_CSV):
        pd.DataFrame([{"id":1,"nombre":"COLEGIO","x":100,"y":100,"icono":"assets/castle1.png"}]).to_csv(COLEGIOS_CSV,index=False)
    return pd.read_csv(COLEGIOS_CSV)

def save_colegios(df):
    df.to_csv(COLEGIOS_CSV, index=False); load_colegios.clear()

# Logs
def load_logs_df():
    if USE_SHEETS and SHEET_LOGS_URL:
        return _sheet_to_df(SHEET_LOGS_URL, expected_cols=["timestamp","id","name","delta_xp","reason"])
    if not os.path.exists(LOG_CSV):
        return pd.DataFrame(columns=["timestamp","id","name","delta_xp","reason"])
    df = pd.read_csv(LOG_CSV)
    for c in ["reason","name"]:
        if c in df.columns: df[c]=df[c].fillna("").astype(str)
    return df

def save_logs_df(df):
    if USE_SHEETS and SHEET_LOGS_URL:
        _df_to_sheet(SHEET_LOGS_URL, df)
    else:
        df.to_csv(LOG_CSV, index=False)

def append_log(row_id,name,delta,reason):
    df = load_logs_df()
    new_row = {"timestamp":now_iso(),"id":int(row_id),"name":name,"delta_xp":int(delta),"reason":(reason or "")}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_logs_df(df)

def recent_logs_for(student_id, limit=12):
    df = load_logs_df()
    df = df[df["id"]==student_id].sort_values("timestamp", ascending=False).head(limit).copy()
    try: df["timestamp"]=pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
    except: pass
    df.rename(columns={"timestamp":"Fecha/Hora","delta_xp":"Δ XP","reason":"Motivo"}, inplace=True)
    df["Motivo"]=df["Motivo"].fillna("").astype(str)
    return df

def all_logs_for(student_id):
    df=load_logs_df()
    df=df[df["id"]==student_id].sort_values("timestamp", ascending=False).copy()
    df["reason"]=df["reason"].fillna("").astype(str)
    return df

def delete_logs_for(student_id, timestamps):
    df=load_logs_df()
    before=len(df)
    keep_mask = ~((df["id"]==student_id) & (df["timestamp"].isin(list(timestamps))))
    df=df[keep_mask]
    save_logs_df(df)
    return before - len(df)

# Observaciones
def load_obs_df():
    if USE_SHEETS and SHEET_OBS_URL:
        return _sheet_to_df(SHEET_OBS_URL, expected_cols=["timestamp","id","name","observacion"])
    if not os.path.exists(OBS_CSV):
        return pd.DataFrame(columns=["timestamp","id","name","observacion"])
    df = pd.read_csv(OBS_CSV)
    df["observacion"]=df["observacion"].fillna("").astype(str)
    return df

def save_obs_df(df):
    if USE_SHEETS and SHEET_OBS_URL:
        _df_to_sheet(SHEET_OBS_URL, df)
    else:
        df.to_csv(OBS_CSV, index=False)

def append_observation(student_id, name, text):
    df=load_obs_df()
    new_row={"timestamp":now_iso(),"id":int(student_id),"name":name,"observacion":(text or "")}
    df=pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_obs_df(df)

def observations_for(student_id, limit=20):
    df=load_obs_df()
    df=(df[df["id"]==student_id].sort_values("timestamp", ascending=False)
        .loc[:,["timestamp","observacion"]].head(limit).copy())
    try: df["timestamp"]=pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
    except: pass
    df.rename(columns={"timestamp":"Fecha/Hora","observacion":"Observación"}, inplace=True)
    df["Observación"]=df["Observación"].fillna("").astype(str)
    return df

def all_observations_for(student_id):
    df=load_obs_df()
    df=df[df["id"]==student_id].sort_values("timestamp", ascending=False).copy()
    df["observacion"]=df["observacion"].fillna("").astype(str)
    return df

def delete_observations_for(student_id, timestamps):
    df=load_obs_df()
    before=len(df)
    keep_mask = ~((df["id"]==student_id) & (df["timestamp"].isin(list(timestamps))))
    df=df[keep_mask]
    save_obs_df(df)
    return before-len(df)

# Asistencia
def load_att_df():
    if USE_SHEETS and SHEET_ATT_URL:
        return _sheet_to_df(SHEET_ATT_URL, expected_cols=["id","date","status"])
    if not os.path.exists(ATT_CSV):
        pd.DataFrame(columns=["id","date","status"]).to_csv(ATT_CSV, index=False)
    return pd.read_csv(ATT_CSV)

def save_att_df(df):
    if USE_SHEETS and SHEET_ATT_URL:
        _df_to_sheet(SHEET_ATT_URL, df)
    else:
        df.to_csv(ATT_CSV, index=False)

ATT_STATES = {None:"◻️","P":"✅","T":"🟧","A":"❌"}
MONTHS_ES  = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

def set_attendance(student_id:int, y:int, m:int, d:int, status:str|None):
    df = load_att_df()
    day = date(y,m,d).isoformat()
    mask = (df.get("id",0).astype(int)==int(student_id)) & (df.get("date","")==day)
    if status in (None,""):
        df = df[~mask]
    else:
        if mask.any():
            df.loc[mask,"status"]=status
        else:
            df = pd.concat([df, pd.DataFrame([{"id":student_id,"date":day,"status":status}])], ignore_index=True)
    save_att_df(df)

def att_map_for_month(student_id:int, y:int, m:int)->dict:
    df=load_att_df()
    df["id"]=pd.to_numeric(df.get("id",0), errors="coerce").fillna(0).astype(int)
    pref=f"{y:04d}-{m:02d}-"
    sub=df[(df["id"]==student_id) & (df["date"].astype(str).str.startswith(pref))]
    mapp={}
    for _,r in sub.iterrows():
        try:
            d=int(str(r["date"]).split("-")[-1])
            stt=r.get("status",None)
            mapp[d] = (stt if stt in ("P","T","A") else None)
        except: pass
    return mapp

def cycle_state(cur: str|None)->str|None:
    order=[None,"P","T","A"]
    i=order.index(cur) if cur in order else 0
    return order[(i+1)%len(order)]

def render_mini_calendar(student_id:int, holder, disabled=False):
    with holder:
        key_y=f"cal_y_{student_id}"
        key_m=f"cal_m_{student_id}"
        if key_y not in st.session_state or key_m not in st.session_state:
            today=date.today()
            st.session_state[key_y]=today.year
            st.session_state[key_m]=today.month
        y=st.session_state[key_y]; m=st.session_state[key_m]

        cprev, ctitle, cnext = st.columns([0.5,3.2,0.5])
        with cprev:
            if st.button("◀", key=f"prev_{student_id}_{y}_{m}", disabled=disabled):
                nm=m-1; ny=y
                if nm==0: nm=12; ny=y-1
                st.session_state[key_y], st.session_state[key_m]=ny,nm; do_rerun()
        with ctitle:
            st.markdown(
                f"<div style='text-align:center; font-weight:700; color:#eaf2ff; margin-top:2px'>{MONTHS_ES[m-1]} {y}</div>",
                unsafe_allow_html=True
            )
        with cnext:
            if st.button("▶", key=f"next_{student_id}_{y}_{m}", disabled=disabled):
                nm=m+1; ny=y
                if nm==13: nm=1; ny=y+1
                st.session_state[key_y], st.session_state[key_m]=ny,nm; do_rerun()

        st.markdown(
            "<div style='display:flex; gap:6px; justify-content:space-between; font-size:0.72rem; color:#a4c0ff; margin:4px 2px 4px 2px'>"
            "<span>L</span><span>M</span><span>X</span><span>J</span><span>V</span><span>S</span><span>D</span>"
            "</div>", unsafe_allow_html=True)

        first_wd, days_in_m = calendar.monthrange(y, m)
        pads = first_wd
        att_map = att_map_for_month(student_id, y, m)

        day=1
        total_cells = pads + days_in_m
        rows = (total_cells + 6)//7
        for r in range(rows):
            cols=st.columns(7, gap="small")
            for c in range(7):
                cell_idx=r*7+c
                with cols[c]:
                    if cell_idx < pads or day > days_in_m:
                        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                    else:
                        cur_state=att_map.get(day, None)
                        emoji=ATT_STATES[cur_state]
                        lbl=f"{emoji} {day:02d}"
                        if st.button(lbl, key=f"att_{student_id}_{y}_{m}_{day}", help="Click para alternar", use_container_width=True, disabled=disabled):
                            new_state = cycle_state(cur_state)
                            set_attendance(student_id, y, m, day, new_state)
                            do_rerun()
                        day+=1

        counts={"P":0,"T":0,"A":0}
        for d in range(1, days_in_m+1):
            s=att_map.get(d, None)
            if s in counts: counts[s]+=1
        st.markdown(
            f"<div style='margin-top:6px; font-size:0.78rem; color:#cfd6ff'>"
            f"<b>Resumen del mes:</b> ✅ {counts['P']} &nbsp; 🟧 {counts['T']} &nbsp; ❌ {counts['A']}"
            f"</div>", unsafe_allow_html=True
        )

# ===== RPG helpers =====
def compute_level(xp,milestones):
    current=milestones[0]; next_m=None
    for m in milestones:
        if xp>=m["threshold"]: current=m
        else: next_m=m; break
    if next_m is None:
        return current["label"], current.get("icon",""), current.get("color","#46A0FF"), 1.0, 0, "MAX", current["threshold"]
    span=max(1,next_m["threshold"]-current["threshold"])
    pct=(xp-current["threshold"])/span
    remaining=max(0,next_m["threshold"]-xp)
    return current["label"], current.get("icon",""), current.get("color","#46A0FF"), pct, remaining, next_m["label"], next_m["threshold"]

def hex_to_rgba(h,a=255):
    try: h=h.lstrip('#'); return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16),a)
    except: return (70,160,255,a)

def pixel_overlay_bar_image(pct,width=560,height=22,color_hex="#46A0FF"):
    pct=max(0.0,min(1.0,float(pct))); W,H=width,height
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=(190,210,255,220), width=2)
    d.rectangle([2,2,W-3,H-3], outline=(10,18,36,255), width=1)
    d.rectangle([3,3,W-4,H-4], fill=(25,36,64,230))
    r,g,b,_=hex_to_rgba(color_hex); fill_w=max(0,int((W-6)*pct))
    for x in range(3,3+fill_w):
        for y in range(3,H-3):
            if ((x+y)&1)==0: rx=min(255,r+18); gx=min(255,g+18); bx=min(255,b+18)
            else: rx=max(0,r-12); gx=max(0,g-12); bx=max(0,b-12)
            img.putpixel((x,y),(rx,gx,bx,235))
    d.line([3,4,3+fill_w,4], fill=(255,255,255,90), width=1)
    d.line([3,H-5,3+fill_w,H-5], fill=(0,0,0,110), width=1)
    return img

# ===== Theme / CSS =====
def inject_css():
    try:
        with open(os.path.join(ASSETS_DIR,"hand.png"),"rb") as f: hand_b64=base64.b64encode(f.read()).decode("utf-8")
        cursor_css=f"cursor:url('data:image/png;base64,{hand_b64}') 8 0, pointer !important;"
    except: cursor_css="cursor:pointer !important;"
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
      .stApp{{background:radial-gradient(1600px 800px at 25% -10%,#20355f 0%,#172748 55%,#0e1a33 100%);}}
      .ff-title{{font-family:'Press Start 2P',monospace!important;letter-spacing:.4px;}}
      .ff-panel{{background:linear-gradient(180deg,rgba(34,57,101,.96),rgba(18,33,66,.96));
                 border:2px solid #a9c2ff;border-radius:12px;box-shadow:0 0 0 2px #0a1326 inset,0 10px 24px rgba(0,0,0,.35);
                 padding:10px 12px;}}
      .ff-card{{border-radius:12px;margin-bottom:10px;}}
      .ff-card:hover{{box-shadow:0 0 0 2px rgba(140,180,255,.4);}}
      .stButton>button{{background:#203a72;color:#eaf2ff;border:1px solid #a9c2ff;border-radius:8px;padding:.28rem .45rem;{cursor_css}}}
      .stImage img,.stDataFrame,.stTabs,.element-container svg{{{cursor_css}}}
      .ff-badge{{display:inline-block;background:#132a59;border:1px solid #a9c2ff;border-radius:6px;padding:2px 6px;margin-left:6px;}}
      .ff-row-tight .block-container{{padding-top:0!important}}
      .ff-stat{{color:#a4c0ff;margin-right:10px}}
      .ff-line{{height:1px;background:rgba(169,194,255,.35);margin:6px 0 8px}}
      .ff-compact p{{margin:0}}

      /* Trinket hover + tooltip + micro-anim */
      .trinket-wrap{{display:flex;flex-direction:column;align-items:center;margin-top:6px}}
      .trinket-img{{transition:filter .18s ease, transform .18s ease; filter:brightness(0.98)}}
      .trinket-img:hover{{filter:brightness(1.18); transform:translateY(-1px)}}
      .trinket-cap{{font-size:.72rem;color:#bcd0ff;text-align:center;margin-top:2px}}

      /* Marca pequeñita fija abajo-izquierda */
      .mhv-mark {{
        position: fixed; left: 8px; bottom: 6px; font-size: 10px; color:#8fa9ff; opacity:.7; z-index: 9999;
        background: rgba(10,20,40,.35); padding: 2px 6px; border: 1px solid rgba(169,194,255,.35); border-radius: 6px;
      }}
    </style>
    """, unsafe_allow_html=True)

def inject_bgm_and_mark():
    # BGM en loop con volumen bajito (0.08). Autoplay puede requerir interacción.
    audio_b64 = ""
    if os.path.isfile(BGM_FILE):
        with open(BGM_FILE, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    if audio_b64:
        st.markdown(f"""
        <audio id="bgm" src="data:audio/mp3;base64,{audio_b64}" autoplay loop></audio>
        <script>
        (function(){{
          try{{ const a = document.getElementById('bgm'); a.volume = 0.08; }}catch(e){{}}
          // En Safari/Chrome móvil: arrancar tras primer toque/click
          window.addEventListener('pointerdown', function once(){{ 
            try{{ document.getElementById('bgm').play(); }}catch(e){{}} 
            this.removeEventListener('pointerdown', once); 
          }}, {{passive:true}});
        }})();
        </script>
        """, unsafe_allow_html=True)

    # Marca pequeñita fija
    st.markdown(
        "<div class='mhv-mark'>© 2025 Mauricio Herrera Valdés — Código de registro 2025</div>",
        unsafe_allow_html=True
    )


# ===== App state =====
st.set_page_config(page_title="Maestros & Dragones — RPG XP", layout="wide")
inject_css()
inject_bgm_and_mark()

# ===== Viewer mode por querystring =====
_qp = get_qp()
VIEWER_MODE = (_qp.get("mode", [""])[0].lower()=="viewer") if isinstance(_qp.get("mode"), list) else (_qp.get("mode","").lower()=="viewer")

# Menu sólo si NO estamos en viewer o si no hay sid
if "selected_colegio" not in st.session_state: st.session_state.selected_colegio=None
if "selected_student" not in st.session_state: st.session_state.selected_student=None
if "view" not in st.session_state: st.session_state.view="Mapa"
if "rank_side" not in st.session_state: st.session_state.rank_side="Izquierda"

# Si viene ?view=... en la URL, respetarlo
if "view" in _qp:
    st.session_state.view = _qp["view"][0] if isinstance(_qp["view"], list) else _qp["view"]

# Si viene ?sid=... ir directo a ficha
if "sid" in _qp:
    sid_str = _qp["sid"][0] if isinstance(_qp["sid"], list) else _qp["sid"]
    try:
        st.session_state.selected_student = int(sid_str)
        st.session_state.view = "Ficha"
    except:
        pass

VIEWS=["Mapa","Colegio","Ficha","Control","Config"]
show_sidebar_nav = not VIEWER_MODE
if show_sidebar_nav:
    nav_choice=st.sidebar.radio("Vista",VIEWS,index=VIEWS.index(st.session_state.view))
    if nav_choice!=st.session_state.view:
        st.session_state.view=nav_choice; do_rerun()

# ===== Cargar datos (CSV o Sheets) =====
if USE_SHEETS and SHEET_STUDENTS_URL:
    @st.cache_data
    def load_students():
        df = _sheet_to_df(SHEET_STUDENTS_URL, expected_cols=[
            "id","name","grupo","xp","colegio_id","phone","teacher","xp_delta","xp_reason","avatar",
            "trinket","trinket_desc"
        ])
        # normaliza tipos
        for c in ["xp","colegio_id","xp_delta","id"]:
            if c in df.columns: df[c]=pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        for c in ["name","grupo","phone","teacher","xp_reason","avatar","trinket","trinket_desc"]:
            if c in df.columns: df[c]=df[c].fillna("").astype(str)
        return df
    def save_students(df): _df_to_sheet(SHEET_STUDENTS_URL, df)
else:
    load_students = load_students_csv
    save_students = save_students_csv

students = load_students()
config   = load_milestones()
ms       = config["milestones"]
colegios = load_colegios()
rank_labels=[m["label"] for m in ms]

# ===== Barra + Rango =====
def bar_with_rank(pct,xp_cur,xp_next,color_hex,icon,label,remain_text,
                  side="Derecha",bar_w=520,bar_h=18,icon_w=68):
    def render():
        st.markdown(f"**XP:** {xp_cur} / {xp_next}")
        st.image(pixel_overlay_bar_image(pct,width=bar_w,height=bar_h,color_hex=color_hex))
        st.markdown(f"""
        <div style="position:relative;width:{bar_w}px;margin-top:{TIGHT_BELOW}px;height:20px">
          <div style="position:absolute;left:{LABEL_OFFSET_X}px;top:{LABEL_OFFSET_Y}px;
                      font-weight:bold;color:#fff;white-space:nowrap">{label}</div>
          <div style="position:absolute;right:0;top:0;color:#cfd6ff;white-space:nowrap">{remain_text}</div>
        </div>""", unsafe_allow_html=True)
    if side=="Izquierda":
        c1,c2=st.columns([1.2,12.0],gap="small")
        with c1:
            if icon: st.image(icon,width=icon_w)
        with c2: render()
    else:
        c1,c2=st.columns([2.0,1.2],gap="small")
        with c1: render()
        with c2:
            if icon: st.image(icon,width=icon_w)

# ===== Utilidad: botón copiar portapapeles =====
def copy_link_button(label, text_to_copy, key):
    st.text_input("URL", value=text_to_copy, key=f"{key}_ti", label_visibility="collapsed")
    st.markdown(f"""
    <button id="{key}_btn" style="margin-top:4px;padding:6px 10px;border-radius:6px;border:1px solid #a9c2ff;background:#203a72;color:#eaf2ff;cursor:pointer">
      {label}
    </button>
    <script>
      (function(){{
        const b=document.getElementById("{key}_btn");
        if(b) b.addEventListener("click", async ()=>{{
          try {{
            const val = document.querySelector('input[id$="{key}_ti"]').value;
            await navigator.clipboard.writeText(val);
            b.innerText = "¡Copiado!";
            setTimeout(()=>b.innerText="{label}", 900);
          }} catch(e) {{}}
        }});
      }})();
    </script>
    """, unsafe_allow_html=True)

def make_student_view_link(student_id:int):
    base = st.session_state.get("_base_url_cache")
    if not base:
        # reconstruir de la URL actual
        try:
            from urllib.parse import urlparse
            loc = st._get_script_run_ctx().session_info.ws.request.headers.get("origin","")
            base = loc if loc else ""
        except Exception:
            base = ""
        if not base:
            base = ""  # si no logramos, dejamos relativo
        st.session_state["_base_url_cache"] = base
    # Streamlit generalmente maneja rutas como / o /?...
    return f"{base}/?view=Ficha&sid={int(student_id)}&mode=viewer"

# ===== MAPA =====
if st.session_state.view=="Mapa":
    if VIEWER_MODE:
        st.info("Acceso solo lectura — usa tu enlace de ficha.")
    st.title("🗺️ Reinos de Práctica Pedagógica")
    st.caption("Haz clic en un castillo para entrar")

    W, H = 900, 550; CASTLE = 64
    try:
        base = Image.open(MAP_IMG).convert("RGBA").resize((W, H), Image.LANCZOS)
    except Exception:
        base = Image.new("RGBA", (W, H), (30, 60, 90, 255))

    img = base.copy(); d = ImageDraw.Draw(img)
    GRID_STEP = 50; GRID_COLOR = (255, 255, 255, 40)
    for x in range(0, W, GRID_STEP): d.line([x, 0, x, H], fill=GRID_COLOR)
    for y in range(0, H, GRID_STEP): d.line([0, y, W, y], fill=GRID_COLOR)

    def measure_text(draw, text, font):
        try:
            bbox = draw.textbbox((0, 0), text, font=font); return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            try: return font.getsize(text)
            except Exception: return (len(text)*8, 16)

    boxes=[]
    for _, row in colegios.iterrows():
        icon_path = str(row.get("icono", "assets/castle1.png"))
        try: castle = Image.open(icon_path).resize((CASTLE, CASTLE), Image.NEAREST)
        except Exception: castle = Image.new("RGBA", (CASTLE, CASTLE), (120,120,120,255))
        x, y = int(row["x"]), int(row["y"])
        img.paste(castle, (x, y), castle)

        try:
            fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except Exception:
            fnt = ImageFont.load_default()

        name = str(row["nombre"])
        text_w, text_h = measure_text(d, name, fnt)
        pad_x, pad_y = 8, 4
        left = max(4, min(x, W - (text_w + pad_x*2) - 4))
        top = y + CASTLE + 3
        right, bottom = left + text_w + pad_x*2, top + text_h + pad_y*2
        d.rectangle([left, top, right, bottom], fill=(20, 30, 40, 200))
        d.text((left + pad_x, top + pad_y), name, font=fnt, fill=(255,255,255,255))
        boxes.append((x, y, x + CASTLE, y + CASTLE, int(row["id"]), name))

    coords = streamlit_image_coordinates(img, key="mapa_colegios", width=W)
    if coords and "x" in coords and "y" in coords and not VIEWER_MODE:
        cx, cy = int(coords["x"]), int(coords["y"])
        for (x1, y1, x2, y2, cid, _name) in boxes:
            if x1 <= cx < x2 and y1 <= cy < y2:
                st.session_state.selected_colegio = cid
                st.session_state.view = "Colegio"
                set_qp(view="Colegio")
                do_rerun()

# ===== COLEGIO =====
elif st.session_state.view=="Colegio":
    if st.session_state.selected_colegio is None:
        st.info("Selecciona un colegio desde el mapa.")
    else:
        cid = st.session_state.selected_colegio
        cname = colegios[colegios["id"] == cid]["nombre"].iloc[0]
        st.markdown(f"<h2 class='ff-title'>{cname}</h2>", unsafe_allow_html=True)

        subset = students[students["colegio_id"] == cid].copy().sort_values("xp", ascending=False)

        for _, r in subset.iterrows():
            label, icon, color_hex, pct, remaining, next_label, next_thr = compute_level(int(r["xp"]), ms)
            try: lv = 1 + rank_labels.index(label)
            except: lv = 1

            st.markdown("<div class='ff-panel ff-card ff-compact'>", unsafe_allow_html=True)
            cardL, cardC, cardR = st.columns([0.9, 5.9, 1.2], gap="small")

            with cardL:
                apath = avatar_path_for(r)
                if apath:
                    try: st.image(Image.open(apath), width=110)
                    except: st.image(Image.new("RGBA",(220,220),(90,90,100,255)), width=110)
                else:
                    st.image(Image.new("RGBA",(220,220),(90,90,100,255)), width=110)
                # copiado link alumno
                s_link = make_student_view_link(int(r["id"]))
                copy_link_button("Copiar link de alumno", s_link, key=f"copy_{int(r['id'])}")

            with cardC:
                st.markdown(
                    f"<div class='ff-title' style='font-size:0.95rem'>{r['name']}"
                    f"<span class='ff-badge'>LV {lv}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                remain_text = ("Nivel máximo alcanzado" if next_label=="MAX"
                               else f"Faltan <b>{remaining} XP</b> para {next_label}")
                bar_with_rank(
                    pct=pct,
                    xp_cur=int(r["xp"]),
                    xp_next=(next_thr if next_label!='MAX' else int(r["xp"])),
                    color_hex=color_hex, icon=icon, label=label, remain_text=remain_text,
                    side=st.session_state.rank_side, bar_w=460, bar_h=18, icon_w=58
                )

            with cardR:
                if st.button("Ficha ▶", key=f"ver_{int(r['id'])}", disabled=VIEWER_MODE):
                    st.session_state.selected_student = int(r["id"])
                    st.session_state.view = "Ficha"
                    set_qp(view="Ficha", sid=int(r["id"]))
                    do_rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# ===== FICHA =====
elif st.session_state.view=="Ficha":
    sid = st.session_state.selected_student
    if not sid:
        st.info("Elige un estudiante desde la lista del colegio.")
    else:
        row = students[students["id"]==sid].iloc[0]
        label,icon,color_hex,pct,remaining,next_label,next_thr = compute_level(int(row["xp"]),ms)
        try:
            cname = load_colegios()[load_colegios()["id"]==int(row["colegio_id"])]["nombre"].iloc[0]
        except:
            cname="—"

        st.markdown("<div class='ff-panel ff-card ff-compact'>", unsafe_allow_html=True)
        topL, topR = st.columns([0.8, 5.4], gap="small")

        with topL:
            apath = avatar_path_for(row.to_dict())
            if apath:
                try: st.image(Image.open(apath), width=120)
                except: st.image(Image.new("RGBA",(320,320),(90,90,100,255)), width=120)
            else:
                st.image(Image.new("RGBA",(320,320),(90,90,100,255)), width=120)
            render_trinket_with_tooltip(row.to_dict(), width_px=64)

            # link alumno (útil para el profe)
            s_link = make_student_view_link(int(row["id"]))
            copy_link_button("Copiar link de alumno", s_link, key=f"copy_ficha_{int(row['id'])}")

        with topR:
            subMain, subCal = st.columns([3.6, 1.7], gap="small")
            with subMain:
                st.markdown(
                    f"<div class='ff-title' style='font-size:1.05rem'>{row['name']} — {row['grupo']}"
                    f"<span class='ff-badge'>LV {1+rank_labels.index(label) if label in rank_labels else 1}</span>"
                    f"</div>", unsafe_allow_html=True
                )
                st.markdown("""
                <div style="display:flex;gap:22px;margin-top:6px">
                  <div><span class="ff-stat">Institución</span></div><div style="color:#eaf2ff">{colegio}</div>
                  <div><span class="ff-stat">Teléfono</span></div><div style="color:#eaf2ff">{telefono}</div>
                  <div><span class="ff-stat">Maestro</span></div><div style="color:#eaf2ff">{maestro}</div>
                </div>
                """.format(colegio=cname, telefono=(row.get("phone","") or ""), maestro=(row.get("teacher","") or "")),
                unsafe_allow_html=True)

                st.markdown("<div class='ff-line'></div>", unsafe_allow_html=True)
                remain_text=("Nivel máximo alcanzado" if next_label=="MAX"
                             else f"Faltan <b>{remaining} XP</b> para {next_label}")
                bar_with_rank(
                    pct=pct, xp_cur=int(row["xp"]),
                    xp_next=(next_thr if next_label!='MAX' else int(row["xp"])),
                    color_hex=color_hex, icon=icon, label=label, remain_text=remain_text,
                    side=st.session_state.rank_side, bar_w=560, bar_h=20, icon_w=72
                )

                st.markdown("<div class='ff-line' style='margin-top:10px'></div>", unsafe_allow_html=True)
                tab_hitos, tab_obs, tab_ajustes = st.tabs(["Últimos hitos","Observaciones","Ajustes"])

                with tab_hitos:
                    st.markdown("<div class='ff-panel'>", unsafe_allow_html=True)
                    st.dataframe(recent_logs_for(int(row["id"]), 12), use_container_width=True, hide_index=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                with tab_obs:
                    st.markdown("<div class='ff-panel'>", unsafe_allow_html=True)
                    if not VIEWER_MODE:
                        st.markdown("#### Nueva observación")
                        obs_text = st.text_area("Escribe una observación (se guardará con fecha/hora)", height=120, key=f"obs_textarea_{sid}")
                        col_obs_btn, _ = st.columns([1,3])
                        with col_obs_btn:
                            if st.button("➕ Guardar observación", key=f"save_obs_{sid}", disabled=VIEWER_MODE):
                                text = (obs_text or "").strip()
                                if not text:
                                    st.warning("La observación está vacía.")
                                else:
                                    append_observation(int(row["id"]), row["name"], text)
                                    st.success("Observación guardada."); do_rerun()

                    st.markdown("#### Observaciones recientes")
                    st.dataframe(observations_for(int(row["id"]), 20), use_container_width=True, hide_index=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                with tab_ajustes:
                    st.markdown("<div class='ff-panel'>", unsafe_allow_html=True)
                    delta=st.number_input("Δ XP", min_value=-1000, max_value=1000, value=10, step=1, key=f"adj_delta_{sid}")
                    reason=st.text_input("Motivo", placeholder="Entregó plan, lideró actividad, etc.", key=f"adj_reason_{sid}")
                    colA,_=st.columns([1,3])
                    with colA:
                        st.markdown("&nbsp;", unsafe_allow_html=True)
                        if st.button("Aplicar cambio de XP", key=f"btn_apply_xp_{sid}", disabled=VIEWER_MODE):
                            students.loc[students["id"]==row["id"],"xp"]=int(row["xp"])+int(delta)
                            save_students(students)
                            append_log(row["id"], row["name"], delta, (reason or ""))
                            if delta>0: play_positive_sound()
                            st.success("XP actualizado y hito registrado."); do_rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            with subCal:
                render_mini_calendar(int(row["id"]), subCal, disabled=VIEWER_MODE)
        st.markdown("</div>", unsafe_allow_html=True)

# ===== CONTROL =====
elif st.session_state.view=="Control":
    st.title("🎛️ Control general de XP")
    choice = st.selectbox("Estudiante", load_students()["name"].tolist())
    row = students[students["name"]==choice].iloc[0]
    sid = int(row["id"])
    st.write(f"Colegio: **{int(row['colegio_id'])}** | Grupo: **{row['grupo']}** | XP: **{int(row['xp'])}**")

    delta=st.number_input("Δ XP (positivo o negativo)", min_value=-1000, max_value=1000, value=10, step=1, key="ctl_delta")
    reason=st.text_input("Motivo (se registrará)", placeholder="Entregó plan de clase, etc.", key="ctl_reason")
    if st.button("Aplicar", key="ctl_apply", disabled=VIEWER_MODE):
        students.loc[students["id"]==sid,"xp"]=int(row["xp"])+int(delta)
        save_students(students)
        append_log(sid, row["name"], delta, (reason or ""))
        if delta>0: play_positive_sound()
        st.success("XP actualizado y hito registrado."); do_rerun()

    st.markdown("### Hitos del estudiante")
    raw_logs = all_logs_for(sid)
    if raw_logs.empty:
        st.info("Este estudiante aún no tiene hitos.")
    else:
        editable = raw_logs.loc[:, ["timestamp","delta_xp","reason"]].copy()
        editable.rename(columns={"timestamp":"Fecha/Hora (ISO)","delta_xp":"Δ XP","reason":"Motivo"}, inplace=True)
        editable["Seleccionar"] = False
        edited = st.data_editor(editable, use_container_width=True, hide_index=True, key="logs_editor", disabled=VIEWER_MODE)
        sel_mask = edited["Seleccionar"] == True if "Seleccionar" in edited.columns else pd.Series([], dtype=bool)
        sel_rows = edited[sel_mask]
        col_del, _ = st.columns([1,4])
        with col_del:
            if st.button("🗑️ Eliminar hitos seleccionados", key="del_logs", disabled=VIEWER_MODE):
                if sel_rows.empty:
                    st.warning("No hay hitos seleccionados.")
                else:
                    timestamps_to_delete = set(sel_rows["Fecha/Hora (ISO)"].tolist())
                    selected_raw = raw_logs[raw_logs["timestamp"].isin(timestamps_to_delete)]
                    sum_selected_delta = int(selected_raw["delta_xp"].sum()) if not selected_raw.empty else 0
                    removed = delete_logs_for(sid, timestamps_to_delete)
                    if removed > 0:
                        current_xp = int(students.loc[students["id"]==sid, "xp"].iloc[0])
                        new_xp = current_xp - sum_selected_delta
                        students.loc[students["id"]==sid, "xp"] = new_xp
                        save_students(students)
                        st.success(f"Eliminados {removed} hito(s). XP ajustado: {current_xp} → {new_xp}.")
                        do_rerun()
                    else:
                        st.info("No se eliminaron hitos (verifica la selección).")

    st.markdown("### Observaciones del estudiante")
    raw_obs = all_observations_for(sid)
    if raw_obs.empty:
        st.info("Este estudiante aún no tiene observaciones.")
    else:
        editable_obs = raw_obs.loc[:, ["timestamp","observacion"]].copy()
        editable_obs.rename(columns={"timestamp":"Fecha/Hora (ISO)","observacion":"Observación"}, inplace=True)
        editable_obs["Seleccionar"] = False

        edited_obs = st.data_editor(editable_obs, use_container_width=True, hide_index=True, key="obs_editor", disabled=VIEWER_MODE)
        sel_mask_obs = edited_obs["Seleccionar"] == True if "Seleccionar" in edited_obs.columns else pd.Series([], dtype=bool)
        sel_rows_obs = edited_obs[sel_mask_obs]
        col_del_obs, _ = st.columns([1,4])
        with col_del_obs:
            if st.button("🗑️ Eliminar observaciones seleccionadas", key="del_obs", disabled=VIEWER_MODE):
                if sel_rows_obs.empty:
                    st.warning("No hay observaciones seleccionadas.")
                else:
                    timestamps_to_delete = set(sel_rows_obs["Fecha/Hora (ISO)"].tolist())
                    removed = delete_observations_for(sid, timestamps_to_delete)
                    if removed > 0:
                        st.success(f"Eliminadas {removed} observación(es).")
                        do_rerun()
                    else:
                        st.info("No se eliminaron observaciones (verifica la selección).")

# ===== CONFIG =====
elif st.session_state.view=="Config":
    st.title("⚙️ Configuración")
    st.subheader("Colegios")
    coledit=st.data_editor(load_colegios(), num_rows="dynamic", use_container_width=True, disabled=VIEWER_MODE)
    if st.button("Guardar colegios", disabled=VIEWER_MODE):
        save_colegios(coledit); st.success("Colegios guardados."); do_rerun()

    st.divider()
    st.subheader("Rangos")
    ms_df=pd.DataFrame(load_milestones()["milestones"])
    ms_edit=st.data_editor(ms_df, num_rows="dynamic", use_container_width=True, disabled=VIEWER_MODE)
    if st.button("Guardar niveles/hitos", disabled=VIEWER_MODE):
        with open(MILESTONES_JSON,"w",encoding="utf-8") as f:
            json.dump({"milestones":ms_edit.to_dict(orient="records")},f,ensure_ascii=False,indent=2)
        load_milestones.clear(); st.success("Niveles/hitos guardados."); do_rerun()

    st.divider()
    st.subheader("Estudiantes (edición, avatar, trinket y ajustes rápidos de XP)")
    st_cols = ["id","name","grupo","colegio_id","xp","phone","teacher","avatar","trinket","trinket_desc","xp_delta","xp_reason"]
    for c in st_cols:
        if c not in students.columns:
            students[c] = "" if c in ["name","grupo","phone","teacher","avatar","trinket","trinket_desc","xp_reason"] else 0

    avatar_col_config = {}
    try:
        avatar_col_config = {
            "avatar": st.column_config.SelectboxColumn("Avatar", help="Selecciona el avatar (assets/avatars)", options=AVATAR_OPTIONS, required=False, width="medium"),
            "trinket": st.column_config.SelectboxColumn("Trinket", help="Selecciona un trinket (assets/trinkets). Deja vacío para ocultarlo.", options=[""]+TRINKET_OPTIONS, required=False, width="medium"),
            "trinket_desc": st.column_config.TextColumn("Descripción del trinket", help="Tooltip breve.", width="large"),
        }
    except Exception:
        avatar_col_config = {}
    stu_edit = st.data_editor(students[st_cols], num_rows="dynamic", use_container_width=True, key="stu_editor", column_config=avatar_col_config, disabled=VIEWER_MODE)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Guardar estudiantes (sin aplicar XP)", disabled=VIEWER_MODE):
            merged = students.copy()
            for col in ["name","grupo","colegio_id","phone","teacher","avatar","trinket","trinket_desc","xp_reason","xp_delta","xp"]:
                if col in stu_edit.columns:
                    merged[col] = stu_edit[col]
            save_students(merged)
            st.success("Estudiantes guardados."); do_rerun()

    with c2:
        if st.button("Aplicar XP y registrar hitos", disabled=VIEWER_MODE):
            base = students.copy()
            edit = stu_edit.copy()
            edit["xp_delta"]=pd.to_numeric(edit["xp_delta"], errors="coerce").fillna(0).astype(int)
            for col in ["xp_reason","phone","teacher","name","grupo","avatar","trinket","trinket_desc"]:
                edit[col]=edit[col].fillna("").astype(str)
            applied_count=0
            for _, rr in edit.iterrows():
                sid = rr.get("id")
                if pd.isna(sid): continue
                for c in ["name","grupo","colegio_id","phone","teacher","avatar","trinket","trinket_desc"]:
                    base.loc[base["id"]==sid, c] = rr.get(c, base.loc[base["id"]==sid, c])
                delta=int(rr.get("xp_delta",0) or 0)
                reason=str(rr.get("xp_reason","") or "").strip()
                if delta!=0:
                    cur_xp = int(base.loc[base["id"]==sid,"xp"].iloc[0])
                    base.loc[base["id"]==sid,"xp"]=cur_xp+delta
                    name = base.loc[base["id"]==sid,"name"].iloc[0]
                    append_log(sid, name, delta, reason)
                    applied_count+=1
            base["xp_delta"]=0
            base["xp_reason"]=base["xp_reason"].fillna("").astype(str)
            save_students(base)
            if applied_count>0: play_positive_sound()
            st.success(f"Aplicados {applied_count} ajuste(s) de XP y registrados sus hitos."); do_rerun()
    st.divider()
    side=st.selectbox("Posición del escudo junto a la barra",["Izquierda","Derecha"], index=0 if st.session_state.rank_side=="Izquierda" else 1, disabled=VIEWER_MODE)
    if st.button("Aplicar posición del escudo", disabled=VIEWER_MODE):
        st.session_state.rank_side=side; st.success(f"Posición aplicada: {side}"); do_rerun()
