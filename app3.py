import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONEXÃO COM GOOGLE SHEETS ---
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

# --- 2. CONFIGURAÇÕES E ESTILO ---
mapa_niveis = {"Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3, "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8}
dias_semana = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}

def definir_status(row):
    v1 = str(row.get('Voluntário 1', '')).strip()
    v2 = str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 2 Vagas"
    if v1 == "" or v2 == "": return "🟡 1 Vaga"
    return "🟢 Completo"

def aplicar_estilo_linha(row):
    # O estilo agora olha para o texto exato da coluna Status
    status = str(row.get('Status', ''))
    if "2 Vagas" in status:
        bg_color = '#FFEBEE' # Vermelho claro
    elif "1 Vaga" in status:
        bg_color = '#FFF9C4' # Amarelo claro
    else:
        bg_color = '#FFFFFF' # Branco
    return [f'background-color: {bg_color}; color: black'] * len(row)

# --- 3. COMPONENTE DE CONFIRMAÇÃO ---
@st.dialog("Confirmar")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx, col_ev):
    st.write(f"**{row[col_ev]}**")
    st.write(f"{row['Data_Formatada'].strftime('%d/%m')} ({row['Dia_da_Semana']})")
    st.write(f"Vaga: {vaga_n}")
    if st.button("Confirmar", type="primary", use_container_width=True):
        with st.spinner("Salvando..."):
            sheet.update_cell(linha, col_idx, st.session_state.nome_usuario)
            st.cache_resource.clear()
            st.rerun()

# --- 4. INTERFACE E LOGIN ---
st.set_page_config(page_title="ProVida", layout="wide")
st.markdown("<style>.stApp {background-color: white; color: black;} h1,h2,h3,p,label,div {color: black !important;}</style>", unsafe_allow_html=True)

if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login")
    with st.form("login"):
        n = st.text_input("Nome Completo")
        niv = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if n: 
                st.session_state.update({"nome_usuario": n, "nivel_num": mapa_niveis[niv], "autenticado": True})
                st.rerun()
    st.stop()

# --- 5. PROCESSAMENTO DE DADOS ---
try:
    sheet, df = load_data()
    col_ev = next((c for c in df.columns if 'Evento' in c), 'Evento')
    
    # Datas e Status
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce')
    df['Data_Formatada'] = df['Data_Dt'].dt.date
    df['Dia_da_Semana'] = df['Data_Dt'].dt.weekday.map(dias_semana)
    df['Niv_N'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df['Status'] = df.apply(definir_status, axis=1)

    st.title(f"🤝 Olá, {st.session_state.nome_usuario.split()[0]}")

    with st.sidebar:
        f_dat = st.date_input("Filtrar Data", datetime.now().date())
        so_vagas = st.checkbox("Ver apenas vagas", value=False)
        if st.button("Sair"): 
            st.session_state.autenticado = False
            st.rerun()

    # Filtro de permissão e data
    df_f = df[(df['Niv_N'] <= st.session_state.nivel_num) & (df['Data_Formatada'] >= f_dat)].copy()
    if so_vagas: 
        df_f = df_f[df_f['Status'] != "🟢 Completo"]

    # --- 6. INSCRIÇÃO POR LISTA (MOBILE FRIENDLY) ---
    st.subheader("📝 Inscrição Rápida")
    v_l = df_f[df_f['Status'] != "🟢 Completo"].copy()
    if not v_l.empty:
        v_l['label'] = v_l.apply(lambda x: f"{x['Data_Formatada'].strftime('%d/%m')} | {x[col_ev][:12]}.. | {x['Status']}", axis=1)
        esc = st.selectbox("Escolha a atividade:", v_l['label'].tolist(), index=None, placeholder="Selecione...")
        if esc:
            idx = v_l[v_l['label'] == esc].index[0]
            if st.button("Inscrever-se", type="primary"):
                lin = int(idx) + 2
                v1_val = str(sheet.cell(lin, 7).value).strip()
                confirmar_dialog(sheet, lin, v_l.loc[idx], ("V1" if v1_val == "" else "V2"), (7 if v1_val == "" else 8), col_ev)
    
    # --- 7. ESCALA (TABELA COLORIDA) ---
    st.divider()
    st.subheader("📋 Escala")
    st.caption("Toque na linha para se inscrever")

    # Preparando DataFrame para exibição mobile
    df_show = df_f.copy()
    df_show = df_show.rename(columns={col_ev: 'Evento', 'Data_Formatada': 'Data', 'Dia_da_Semana': 'Dia', 'Voluntário 1': 'V1', 'Voluntário 2': 'V2'})
    cols_display = ['Status', 'Evento', 'Data', 'Dia', 'V1', 'V2']

    # Aplicação do Estilo e Exibição
    sel = st.dataframe(
        df_show[cols_display].style.apply(aplicar_estilo_linha, axis=1), 
        use_container_width=True, 
        hide_index=True, 
        on_select="rerun", 
        selection_mode="single-row"
    )

    # Detecção de Clique na Tabela
    if sel.selection.rows:
        r_idx = sel.selection.rows[0]
        r_sel = df_f.iloc[r_idx] # Usa o DF original para pegar dados reais
        if "Completo" not in r_sel['Status']:
            lin_orig = int(r_sel.name) + 2
            v1_a = str(r_sel['Voluntário 1']).strip()
            confirmar_dialog(sheet, lin_orig, r_sel, ("V1" if v1_a == "" else "V2"), (7 if v1_a == "" else 8), col_ev)
        else:
            st.warning("Escala já preenchida.")

except Exception as e:
    st.error("Erro ao carregar os dados. Verifique a planilha.")
