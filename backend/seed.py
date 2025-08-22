import pandas as pd
from .database import Base, ENGINE, SessionLocal, Produto, Vendedor, Venda

def load_file(path: str):
    if path.endswith(".csv"):
        return pd.read_csv(path, sep=";")
    elif path.endswith(".xlsx"):
        return pd.read_excel(path)
    else:
        raise ValueError(f"Formato não suportado: {path}")

def seed_db_from_files():
    # Cria as tabelas
    Base.metadata.create_all(ENGINE)

    # Cria uma sessão usando SessionLocal
    with SessionLocal() as s:
        # Verifica se já há dados
        if s.query(Produto).first():
            return  # já populado

        # Carrega arquivos
        df_produtos = load_file("data/produtos.xlsx")
        df_vendedores = load_file("data/vendedores.xlsx")
        df_vendas = load_file("data/vendas.xlsx")

# Normaliza nomes de colunas para bater com os modelos ORM
        df_produtos.rename(columns={
            "Id_Produto": "id_produto",
            "Nome_Produto": "nome_produto",
            "Categoria": "categoria",
            "R$_Unit": "preco"   # <-- mapeia o nome real para 'preco'
        }, inplace=True)

        # Converte para float
        df_produtos["preco"] = df_produtos["preco"].astype(float)
        
        df_vendedores.rename(columns={
            "Id_Vendedor": "id_vendedor",
            "Nome_Vendedor": "nome_vendedor",
            "Região": "regiao"
        }, inplace=True)

        df_vendas.rename(columns={
            "Id_Venda": "id_venda",
            "Id_Produto": "id_produto",
            "Id_Vendedor": "id_vendedor",
            "Quantidade": "quantidade",
            "Data_Venda": "data_venda",
            "R$_Unit": "preco_unit",
            "R$_Total": "valor_total"
        }, inplace=True)

        # Remove linhas sem preco_unit ou valor_total
        df_vendas = df_vendas.dropna(subset=["preco_unit", "valor_total"])
        
        # Ajusta tipos
        df_produtos["preco"] = df_produtos["preco"].astype(float)
        df_vendas["quantidade"] = df_vendas["quantidade"].astype(int)
        df_vendas["preco_unit"] = df_vendas["preco_unit"].astype(float)
        df_vendas["valor_total"] = df_vendas["valor_total"].astype(float)
        df_vendas["data_venda"] = pd.to_datetime(df_vendas["data_venda"]).dt.date



        # Popula o banco
        for _, row in df_produtos.iterrows():
            s.add(Produto(**row.to_dict()))
        for _, row in df_vendedores.iterrows():
            s.add(Vendedor(**row.to_dict()))
        for _, row in df_vendas.iterrows():
            s.add(Venda(**row.to_dict()))

        # Confirma alterações
        s.commit()
