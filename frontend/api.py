from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from backend import service
import re

router = APIRouter()

class Pergunta(BaseModel):
    texto: str

# -----------------------------
# Endpoint de Chat
# -----------------------------
@router.post("/chat")
async def chat_endpoint(payload: Pergunta):
    pergunta = payload.texto.lower()

    # =====================
    # VENDAS
    # =====================
    if "venda" in pergunta:
        # Total de vendas de um produto
        if match := re.search(r'produto (\d+)', pergunta):
            id_prod = int(match.group(1))
            total = service.total_vendas_produto(id_prod)
            return {
                "pergunta": pergunta,
                "resposta": f"Total de vendas do produto {id_prod}: R$ {total['total_vendas']:.2f}"
            }

        # Total de vendas de um vendedor
        elif match := re.search(r'vendedor (\d+)', pergunta):
            id_vend = int(match.group(1))
            total = service.total_vendas_vendedor(id_vend)
            return {
                "pergunta": pergunta,
                "resposta": f"Total de vendas do vendedor {id_vend}: R$ {total['total_vendas']:.2f}"
            }

        # Vendas por região
        elif re.search(r"regi[aã]o", pergunta, re.I):
            vendas_regiao = service.vendas_por_regiao()
            return {
                "pergunta": pergunta,
                "resposta": "Valor total de vendas por região:",
                "dados": vendas_regiao
            }

    # =====================
    # PRODUTOS
    # =====================
    if "produto" in pergunta:
        if "prever" in pergunta or "previsao" in pergunta:
            if match := re.search(r'produto (\d+)', pergunta):
                id_prod = int(match.group(1))
                resultado = service.prever_vendas_produto_trimestre(id_prod)
                if "erro" in resultado:
                    return {"pergunta": pergunta, "resposta": resultado["erro"]}
        
                return {
                    "pergunta": pergunta,
                    "grafico_img": resultado["grafico"]
                }

        

        # Detalhes do produto
        elif match := re.search(r'produto (\d+)', pergunta):
            id_prod = int(match.group(1))
            detalhes = service.detalhes_produto(id_prod)
            return {
                "pergunta": pergunta,
                "resposta": f"Detalhes do produto {id_prod}:",
                "dados": detalhes
            }

        # Top produtos por categoria e ano
        elif "categoria" in pergunta and "ano" in pergunta:
            filtros = service.extrair_filtros_produtos(pergunta)
            if filtros.get("categoria"):
                top_n = filtros.get("top_n", 5)
                categoria = filtros["categoria"]
                ano = filtros.get("ano")
                produtos = service.top_produtos_categoria_ano(
                    categoria=categoria, ano=ano, top_n=top_n
                )

                return {
                    "pergunta": pergunta,
                    "resposta": f"Top {top_n} produtos da categoria '{categoria}':",
                    "produtos": produtos
                }

        # =====================
        # VENDEDORES
        # =====================
        if "vendedor" in pergunta:
            # Top vendedores
            if "top" in pergunta:
                resultado = service.top_vendedores()
                return {
                    "pergunta": pergunta,
                    "resposta": "Top vendedores:",
                    "dados": resultado,
                    "grafico": {
                        "tipo": "bar",
                        "labels": [r['nome'] for r in resultado],
                        "values": [r['crescimento'] for r in resultado]
                    }
                }

            elif match := re.search(r'vendedor (\d+)', pergunta):
                id_vend = int(match.group(1))
                resultado = service.potencial_crescimento_vendedor(id_vend)

                return {
                    "pergunta": pergunta,
                    "resposta": f"Informações do vendedor {resultado['nome_vendedor']}:",
                    "potencial_crescimento": round(resultado['potencial_crescimento'], 4),
                    "regiao": resultado['regiao'],
                    "vendas_totais": resultado['vendas_totais'],
                    "produtos_mais_vendidos": resultado['produtos_mais_vendidos']
                }

    





    # --------------------
    # Pergunta não reconhecida
    # --------------------
    return {
        "pergunta": pergunta,
        "resposta": "Desculpe, não entendi sua pergunta. Pergunte sobre produtos, vendedores ou vendas."
    }


# =====================
# Configuração do FastAPI
# =====================
app = FastAPI(title="Chatbot 🚀")
app.include_router(router, prefix="/api")
