import streamlit as st
import re
import base64

st.set_page_config(page_title="Super Validador 20", layout="wide")
st.title("🔬 Microscópio de Chave (20 Segmentos)")

def analisar():
    partes = [f"S{i}" for i in range(1, 21)]
    chave_full = ""
    
    # 1. Tabela de Verificação Unitária
    st.subheader("📊 Verificação de 1 a 20")
    col_a, col_b = st.columns(2)
    
    for i, nome in enumerate(partes):
        target_col = col_a if i < 10 else col_b
        if nome in st.secrets:
            val = st.secrets[nome].strip()
            limpo = re.sub(r'[^A-Za-z0-9+/=]', '', val)
            chave_full += limpo
            target_col.write(f"**{nome}:** {len(limpo)} chars")
        else:
            target_col.error(f"**{nome}:** ❌ AUSENTE")

    st.divider()

    # 2. Análise por Blocos (10 em 10)
    st.subheader("📦 Análise por Blocos")
    bloco1 = "".join([re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets.get(f"S{i}", "")) for i in range(1, 11)])
    bloco2 = "".join([re.sub(r'[^A-Za-z0-9+/=]', '', st.secrets.get(f"S{i}", "")) for i in range(11, 21)])
    
    c1, c2 = st.columns(2)
    c1.metric("Bloco 1 (S1-S10)", len(bloco1))
    c2.metric("Bloco 2 (S11-S20)", len(bloco2))

    st.divider()

    # 3. Veredito Final
    st.subheader("⚖️ Veredito Final")
    total = len(chave_full)
    resto = total % 4
    
    st.write(f"**Total acumulado:** {total} caracteres")
    
    if resto == 0:
        st.success("✅ PERFEITO! A chave é múltipla de 4.")
    else:
        st.error(f"❌ ERRO: Sobram {resto} caracteres. (Total: {total})")
        # Identificando o caractere intruso
        st.write(f"Últimos 5 caracteres da chave: `{chave_full[-5:]}`")

    try:
        base64.b64decode(chave_full)
        st.success("✅ Base64 matematicamente válido!")
    except Exception as e:
        st.error(f"❌ Falha na decodificação: {e}")

if st.button("🔍 Rodar Diagnóstico"):
    analisar()
