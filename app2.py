import streamlit as st
import re
import textwrap
import base64

st.set_page_config(page_title="Validador de Precisão RSA", layout="wide")

st.title("🛠️ Validador de Precisão: Reconstrução de Chave")

def limpar_string(texto):
    # Remove TUDO que não for caractere válido de Base64 (A-Z, a-z, 0-9, +, /, =)
    return re.sub(r'[^A-Za-z0-9+/=]', '', texto)

def validar_processo():
    partes_nome = ["P1", "P2", "P3", "P4", "P5", "P6"]
    chave_reconstruida = ""
    detalhes = []
    
    st.markdown("### 1. Inspeção de Segmentos")
    
    for nome in partes_nome:
        if nome in st.secrets:
            conteudo_bruto = st.secrets[nome]
            conteudo_limpo = limpar_string(conteudo_bruto)
            
            # Verifica se houve limpeza (se o tamanho mudou)
            caracteres_removidos = len(conteudo_bruto) - len(conteudo_limpo)
            chave_reconstruida += conteudo_limpo
            
            detalhes.append({
                "Segmento": nome,
                "Tamanho Lido": len(conteudo_limpo),
                "Lixo Removido": caracteres_removidos,
                "Status": "✅ Carregado" if len(conteudo_limpo) > 0 else "⚠️ Vazio"
            })
        else:
            detalhes.append({"Segmento": nome, "Tamanho Lido": 0, "Lixo Removido": 0, "Status": "❌ AUSENTE"})

    st.table(detalhes)

    st.markdown("### 2. Análise da Integridade Base64")
    total_caracteres = len(chave_reconstruida)
    resto = total_caracteres % 4
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Caracteres", total_caracteres)
    
    if resto == 0:
        col2.success("Múltiplo de 4: SIM")
        status_base64 = True
    else:
        col2.error(f"Múltiplo de 4: NÃO (Sobram {resto})")
        status_base64 = False
        st.warning(f"💡 Dica técnica: A chave tem {total_caracteres} caracteres. Para ser perfeita, deveria ter {total_caracteres - resto}. O código abaixo irá truncar para testar.")

    # Tentativa de Decodificação binária
    try:
        # Se não for múltiplo de 4, o Python força o erro. 
        # Vamos tentar decodificar a versão limpa.
        base64.b64decode(chave_reconstruida)
        col3.success("Decodificação: SUCESSO")
    except Exception as e:
        col3.error(f"Decodificação: FALHOU")
        st.error(f"Erro do Interpretador: {e}")

    st.markdown("### 3. Visualização da Chave Final (PEM)")
    # Se houver erro de múltiplo de 4, mostramos onde pode estar o erro
    if total_caracteres > 0:
        linhas = textwrap.wrap(chave_reconstruida, 64)
        pem_final = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(linhas) + "\n-----END PRIVATE KEY-----\n"
        
        st.text_area("Texto que será enviado ao Google API:", pem_final, height=250)
        
        # Comparação de início e fim para garantir que não houve troca de ordem
        st.info(f"**Assinatura de conferência:**\n\nInício: `{chave_reconstruida[:15]}...` | Fim: `...{chave_reconstruida[-15:]}`")

if st.button("🔍 Iniciar Auditoria da Chave"):
    validar_processo()
else:
    st.info("Clique no botão para validar as variáveis P1 a P6 configuradas no Streamlit Secrets.")
