import pandas as pd
from backend.database import SessionLocal, Venda
import re
import os
from sklearn.linear_model import LinearRegression
import numpy as np
import matplotlib.pyplot as plt
from backend.service_helpers import prever_vendas_produto 

PATH_VENDAS = "data/vendas_limpo.xlsx"
PATH_PRODUTOS = "data/produtos_limpo.xlsx"
PATH_VENDEDORES = "data/vendedores_limpo.xlsx"

def carregar_dados():
    if not all(os.path.exists(p) for p in [PATH_VENDAS, PATH_PRODUTOS, PATH_VENDEDORES]):
        raise FileNotFoundError("Arquivos de dados não encontrados")
    df_vendas = pd.read_excel(PATH_VENDAS)
    df_produtos = pd.read_excel(PATH_PRODUTOS)
    df_vendedores = pd.read_excel(PATH_VENDEDORES)

    # padronização de colunas
    df_vendas.columns = df_vendas.columns.str.strip().str.lower()
    df_produtos.columns = df_produtos.columns.str.strip().str.lower()
    df_vendedores.columns = df_vendedores.columns.str.strip().str.lower()

    if 'nome' not in df_produtos.columns:
        df_produtos['nome'] = "Desconhecido"
    if 'nome' not in df_vendedores.columns:
        df_vendedores['nome'] = "Desconhecido"

    return df_vendas, df_produtos, df_vendedores

# -----------------------------
# Produtos
# -----------------------------
def get_top_produtos(top_n=5):
    df_vendas, df_produtos, _ = carregar_dados()
    df_vendas['produto_nome'] = df_vendas['id_produto'].map(df_produtos.set_index('id_produto')['nome'])
    total_vendas = df_vendas.groupby('produto_nome')['valor'].sum().sort_values(ascending=False).head(top_n)
    return [{"produto": p, "total_vendas": float(v)} for p, v in total_vendas.items()]

def get_previsao_vendas_produto(id_produto):
    df_vendas, _, _ = carregar_dados()
    pred, img_path = prever_vendas_produto(df_vendas, id_produto)
    return {"id_produto": id_produto, "previsao": float(pred), "grafico_img": img_path}

# -----------------------------
# Vendedores
# -----------------------------
def get_top_vendedores(top_n=3):
    df_vendas, _, df_vendedores = carregar_dados()
    df_vendas['mes'] = pd.to_datetime(df_vendas['data_venda']).dt.to_period('M')
    df_mes = df_vendas.groupby(['id_vendedor', 'mes'])['valor'].sum().unstack(fill_value=0)
    crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)
    df_nomes = df_vendedores.set_index("id_vendedor")["nome"]
    resultado = [{"id_vendedor": vid, "nome": df_nomes.get(vid, "Desconhecido"), "crescimento": round(val, 4)}
                 for vid, val in crescimento.sort_values(ascending=False).head(top_n).items()]
    return resultado

def get_previsao_vendedor(id_vendedor):
    df_vendas, _, df_vendedores = carregar_dados()
    df_vendas['mes'] = pd.to_datetime(df_vendas['data_venda']).dt.to_period('M')
    df_mes = df_vendas[df_vendas['id_vendedor'] == id_vendedor].groupby('mes')['valor'].sum()
    previsao = {str(m): float(v) for m, v in df_mes.items()}
    return {"id_vendedor": id_vendedor, "previsao": previsao, "nome": df_vendedores.set_index("id_vendedor").get("nome", {}).get(id_vendedor, "Desconhecido")}


def prever_vendas_produto(id_produto: int):
    db = SessionLocal()
    vendas = db.query(Venda).filter(Venda.Id_Produto == id_produto).all()
    db.close()

    if not vendas:
        return {"erro": f"Produto {id_produto} não encontrado"}

    # Simples previsão (exemplo: média + 10%)
    valores = [v.Quantidade for v in vendas]
    media = sum(valores) / len(valores)
    previsao = round(media * 1.1, 2)

    return {
        "produto": id_produto,
        "media_historica": media,
        "previsao_proximo_trimestre": previsao
    }



def top_produtos_categoria_ano(df_vendas, df_produtos, categoria: str, ano: int, top_n: int = 5):
    """
    Retorna os top N produtos de uma categoria específica em um ano, ordenados por vendas.
    """
    # Garantir que datas são datetime
    df_vendas['data'] = pd.to_datetime(df_vendas['data'])
    
    # Filtrar por ano
    df = df_vendas[df_vendas['data'].dt.year == ano]
    
    # Filtrar por categoria
    ids_produtos = df_produtos[df_produtos['categoria'].str.contains(categoria, case=False, na=False)]['id_produto']
    df = df[df['id_produto'].isin(ids_produtos)]
    
    # Agrupar por produto e somar vendas
    resumo = df.groupby('id_produto')['valor'].sum().reset_index()
    
    # Adicionar nome do produto
    resumo['nome'] = resumo['id_produto'].map(df_produtos.set_index('id_produto')['nome'])
    
    # Ordenar crescente
    resumo = resumo.sort_values(by='valor', ascending=True).head(top_n)
    
    # Transformar em lista de dicionários
    resultado = resumo.to_dict(orient='records')
    
    return resultado




def extrair_filtros_produtos(texto: str):
    """
    Extrai categoria, ano e top_n do texto da pergunta.
    Retorna um dicionário com os filtros encontrados.
    """
    filtros = {}

    # Categoria
    cat_match = re.search(r'categoria ([\w\s]+)', texto, re.IGNORECASE)
    if cat_match:
        filtros['categoria'] = cat_match.group(1).strip()

    # Ano
    ano_match = re.search(r'ano de (\d{4})', texto, re.IGNORECASE)
    if ano_match:
        filtros['ano'] = int(ano_match.group(1))

    # Número de produtos (top N)
    top_match = re.search(r'([0-9]+) produtos', texto, re.IGNORECASE)
    if top_match:
        filtros['top_n'] = int(top_match.group(1))
    else:
        filtros['top_n'] = 5  # padrão

    return filtros

def prever_vendas_produto(df_vendas, id_produto):
    # Filtra apenas as vendas do produto solicitado
    df = df_vendas[df_vendas['id_produto'] == id_produto].copy()
    df['data'] = pd.to_datetime(df['data'])
    
    # Agrupa por trimestre e soma os valores de vendas
    df['trimestre'] = df['data'].dt.to_period('Q')
    df_trimestre = df.groupby('trimestre')['valor'].sum().reset_index()
    
    # Cria variável numérica para regressão (0,1,2,...)
    df_trimestre['trimestre_num'] = np.arange(len(df_trimestre))
    
    # Cria modelo de regressão linear
    model = LinearRegression()
    model.fit(df_trimestre[['trimestre_num']], df_trimestre['valor'])
    
    # Predição do próximo trimestre
    prox_trimestre = np.array([[len(df_trimestre)]])
    pred = model.predict(prox_trimestre)[0]
    
    # Gera gráfico (histórico + previsão)
    plt.plot(df_trimestre['trimestre_num'], df_trimestre['valor'], marker='o', label='Histórico')
    plt.plot(prox_trimestre[0], pred, marker='x', color='red', label='Previsto')
    plt.xlabel('Trimestre')
    plt.ylabel('Vendas (R$)')
    plt.legend()
    plt.title(f'Projeção de vendas Produto {id_produto}')
    img_path = f'vendas_produto_{id_produto}.png'
    plt.savefig(img_path)
    plt.close()
    
    # Retorna valor previsto e caminho do gráfico
    return pred, img_path
