import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import textwrap
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

@st.cache_resource
def get_gspread_client():
    try:
        # Lista das partes que definimos no Secrets
        partes_nome = ["P1", "P2", "P3", "P4", "P5", "P6"]
        chave_reconstruida = ""
        
        # Reconstrução com limpeza de caracteres
        for nome in partes_nome:
            if nome in st.secrets:
                valor = st.secrets[nome].strip()
                # Remove qualquer coisa que não seja Base64 válido
                limpo = re.sub(r'[^A-Za-z0-9+/=]', '', valor)
                chave_reconstruida += limpo
            else:
                st.error(f"❌ Erro: A parte '{nome}' não foi encontrada nos Secrets.")
                st.stop()

        # Validação Base64 (Múltiplo de 4)
        if len(chave_reconstruida) % 4 != 0:
            st.error(f"⚠️ Erro de tamanho: {len(chave_reconstruida)} chars. Verifique se copiou as 6 partes completas.")
            st.stop()

        # Formatação PEM para o Google
        key_lines = textwrap.wrap(chave_reconstruida, 64)
        private_key_pem = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        
        creds_info = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": "866d21c6b1ad8efba9661a2a15b47b658d9e1573",
            "private_key": private_key_pem,
            "client_email": "volutarios@chromatic-tree-279819.iam.gserviceaccount.com",
            "client_id": "110888986067806154751",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/volutarios%40chromatic-tree-279819.iam.gserviceaccount.com"
        }
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    
    except Exception as e:
        st.error(f"❌ Falha Crítica na Autenticação: {e}")
        st.stop()

# --- MAPEAMENTO E LOGIN ---
mapa_niveis = {"Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3, "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login de Voluntários")
    with st.form("login_form"):
        nome = st.text_input("Seu Nome")
        nivel = st.selectbox("Seu Nível", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar"):
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
    st.stop()

# --- CARREGAMENTO DA PLANILHA ---
try:
    client = get_gspread_client()
    sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    df = pd.DataFrame(sh.worksheet("Calendario_Eventos").get_all_records())
    
    df.columns = [c.strip() for c in df.columns]
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df_filtrado = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num]

    st.header(f"Olá, {st.session_state.nome_usuario}")
    st.dataframe(df_filtrado[['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']], hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
