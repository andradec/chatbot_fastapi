from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Engine do banco de dados SQLite
ENGINE = create_engine("sqlite:///chatbot.db", echo=True)

# Factory de sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

# Base para os models
Base = declarative_base()

# -----------------------------
# Models
# -----------------------------
class Produto(Base):
    __tablename__ = "produtos"
    id_produto = Column(Integer, primary_key=True, index=True)
    nome_produto = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    preco = Column(Float, nullable=False)

    # Relacionamento com vendas
    vendas = relationship("Venda", back_populates="produto")


class Vendedor(Base):
    __tablename__ = "vendedores"
    id_vendedor = Column(Integer, primary_key=True, index=True)
    nome_vendedor = Column(String, nullable=False)
    regiao = Column(String, nullable=False)

    # Relacionamento com vendas
    vendas = relationship("Venda", back_populates="vendedor")


class Venda(Base):
    __tablename__ = "vendas"
    id_venda = Column(Integer, primary_key=True, index=True)
    id_produto = Column(Integer, ForeignKey("produtos.id_produto"))
    id_vendedor = Column(Integer, ForeignKey("vendedores.id_vendedor"))
    quantidade = Column(Integer, nullable=False)
    data_venda = Column(Date, nullable=False)
    preco_unit = Column(Float, nullable=False)
    valor_total = Column(Float, nullable=False)

    # Relacionamentos
    produto = relationship("Produto", back_populates="vendas")
    vendedor = relationship("Vendedor", back_populates="vendas")

# -----------------------------
# Função auxiliar para criar as tabelas
# -----------------------------
def init_db():
    Base.metadata.create_all(bind=ENGINE)
