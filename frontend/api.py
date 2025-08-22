from fastapi import APIRouter
from backend.service import (
    get_top_produtos,
    get_top_vendedores,
    get_previsao_vendas_produto,
    get_previsao_vendedor,
    top_produtos_categoria_ano,
    prever_vendas_produto
)
from pydantic import BaseModel
import pandas as pd
import re
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import numpy as np
import os

router = APIRouter()

class Pergunta(BaseModel):
    texto: str

# -----------------------------
# Funções auxiliares
# -----------------------------
def extrair_filtros_produtos(texto: str):
    filtros = {}
    cat_match = re.search(r'categoria ([\w\s]+)', texto, re.IGNORECASE | re.UNICODE)
    if cat_match:
        filtros['categoria'] = cat_match.group(1).strip()
    ano_match = re.search(r'ano de (\d{4})', texto, re.IGNORECASE)
    if ano_match:
        filtros['ano'] = int(ano_match.group(1))
    top_match = re.search(r'([0-9]+) produtos', texto, re.IGNORECASE)
    filtros['top_n'] = int(top_match.group(1)) if top_match else 5
    return filtros

def carregar_dados():
    paths = {
        "vendas": "data/vendas_limpo.xlsx",
        "produtos": "data/produtos_limpo.xlsx",
        "vendedores": "data/vendedores_limpo.xlsx"
    }
    if not all(os.path.exists(p) for p in paths.values()):
        raise FileNotFoundError("Arquivos limpos não encontrados")
    
    df_vendas = pd.read_excel(paths["vendas"])
    df_produtos = pd.read_excel(paths["produtos"])
    df_vendedores = pd.read_excel(paths["vendedores"])
    
    # Padronizar colunas: minúsculas, sem espaços, sem acentos
    def normalize_cols(df):
        return (df.columns.str.strip()
                  .str.lower()
                  .str.replace(" ", "_")
                  .str.replace("ç","c")
                  .str.replace("á","a")
                  .str.replace("é","e")
                  .str.replace("í","i")
                  .str.replace("ó","o")
                  .str.replace("ú","u"))
    
    df_vendas.columns = normalize_cols(df_vendas)
    df_produtos.columns = normalize_cols(df_produtos)
    df_vendedores.columns = normalize_cols(df_vendedores)
    
    # Garantir colunas essenciais em vendas
    if 'preco_unit' not in df_vendas.columns:
        for col in df_vendas.columns:
            if 'unit' in col:
                df_vendas['preco_unit'] = df_vendas[col]
                break
        else:
            df_vendas['preco_unit'] = 0.0

    if 'quantidade' not in df_vendas.columns:
        df_vendas['quantidade'] = 0

    if 'valor' not in df_vendas.columns:
        df_vendas['valor'] = df_vendas['quantidade'] * df_vendas['preco_unit']

    if 'data' not in df_vendas.columns:
        for col in df_vendas.columns:
            if 'data' in col:
                df_vendas['data'] = pd.to_datetime(df_vendas[col]).dt.date
                break
        else:
            df_vendas['data'] = pd.to_datetime('today').date()

    # Garantir coluna de nome de produtos
    nome_col_produto = None
    for col in df_produtos.columns:
        if "nome" in col and "produt" in col:
            nome_col_produto = col
            break
    if not nome_col_produto:
        df_produtos['nome_produto'] = "Desconhecido"
        nome_col_produto = 'nome_produto'

    # Garantir coluna de nome de vendedores
    nome_col_vendedor = None
    for col in df_vendedores.columns:
        if "nome" in col:
            nome_col_vendedor = col
            break
    if not nome_col_vendedor:
        df_vendedores['nome_vendedor'] = "Desconhecido"
        nome_col_vendedor = 'nome_vendedor'

    return df_vendas, df_produtos, df_vendedores, nome_col_produto, nome_col_vendedor

def prever_vendas_produto(df_vendas, prod_id, periodo_meses=3):
    df_prod = df_vendas[df_vendas['id_produto'] == prod_id].copy()
    if df_prod.empty:
        return None, None
    
    # Converter datas para ordinal
    df_prod['data_ord'] = pd.to_datetime(df_prod['data']).map(pd.Timestamp.toordinal)
    X = df_prod[['data_ord']]
    y = df_prod['quantidade']
    
    model = LinearRegression()
    model.fit(X, y)
    
    ultima_data = pd.to_datetime(df_prod['data']).max()
    futuras_datas = [ultima_data + pd.DateOffset(months=i+1) for i in range(periodo_meses)]
    futuras_ord = np.array([d.toordinal() for d in futuras_datas]).reshape(-1,1)
    previsao = model.predict(futuras_ord)
    
    # Gerar gráfico
    plt.figure(figsize=(8,4))
    plt.plot(pd.to_datetime(df_prod['data']), y, label='Histórico')
    plt.plot(futuras_datas, previsao, label='Previsão', linestyle='--')
    plt.title(f"Previsão de vendas do produto {prod_id}")
    plt.xlabel("Data")
    plt.ylabel("Quantidade")
    plt.legend()
    
    img_path = f"static/previsao_produto_{prod_id}.png"
    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    plt.savefig(img_path)
    plt.close()
    
    return previsao.tolist(), img_path

def analisar_vendedor(df_vendas, df_vendedores, vend_id):
    df_vendas['data'] = pd.to_datetime(df_vendas['data'])
    df_vendas['mes'] = df_vendas['data'].dt.to_period('M')
    df_mes = df_vendas.groupby(['id_vendedor','mes'])['valor'].sum().unstack(fill_value=0)
    crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)
    potencial = crescimento.get(vend_id, None)
    df_nomes = df_vendedores.set_index('id_vendedor')['nome']
    nome_vendedor = df_nomes.get(vend_id, "Desconhecido")
    
    return potencial, nome_vendedor

# -----------------------------
# Endpoint de Chat
# -----------------------------
@router.post("/chat")
async def chat_endpoint(payload: dict):
    pergunta = payload.get("texto", "").lower()
    
    try:
        df_vendas, df_produtos, df_vendedores, nome_col_produto, nome_col_vendedor = carregar_dados()
    except FileNotFoundError as e:
        return {"error": str(e)}
    
     # -------------------- Detecção de previsão de vendas --------------------
    if "prever" in pergunta or "previsao" in pergunta or "projecao" in pergunta:
        if match := re.search(r'produto (\d+)', pergunta):
            prod_id = int(match.group(1))
            periodo = int(re.search(r'(\d+) meses', pergunta).group(1)) if re.search(r'(\d+) meses', pergunta) else 3
            previsao, img_path = prever_vendas_produto(df_vendas, prod_id, periodo)
            if previsao is None:
                return {"pergunta": pergunta, "resposta": "Produto não encontrado ou sem histórico"}
            
            return {
                "pergunta": pergunta,
                "resposta": f"Previsão de vendas do produto {prod_id} para os próximos {periodo} meses:",
                "previsao_quantidade": [int(q) for q in previsao],
                "grafico_img": img_path
            }
        elif match := re.search(r'vendedor (\d+)', pergunta):
            vend_id = int(match.group(1))
            potencial, nome_vendedor = analisar_vendedor(df_vendas, df_vendedores, vend_id)
            if potencial is None:
                return {"pergunta": pergunta, "resposta": "Vendedor não encontrado"}
            
            return {
                "pergunta": pergunta,
                "resposta": f"Potencial de crescimento médio do vendedor {nome_vendedor}:",
                "potencial_crescimento_medio": round(float(potencial),4)
            }

    # -------------------- Produtos --------------------
    if "produto" in pergunta:
        filtros = extrair_filtros_produtos(pergunta)

        # 1️⃣ Top produtos por categoria e ano
        if filtros.get('categoria') and filtros.get('ano'):
            resultado = top_produtos_categoria_ano(
                df_vendas, df_produtos,
                filtros['categoria'], filtros['ano'], filtros['top_n']
            )
            return {
                "pergunta": pergunta,
                "resposta": f"Top {filtros['top_n']} produtos da categoria {filtros['categoria']} em {filtros['ano']}:",
                "dados": resultado,
                "grafico": {
                    "tipo": "bar",
                    "labels": [r['nome'] for r in resultado],
                    "values": [r['valor'] for r in resultado]
                }
            }

        # 2️⃣ Previsão de vendas de produto específico
        elif match := re.search(r'produto (\d+)', pergunta):
            prod_id = int(match.group(1))
            pred, img_path = prever_vendas_produto(df_vendas, prod_id)
            previsao_formatada = [f"R$ {p:.2f}" for p in pred]
            return {
                "pergunta": pergunta,
                "resposta": f"Projeção de vendas do produto {prod_id} para os próximos períodos:",
                "previsao": previsao_formatada,
                "grafico_img": img_path
        }

        # 3️⃣ Top produtos gerais (sem filtros)
        else:
            total_vendas = df_vendas.groupby('id_produto')['quantidade'].sum()
            df_produtos_dict = df_produtos.set_index('id_produto')[nome_col_produto].to_dict()
            top_produtos = total_vendas.sort_values(ascending=False).head(5)
            resultado = [
                {"Produto": df_produtos_dict.get(pid, "Desconhecido"), "Quantidade_Total": int(qty)}
                for pid, qty in top_produtos.items()
            ]
            return {
                "pergunta": pergunta,
                "resposta": "Top produtos mais vendidos:",
                "dados": resultado,
                "grafico": {
                    "tipo": "bar",
                    "labels": [r['Produto'] for r in resultado],
                    "values": [r['Quantidade_Total'] for r in resultado]
                }
            }

    # -------------------- Vendedores --------------------
    elif "vendedor" in pergunta:
        df_vendas['mes'] = pd.to_datetime(df_vendas['data']).dt.to_period('M')
        df_mes = df_vendas.groupby(['id_vendedor','mes'])['valor'].sum().unstack(fill_value=0)
        crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)
        df_nomes = df_vendedores.set_index('id_vendedor')[nome_col_vendedor]
        resultado = [
            {"Id_Vendedor": vid, "Nome_Vendedor": df_nomes.get(vid, "Desconhecido"), "Crescimento": round(val,4)}
            for vid, val in crescimento.sort_values(ascending=False).head(3).items()
        ]
        return {
            "pergunta": pergunta,
            "resposta": "Top vendedores:",
            "dados": resultado,
            "grafico": {
                "tipo": "bar",
                "labels": [r['Nome_Vendedor'] for r in resultado],
                "values": [r['Crescimento'] for r in resultado]
            }
        }

    # -------------------- Vendas / Previsões --------------------
    elif "venda" in pergunta or "previsão" in pergunta:
        df_vendas['produto_nome'] = df_vendas['id_produto'].map(df_produtos.set_index('id_produto')[nome_col_produto])
        total_vendas = df_vendas.groupby('produto_nome')['quantidade'].sum()
        resultado = [{"Produto": p, "Quantidade_Total": int(qty)} for p, qty in total_vendas.items()]
        return {
            "pergunta": pergunta,
            "resposta": "Vendas totais por produto:",
            "dados": resultado,
            "grafico": {
                "tipo": "bar",
                "labels": [r['Produto'] for r in resultado],
                "values": [r['Quantidade_Total'] for r in resultado]
            }
        }

    # -------------------- Perguntas não reconhecidas --------------------
    else:
        return {
            "pergunta": pergunta,
            "resposta": "Desculpe, não entendi sua pergunta. Pergunte sobre produtos, vendedores ou vendas."
        }
