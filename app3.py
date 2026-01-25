import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import textwrap
import re

# --- 1. CONFIGURAÇÃO DE ACESSO ---
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
    except Exception as e:
        st.error(f"Erro na Autenticação: {e}")
        st.stop()

def load_data():
    client = get_gspread_client()
    spreadsheet_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
    ss = client.open_by_key(spreadsheet_id)
    sheet = ss.worksheet("Calendario_Eventos")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [col.strip() for col in df.columns]
    return sheet, df

# --- 2. CONFIGURAÇÕES E ESTILOS ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

dias_semana_pt = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

# Funções de Status e Cor
def definir_status(row):
    v1 = str(row.get('Voluntário 1', '')).strip()
    v2 = str(row.get('Voluntário 2', '')).strip()
    if v1 == "" and v2 == "": return "🔴 Vazio (0/2)"
    if v1 == "" or v2 == "": return "🟡 1 Vaga (1/2)"
    return "🟢 Completo (2/2)"

def aplicar_estilo_linha(row):
    status = definir_status(row)
    if "Vazio" in status: return ['background-color: #FFEBEE; color: black'] * len(row)
    if "1 Vaga" in status: return ['background-color: #FFF9C4; color: black'] * len(row)
    return ['background-color: #FFFFFF; color: black'] * len(row)

# --- 3. DIÁLOGO DE CONFIRMAÇÃO ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, row_data, vaga_nome, col_index, col_evento):
    st.markdown("### 📋 Resumo da Atividade")
    st.markdown(f"**🔹 Evento:** {row_data[col_evento]}")
    st.markdown(f"**🔹 Data:** {row_data['Data_Formatada'].strftime('%d/%m/%Y')} ({row_data['Dia_da_Semana']})")
    st.markdown(f"**🔹 Nível:** {row_data['Nível']}")
    st.markdown(f"**🔹 Vaga disponível:** {vaga_nome}")
    
    st.divider()
    st.write(f"Deseja confirmar a inscrição para **{st.session_state.nome_usuario}**?")
    
    if st.button("✅ Sim, confirmar", type="primary", use_container_width=True):
        with st.spinner("Atualizando planilha..."):
            sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
            st.success("Inscrição realizada com sucesso!")
            st.cache_resource.clear()
            st.rerun()

# --- 4. INTERFACE E LOGIN ---
st.set_page_config(page_title="Portal de Voluntários ProVida", layout="wide")

# CSS para forçar modo claro caso o config.toml falhe
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #000000; }
    h1, h2, h3, p, label, .stMarkdown { color: #000000 !important; }
    </style>
""", unsafe_allow_html=True)

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Login do Voluntário")
    with st.form("login"):
        nome = st.text_input("Nome Completo")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        if st.form_submit_button("Entrar"):
            if nome:
                st.session_state.update({"nome_usuario": nome, "nivel_usuario_num": mapa_niveis[nivel], "autenticado": True})
                st.rerun()
    st.stop()

# --- 5. CARREGAMENTO E PROCESSAMENTO ---
try:
    sheet, df = load_data()
    col_evento = next((c for c in df.columns if 'Evento' in c), 'Nome do Evento')
    col_depto = next((c for c in df.columns if 'Departamento' in c), 'Departamento Responsável')
    
    df['Data_Dt'] = pd.to_datetime(df['Data Específica'], errors='coerce')
    df['Data_Formatada'] = df['Data_Dt'].dt.date
    df['Dia_da_Semana'] = df['Data_Dt'].dt.weekday.map(dias_semana_pt)
    df['Nivel_Num'] = df['Nível'].astype(str).str.strip().map(mapa_niveis).fillna(99)
    df['Status'] = df.apply(definir_status, axis=1)

    st.title(f"🤝 Bem-vindo(a), {st.session_state.nome_usuario}")

    # Sidebar Filtros
    with st.sidebar:
        st.header("🔍 Filtros")
        f_ev = st.selectbox("Evento", ["Todos"] + sorted(df[df[col_evento]!=''][col_evento].unique().tolist()))
        f_dep = st.selectbox("Departamento", ["Todos"] + sorted(df[df[col_depto]!=''][col_depto].unique().tolist()))
        f_dat = st.date_input("A partir de", datetime.now().date())
        ocultar_cheios = st.checkbox("Mostrar apenas vagas abertas", value=False)
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    # Filtros de Visibilidade e Seleção
    df_f = df[(df['Nivel_Num'] <= st.session_state.nivel_usuario_num) & (df['Data_Formatada'] >= f_dat)].copy()
    
    if f_ev != "Todos": df_f = df_f[df_f[col_evento] == f_ev]
    if f_dep != "Todos": df_f = df_f[df_f[col_depto] == f_dep]
    if ocultar_cheios:
        df_f = df_f[df_f['Status'] != "🟢 Completo (2/2)"]

    # --- 6. OPÇÃO 1: DROP DOWN ---
    st.subheader("📝 Inscrição Rápida")
    vagas = df_f[df_f['Status'] != "🟢 Completo (2/2)"].copy()
    if not vagas.empty:
        vagas['label'] = vagas.apply(lambda x: f"{x[col_evento]} | {x['Data_Formatada'].strftime('%d/%m')} | {x['Status']}", axis=1)
        escolha = st.selectbox("Selecione uma atividade:", vagas['label'].tolist(), index=None, placeholder="Escolha aqui...")
        if escolha:
            idx = vagas[vagas['label'] == escolha].index[0]
            if st.button("Confirmar via Lista"):
                linha_p = int(idx) + 2
                v1 = str(sheet.cell(linha_p, 7).value).strip()
                vaga_n = "Voluntário 1" if v1 == "" else "Voluntário 2"
                confirmar_inscricao_dialog(sheet, linha_p, vagas.loc[idx], vaga_n, (7 if v1 == "" else 8), col_evento)
    else:
        st.info("Nenhuma vaga aberta encontrada para os filtros selecionados.")

    # --- 7. OPÇÃO 2: TABELA COLORIDA ---
    st.divider()
    st.subheader("📋 Escala Completa")
    st.caption("Linhas em **Amarelo** ou **Vermelho** têm vagas. Clique na linha para se inscrever.")
    
    cols_tab = ['Status', col_evento, 'Data_Formatada', 'Dia_da_Semana', 'Voluntário 1', 'Voluntário 2']
    
    selecao = st.dataframe(
        df_f[cols_tab].style.apply(aplicar_estilo_linha, axis=1),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if selecao.selection.rows:
        row_idx = selecao.selection.rows[0]
        row_sel = df_f.iloc[row_idx]
        if row_sel['Status'] != "🟢 Completo (2/2)":
            linha_original = int(row_sel.name) + 2
            v1_at = str(row_sel['Voluntário 1']).strip()
            vaga_n = "Voluntário 1" if v1_at == "" else "Voluntário 2"
            confirmar_inscricao_dialog(sheet, linha_original, row_sel, vaga_n, (7 if v1_at == "" else 8), col_evento)
        else:
            st.warning("Esta atividade já está completa!")

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
