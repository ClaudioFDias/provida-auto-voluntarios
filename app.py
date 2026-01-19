import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import textwrap
import re

@st.cache_resource
def get_gspread_client():
    try:
        # 1. Reconstituir a Chave Privada
        partes = [f"S{i}" for i in range(1, 22)]
        chave_full = "".join([re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[p]) for p in partes])
        
        # Formatar para o padrão PEM
        key_lines = textwrap.wrap(chave_full, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"
        
        # 2. Montar o dicionário pegando TUDO do Secrets
        creds_info = {
            "type": st.secrets["TYPE"],
            "project_id": st.secrets["PROJECT_ID"],
            "private_key_id": st.secrets["PRIVATE_KEY_ID"],
            "private_key": formatted_key,
            "client_email": st.secrets["CLIENT_EMAIL"],
            "client_id": st.secrets["CLIENT_ID"],
            "auth_uri": st.secrets["AUTH_URI"],
            "token_uri": st.secrets["TOKEN_URI"],
            "auth_provider_x509_cert_url": st.secrets["AUTH_PROVIDER_X509_CERT_URL"],
            "client_x509_cert_url": st.secrets["CLIENT_X509_CERT_URL"]
        }
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro ao carregar credenciais do Secrets: {e}")
        st.stop()

# --- 2. MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login de Voluntários")
    with st.form("login_form"):
        nome = st.text_input("Seu Nome")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar Calendário"):
            if nome:
                st.session_state.update({
                    "nome_usuario": nome,
                    "nivel_usuario_num": mapa_niveis[nivel],
                    "autenticado": True
                })
                st.rerun()
            else:
                st.warning("Por favor, digite seu nome.")
    st.stop()

# --- 4. EXIBIÇÃO DA PLANILHA ---
try:
    client = get_gspread_client()
    # Abrindo a planilha confirmada no teste: 'Automação de Agenda'
    sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
    worksheet = sh.worksheet("Calendario_Eventos")
    
    # Carregando dados para o Pandas
    df = pd.DataFrame(worksheet.get_all_records())
    df.columns = [c.strip() for c in df.columns]
    
    # Lógica de Filtro por Nível
    if 'Nível' in df.columns:
        df['Nivel_Num_Tabela'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
        df_filtrado = df[df['Nivel_Num_Tabela'] <= st.session_state.nivel_usuario_num].copy()
        
        st.header(f"Olá, {st.session_state.nome_usuario}!")
        st.subheader("📅 Calendário de Eventos Disponíveis")
        
        # Seleção das colunas para visualização limpa
        colunas_u = ['Nome do Evento ou da Atividade', 'Data Específica', 'Nível', 'Voluntário 1', 'Voluntário 2']
        colunas_exibir = [c for c in colunas_u if c in df_filtrado.columns]
        
        st.dataframe(df_filtrado[colunas_exibir], use_container_width=True, hide_index=True)
    else:
        st.error("Coluna 'Nível' não encontrada na planilha.")

except Exception as e:
    st.error(f"Erro ao carregar os dados: {e}")

# --- 5. LOGOUT ---
if st.sidebar.button("Sair"):
    st.session_state.autenticado = False
    st.rerun()

