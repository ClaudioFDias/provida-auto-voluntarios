import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURAÇÃO DE ACESSO (GOOGLE SHEETS) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Pega o dicionário dos secrets
    creds_info = dict(st.secrets["gcp_service_account"])
    
    # CONSERTO DEFINITIVO PARA JWT SIGNATURE:
    # Se a chave vier com aspas duplas escapadas ou quebras de linha literais, isso limpa tudo.
    if "private_key" in creds_info:
        # Substitui a representação de texto '\n' por quebras de linha reais
        key = creds_info["private_key"].replace("\\n", "\n")
        # Remove possíveis aspas extras que o TOML às vezes insere
        key = key.strip('"').strip("'")
        creds_info["private_key"] = key

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    return gspread.authorize(creds)

def load_data():
    client = get_gspread_client()
    # ID da sua planilha (extraído do link que você forneceu anteriormente)
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # Limpa espaços em branco dos nomes das colunas
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- 3. OVERLAY DE CONFIRMAÇÃO ---
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
            with st.spinner("Gravando na planilha..."):
                # Atualiza a célula específica na planilha
                sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
                st.success("Inscrição realizada com sucesso!")
                st.cache_resource.clear() # Limpa o cache para atualizar a tabela
                st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()

# --- 4. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal ProVida", page_icon="🤝", layout="wide")

# Inicialização do estado de login
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
                st.error("Por favor, insira seu nome para continuar.")
    st.stop()

# --- TELA PRINCIPAL DO PORTAL ---
try:
    sheet, df = load_data()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

st.title(f"🤝 Bem-vindo(a), {st.session_state.nome_usuario}")

# Processamento de dados
df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date

# Lógica de Visibilidade (quem pode ver o quê)
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

# Ajuste automático de nomes de colunas caso variem na planilha
col_nome_ev = 'Nome do Evento ou da Atividade' if 'Nome do Evento ou da Atividade' in df_visivel.columns else 'Nome do Evento'
col_depto = 'Departamento Responsável' if 'Departamento Responsável' in df_visivel.columns else 'Departamento'

with c1:
    filtro_evento = st.selectbox("Evento Específico", ["Todos"] + sorted(df_visivel[col_nome_ev].unique().tolist()))
with c2:
    filtro_depto = st.selectbox("Departamento", ["Todos"] + sorted(df_visivel[col_depto].unique().tolist()))
with c3:
    data_filtro = st.date_input("A partir de:", datetime.now().date())

# Aplicação dos filtros
df_filtrado = df_visivel[df_visivel['Data Formatada'] >= data_filtro]
if filtro_evento != "Todos": 
    df_filtrado = df_filtrado[df_filtrado[col_nome_ev] == filtro_evento]
if filtro_depto != "Todos": 
    df_filtrado = df_filtrado[df_filtrado[col_depto] == filtro_depto]

# --- ÁREA DE INSCRIÇÃO ---
st.markdown("---")
if not df_filtrado.empty:
    df_filtrado['label'] = df_filtrado.apply(lambda x: f"[{x[col_depto]}] {x[col_nome_ev]} - {x['Data Formatada']}", axis=1)
    
    # Só mostra para inscrição eventos que tenham pelo menos uma vaga vazia
    df_com_vaga = df_filtrado[(df_filtrado['Voluntário 1'] == "") | (df_filtrado['Voluntário 2'] == "")].copy()
    
    if not df_com_vaga.empty:
        escolha = st.selectbox("Selecione uma atividade para se inscrever:", df_com_vaga['label'].tolist())
        if st.button("Me inscrever nesta atividade", type="primary"):
            idx_selecionado = df_com_vaga[df_com_vaga['label'] == escolha].index[0]
            linha_planilha = int(idx_selecionado) + 2 # +2 porque o pandas ignora o cabeçalho e começa em 0
            
            # Verifica qual vaga está disponível
            v1 = str(df_com_vaga.loc[idx_selecionado, 'Voluntário 1']).strip()
            vaga_nome = "Voluntário 1" if v1 == "" else "Voluntário 2"
            col_alvo = 7 if v1 == "" else 8 # Coluna G ou H
            
            confirmar_inscricao_dialog(sheet, linha_planilha, df_com_vaga.loc[idx_selecionado, col_nome_ev], df_com_vaga.loc[idx_selecionado, 'Data Formatada'], vaga_nome, col_alvo)
    else:
        st.info("Todas as atividades filtradas já estão com as vagas preenchidas.")
else:
    st.info("Nenhuma atividade disponível para o seu nível com os filtros selecionados.")

# --- ESCALA ATUAL (TABELA) ---
st.markdown("### 📋 Escala de Voluntários")
colunas_exibicao = [col_nome_ev, 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']
st.dataframe(df_filtrado[colunas_exibicao], use_container_width=True, hide_index=True)

# Rodapé
st.sidebar.markdown(f"**Usuário:** {st.session_state.nome_usuario}")
st.sidebar.markdown(f"**Nível:** {st.session_state.nivel_usuario_nome}")
if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state.autenticado = False
    st.rerun()



