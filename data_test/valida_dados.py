import pandas as pd
import os

def validar_dados():
    arquivos = {
        "Produtos": "data/produtos.xlsx",
        "Vendedores": "data/vendedores.xlsx",
        "Vendas": "data/vendas.xlsx"
    }

    erros = []
    log = []

    # Verificar existência dos arquivos
    for nome, path in arquivos.items():
        if not os.path.exists(path):
            erros.append(f"Arquivo não encontrado: {path}")
    
    if erros:
        print("Erro(s) crítico(s) de arquivos:")
        for e in erros:
            print("-", e)
        return False

    # Carregar arquivos
    df_produtos = pd.read_excel(arquivos["Produtos"])
    df_vendedores = pd.read_excel(arquivos["Vendedores"])
    df_vendas = pd.read_excel(arquivos["Vendas"])

    # Valores ausentes: remover ou preencher
    for df, nome, criticas in zip(
        [df_produtos, df_vendedores, df_vendas],
        ["Produtos", "Vendedores", "Vendas"],
        [["Id_Produto","R$_Unit"], ["Id_Vendedor"], ["Id_Venda","Id_Produto","Id_Vendedor","Quantidade","R$_Unit"]]
    ):
        # Contar NaN
        n_nan = df[criticas].isna().sum().sum()
        if n_nan > 0:
            log.append(f"{nome}: {n_nan} valores ausentes em colunas críticas, serão removidos")
            df.dropna(subset=criticas, inplace=True)

    # Corrigir tipos
    try:
        df_produtos["R$_Unit"] = pd.to_numeric(df_produtos["R$_Unit"], errors="coerce")
        df_vendas["Quantidade"] = pd.to_numeric(df_vendas["Quantidade"], errors="coerce").astype(int)
        df_vendas["R$_Unit"] = pd.to_numeric(df_vendas["R$_Unit"], errors="coerce")
        df_vendas["R$_Total"] = pd.to_numeric(df_vendas["R$_Total"], errors="coerce")
        df_vendas["Data_Venda"] = pd.to_datetime(df_vendas["Data_Venda"], errors="coerce")
    except Exception as e:
        erros.append(f"Problema de tipo: {e}")

    # Integridade: remover vendas com produto ou vendedor inexistente
    prod_ids = set(df_produtos["Id_Produto"])
    vend_ids = set(df_vendedores["Id_Vendedor"])
    mask_prod = df_vendas["Id_Produto"].isin(prod_ids)
    mask_vend = df_vendas["Id_Vendedor"].isin(vend_ids)
    removed = (~mask_prod | ~mask_vend).sum()
    if removed > 0:
        log.append(f"Vendas: {removed} registros removidos por referenciar produto ou vendedor inexistente")
        df_vendas = df_vendas[mask_prod & mask_vend]

    # Duplicidades
    dup = df_vendas["Id_Venda"].duplicated().sum()
    if dup > 0:
        log.append(f"{dup} duplicidades em Id_Venda removidas")
        df_vendas = df_vendas.drop_duplicates(subset=["Id_Venda"])

    # Outliers básicos
    mask_out = (df_vendas["Quantidade"] <= 0) | (df_vendas["R$_Unit"] <= 0)
    outliers = df_vendas[mask_out]
    if not outliers.empty:
        log.append(f"{len(outliers)} registros com quantidade ou preço <= 0 removidos")
        df_vendas = df_vendas[~mask_out]

    # Salvar arquivos limpos (opcional)
    df_produtos.to_excel("data/produtos_limpo.xlsx", index=False)
    df_vendedores.to_excel("data/vendedores_limpo.xlsx", index=False)
    df_vendas.to_excel("data/vendas_limpo.xlsx", index=False)
    log.append("Arquivos limpos salvos como *_limpo.xlsx na pasta data/")

    print("== LOG DE VALIDAÇÃO E LIMPEZA ==")
    for l in log:
        print("-", l)

    if erros:
        print("Erros críticos encontrados, intervenção manual necessária:")
        for e in erros:
            print("-", e)
        return False

    print("Dados validados e limpos com sucesso!")
    return True
