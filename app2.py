import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import textwrap

st.set_page_config(page_title="Validador de Assinatura JWT", layout="wide")
st.title("🧪 Teste de Conexão em Tempo Real")

def testar_conexao_completa():
    try:
        # 1. Reconstrução
        st.subheader("1. Reconstruindo a Chave...")
        partes = [f"S{i}" for i in range(1, 21)]
        chave_full = ""
        for nome in partes:
            if nome in st.secrets:
                chave_full += re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[nome])
        
        st.write(f"✅ Chave reconstruída com {len(chave_full)} caracteres.")

        # 2. Montagem do PEM
        # Cortamos em 1620 por segurança (conforme nosso último sucesso no microscópio)
        chave_final = chave_full[:1620]
        key_lines = textwrap.wrap(chave_final, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"

        # 3. Tentativa de Autenticação
        st.subheader("2. Tentando Autenticar no Google...")
        
        creds_info = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": "866d21c6b1ad8efba9661a2a15b47b658d9e1573",
            "private_key": formatted_key,
            "client_email": "volutarios@chromatic-tree-279819.iam.gserviceaccount.com",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        
        st.success("🔥 SUCESSO! O Google aceitou a assinatura da chave.")

        # 4. Teste de Acesso à Planilha
        st.subheader("3. Testando Acesso à Planilha...")
        sh = client.open_by_key("1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c")
        st.write(f"✅ Planilha aberta: **{sh.title}**")
        
    except Exception as e:
        st.error(f"❌ Falha no Teste: {e}")
        if "invalid_grant" in str(e):
            st.warning("⚠️ O erro 'Invalid JWT Signature' confirma que o conteúdo da chave está incorreto ou ela foi revogada no Google Cloud.")
            st.info("Ação recomendada: Gere uma nova chave JSON no console do Google e substitua os S1-S20.")

if st.button("🚀 Rodar Teste de Fogo"):
    testar_conexao_completa()
