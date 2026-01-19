import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import textwrap

st.set_page_config(page_title="Validador de Nova Chave", layout="wide")
st.title("🚀 Teste de Fogo: Nova Credencial")

def realizar_teste():
    try:
        # 1. Reconstrução das 21 partes (S1 a S21)
        st.subheader("1. Reconstruindo Chave do Secrets...")
        partes = [f"S{i}" for i in range(1, 22)]
        chave_full = ""
        
        for p in partes:
            if p in st.secrets:
                chave_full += re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets[p])
            else:
                st.error(f"Faltando a parte {p} no Secrets!")
                return

        st.write(f"✅ Total de caracteres: {len(chave_full)}")
        
        # 2. Montagem do Objeto de Credenciais
        st.subheader("2. Validando Assinatura com o Google...")
        
        key_lines = textwrap.wrap(chave_full, 64)
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(key_lines) + "\n-----END PRIVATE KEY-----\n"

        creds_info = {
            "type": "service_account",
            "project_id": "chromatic-tree-279819",
            "private_key_id": st.secrets.get("PRIVATE_KEY_ID", "NÃO ENCONTRADO"),
            "private_key": formatted_key,
            "client_email": "volutarios@chromatic-tree-279819.iam.gserviceaccount.com",
            "client_id": "110888986067806154751",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/volutarios%40chromatic-tree-279819.iam.gserviceaccount.com"
        }

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        st.success("✅ Assinatura JWT aceita pelo Google!")

        # 3. Teste de Acesso à Planilha
        st.subheader("3. Verificando Acesso à Planilha...")
        planilha_id = "1paP1ZB2ufwCc95T_gdCR92kx-suXbROnDfbWMC_ka0c"
        sh = client.open_by_key(planilha_id)
        
        st.balloons()
        st.success(f"🔥 SUCESSO TOTAL! Planilha '{sh.title}' acessada.")
        
        # Mostrar uma prévia dos dados para confirmar
        dados = sh.worksheet("Calendario_Eventos").get_all_records()
        st.write(f"Encontradas {len(dados)} linhas na planilha.")

    except Exception as e:
        st.error(f"❌ Falha no Teste: {e}")
        st.info("Dica: Se aparecer 'Permission Denied', verifique se o e-mail 'volutarios@...' está como Editor na sua Planilha Google.")

if st.button("Iniciar Validação Real"):
    realizar_teste()
