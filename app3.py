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

# --- 2. CONFIGURAÇÕES ---
mapa_niveis = {
    "Nenhum": 0, "Básico": 1, "Av.1": 2, "Introdução": 3,
    "Av.2": 4, "Av.2|": 5, "Av.3": 6, "Av.3|": 7, "Av.4": 8
}

dias_semana_pt = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

# --- 3. DIÁLOGO DE CONFIRMAÇÃO (NOVO FORMATO) ---
@st.dialog("Confirmar Inscrição")
def confirmar_inscricao_dialog(sheet, linha, row_data, vaga_nome, col_index, col_evento):
    st.subheader("📋 Resumo da Atividade")
    
    # Formato Rótulo: Valor Amigável
    st.write(f"**Atividade:** {row_data[col_evento]}")
    st.write(f"**Nível:** {row_data['Nível']}")
    st.write(f"**Data:** {row_data['Data_Formatada'].strftime('%d/%m/%Y')}")
    st.write(f"**Dia:** {row_data['Dia_da_Semana']}")
    st.write(f"**Sua Vaga:** {vaga_nome}")
    
    st.divider()
    st.write(f"Confirmar participação de **{st.session_state.nome_usuario}**?")
    
    if st.button("✅ Sim, Confirmar", type="primary", use_container_width=True):
        with st.spinner("Gravando..."):
            sheet.update_cell(linha, col_index, st.session_state.nome_usuario)
            st.success("Inscrição Realizada!")
            st.cache_resource.clear()
            st.rerun()

# --- 4. FLUXO DE LOGIN ---
st.set_page_config(page_title="Portal ProVida", layout="wide")

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Portal")
    with st.form("login"):
        nome = st.text_input("Nome Completo")
        nivel = st.selectbox("Seu Nível Atual", list(mapa_niveis.keys()))
        if st.form_submit_button("Acessar Calendário"):
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

    st.title(f"🤝 Olá, {st.session_state.nome_usuario}")

    # FILTROS
    with st.expander("🔍 Filtros de Busca", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_ev = st.selectbox("Evento", ["Todos"] + sorted(df[df[col_evento]!=''][col_evento].unique().tolist()))
        with c2: f_dep = st.selectbox("Departamento", ["Todos"] + sorted(df[df[col_depto]!=''][col_depto].unique().tolist()))
        with c3: f_niv = st.selectbox("Nível", ["Todos"] + list(mapa_niveis.keys()))
        with c4: f_dat = st.date_input("A partir de", datetime.now().date())
        ocultar_cheios = st.checkbox("Ocultar atividades com escala preenchida", value=False)

    # Visibilidade
    def visivel(row, n_user):
        t = str(row.get('Tipo', '')).strip()
        n_ev = row['Nivel_Num']
        if t in ["Aberto a não alunos", "Aberto a todos os níveis"]: return True
        return n_user >= n_ev

    df['Pode_Ver'] = df.apply(lambda r: visivel(r, st.session_state.nivel_usuario_num), axis=1)
    df_f = df[(df['Pode_Ver']) & (df['Data_Formatada'] >= f_dat)].copy()

    if f_ev != "Todos": df_f = df_f[df_f[col_evento] == f_ev]
    if f_dep != "Todos": df_f = df_f[df_f[col_depto] == f_dep]
    if f_niv != "Todos": df_f = df_f[df_f['Nível'] == f_niv]
    if ocultar_cheios:
        df_f = df_f[~((df_f['Voluntário 1'].astype(str).str.strip() != "") & (df_f['Voluntário 2'].astype(str).str.strip() != ""))]

    # --- 6. OPÇÃO 1: SELEÇÃO POR DROP DOWN ---
    st.subheader("📝 Opção 1: Selecionar via Lista")
    vagas_disponiveis = df_f[(df_f['Voluntário 1'].astype(str).str.strip() == "") | (df_f['Voluntário 2'].astype(str).str.strip() == "")].copy()

    if not vagas_disponiveis.empty:
        vagas_disponiveis['label'] = vagas_disponiveis.apply(lambda x: f"{x[col_depto]} | {x[col_evento]} | {x['Nível']} | {x['Data_Formatada'].strftime('%d/%m')} ({x['Dia_da_Semana']})", axis=1)
        escolha = st.selectbox("Escolha uma atividade da lista:", vagas_disponiveis['label'].tolist(), index=None, placeholder="Clique para buscar...")
        
        if escolha:
            idx_escolha = vagas_disponiveis[vagas_disponiveis['label'] == escolha].index[0]
            if st.button("Inscrever-me através da lista", type="primary"):
                linha_planilha = int(idx_escolha) + 2
                row_vals = sheet.row_values(linha_planilha)
                v1_vazio = True if len(row_vals) < 7 or not str(row_vals[6]).strip() else False
                confirmar_inscricao_dialog(sheet, linha_planilha, vagas_disponiveis.loc[idx_escolha], ("Voluntário 1" if v1_vazio else "Voluntário 2"), (7 if v1_vazio else 8), col_evento)
    else:
        st.info("Nenhuma vaga disponível com estes filtros.")

    # --- 7. OPÇÃO 2: CLIQUE NA TABELA ---
    st.markdown("---")
    st.subheader("📋 Opção 2: Clique na Escala")
    st.caption("Dica: Clique em qualquer linha da tabela para abrir a confirmação.")
    
    cols_tabela = [col_evento, 'Data_Formatada', 'Dia_da_Semana', 'Nível', 'Voluntário 1', 'Voluntário 2']
    
    # Tabela Interativa
    selecao = st.dataframe(
        df_f[cols_tabela], 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # Lógica do Clique na Tabela
    if selecao.selection.rows:
        row_idx = selecao.selection.rows[0]
        row_data = df_f.iloc[row_idx]
        
        v1 = str(row_data['Voluntário 1']).strip()
        v2 = str(row_data['Voluntário 2']).strip()
        
        if v1 == "" or v2 == "":
            linha_orig = int(row_data.name) + 2
            vaga_n = "Voluntário 1" if v1 == "" else "Voluntário 2"
            col_target = 7 if v1 == "" else 8
            confirmar_inscricao_dialog(sheet, linha_orig, row_data, vaga_n, col_target, col_evento)
        else:
            st.warning("Esta atividade já está preenchida. Por favor, selecione outra.")

except Exception as e:
    st.error(f"Erro no Portal: {e}")

if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state.autenticado = False
    st.rerun()
