import matplotlib.pyplot as plt
import os
import numpy as np

def prever_vendas_produto(prod_id, df_vendas, meses=3):
    df = df_vendas[df_vendas["id_produto"]==prod_id]
    if df.empty:
        return [], None

    ultima = df["valor"].iloc[-1]
    previsao = list(np.round(np.linspace(ultima, ultima*1.05, meses),2))

    plt.figure()
    plt.plot(df["valor"].values, label="Histórico")
    plt.plot(range(len(df), len(df)+meses), previsao, "--", label="Previsão")
    plt.legend()
    os.makedirs("static", exist_ok=True)
    path = f"static/previsao_produto_{prod_id}.png"
    plt.savefig(path)
    plt.close()
    return previsao, path

def analisar_vendedor(vend_id, df_vendas):
    df = df_vendas[df_vendas["id_vendedor"]==vend_id]
    if df.empty:
        return 0, None

    por_ano = df.groupby("ano")["valor"].sum()
    crescimento = (por_ano.pct_change().mean() or 0) * 100

    plt.figure()
    por_ano.plot(kind="bar")
    plt.title(f"Evolução Vendas - Vendedor {vend_id}")
    os.makedirs("static", exist_ok=True)
    path = f"static/vendedor_{vend_id}.png"
    plt.savefig(path)
    plt.close()
    return crescimento, path
