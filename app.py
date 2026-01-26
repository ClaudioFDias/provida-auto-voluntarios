import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONEXÃO (Mantida) ---
@st.cache_resource
def get_gspread_client():
    try:
        partes = [f"S{i}" for i in range(1, 22)]
        chave_full = "".join([re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[p]) for p in partes])
        key_lines = textwrap.wrap(chave_full, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        creds_info = {
            "type": st.secrets["TYPE"], "project_id": st.secrets["PROJECT_ID"],
            "private_key_id": st.secrets["PRIVATE_KEY_ID"], "private_key": formatted_key,
            "client_email": st.secrets["CLIENT_EMAIL"], "client_id": st.secrets["CLIENT_ID"],
            "auth_uri": st.secrets["AUTH_URI"], "token_uri": st.secrets["TOKEN_URI"],
            "auth_provider_x509_cert_url": st.secrets["AUTH_PROVIDER_X509_CERT_URL"],
            "client_x509_cert_url": st.secrets["CLIENT_X509_CERT_URL"]
        }
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception:
        st.error("Erro de conexão."); st.stop()

def load_data():
    client = get_gspread_client()
    ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    sheet = ss.worksheet("Calendario_Eventos")
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. CONFIGURAÇÕES VISUAIS ---
cores_niveis = {
    "Nenhum": "#FFFFFF", "BAS": "#C8E6C9", "AV1": "#FFCDD2", "IN": "#BBDEFB",
    "AV2": "#795548", "AV2-24": "#795548", "AV2-23": "#795548", "Av.2/": "#795548",
    "AV3": "#E1BEE7", "AV3A": "#E1BEE7", "AV3/": "#E1BEE7", "AV4": "#FFF9C4", "AV4A": "#FFF9C4"
}

def cor_texto(nivel):
    return "#FFFFFF" if "AV2" in nivel else "#000000"

mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}
dias_semana_extenso = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}

def info_status(row):
    v1, v2 = str(row.get('Voluntário 1', '')).strip(), str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 2 Vagas"
    if v1 == "" or v2 == "": return "🟡 1 Vaga"
    return "🟢 Completo"

# --- 3. DIALOG ---
@st.dialog("Confirmar Inscrição")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx, col_ev, col_hr):
    st.markdown(f"### {row[col_ev]}")
    st.write(f"📅 **Data:** {row['Data_Dt'].strftime('%d/%m')} ({row['Dia_Extenso']})")
    st.write(f"👤 **Vaga:** {vaga_n}")
    if st.button("Confirmar", type="primary", width="stretch"):
        sheet.update_cell(linha, col_idx, st.session_state.nome_usuario)
        st.cache_resource.clear()
        st.rerun()

# --- 4. LOGIN ---
st.set_page_config(page_title="ProVida Escala", layout="centered")

if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login")
    with st.form("login"):
        n = st.text_input("Nome Completo")
        niv = st.selectbox("Seu Nível", list(cores_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if n: 
                st.session_state.update({"nome_usuario": n, "nivel_num": mapa_niveis_num[niv], "autenticado": True})
                st.rerun()
    st.stop()

# --- 5. PROCESSAMENTO ---
try:
    sheet, df = load_data()
    col_ev = next((c for c in df.columns if 'Evento' in c), 'Evento')
    col_hr = next((c for c in df.columns if c.lower() in ['horário', 'horario', 'hora']), 'Horario')
    
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce', dayfirst=True)
    df['Dia_Extenso'] = df['Data_Dt'].dt.weekday.map(dias_semana_extenso)
    df['Niv_N'] = df['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
    df = df.sort_values(by=['Data_Dt', col_hr]).reset_index(drop=False)

    # --- 6. INTERFACE DE FILTROS RÁPIDOS (SEM SIDEBAR) ---
    st.title(f"🤝 Olá, {st.session_state.nome_usuario.split()[0]}")
    
    # Usando st.pills para filtros de um clique (Novidade Streamlit)
    st.write("🔍 **Filtros Rápidos:**")
    filtro_status = st.pills(
        "Ver apenas:",
        ["Tudo", "Minhas Inscrições", "Sem Voluntários", "Vagas Abertas"],
        default="Tudo"
    )
    
    with st.expander("📅 Filtrar por Data ou Nível"):
        col1, col2 = st.columns(2)
        f_dat = col1.date_input("A partir de:", datetime.now().date())
        niveis_disp = sorted(df['Nível'].unique().tolist())
        f_nivel = col2.multiselect("Nível específico:", niveis_disp)

    # Lógica de Filtros
    df_f = df[(df['Niv_N'] <= st.session_state.nivel_num) & (df['Data_Dt'].dt.date >= f_dat)].copy()

    if f_nivel:
        df_f = df_f[df_f['Nível'].isin(f_nivel)]

    if filtro_status == "Minhas Inscrições":
        nome = st.session_state.nome_usuario.strip().lower()
        df_f = df_f[(df_f['Voluntário 1'].astype(str).str.lower().str.contains(nome)) | 
                    (df_f['Voluntário 2'].astype(str).str.lower().str.contains(nome))]
    
    elif filtro_status == "Sem Voluntários":
        df_f = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") & 
                    (df_f['Voluntário 2'].astype(str).str.strip() == "")]
    
    elif filtro_status == "Vagas Abertas":
        df_f = df_f[df_f.apply(lambda x: "Vaga" in info_status(x), axis=1)]

    # --- 7. EXIBIÇÃO ---
    st.subheader(f"📋 Atividades Encontradas: {len(df_f)}")
    
    for i, row in df_f.iterrows():
        status_txt = info_status(row)
        nivel_row = str(row['Nível']).strip()
        bg_cor = cores_niveis.get(nivel_row, "#FFFFFF")
        txt_cor = cor_texto(nivel_row)
        v1_val, v2_val = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()

        st.markdown(f"""
            <div style="background-color: {bg_cor}; padding: 15px; border-radius: 10px 10px 0 0; border: 1px solid #ddd; color: {txt_cor}; margin-top: 15px;">
                <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 0.85em; opacity: 0.9;">
                    <span>{status_txt}</span>
                    <span>{row['Data_Dt'].strftime('%d/%m')} - {row['Dia_Extenso']}</span>
                </div>
                <h3 style="margin: 8px 0; color: {txt_cor}; border: none; font-size: 1.2em;">{row[col_ev]}</h3>
                <div style="font-size: 1em; margin-bottom: 8px;">
                    ⏰ <b>Horário:</b> {row[col_hr]} | 🎓 <b>Nível:</b> {nivel_row}
                </div>
                <div style="background: rgba(0,0,0,0.1); padding: 8px; border-radius: 5px; font-size: 0.95em;">
                    👤 <b>Voluntário 1:</b> {v1_val}<br>
                    👤 <b>Voluntário 2:</b> {v2_val}
                </div>
            </div>
        """, unsafe_allow_html=True)

        if "Completo" not in status_txt:
            if st.button(f"Quero me inscrever", key=f"btn_{i}", type="primary", width="stretch"):
                confirmar_dialog(sheet, int(row['index'])+2, row, ("Voluntário 1" if v1_val=="" else "Voluntário 2"), (7 if v1_val=="" else 8), col_ev, col_hr)
        else:
            msg = "✅ Você está inscrito" if st.session_state.nome_usuario.lower() in [v1_val.lower(), v2_val.lower()] else "✅ Escala Completa"
            st.button(msg, key=f"btn_{i}", disabled=True, width="stretch")

    if st.button("Sair do Sistema", icon="🚪"):
        st.session_state.autenticado = False
        st.rerun()

except Exception as e:
    st.error(f"Erro: {e}")
