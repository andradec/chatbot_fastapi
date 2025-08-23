import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from .database import SessionLocal, Produto, Vendedor, Venda
import os

import re
import unidecode

# -----------------------------
# Funções Auxiliares
# -----------------------------
def carregar_dados():
    """
    Carrega dados do banco para DataFrames pandas.
    """
    with SessionLocal() as session:
        df_produtos = pd.DataFrame([p.__dict__ for p in session.query(Produto).all()])
        df_vendedores = pd.DataFrame([v.__dict__ for v in session.query(Vendedor).all()])
        df_vendas = pd.DataFrame([v.__dict__ for v in session.query(Venda).all()])

    # Remove colunas internas do SQLAlchemy
    for df in [df_produtos, df_vendedores, df_vendas]:
        if "_sa_instance_state" in df.columns:
            df.drop(columns=["_sa_instance_state"], inplace=True)

    return df_vendas, df_produtos, df_vendedores

# -----------------------------
# VENDAS
# -----------------------------
def total_vendas_produto(id_produto: int):
    df_vendas, df_produtos, _ = carregar_dados()
    df_vendas['produto_nome'] = df_vendas['id_produto'].map(df_produtos.set_index('id_produto')['nome_produto'])
    total = df_vendas[df_vendas['id_produto'] == id_produto]['valor_total'].sum()
    return {"id_produto": id_produto, "produto_nome": df_vendas['produto_nome'].iloc[0], "total_vendas": float(total)}

def total_vendas_vendedor(id_vendedor: int):
    df_vendas, _, df_vendedores = carregar_dados()
    df_vendas['nome_vendedor'] = df_vendas['id_vendedor'].map(df_vendedores.set_index('id_vendedor')['nome_vendedor'])
    total = df_vendas[df_vendas['id_vendedor'] == id_vendedor]['valor_total'].sum()
    return {"id_vendedor": id_vendedor, "nome_vendedor": df_vendas['nome_vendedor'].iloc[0], "total_vendas": float(total)}

def vendas_por_regiao():
    df_vendas, _, df_vendedores = carregar_dados()
    df_vendas['regiao'] = df_vendas['id_vendedor'].map(df_vendedores.set_index('id_vendedor')['regiao'])
    resumo = df_vendas.groupby('regiao')['valor_total'].sum().reset_index()
    return resumo.to_dict(orient='records')

# -----------------------------
# PRODUTOS
# -----------------------------
def detalhes_produto(id_produto: int):
    df_vendas, df_produtos, _ = carregar_dados()
    prod = df_produtos[df_produtos['id_produto'] == id_produto].to_dict(orient='records')
    return prod[0] if prod else None

def top_produtos_categoria_ano(categoria: str, ano: int, top_n: int = 5):
    df_vendas, df_produtos, _ = carregar_dados()
    df_vendas['data_venda'] = pd.to_datetime(df_vendas['data_venda'])
    df = df_vendas[df_vendas['data_venda'].dt.year == ano]
    ids = df_produtos[df_produtos['categoria'].str.contains(categoria, case=False, na=False)]['id_produto']
    df = df[df['id_produto'].isin(ids)]
    resumo = df.groupby('id_produto')['valor_total'].sum().reset_index()
    resumo['nome_produto'] = resumo['id_produto'].map(df_produtos.set_index('id_produto')['nome_produto'])
    resumo = resumo.sort_values('valor_total', ascending=True).head(top_n)
    return resumo.to_dict(orient='records')

# -----------------------------
# VENDEDORES
# -----------------------------
def top_vendedores(top_n: int = 3):
    df_vendas, _, df_vendedores = carregar_dados()
    df_vendas['mes'] = pd.to_datetime(df_vendas['data_venda']).dt.to_period('M')
    df_mes = df_vendas.groupby(['id_vendedor','mes'])['valor_total'].sum().unstack(fill_value=0)
    crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)
    df_nomes = df_vendedores.set_index("id_vendedor")["nome_vendedor"]
    resultado = [{"id_vendedor": vid, "nome_vendedor": df_nomes.get(vid, "Desconhecido"), "crescimento": round(val, 4)}
                 for vid, val in crescimento.sort_values(ascending=False).head(top_n).items()]
    return resultado

def potencial_crescimento_vendedor(id_vendedor: int):
    """
    Retorna o potencial médio de crescimento do vendedor, seu nome e região.
    """
    df_vendas, _, df_vendedores = carregar_dados()
    
    # Filtra vendas do vendedor
    df_vend = df_vendas[df_vendas['id_vendedor'] == id_vendedor].copy()
    if df_vend.empty:
        return {
            "potencial_crescimento": 0,
            "nome_vendedor": df_vendedores.set_index('id_vendedor').get('nome', {}).get(id_vendedor, "Desconhecido"),
            "regiao": df_vendedores.set_index('id_vendedor').get('regiao', {}).get(id_vendedor, "Desconhecida")
        }
    
    # Calcula crescimento médio mensal
    df_vend['mes'] = pd.to_datetime(df_vend['data_venda']).dt.to_period('M')
    df_mes = df_vend.groupby('mes')['valor_total'].sum()
    crescimento = df_mes.pct_change().replace([float('inf'), float('-inf')], 0).mean()
    
    # Nome e região
    vendedor_info = df_vendedores.set_index('id_vendedor').loc[id_vendedor]
    
    return {
        "potencial_crescimento": crescimento,
        "nome_vendedor": vendedor_info.get('nome', 'Desconhecido'),
        "regiao": vendedor_info.get('regiao', 'Desconhecida')
    }


# -----------------------------
# PREVISÃO VENDAS PRODUTO
# -----------------------------
def prever_vendas_produto_trimestre(id_produto: int):
    df_vendas, _, df_produtos = carregar_dados()
    df = df_vendas[df_vendas['id_produto'] == id_produto].copy()
    if df.empty:
        return {"erro": "Produto não encontrado"}
    df['data_venda'] = pd.to_datetime(df['data_venda'])
    df['trimestre'] = df['data_venda'].dt.to_period('Q')
    df_trimestre = df.groupby('trimestre')['valor_total'].sum().reset_index()
    df_trimestre['trimestre_num'] = np.arange(len(df_trimestre))
    model = LinearRegression()
    model.fit(df_trimestre[['trimestre_num']], df_trimestre['valor_total'])
    prox_trimestre = np.array([[len(df_trimestre)]])
    pred = model.predict(prox_trimestre)[0]

    # Gráfico
    plt.plot(df_trimestre['trimestre_num'], df_trimestre['valor_total'], marker='o', label='Histórico')
    plt.plot(prox_trimestre[0], pred, marker='x', color='red', label='Previsto')
    plt.xlabel('Trimestre')
    plt.ylabel('Vendas (R$)')
    plt.legend()
    plt.title(f'Projeção Produto {id_produto}')
    os.makedirs("static", exist_ok=True)
    img_path = f"static/vendas_produto_{id_produto}.png"
    plt.savefig(img_path)
    plt.close()

    return {"id_produto": id_produto, "previsao": float(pred), "grafico": img_path}



def extrair_filtros_produtos(texto: str):
    """
    Extrai filtros de uma pergunta sobre produtos:
    - categoria (aceita acentos e espaços)
    - ano
    - top_n (quantidade de produtos)
    
    Retorna um dicionário com os filtros encontrados, usando valores padrão quando não especificados.
    """
    filtros = {}

    # Normaliza texto: remove acentos e coloca em minúsculas
    texto_normalizado = unidecode.unidecode(texto.lower())

    # Categoria: busca "categoria <nome>"
    cat_match = re.search(r'categoria ([\w\s]+)', texto_normalizado)
    if cat_match:
        filtros['categoria'] = cat_match.group(1).strip()

    # Ano: busca "ano de <4 dígitos>"
    ano_match = re.search(r'ano de (\d{4})', texto_normalizado)
    if ano_match:
        filtros['ano'] = int(ano_match.group(1))

    # Número de produtos (top N): busca "<n> produtos"
    top_match = re.search(r'(\d+)\s+produtos', texto_normalizado)
    filtros['top_n'] = int(top_match.group(1)) if top_match else 5  # padrão: 5

    return filtros