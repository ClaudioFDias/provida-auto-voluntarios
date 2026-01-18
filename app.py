import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime


# 1. Configuração de Acesso
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [col.strip() for col in df.columns]
    return sheet, df


# 2. Configurações de Níveis
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}


# --- FUNÇÃO DO OVERLAY DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, evento, data_ev, vaga_nome, col_index):
    st.warning(f"Você está se inscrevendo como **{vaga_nome}**.")
    st.markdown(f"""
    **Detalhes da Atividade:**
    - **Evento:** {evento}
    - **Data:** {data_ev}
    - **Voluntário:** {st.session_state.nome_usuario}
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, Confirmar", type="primary", use_container_width=True):
            with st.spinner("Gravando..."):
                sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
                st.success("Inscrição realizada!")
                st.cache_resource.clear()
                st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


st.set_page_config(page_title="Portal ProVida", page_icon="🤝", layout="wide")

# --- PASSO 1: IDENTIFICAÇÃO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

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
                st.error("Por favor, insira seu nome.")
    st.stop()

# --- PASSO 2: PORTAL ---
sheet, df = load_data()
st.title(f"🤝 Bem-vindo(a), {st.session_state.nome_usuario}")

df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date


# Lógica de Visibilidade
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

# Filtros
st.markdown("### 🔍 Filtrar Atividades")
c1, c2, c3 = st.columns(3)
col_nome_ev = 'Nome do Evento ou da Atividade' if 'Nome do Evento ou da Atividade' in df_visivel.columns else 'Nome do Evento'
col_depto = 'Departamento Responsável' if 'Departamento Responsável' in df_visivel.columns else 'Departamento'

with c1:
    filtro_evento = st.selectbox("Evento Específico", ["Todos"] + sorted(df_visivel[col_nome_ev].unique().tolist()))
with c2:
    filtro_depto = st.selectbox("Departamento", ["Todos"] + sorted(df_visivel[col_depto].unique().tolist()))
with c3:
    data_filtro = st.date_input("A partir de:", datetime.now().date())

df_filtrado = df_visivel[df_visivel['Data Formatada'] >= data_filtro]
if filtro_evento != "Todos": df_filtrado = df_filtrado[df_filtrado[col_nome_ev] == filtro_evento]
if filtro_depto != "Todos": df_filtrado = df_filtrado[df_filtrado[col_depto] == filtro_depto]

# --- ÁREA DE INSCRIÇÃO ---
st.markdown("---")
if not df_filtrado.empty:
    df_filtrado['label'] = df_filtrado.apply(lambda x: f"[{x[col_depto]}] {x[col_nome_ev]} - {x['Data Formatada']}",
                                             axis=1)
    df_com_vaga = df_filtrado[(df_filtrado['Voluntário 1'] == "") | (df_filtrado['Voluntário 2'] == "")].copy()

    if not df_com_vaga.empty:
        escolha = st.selectbox("Escolha a atividade:", df_com_vaga['label'].tolist())
        if st.button("Me inscrever nesta atividade", type="primary"):
            # Localiza dados para passar para o Dialog
            idx_selecionado = df_com_vaga[df_com_vaga['label'] == escolha].index[0]
            linha_planilha = int(idx_selecionado) + 2

            # Checa qual vaga está livre antes de abrir o pop-up
            row_values = sheet.row_values(linha_planilha)
            v1_vazio = True if len(row_values) < 7 or not str(row_values[6]).strip() else False

            vaga_nome = "Voluntário 1" if v1_vazio else "Voluntário 2"
            col_alvo = 7 if v1_vazio else 8

            # ABRE O OVERLAY DE CONFIRMAÇÃO
            confirmar_inscricao_dialog(
                sheet,
                linha_planilha,
                df_com_vaga.loc[idx_selecionado, col_nome_ev],
                df_com_vaga.loc[idx_selecionado, 'Data Formatada'],
                vaga_nome,
                col_alvo
            )
    else:
        st.warning("Sem vagas disponíveis para estes filtros.")
else:
    st.info("Nenhuma atividade encontrada.")

# Escala Atual
st.markdown("### 📋 Escala Atual")
st.dataframe(df_filtrado[[col_nome_ev, 'Data Formatada', 'Nível', 'Tipo', 'Voluntário 1', 'Voluntário 2']],
             use_container_width=True)

if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state.autenticado = False
    st.rerun()