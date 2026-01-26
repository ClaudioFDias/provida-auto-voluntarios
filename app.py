import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONEXÃO ---
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
    sheet_ev = ss.worksheet("Calendario_Eventos")
    sheet_us = ss.worksheet("Usuarios") 
    
    df_ev = pd.DataFrame(sheet_ev.get_all_records())
    df_ev.columns = [c.strip() for c in df_ev.columns]
    
    data_us = sheet_us.get_all_records()
    if not data_us:
        df_us = pd.DataFrame(columns=['Email', 'Nome', 'Telefone', 'Departamentos', 'Nivel'])
    else:
        df_us = pd.DataFrame(data_us)
        df_us.columns = [c.strip() for c in df_us.columns]
        
    return sheet_ev, sheet_us, df_ev, df_us

# --- 2. CONFIGURAÇÕES ---
cores_niveis = {
    "Nenhum": "#FFFFFF", "BAS": "#C8E6C9", "AV1": "#FFCDD2", "IN": "#BBDEFB",
    "AV2": "#795548", "AV2-24": "#795548", "AV2-23": "#795548", "AV2/": "#795548",
    "AV3": "#E1BEE7", "AV3A": "#E1BEE7", "AV3/": "#E1BEE7", "AV4": "#FFF9C4", "AV4A": "#FFF9C4"
}
lista_deps = ["Rede Global", "Cultural", "Portaria", "Estacionamento"]
mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}

# --- 3. DIALOG ---
@st.dialog("Confirmar Inscrição")
def confirmar_dialog(sheet, linha, row, vaga_n, col_idx):
    st.markdown(f"### {row['Nome do Evento']}")
    st.write(f"📅 **Data:** {row['Data_Dt'].strftime('%d/%m')}")
    st.write(f"👤 **Vaga:** {vaga_n}")
    if st.button("Confirmar", type="primary", width="stretch"):
        sheet.update_cell(linha, col_idx, st.session_state.user['Nome'])
        st.cache_resource.clear()
        st.rerun()

# --- 4. ESTILO GLOBAL ---
st.set_page_config(page_title="ProVida Escala", layout="centered")

# CSS Reforçado para botões de inscrição (Inscrito/Completo)
st.markdown("""
    <style>
    /* Estiliza botões desabilitados para ficarem escuros e legíveis */
    .stButton > button:disabled {
        background-color: #333333 !important;
        color: white !important;
        opacity: 1 !important;
        border: 1px solid #111 !important;
        font-weight: bold !important;
    }
    /* Estilo para botões primários (Quero me inscrever) */
    .stButton > button[kind="primary"] {
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state.user = None
if 'modo_edicao' not in st.session_state: st.session_state.modo_edicao = False

sheet_ev, sheet_us, df_ev, df_us = load_data()

# --- 5. FLUXO DE ACESSO ---
if st.session_state.user is None:
    st.title("🤝 Escala de Voluntários")
    
    if st.session_state.modo_edicao:
        st.subheader("📝 Alterar Meus Dados")
        email_busca = st.text_input("Confirme seu e-mail cadastrado:").strip().lower()
        if email_busca:
            user_row = df_us[df_us['Email'].astype(str).str.lower() == email_busca]
            if not user_row.empty:
                dados_atuais = user_row.iloc[0]
                idx_linha = user_row.index[0] + 2
                with st.form("form_edicao"):
                    nome_e = st.text_input("Nome no crachá:", value=dados_atuais['Nome'])
                    tel_e = st.text_input("Telefone:", value=dados_atuais['Telefone'])
                    deps_atuais = str(dados_atuais['Departamentos']).split(",") if dados_atuais['Departamentos'] else []
                    deps_e = st.multiselect("Departamentos:", lista_deps, default=[d for d in deps_atuais if d in lista_deps])
                    niveis_lista = list(cores_niveis.keys())
                    try: idx_niv = niveis_lista.index(dados_atuais['Nivel'])
                    except: idx_niv = 0
                    niv_e = st.selectbox("Nível do Curso:", niveis_lista, index=idx_niv)
                    if st.form_submit_button("Salvar Alterações"):
                        novos_dados = [email_busca, nome_e, tel_e, ",".join(deps_e), niv_e]
                        sheet_us.update(f"A{idx_linha}:E{idx_linha}", [novos_dados])
                        st.success("Dados atualizados!")
                        st.session_state.modo_edicao = False
                        st.cache_resource.clear(); st.rerun()
            else: st.error("E-mail não encontrado.")
        if st.button("Voltar"): st.session_state.modo_edicao = False; st.rerun()
            
    else:
        email_input = st.text_input("Digite seu e-mail para entrar:").strip().lower()
        if email_input:
            user_row = df_us[df_us['Email'].astype(str).str.lower() == email_input]
            if not user_row.empty:
                st.session_state.user = user_row.iloc[0].to_dict()
                st.rerun() 
            else:
                st.info("E-mail não cadastrado. Crie seu perfil:")
                with st.form("cadastro_form"):
                    nome_c = st.text_input("Nome Crachá:")
                    tel_c = st.text_input("Telefone:")
                    deps_c = st.multiselect("Departamentos:", lista_deps)
                    niv_c = st.selectbox("Nível:", list(cores_niveis.keys()))
                    if st.form_submit_button("Criar e Entrar"):
                        if nome_c and tel_c and deps_c:
                            sheet_us.append_row([email_input, nome_c, tel_c, ",".join(deps_c), niv_c])
                            st.session_state.user = {"Email": email_input, "Nome": nome_c, "Telefone": tel_c, "Departamentos": ",".join(deps_c), "Nivel": niv_c}
                            st.cache_resource.clear(); st.rerun()
        st.markdown("---")
        if st.button("⚙️ Alterar Meus Dados"): st.session_state.modo_edicao = True; st.rerun()
    st.stop()

# --- 6. DASHBOARD ---
user = st.session_state.user
st.title(f"🤝 Olá, {user['Nome'].split()[0]}!")

meus_deps = str(user['Departamentos']).split(",")
nivel_max_num = mapa_niveis_num.get(user['Nivel'], 0)

with st.expander("🔍 Filtros"):
    f_dat = st.date_input("A partir de:", datetime.now().date())
    filtro_status = st.pills("Status:", ["Tudo", "Minhas Inscrições", "Vagas Abertas"], default="Tudo")

df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], errors='coerce', dayfirst=True)
df_ev['Niv_N'] = df_ev['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
df_ev = df_ev.sort_values(by=['Data_Dt', 'Horario']).reset_index(drop=False)

df_f = df_ev[
    (df_ev['Departamento'].isin(meus_deps)) & 
    (df_ev['Niv_N'] <= nivel_max_num) & 
    (df_ev['Data_Dt'].dt.date >= f_dat)
].copy()

if filtro_status == "Minhas Inscrições":
    n_l = user['Nome'].lower()
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.lower() == n_l) | (df_f['Voluntário 2'].astype(str).str.lower() == n_l)]
elif filtro_status == "Vagas Abertas":
    df_f = df_f[df_f.apply(lambda x: str(x['Voluntário 1']).strip() == "" or str(x['Voluntário 2']).strip() == "", axis=1)]

# Exibição
if df_f.empty:
    st.info("Nenhuma atividade disponível para seu perfil.")
else:
    for i, row in df_f.iterrows():
        v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()
        bg = cores_niveis.get(str(row['Nível']).strip(), "#FFFFFF")
        tx = "#FFFFFF" if "AV2" in str(row['Nível']) else "#000000"
        status = "🟢 Completo" if v1 and v2 else ("🟡 1 Vaga" if v1 or v2 else "🔴 2 Vagas")
        ja_in = (v1.lower() == user['Nome'].lower() or v2.lower() == user['Nome'].lower())

        st.markdown(f"""
            <div style="background-color: {bg}; padding: 15px; border-radius: 10px 10px 0 0; border: 1px solid #ddd; color: {tx}; margin-top: 15px;">
                <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 0.85em;">
                    <span>{status}</span><span>{row['Data_Dt'].strftime('%d/%m')}</span>
                </div>
                <h3 style="margin: 5px 0; color: {tx}; border: none;">{row['Nome do Evento']}</h3>
                <div style="font-size: 0.9em; font-weight: 600; opacity: 0.85; margin-bottom: 5px;">🏢 {row['Departamento']}</div>
                <div style="font-size: 0.9em; margin-bottom: 8px;">⏰ {row['Horario']} | 🎓 Nível: {row['Nível']}</div>
                <div style="background: rgba(0,0,0,0.15); padding: 8px; border-radius: 5px; font-size: 0.9em;">
                    <b>V1:</b> {v1}<br><b>V2:</b> {v2}
                </div>
            </div>
        """, unsafe_allow_html=True)

        if ja_in:
            st.button("✅ VOCÊ JÁ ESTÁ INSCRITO", key=f"btn_in_{i}", disabled=True, width="stretch")
        elif v1 and v2:
            st.button("🚫 ESCALA COMPLETA", key=f"btn_full_{i}", disabled=True, width="stretch")
        else:
            if st.button("Quero me inscrever", key=f"btn_go_{i}", type="primary", width="stretch"):
                v_alvo, c_alvo = ("Voluntário 1", 8) if v1 == "" else ("Voluntário 2", 9)
                confirmar_dialog(sheet_ev, int(row['index'])+2, row, v_alvo, c_alvo)

st.divider()
if st.button("Sair / Trocar Conta"):
    st.session_state.user = None
    st.session_state.modo_edicao = False
    st.rerun()
