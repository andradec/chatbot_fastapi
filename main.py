from fastapi import FastAPI, Body, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from contextlib import asynccontextmanager
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
import matplotlib.pyplot as plt
import os
from valida_dados import validar_dados
import re
from fastapi import FastAPI, Body
from pydantic import BaseModel
import pandas as pd
import os

# ---------- Banco de Dados ----------
Base = declarative_base()
ENGINE = create_engine("sqlite:///chatbot.db")
Session = sessionmaker(bind=ENGINE)

class Produto(Base):
    __tablename__ = "produtos"
    id_produto = Column(Integer, primary_key=True)
    nome = Column(String)
    categoria = Column(String)
    preco = Column(Float)
    vendas = relationship("Venda", back_populates="produto")

class Vendedor(Base):
    __tablename__ = "vendedores"
    id_vendedor = Column(Integer, primary_key=True)
    nome = Column(String)
    regiao = Column(String)
    vendas = relationship("Venda", back_populates="vendedor")

class Venda(Base):
    __tablename__ = "vendas"
    id_venda = Column(Integer, primary_key=True)
    id_produto = Column(Integer, ForeignKey("produtos.id_produto"))
    id_vendedor = Column(Integer, ForeignKey("vendedores.id_vendedor"))
    quantidade = Column(Integer)
    data = Column(Date)
    preco_unit = Column(Float)
    valor = Column(Float)

    produto = relationship("Produto", back_populates="vendas")
    vendedor = relationship("Vendedor", back_populates="vendas")

# ---------- Função para carregar arquivos ----------
def load_file(path: str):
    if path.endswith(".csv"):
        return pd.read_csv(path, sep=";")
    elif path.endswith(".xlsx"):
        return pd.read_excel(path)
    else:
        raise ValueError(f"Formato não suportado: {path}")

# ---------- Seed Database ----------
def seed_db_from_files():
    Base.metadata.create_all(ENGINE)
    with Session() as s:
        if s.query(Produto).first():
            return  # já populado

        # Carregar arquivos
        df_produtos = load_file("data/produtos.xlsx")
        df_vendedores = load_file("data/vendedores.xlsx")
        df_vendas = load_file("data/vendas.xlsx")

        # Renomear colunas para padronizar
        df_produtos.rename(columns={
            "Id_Produto": "id_produto",
            "Nome_Produto": "nome",        # <-- aqui
            "Categoria": "categoria",
            "R$_Unit": "preco"
        }, inplace=True)
        df_produtos.columns = df_produtos.columns.str.lower()

        df_vendedores.rename(columns={
            "Id_Vendedor": "id_vendedor",
            "Nome_Vendedor": "nome",
            "Região": "regiao"
        }, inplace=True)

        df_vendas.rename(columns={
            "Id_Venda": "id_venda",
            "Id_Produto": "id_produto",
            "Id_Vendedor": "id_vendedor",
            "Quantidade": "quantidade",
            "Data_Venda": "data",
            "R$_Unit": "preco_unit",
            "R$_Total": "valor"
        }, inplace=True)

        # Ajustar tipos
        df_produtos["preco"] = df_produtos["preco"].astype(float)
        df_vendas["quantidade"] = df_vendas["quantidade"].astype(int)
        df_vendas["preco_unit"] = df_vendas["preco_unit"].astype(float)
        df_vendas["valor"] = df_vendas["valor"].astype(float)
        df_vendas["data"] = pd.to_datetime(df_vendas["data"]).dt.date

        # Inserir no banco
        for _, row in df_produtos.iterrows():
            s.add(Produto(**row.to_dict()))
        for _, row in df_vendedores.iterrows():
            s.add(Vendedor(**row.to_dict()))
        for _, row in df_vendas.iterrows():
            s.add(Venda(**row.to_dict()))

        s.commit()


# ---------- Funções auxiliares ----------
def prever_vendas_produto(df_vendas, id_produto):
    df = df_vendas[df_vendas['id_produto'] == id_produto].copy()
    df['data'] = pd.to_datetime(df['data'])
    df['trimestre'] = df['data'].dt.to_period('Q')
    df_trimestre = df.groupby('trimestre')['valor'].sum().reset_index()
    df_trimestre['trimestre_num'] = np.arange(len(df_trimestre))

    model = LinearRegression()
    model.fit(df_trimestre[['trimestre_num']], df_trimestre['valor'])

    prox_trimestre = np.array([[len(df_trimestre)]])
    pred = model.predict(prox_trimestre)[0]

    # Gráfico
    plt.plot(df_trimestre['trimestre_num'], df_trimestre['valor'], marker='o', label='Histórico')
    plt.plot(prox_trimestre[0], pred, marker='x', color='red', label='Previsto')
    plt.xlabel('Trimestre')
    plt.ylabel('Vendas (R$)')
    plt.legend()
    plt.title(f'Projeção de vendas Produto {id_produto}')
    plt.savefig(f'vendas_produto_{id_produto}.png')
    plt.close()

    return pred, f'vendas_produto_{id_produto}.png'


def potenciais_vendedores(df_vendas):
    df = df_vendas.copy()
    df['data'] = pd.to_datetime(df['data'])
    df['mes'] = df['data'].dt.to_period('M')
    df_mes = df.groupby(['id_vendedor','mes'])['valor'].sum().unstack(fill_value=0)
    crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)
    top_vendedores = crescimento.sort_values(ascending=False).head(3)
    return top_vendedores

# ---------- Lifespan moderno ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not validar_dados():
        raise Exception("Falha na validação/limpeza de dados. Corrija manualmente os problemas críticos.")
    seed_db_from_files()
    print("Dados validados e seed carregado.")
    yield

app = FastAPI(title="Chatbot Vendas/Produtos/Vendedores", lifespan=lifespan)

# ---------- Modelo de entrada ----------
class Pergunta(BaseModel):
    texto: str

# ---------- Endpoints ----------
from fastapi.responses import JSONResponse

def filtrar_dataframe(df_vendas, df_produtos, df_vendedores, texto):
    """Tenta extrair filtros de categoria, ano, produto, vendedor do texto."""
    filtros = {}

    # Categoria
    cat_match = re.search(r'categoria ([\w\s]+)', texto)
    if cat_match:
        filtros['categoria'] = cat_match.group(1).strip()

    # Ano
    ano_match = re.search(r'(\d{4})', texto)
    if ano_match:
        filtros['ano'] = int(ano_match.group(1))

    # Produto (por id)
    prod_match = re.search(r'produto (\d+)', texto)
    if prod_match:
        filtros['id_produto'] = int(prod_match.group(1))

    # Vendedor (por id)
    vend_match = re.search(r'vendedor (\d+)', texto)
    if vend_match:
        filtros['id_vendedor'] = int(vend_match.group(1))

    # Filtro dataframe
    df = df_vendas.copy()
    df['data_venda'] = pd.to_datetime(df['data_venda'])

    if 'ano' in filtros:
        df = df[df['data_venda'].dt.year == filtros['ano']]
    if 'id_produto' in filtros:
        df = df[df['id_produto'] == filtros['id_produto']]
    if 'id_vendedor' in filtros:
        df = df[df['id_vendedor'] == filtros['id_vendedor']]
    if 'categoria' in filtros:
        ids_produtos = df_produtos[df_produtos['categoria'].str.contains(filtros['categoria'], case=False, na=False)]['id_produto']
        df = df[df['id_produto'].isin(ids_produtos)]

    return df

@app.post("/chat")
def chat(input: Pergunta):
    texto = input.texto.lower()

    try:
        # Arquivos limpos
        path_vendas = "data/vendas_limpo.xlsx"
        path_vendedores = "data/vendedores_limpo.xlsx"
        path_produtos = "data/produtos_limpo.xlsx"

        if not all(os.path.exists(p) for p in [path_vendas, path_vendedores, path_produtos]):
            return JSONResponse(status_code=500, content={"error": "Arquivos limpos não encontrados"})

        df_vendas = pd.read_excel(path_vendas)
        df_vendedores = pd.read_excel(path_vendedores)
        df_produtos = pd.read_excel(path_produtos)

        # Padronizar nomes de colunas
        df_vendas.columns = df_vendas.columns.str.lower()
        df_vendedores.columns = df_vendedores.columns.str.lower()
        df_produtos.columns = df_produtos.columns.str.lower()

        # Garantir colunas 'nome' existem
        if 'nome' not in df_produtos.columns:
            df_produtos['nome'] = "Desconhecido"
        if 'nome' not in df_vendedores.columns:
            df_vendedores['nome'] = "Desconhecido"

        # ---------- Top vendedores ----------
        if "melhor vendedor" in texto or "top vendedor" in texto:
            df_vendas['mes'] = pd.to_datetime(df_vendas['data_venda']).dt.to_period('M')
            df_mes = df_vendas.groupby(['id_vendedor','mes'])['quantidade'].sum().unstack(fill_value=0)
            crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)

            df_nomes = df_vendedores.set_index("id_vendedor")["nome"]
            resultado = [
                {"Id_Vendedor": vid, "Nome_Vendedor": df_nomes.get(vid, "Desconhecido"), "Crescimento": round(val,4)}
                for vid,val in crescimento.sort_values(ascending=False).head(3).items()
            ]
            return {"pergunta": texto, "resposta": "Top vendedores encontrados:", "dados": resultado}

        # ---------- Top produtos ----------
        elif "produto" in texto and ("mais vendido" in texto or "vendidos" in texto or "top" in texto):
            df_produtos_vendas = df_vendas.groupby("id_produto")['quantidade'].sum()
            df_nomes = df_produtos.set_index('id_produto')['nome']

            resultado = [
                {"Id_Produto": pid, "Nome_Produto": df_nomes.get(pid, "Desconhecido"), "Quantidade_Total": int(qty)}
                for pid, qty in df_produtos_vendas.sort_values(ascending=False).head(5).items()
            ]
            return {"pergunta": texto, "resposta": "Top produtos encontrados:", "dados": resultado}

        # ---------- Perguntas sobre vendas totais ----------
        elif "vendas" in texto or "quantidade vendida" in texto:
            df_vendas['produto_nome'] = df_vendas['id_produto'].map(df_produtos.set_index('id_produto')['nome'])
            df_vendas['vendedor_nome'] = df_vendas['id_vendedor'].map(df_vendedores.set_index('id_vendedor')['nome'])

            total_vendas = df_vendas.groupby('produto_nome')['quantidade'].sum()
            resultado = [{"Produto": p, "Quantidade_Total": int(qty)} for p, qty in total_vendas.items()]

            return {"pergunta": texto, "resposta": "Vendas totais por produto:", "dados": resultado}

        # ---------- Perguntas não reconhecidas ----------
        else:
            return {"pergunta": texto, "resposta": "Desculpe, não entendi sua pergunta. Tente perguntar sobre vendedores, produtos ou vendas."}

    except Exception as e:
        return {"pergunta": texto, "resposta": f"Erro interno: {str(e)}"}
    
    
@app.post("/prever_vendas")
def api_prever_vendas(produto_id: int):
    with Session() as s:
        df_vendas = pd.read_sql(s.query(Venda).statement, s.bind)
    pred, img_path = prever_vendas_produto(df_vendas, produto_id)
    return {"previsao": f"R$ {pred:.2f}", "grafico": img_path}


@app.get("/top_vendedores")
def api_top_vendedores():
    import os
    import pandas as pd

    path_vendas = "data/vendas_limpo.xlsx"
    path_vendedores = "data/vendedores_limpo.xlsx"

    if not all(os.path.exists(p) for p in [path_vendas, path_vendedores]):
        return {"error": "Arquivos limpos não encontrados"}

    df_vendas = pd.read_excel(path_vendas)
    df_vendedores = pd.read_excel(path_vendedores)

    # Padronizar nomes de colunas
    df_vendas.columns = df_vendas.columns.str.lower()
    df_vendedores.columns = df_vendedores.columns.str.lower()

    # Garantir que a coluna 'nome' exista
    if 'nome' not in df_vendedores.columns:
        df_vendedores['nome'] = "Desconhecido"

    # Agrupar por mês
    df_vendas['mes'] = pd.to_datetime(df_vendas['data_venda']).dt.to_period('M')
    df_mes = df_vendas.groupby(['id_vendedor', 'mes'])['quantidade'].sum().unstack(fill_value=0)

    if df_mes.shape[1] < 2:
        return {"error": "Não há meses suficientes para calcular crescimento"}

    # Crescimento percentual médio
    crescimento = df_mes.pct_change(axis=1).replace([float('inf'), float('-inf')], 0).mean(axis=1).fillna(0)

    # Pegar top 3
    df_nomes = df_vendedores.set_index("id_vendedor")["nome"]
    resultado = [
        {"Id_Vendedor": vid, "Nome_Vendedor": df_nomes.get(vid, "Desconhecido"), "Crescimento": round(val, 4)}
        for vid, val in crescimento.sort_values(ascending=False).head(3).items()
    ]

    return {"top_vendedores": resultado}



@app.get("/top_produtos")
def api_top_produtos():
    path_vendas = "data/vendas_limpo.xlsx"
    path_produtos = "data/produtos_limpo.xlsx"

    if not all(os.path.exists(p) for p in [path_vendas, path_produtos]):
        return {"error": "Arquivos limpos não encontrados"}

    df_vendas = pd.read_excel(path_vendas)
    df_produtos = pd.read_excel(path_produtos)

    df_vendas.columns = df_vendas.columns.str.strip().str.lower()
    df_produtos.columns = df_produtos.columns.str.strip().str.lower()

    if 'nome' not in df_produtos.columns:
        df_produtos['nome'] = "Desconhecido"

    df_produtos_vendas = df_vendas.groupby("id_produto")["quantidade"].sum()
    resultado = [
        {
            "Id_Produto": pid,
            "Nome_Produto": df_produtos.set_index("id_produto")["nome"].get(pid,"Desconhecido"),
            "Quantidade_Total": int(qtd)
        }
        for pid, qtd in df_produtos_vendas.sort_values(ascending=False).head(5).items()
    ]
    return {"top_produtos": resultado}


