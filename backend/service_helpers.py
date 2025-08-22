# backend/service_helpers.py
import pandas as pd
import matplotlib.pyplot as plt
import os

def prever_vendas_produto(df_vendas, id_produto, trimestres_previsao=4):
    """
    Retorna uma previsão de vendas para o próximo trimestre
    usando média móvel simples nos últimos meses.
    """
    # Filtrar vendas do produto
    df_prod = df_vendas[df_vendas['id_produto'] == id_produto].copy()
    if df_prod.empty:
        return 0, None

    # Garantir que a coluna de datas seja datetime
    df_prod['data_venda'] = pd.to_datetime(df_prod['data_venda'])

    # Agrupar por trimestre
    df_prod['trimestre'] = df_prod['data_venda'].dt.to_period('Q')
    vendas_trimestrais = df_prod.groupby('trimestre')['quantidade'].sum()

    if vendas_trimestrais.empty:
        return 0, None

    # Previsão: média dos últimos 3 trimestres
    media_ultimos = vendas_trimestrais.tail(3).mean()
    previsao = media_ultimos

    # Criar gráfico simples
    plt.figure(figsize=(6,4))
    vendas_trimestrais.plot(kind='bar', color='skyblue', title=f"Vendas do Produto {id_produto}")
    plt.ylabel("Quantidade Vendida")
    plt.xlabel("Trimestre")

    # Adicionar previsão como barra vermelha
    plt.bar(f"Next-Q", previsao, color='red')
    
    # Criar pasta para gráficos, se não existir
    pasta_graficos = "data/graficos"
    os.makedirs(pasta_graficos, exist_ok=True)
    
    img_path = os.path.join(pasta_graficos, f"previsao_produto_{id_produto}.png")
    plt.savefig(img_path)
    plt.close()

    return float(previsao), img_path
