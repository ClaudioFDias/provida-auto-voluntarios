import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURAÇÃO DE ACESSO (HÍBRIDO) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # Pega a chave e o email
        key_body = st.secrets["PRIVATE_KEY_BODY"]
        email = st.secrets["CLIENT_EMAIL"]
        
        # --- LIMPEZA AGRESSIVA ---
        # Remove espaços, quebras de linha e aspas que podem ter vindo na colagem
        clean_key = key_body.replace("\n", "").replace(" ", "").strip().strip('"').strip("'")
        
        # Reconstrói o dicionário
        creds_info = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": "866d21c6b1ad8efba9661a2a15b47b658d9e1573",
            "private_key": f"-----BEGIN PRIVATE KEY-----\n{clean_key}\n-----END PRIVATE KEY-----\n",
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
        st.error(f"Erro na conexão: {e}")
        st.stop()
def load_data():
    client = get_gspread_client()
    # Seu ID da Planilha
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # Limpa nomes de colunas
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. MAPEAMENTO DE NÍVEIS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

# --- 3. DIÁLOGO DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, evento, data_ev, vaga_nome, col_index):
    st.warning(f"Você está se inscrevendo como **{vaga_nome}**.")
    st.markdown(f"**Atividade:** {evento}  \n**Data:** {data_ev}")
    
    if st.button("Sim, Confirmar Inscrição", type="primary", use_container_width=True):
        try:
            sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
            st.success("Inscrição realizada com sucesso!")
            st.cache_resource.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao gravar na planilha: {e}")

# --- 4. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal de Voluntários ProVida", page_icon="🤝", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- TELA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Portal")
    with st.form("login_form"):
        nome = st.text_input("Seu Nome Completo")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar no Sistema"):
            if nome:
                st.session_state.nome_usuario = nome
                st.session_state.nivel_usuario_num = mapa_niveis[nivel]
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Por favor, digite seu nome para continuar.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
try:
    sheet, df = load_data()
    
    st.title(f"🤝 Bem-vindo(a), {st.session_state.nome_usuario}")
    
    # Processamento de Dados
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df['Data Formatada'] = pd.to_datetime(df['Data Específica']).dt.date
    
    # Lógica de Visibilidade: Aluno vê apenas o seu nível ou inferior
    df_visivel = df[df['Nivel_Num'] <= st.session_state.nivel_usuario_num].copy()

    # Filtros
    st.markdown("### 🔍 Filtrar Atividades")
    col1, col2 = st.columns(2)
    with col1:
        data_min = st.date_input("A partir de:", datetime.now().date())
    with col2:
        lista_deptos = ["Todos"] + sorted(df_visivel['Departamento Responsável'].unique().tolist())
        depto_sel = st.selectbox("Filtrar por Departamento:", lista_deptos)

    df_filtrado = df_visivel[df_visivel['Data Formatada'] >= data_min]
    if depto_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Departamento Responsável'] == depto_sel]

    # Inscrição
    st.markdown("---")
    st.subheader("📝 Inscrição Rápida")
    
    # Só mostra atividades que tenham pelo menos uma vaga vazia
    df_com_vagas = df_filtrado[(df_filtrado['Voluntário 1'] == "") | (df_filtrado['Voluntário 2'] == "")].copy()
    
    if not df_com_vagas.empty:
        df_com_vagas['display_label'] = df_com_vagas.apply(lambda x: f"{x['Data Formatada']} - {x['Nome do Evento ou da Atividade']}", axis=1)
        escolha = st.selectbox("Selecione uma atividade com vaga aberta:", df_com_vagas['display_label'].tolist())
        
        if st.button("Quero participar desta atividade", type="primary"):
            row_data = df_com_vagas[df_com_vagas['display_label'] == escolha].iloc[0]
            idx_original = df[df.values == row_data.values].index[0]
            linha_excel = int(idx_original) + 2
            
            # Decide se vai para vaga 1 ou 2
            v1 = str(row_data['Voluntário 1']).strip()
            vaga_txt = "Voluntário 1" if v1 == "" else "Voluntário 2"
            col_excel = 7 if v1 == "" else 8 # Coluna G ou H
            
            confirmar_inscricao_dialog(sheet, linha_excel, row_data['Nome do Evento ou da Atividade'], row_data['Data Formatada'], vaga_txt, col_excel)
    else:
        st.info("Não há vagas disponíveis para os filtros selecionados.")

    # Tabela de Escala
    st.markdown("---")
    st.subheader("📋 Escala Geral de Voluntários")
    cols_display = ['Nome do Evento ou da Atividade', 'Data Formatada', 'Nível', 'Voluntário 1', 'Voluntário 2']
    st.dataframe(df_filtrado[cols_display], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Ocorreu um erro ao carregar o portal: {e}")

if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state.autenticado = False
    st.rerun()

