import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, date
import textwrap
import re
import time

# --- 1. CONEXÃO RESILIENTE ---
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
        st.error("Erro crítico de conexão."); st.stop()

@st.cache_data(ttl=300) # Cache de 5 minutos
def load_data_cached():
    client = get_gspread_client()
    # Tentativas de leitura para evitar erro de cota
    for tentativa in range(3):
        try:
            ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
            
            # Lendo Calendário
            sheet_ev = ss.worksheet("Calendario_Eventos")
            data_ev = sheet_ev.get_all_records()
            df_ev = pd.DataFrame(data_ev)
            df_ev.columns = [c.strip() for c in df_ev.columns]
            
            # Lendo Usuários
            sheet_us = ss.worksheet("Usuarios") 
            data_us = sheet_us.get_all_records()
            df_us = pd.DataFrame(data_us) if data_us else pd.DataFrame(columns=['Email', 'Nome', 'Telefone', 'Departamentos', 'Nivel'])
            df_us.columns = [c.strip() for c in df_us.columns]
            
            return df_ev, df_us
        except gspread.exceptions.APIError as e:
            if tentativa < 2:
                time.sleep(2) # Espera 2 segundos e tenta de novo
                continue
            else:
                st.error("O Google Sheets está ocupado. Aguarde 30 segundos e atualize a página.")
                st.stop()

def get_sheets():
    # Sem cache para operações de escrita (Update)
    client = get_gspread_client()
    ss = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    return ss.worksheet("Calendario_Eventos"), ss.worksheet("Usuarios")

# --- 2. CONFIGURAÇÕES ---
cores_niveis = {
    "Nenhum": "#FFFFFF", "BAS": "#C8E6C9", "AV1": "#FFCDD2", "IN": "#BBDEFB",
    "AV2": "#795548", "AV2-24": "#795548", "AV2-23": "#795548", "AV2/": "#795548",
    "AV3": "#E1BEE7", "AV3A": "#E1BEE7", "AV3/": "#E1BEE7", "AV4": "#FFF9C4", "AV4A": "#FFF9C4"
}
mapa_niveis_num = {k: i for i, k in enumerate(cores_niveis.keys())}
dias_semana = {"Monday": "Seg", "Tuesday": "Ter", "Wednesday": "Qua", "Thursday": "Qui", "Friday": "Sex", "Saturday": "Sáb", "Sunday": "Dom"}

# --- 3. DIALOGS ---
@st.dialog("Conflito de Agenda")
def conflito_dialog(evento_nome, horario):
    st.warning("⚠️ **Você já possui uma atividade neste horário!**")
    st.info(f"Evento conflitante: **{evento_nome}** às **{horario}**")
    if st.button("Entendido", type="primary", width="stretch"):
        st.rerun()

@st.dialog("Confirmar Alteração de Cadastro")
def confirmar_edicao_dialog(linha, novos_dados):
    st.markdown("### Verifique seus novos dados:")
    st.markdown(f"**Nome:** {novos_dados[1]}\n**Telefone:** {novos_dados[2]}\n**Nível:** {novos_dados[4]}\n**Departamentos:** {novos_dados[3]}")
    st.info("Ao confirmar, o app será atualizado.")
    if st.button("Confirmar e Salvar", type="primary", width="stretch"):
        _, sheet_us = get_sheets()
        sheet_us.update(f"A{linha}:E{linha}", [novos_dados])
        st.session_state.user = {"Email": novos_dados[0], "Nome": novos_dados[1], "Telefone": novos_dados[2], "Departamentos": novos_dados[3], "Nivel": novos_dados[4]}
        st.session_state.modo_edicao = False
        st.cache_data.clear(); st.success("Atualizado!"); st.rerun()

@st.dialog("Confirmar Inscrição")
def confirmar_dialog(linha, row, col_idx):
    dia_pt = dias_semana.get(row['Data_Dt'].strftime('%A'), "")
    st.markdown(f"### {row['Nível']} - {row['Nome do Evento']}")
    st.write(f"📅 **Data:** {dia_pt} - {row['Data_Dt'].strftime('%d/%m/%Y')}")
    st.write(f"⏰ **Horário:** {row['Horario']} | 🏢 **Depto:** {row['Departamento']}")
    st.divider()
    if st.button("Confirmar Inscrição", type="primary", width="stretch"):
        with st.spinner("Salvando..."):
            sheet_ev, _ = get_sheets()
            sheet_ev.update_cell(linha, col_idx, st.session_state.user['Nome'])
            st.cache_data.clear()
            st.rerun()

# --- 4. STYLE ---
st.set_page_config(page_title="ProVida Escala", layout="centered")
st.markdown("""
    <style>
    .card-container { padding: 15px; border-radius: 12px 12px 0 0; border: 1px solid #ddd; margin-top: 15px; }
    .card-header { display: flex; justify-content: space-between; align-items: center; font-weight: 800; }
    .card-title { margin: 8px 0; font-size: 1.4em; line-height: 1.2; }
    .voluntarios-box { background: rgba(0,0,0,0.07); padding: 10px; border-radius: 8px; font-size: 1rem; }
    .data-text { font-size: 1.2em; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state.user = None
if 'modo_edicao' not in st.session_state: st.session_state.modo_edicao = False

# Carregamento inicial com Retry
df_ev, df_us = load_data_cached()
deps_na_planilha = sorted([d for d in df_ev['Departamento'].unique() if str(d).strip() != ""])

# --- 5. ACESSO / LOGIN / EDIÇÃO ---
if st.session_state.user is None:
    st.title("🤝 Escala de Voluntários")
    if st.session_state.modo_edicao:
        st.subheader("📝 Alterar Meus Dados")
        with st.form("busca_edicao"):
            email_b = st.text_input("E-mail cadastrado:").strip().lower()
            if st.form_submit_button("Buscar Cadastro", type="primary", width="stretch"):
                user_row = df_us[df_us['Email'].astype(str).str.lower() == email_b]
                if not user_row.empty: 
                    st.session_state['edit_row'] = user_row.iloc[0].to_dict()
                    st.session_state['edit_idx'] = user_row.index[0] + 2
                else: st.error("E-mail não encontrado.")
        if 'edit_row' in st.session_state:
            with st.form("edicao_final"):
                dados = st.session_state['edit_row']
                n_e = st.text_input("Nome Crachá:", value=dados['Nome'])
                t_e = st.text_input("Telefone:", value=dados['Telefone'])
                d_e = st.multiselect("Seus Departamentos:", options=deps_na_planilha, default=[d.strip() for d in str(dados['Departamentos']).split(",") if d.strip() in deps_na_planilha])
                niv_l = list(cores_niveis.keys())
                niv_e = st.selectbox("Nível:", niv_l, index=niv_l.index(dados['Nivel']) if dados['Nivel'] in niv_l else 0)
                if st.form_submit_button("Revisar Alterações", type="primary", width="stretch"):
                    confirmar_edicao_dialog(st.session_state['edit_idx'], [dados['Email'], n_e, t_e, ",".join(d_e), niv_e])
        if st.button("Voltar"): st.session_state.modo_edicao = False; st.rerun()
    else:
        with st.form("login"):
            em = st.text_input("E-mail para entrar:").strip().lower()
            if st.form_submit_button("Entrar no Sistema", type="primary", width="stretch"):
                u = df_us[df_us['Email'].astype(str).str.lower() == em]
                if not u.empty: st.session_state.user = u.iloc[0].to_dict(); st.rerun()
                else: st.session_state['novo_em'] = em
        if 'novo_em' in st.session_state:
            with st.form("cad"):
                nc = st.text_input("Nome Crachá:"); tc = st.text_input("Telefone:")
                dc = st.multiselect("Departamentos:", options=deps_na_planilha)
                nv = st.selectbox("Nível:", list(cores_niveis.keys()))
                if st.form_submit_button("Cadastrar"):
                    _, sheet_us = get_sheets()
                    sheet_us.append_row([st.session_state['novo_em'], nc, tc, ",".join(dc), nv])
                    st.session_state.user = {"Email": st.session_state['novo_em'], "Nome": nc, "Telefone": tc, "Departamentos": ",".join(dc), "Nivel": nv}
                    st.cache_data.clear(); st.rerun()
        st.divider()
        if st.button("⚙️ Alterar Meus Dados"): st.session_state.modo_edicao = True; st.rerun()
    st.stop()

# --- 6. DASHBOARD ---
user = st.session_state.user
meus_deps = [d.strip() for d in str(user['Departamentos']).split(",") if d.strip() != ""]
st.title(f"🤝 Olá, {user['Nome'].split()[0]}!")

filtro_status = st.pills("Status:", ["Vagas Abertas", "Vagas Vazias", "Minhas Inscrições", "Tudo"], default="Vagas Abertas")
f_depto_pill = st.pills("Departamento:", ["Todos"] + meus_deps, default="Todos")

c1, c2 = st.columns(2)
with c1: f_nivel = st.selectbox("Filtrar por Nível:", ["Todos"] + list(cores_niveis.keys()))
with c2: f_data = st.date_input("A partir de:", value=date.today())

# Processamento de Dados
df_ev['Data_Dt'] = pd.to_datetime(df_ev['Data Específica'], errors='coerce', dayfirst=True)
df_ev['Niv_N'] = df_ev['Nível'].astype(str).str.strip().map(mapa_niveis_num).fillna(99)
df_ev = df_ev.sort_values(by=['Data_Dt', 'Horario']).reset_index(drop=False)

df_f = df_ev[df_ev['Departamento'].isin(meus_deps)].copy()
df_f = df_f[(df_f['Niv_N'] <= mapa_niveis_num.get(user['Nivel'], 0)) & (df_f['Data_Dt'].dt.date >= f_data)]

if f_depto_pill != "Todos": df_f = df_f[df_f['Departamento'] == f_depto_pill]
if f_nivel != "Todos": df_f = df_f[df_f['Nível'].astype(str).str.strip() == f_nivel]

nome_u_comp = user['Nome'].lower().strip()
if filtro_status == "Minhas Inscrições":
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.lower().str.strip() == nome_u_comp) | (df_f['Voluntário 2'].astype(str).str.lower().str.strip() == nome_u_comp)]
elif filtro_status == "Vagas Abertas":
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") | (df_f['Voluntário 2'].astype(str).str.strip() == "")]
elif filtro_status == "Vagas Vazias":
    df_f = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") & (df_f['Voluntário 2'].astype(str).str.strip() == "")]

# Listagem
for i, row in df_f.iterrows():
    v1, v2 = str(row['Voluntário 1']).strip(), str(row['Voluntário 2']).strip()
    dia_abreviado = dias_semana.get(row['Data_Dt'].strftime('%A'), "")
    bg = cores_niveis.get(str(row['Nível']).strip(), "#FFFFFF")
    tx = "#FFFFFF" if "AV2" in str(row['Nível']) else "#000000"
    st_vaga = "🟢 Cheio" if v1 and v2 else ("🟡 1 Vaga" if v1 or v2 else "🔴 2 Vagas")

    st.markdown(f"""
        <div class="card-container" style="background-color: {bg}; color: {tx};">
            <div class="card-header"><span style="opacity: 0.8;">{st_vaga}</span><span class="data-text">{dia_abreviado} - {row['Data_Dt'].strftime('%d/%m')}</span></div>
            <h2 class="card-title" style="color: {tx};">{row['Nível']} - {row['Nome do Evento']}</h2>
            <div style="font-weight: 800; margin-bottom: 10px;">🏢 {row['Departamento']} | ⏰ {row['Horario']}</div>
            <div class="voluntarios-box"><b>Voluntário 1:</b> {v1 if v1 else "---"}<br><b>Voluntário 2:</b> {v2 if v2 else "---"}</div>
        </div>
    """, unsafe_allow_html=True)

    ja_in = (v1.lower() == nome_u_comp or v2.lower() == nome_u_comp)
    if ja_in: st.button("✅ INSCRITO", key=f"bi_{i}", disabled=True, width="stretch")
    elif v1 and v2: st.button("🚫 CHEIO", key=f"bf_{i}", disabled=True, width="stretch")
    else:
        if st.button("Quero me inscrever", key=f"bq_{i}", type="primary", width="stretch"):
            conflito = df_ev[(df_ev['Data Específica'] == row['Data Específica']) & (df_ev['Horario'] == row['Horario']) & ((df_ev['Voluntário 1'].astype(str).str.lower().str.strip() == nome_u_comp) | (df_ev['Voluntário 2'].astype(str).str.lower().str.strip() == nome_u_comp))]
            if not conflito.empty: conflito_dialog(conflito.iloc[0]['Nome do Evento'], conflito.iloc[0]['Horario'])
            else:
                v_alvo, c_alvo = ("Voluntário 1", 8) if v1 == "" else ("Voluntário 2", 9)
                confirmar_dialog(int(row['index'])+2, row, c_alvo)

st.divider()
if st.button("🔄 Sincronizar Planilha"): st.cache_data.clear(); st.rerun()
if st.button("Sair"): st.session_state.user = None; st.rerun()
