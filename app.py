import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import base64

# --- 1. CONFIGURAÇÃO DE ACESSO (GOOGLE SHEETS) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Verifica se a seção existe para evitar erro de 'KeyError'
    if "gcp_service_account" not in st.secrets:
        st.error("A seção [gcp_service_account] não foi encontrada nos Secrets do Streamlit.")
        st.stop()
        
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # Verifica se o e-mail do cliente existe
    if "client_email" not in creds_info:
        st.error("O campo 'client_email' está em falta nos Secrets. Por favor, verifique a colagem.")
        st.stop()

    # Limpeza da chave privada
    key = creds_info["private_key"].replace("\\n", "\n")
    lines = [line.strip() for line in key.split('\n') if line.strip()]
    creds_info["private_key"] = "\n".join(lines)
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na autorização do Google: {e}")
        st.stop()

def load_data():
    client = get_gspread_client()
    # ID da sua planilha
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- 3. DIÁLOGO DE INSCRIÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, evento, data_ev, vaga_nome, col_index):
    st.warning(f"Você está se inscrevendo como **{vaga_nome}**.")
    st.markdown(f"**Evento:** {evento}  \n**Data:** {data_ev}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, Confirmar", type="primary", use_container_width=True):
            with st.spinner("Gravando..."):
                sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
                st.success("Inscrição confirmada!")
                st.cache_resource.clear()
                st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()

# --- 4. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal ProVida", page_icon="🤝", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- TELA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Portal do Voluntário")
    with st.form("identificacao"):
        nome = st.text_input("Seu Nome Completo")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        submit = st.form_submit_button("Acessar Calendário")
        if submit:
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_nome = nivel
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Por favor, preencha seu nome.")
    st.stop()

# --- CARREGAMENTO DE DADOS ---
try:
    sheet, df = load_data()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

# --- LOGICA DE EXIBIÇÃO ---
st.title(f"🤝 Bem-vindo(a), {st.session_state.nome_usuario}")

df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date

def checar_visibilidade(row, nivel_user):
    tipo_ev = str(row.get('Tipo', '')).strip()
    nivel_ev = row['Nivel_Num']
    if tipo_ev in ["Aberto a não alunos", "Aberto a todos os níveis"]: return True
    if tipo_ev == "Somente o nível da atividade": return nivel_user == nivel_ev
    if tipo_ev == "Nível da atividade e superiores": return nivel_user >= nivel_ev
    if tipo_ev == "Nível da atividade e inferiores": return nivel_user <= nivel_ev
    return nivel_user >= nivel_ev

df['Visivel'] = df.apply(lambda row: checar_visibilidade(row, st.session_state.nivel_usuario_num), axis=1)
df_visivel = df[df['Visivel'] == True].copy()

# --- FILTROS ---
st.markdown("### 🔍 Filtrar Atividades")
c1, c2, c3 = st.columns(3)
col_nome_ev = 'Nome do Evento ou da Atividade' if 'Nome do Evento ou da Atividade' in df_visivel.columns else 'Nome do Evento'
col_depto = 'Departamento Responsável' if 'Departamento Responsável' in df_visivel.columns else 'Departamento'

with c1:
    filtro_evento = st.selectbox("Evento", ["Todos"] + sorted(df_visivel[col_nome_ev].unique().tolist()))
with c2:
    filtro_depto = st.selectbox("Departamento", ["Todos"] + sorted(df_visivel[col_depto].unique().tolist()))
with c3:
    data_filtro = st.date_input("Data mínima:", datetime.now().date())

df_filtrado = df_visivel[df_visivel['Data Formatada'] >= data_filtro]
if filtro_evento != "Todos": df_filtrado = df_filtrado[df_filtrado[col_nome_ev] == filtro_evento]
if filtro_depto != "Todos": df_filtrado = df_filtrado[df_filtrado[col_depto] == filtro_depto]

# --- ÁREA DE INSCRIÇÃO ---
st.markdown("---")
if not df_filtrado.empty:
    df_filtrado['label'] = df_filtrado.apply(lambda x: f"[{x[col_depto]}] {x[col_nome_ev]} - {x['Data Formatada']}", axis=1)
    df_com_vaga = df_filtrado[(df_filtrado['Voluntário 1'] == "") | (df_filtrado['Voluntário 2'] == "")].copy()
    
    if not df_com_vaga.empty:
        escolha = st.selectbox("Escolha uma atividade:", df_com_vaga['label'].tolist())
        if st.button("Me inscrever agora", type="primary"):
            idx = df_com_vaga[df_com_vaga['label'] == escolha].index[0]
            linha_planilha = int(idx) + 2
            v1 = str(df_com_vaga.loc[idx, 'Voluntário 1']).strip()
            vaga_nome = "Voluntário 1" if v1 == "" else "Voluntário 2"
            col_alvo = 7 if v1 == "" else 8
            confirmar_inscricao_dialog(sheet, linha_planilha, df_com_vaga.loc[idx, col_nome_ev], df_com_vaga.loc[idx, 'Data Formatada'], vaga_nome, col_alvo)
    else:
        st.info("Vagas preenchidas para os filtros atuais.")
else:
    st.info("Nenhuma atividade encontrada.")

# --- TABELA ---
st.markdown("### 📋 Escala Atual")
st.dataframe(df_filtrado[[col_nome_ev, 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']], use_container_width=True, hide_index=True)

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()




