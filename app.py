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
    df_us = pd.DataFrame(data_us) if data_us else pd.DataFrame(columns=['Email', 'Nome', 'Telefone', 'Departamentos', 'Nivel'])
    df_us.columns = [c.strip() for c in df_us.columns]
    return sheet_ev, sheet_us, df_ev, df_us

# --- 2. CONFIGURAÇÕES ---
cores_niveis = {
    "Nenhum": "#FFFFFF", "BAS": "#C8E6C9", "AV1": "#FFCDD2", "IN": "#BBDEFB",
    "AV2": "#795548", "AV2-24": "#795548", "AV2-23": "#795548", "AV2/": "#795548",
    "AV3": "#E1BEE7", "AV3A": "#E1BEE7", "AV3/": "#E1BEE7", "AV4": "#FFF9C4", "AV4A": "#FFF9C4"
}
lista_deps_fixa = ["Rede Global", "Cultural", "Portaria", "Estacionamento"]
mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}

# --- 3. DIALOGS (CONFIRMAÇÕES) ---

@st.dialog("Confirmar Alteração de Dados")
def confirmar_edicao_dialog(sheet, linha, novos_dados):
    st.warning("Confirme seus novos dados abaixo:")
    st.write(f"📧 **Email:** {novos_dados[0]}")
    st.write(f"👤 **Nome:** {novos_dados[1]}")
    st.write(f"📞 **Telefone:** {novos_dados[2]}")
    st.write(f"🏢 **Deps:** {novos_dados[3]}")
    st.write(f"🎓 **Nível:** {novos_dados[4]}")
    
    if st.button("Confirmar e Entrar", type="primary", width="stretch"):
        # Atualiza a planilha (A até E na linha correspondente)
        sheet.update(f"A{linha}:E{linha}", [novos_dados])
        # Atualiza a sessão para logar direto
        st.session_state.user = {
            "Email": novos_dados[0], "Nome": novos_dados[1], 
            "Telefone": novos_dados[2], "Departamentos": novos_dados[3], 
            "Nivel": novos_dados[4]
        }
        st.session_state.modo_edicao = False
        st.cache_resource.clear()
        st.success("Dados atualizados!")
        st.rerun()

@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, row, vaga_n, col_idx):
    st.markdown(f"### {row['Nome do Evento']}")
    st.write(f"👤 **Vaga:** {vaga_n}")
    if st.button("Confirmar", type="primary", width="stretch"):
        sheet.update_cell(linha, col_idx, st.session_state.user['Nome'])
        st.cache_resource.clear()
        st.rerun()

# --- 4. STYLE ---
st.set_page_config(page_title="ProVida Escala", layout="centered")
st.markdown("""<style>.stButton > button:disabled { background-color: #333333 !important; color: white !important; opacity: 1 !important; border: 1px solid #111 !important; }</style>""", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state.user = None
if 'modo_edicao' not in st.session_state: st.session_state.modo_edicao = False

sheet_ev, sheet_us, df_ev, df_us = load_data()

# --- 5. FLUXO DE ACESSO ---
if st.session_state.user is None:
    st.title("🤝 Escala de Voluntários")
    
    if st.session_state.modo_edicao:
        st.subheader("📝 Alterar Meus Dados")
        # Usamos uma chave para o form de busca
        with st.form("busca_user"):
            email_b = st.text_input("Digite seu e-mail cadastrado:").strip().lower()
            btn_b = st.form_submit_button("Buscar Dados", type="primary")
        
        if email_b:
            user_row = df_us[df_us['Email'].astype(str).str.lower() == email_b]
            if not user_row.empty:
                dados = user_row.iloc[0]
                idx_planilha = user_row.index[0] + 2
                
                # Formulário de edição (sem dialog aninhado diretamente no submit)
                with st.form("edicao_campos"):
                    n_e = st.text_input("Nome Crachá:", value=dados['Nome'])
                    t_e = st.text_input("Telefone:", value=dados['Telefone'])
                    d_atuais = str(dados['Departamentos']).split(",") if dados['Departamentos'] else []
                    d_e = st.multiselect("Departamentos:", lista_deps_fixa, default=[x for x in d_atuais if x in lista_deps_fixa])
                    niv_l = list(cores_niveis.keys())
                    niv_index = niv_l.index(dados['Nivel']) if dados['Nivel'] in niv_l else 0
                    niv_e = st.selectbox("Nível do Curso:", niv_l, index=niv_index)
                    
                    if st.form_submit_button("Salvar Alterações"):
                        lista_novos = [email_b, n_e, t_e, ",".join(d_e), niv_e]
                        confirmar_edicao_dialog(sheet_us, idx_planilha, lista_novos)
            elif btn_b:
                st.error("E-mail não encontrado.")

        if st.button("Voltar"):
            st.session_state.modo_edicao = False
            st.rerun()
            
    else:
        # LOGIN NORMAL
        with st.form("login_main"):
            email_in = st.text_input("Digite seu e-mail para entrar:").strip().lower()
            if st.form_submit_button("Entrar no Sistema", type="primary"):
                u_row = df_us[df_us['Email'].astype(str).str.lower() == email_in]
                if not u_row.empty:
                    st.session_state.user = u_row.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.session_state['temp_email'] = email_in # Guarda para o cadastro

        if 'temp_email' in st.session_state:
            st.info(f"E-mail {st.session_state['temp_email']} não cadastrado. Crie seu perfil:")
            with st.form("novo_cadastro"):
                nc = st.text_input("Nome Crachá:")
                tc = st.text_input("Telefone:")
                dc = st.multiselect("Departamentos:", lista_deps_fixa)
                nvc = st.selectbox("Nível:", list(cores_niveis.keys()))
                if st.form_submit_button("Cadastrar e Entrar"):
                    sheet_us.append_row([st.session_state['temp_email'], nc, tc, ",".join(dc), nvc])
                    st.session_state.user = {"Email": st.session_state['temp_email'], "Nome": nc, "Telefone": tc, "Departamentos": ",".join(dc), "Nivel": nvc}
                    st.cache_resource.clear(); st.rerun()
        
        st.divider()
        if st.button("⚙️ Alterar Meus Dados"):
            st.session_state.modo_edicao = True
            st.rerun()
    st.stop()

# --- 6. DASHBOARD (SÓ CHEGA AQUI SE LOGADO) ---
user = st.session_state.user
st.title(f"🤝 Olá, {user['Nome'].split()[0]}!")

# Filtros
filtro_status = st.pills("Status:", ["Tudo", "Minhas Inscrições", "Vagas Abertas"], default="Tudo")

with st.expander("📅 Mais Filtros"):
    c1, c2 = st.columns(2)
    f_data = c1.date_input("A partir de:", datetime.now().date())
    f_depto = st.multiselect("Departamentos:", lista_deps_fixa, default=lista_deps_fixa)

# Dados Eventos
df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], errors='coerce', dayfirst=True)
df_ev['Niv_N'] = df_ev['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
nivel_user_num = mapa_niveis_num.get(user['Nivel'], 0)
df_ev = df_ev.sort_values(by=['Data_Dt', 'Horario']).reset_index(drop=False)

df_f = df_ev[
    (df_ev['Departamento'].isin(f_depto)) & 
    (df_ev['Niv_N'] <= nivel_user_num) & 
    (df_ev['Data_Dt'].dt.date >= f_data)
].copy()

if filtro_status == "Minhas Inscrições":
    n_l = user['Nome'].lower()
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.lower() == n_l) | (df_f['Voluntário 2'].astype(str).str.lower() == n_l)]
elif filtro_status == "Vagas Abertas":
    df_f = df_f[df_f.apply(lambda x: str(x['Voluntário 1']).strip() == "" or str(x['Voluntário 2']).strip() == "", axis=1)]

# Exibição dos Cards
for i, row in df_f.iterrows():
    v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()
    bg = cores_niveis.get(str(row['Nível']).strip(), "#FFFFFF")
    tx = "#FFFFFF" if "AV2" in str(row['Nível']) else "#000000"
    ja_in = (v1.lower() == user['Nome'].lower() or v2.lower() == user['Nome'].lower())

    st.markdown(f"""
        <div style="background-color: {bg}; padding: 15px; border-radius: 10px 10px 0 0; border: 1px solid #ddd; color: {tx}; margin-top: 15px;">
            <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 0.85em;">
                <span>{"🟢 Completo" if v1 and v2 else ("🟡 1 Vaga" if v1 or v2 else "🔴 2 Vagas")}</span>
                <span>{row['Data_Dt'].strftime('%d/%m')}</span>
            </div>
            <h3 style="margin: 5px 0; color: {tx}; border: none;">{row['Nome do Evento']}</h3>
            <div style="font-size: 0.9em; font-weight: 600; opacity: 0.85; margin-bottom: 5px;">🏢 {row['Departamento']}</div>
            <div style="font-size: 0.9em; margin-bottom: 8px;">⏰ {row['Horario']} | 🎓 Nível: {row['Nível']}</div>
        </div>
    """, unsafe_allow_html=True)

    if ja_in:
        st.button("✅ INSCRITO", key=f"bi_{i}", disabled=True, width="stretch")
    elif v1 and v2:
        st.button("🚫 COMPLETO", key=f"bf_{i}", disabled=True, width="stretch")
    else:
        if st.button("Inscrever-se", key=f"bq_{i}", type="primary", width="stretch"):
            v_alvo, c_alvo = ("Voluntário 1", 8) if v1 == "" else ("Voluntário 2", 9)
            confirmar_inscricao_dialog(sheet_ev, int(row['index'])+2, row, v_alvo, c_alvo)

st.divider()
if st.button("Sair / Trocar Conta"):
    st.session_state.user = None; st.session_state.modo_edicao = False; st.rerun()
