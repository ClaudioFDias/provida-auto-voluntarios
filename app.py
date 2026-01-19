import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import re

# --- 1. RECONSTRUÇÃO DA CHAVE (CORREÇÃO DO "Q" E JUNÇÃO PERFEITA) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # PREFIXO CORRIGIDO (Adicionado o 'q' que faltava)
        prefix = "MIIEugIBADANBgkqhkiG" 
        # SUFIXO COMPLETO
        suffix = "+b78NxZxsgwTfk6T9U="
        
        # Carrega o corpo do segredo
        middle = st.secrets["KEY_MIDDLE"].strip()
        email = st.secrets["CLIENT_EMAIL"].strip()
        
        # Montagem e Limpeza
        full_body = prefix + middle + suffix
        clean_body = re.sub(r'[^A-Za-z0-9+/=]', '', full_body)
        
        creds_info = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": "866d21c6b1ad8efba9661a2a15b47b658d9e1573",
            "private_key": f"-----BEGIN PRIVATE KEY-----\n{clean_body}\n-----END PRIVATE KEY-----\n",
            "client_email": email,
            "client_id": "110888986067806154751",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{email.replace('@', '%40')}",
            "universe_domain": "googleapis.com"
        }
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
        
    except Exception as e:
        st.error(f"Erro Crítico de Conexão: {e}")
        st.stop()

# --- 2. CARREGAMENTO DOS DADOS ---
def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 3. CONFIGURAÇÃO DA PÁGINA E LOGIN ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

st.set_page_config(page_title="Portal de Voluntários", page_icon="🤝", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Portal ProVida")
    with st.form("login"):
        nome = st.text_input("Seu Nome Completo")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar"):
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Por favor, informe seu nome.")
    st.stop()

# --- 4. EXIBIÇÃO DO PAINEL ---
try:
    sheet, df = load_data()
    st.success(f"Conectado! Bem-vindo, {st.session_state.nome_usuario}")

    # Processamento de Datas
    df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    
    # Filtro: Usuário vê o seu nível e níveis inferiores
    df_visivel = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num].copy()

    st.subheader("📅 Próximas Atividades")
    cols_mostrar = ['Nome do Evento ou da Atividade', 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']
    st.dataframe(df_visivel[cols_mostrar], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao processar planilha: {e}")

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

# --- 5. INTERFACE PRINCIPAL ---
try:
    sheet, df = load_data()
    st.title(f"Olá, {st.session_state.nome_usuario}!")
    
    # Processamento de datas
    df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date
    
    # Filtro de Nível: vê o seu nível e inferiores
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_visivel = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num].copy()

    st.subheader("📅 Escala de Atividades")
    cols = ['Nome do Evento ou da Atividade', 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']
    st.dataframe(df_visivel[cols], use_container_width=True, hide_index=True)

    # Botão de Inscrição Simples
    with st.expander("Fazer minha inscrição"):
        vagas_abertas = df_visivel[(df_visivel['Voluntário 1'] == "") | (df_visivel['Voluntário 2'] == "")]
        if not vagas_abertas.empty:
            opcao = st.selectbox("Escolha a atividade:", vagas_abertas['Nome do Evento ou da Atividade'].unique())
            if st.button("Confirmar minha participação"):
                st.info("Função de gravação pronta para ser acionada.")
        else:
            st.write("Nenhuma vaga aberta no seu nível.")

except Exception as e:
    st.error(f"Erro ao conectar: {e}")

if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

