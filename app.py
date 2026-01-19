import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

# --- FUNÇÃO DE CONEXÃO COM DIAGNÓSTICO ---
@st.cache_resource
def get_gspread_client():
    try:
        # 1. Carrega a string do segredo
        raw_json = st.secrets["GCP_JSON_ESTRITO"]
        
        # 2. Converte para dicionário
        info = json.loads(raw_json)
        
        # 3. Trata quebras de linha na chave privada
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        
        # 4. Escopo e Autenticação
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
        return gspread.authorize(creds)
    
    except Exception as e:
        st.error(f"❌ Erro na autenticação: {e}")
        st.info("💡 Verifique se o Secret 'GCP_JSON_ESTRITO' foi colado corretamente com aspas simples.")
        st.stop()

# --- CARREGAMENTO DE DADOS ---
def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    try:
        sh = client.open_by_key(spreadsheet_id)
        df = pd.DataFrame(sh.worksheet("Calendario_Eventos").get_all_records())
        df.columns = [c.strip() for c in df.columns] # Limpa nomes das colunas
        return df
    except Exception as e:
        st.error(f"❌ Erro ao abrir planilha: {e}")
        st.info("💡 Certifique-se que o e-mail da conta de serviço é EDITOR na sua planilha.")
        return None

# --- MAPEAMENTO E LÓGICA DE LOGIN ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🤝 Portal de Voluntários ProVida")
    with st.form("login"):
        nome = st.text_input("Seu Nome Completo")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar Calendário"):
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.warning("Por favor, digite seu nome.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

st.header(f"Olá, {st.session_state.nome_usuario}!")

df = load_data()

if df is not None:
    # 1. Filtro por Nível
    # Criamos uma coluna numérica para comparar os níveis
    df['Nivel_Num_Check'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_filtrado = df[df['Nivel_Num_Check'] <= st.session_state.nivel_usuario_num].copy()
    
    # 2. Formatação de Data (opcional, se a coluna existir)
    if 'Data Específica' in df_filtrado.columns:
        df_filtrado['Data'] = pd.to_datetime(df_filtrado['Data Específica'], errors='coerce').dt.date

    # 3. Exibição
    st.subheader("📅 Atividades Disponíveis para Você")
    colunas_finais = ['Nome do Evento ou da Atividade', 'Data', 'Nível', 'Voluntário 1', 'Voluntário 2']
    # Mostra apenas colunas que realmente existem no seu Excel/Sheets
    cols_existentes = [c for c in colunas_finais if c in df_filtrado.columns]
    
    st.dataframe(df_filtrado[cols_existentes], use_container_width=True, hide_index=True)
