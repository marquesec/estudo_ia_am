"""
LCEL LAB — Reviews & Tickets  (mesmas 7 lições, zero segurança)
==============================================================
Rode UM por vez. Descomente no final.

    pip install -U langchain langchain-core langchain-google-genai pydantic python-dotenv
    python .\exercicio.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import (
    RunnableParallel,
    RunnablePassthrough,
    RunnableLambda,
    RunnableBranch,
)
from pydantic import BaseModel, Field
from typing import Literal

MODEL = "gemini-3.5-flash"

rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.2,      # 1 chamada a cada 5s. Baixe pra 0.1 se estourar.
    check_every_n_seconds=0.1,
    max_bucket_size=1,
)

llm = ChatGoogleGenerativeAI(
    model=MODEL,
    temperature=0,
    max_retries=1,
    timeout=60,
    rate_limiter=rate_limiter,
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

# ── Os dados. Só isto e os prompts mudaram em relação ao lab de AppSec. ──
RUIM = """
Comprei o fone semana passada e o lado direito já parou de funcionar.
Mandei email pro suporte (andre.marques@email.com) há 4 dias e ninguém respondeu.
Paguei R$ 890 nisso. Quero meu dinheiro de volta.
"""

BOM = """
Chegou antes do prazo, bateria dura o dia todo mesmo.
O app podia ser melhor mas pelo preço tá excelente. Recomendo.
"""

CONFUSO = """
Alguém sabe se dá pra usar com dois celulares ao mesmo tempo?
Não achei no manual. O produto em si é bom.
"""


# ─────────────────────────────────────────────────────────────
def ex1():
    """LIÇÃO: llm devolve AIMessage, não str. O parser só extrai .content.
    Repara no parser invocado FORA do pipe — ele é só mais um Runnable."""
    prompt = ChatPromptTemplate.from_template(
        "Resuma esta review em uma frase:\n{review}"
    )
    msg = (prompt | llm).invoke({"review": RUIM})
    print("SEM parser →", type(msg))
    print("COM parser →", type(StrOutputParser().invoke(msg)))
    print(StrOutputParser().invoke(msg))


def ex2():
    """LIÇÃO: batch e stream de graça. Você não escreveu paralelismo.
    Aqui fica óbvio o valor: 3 reviews, uma linha."""
    chain = (
        ChatPromptTemplate.from_template(
            "Sentimento em 1 palavra — POSITIVO, NEGATIVO ou NEUTRO:\n{review}"
        )
        | llm
        | StrOutputParser()
    )
    print(chain.batch([{"review": RUIM}, {"review": BOM}, {"review": CONFUSO}]))

    for pedaco in chain.stream({"review": RUIM}):
        print(pedaco, end="", flush=True)
    print()


def ex3():
    """LIÇÃO: qualquer função vira Runnable. Pré-processamento
    determinístico ANTES do modelo ver. Aqui: mascarar PII —
    o email do cliente não precisa ir pro provedor."""
    def mascarar_pii(payload: dict) -> dict:
        import re
        limpo = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', payload["review"])
        limpo = re.sub(r'R\$\s?[\d\.,]+', '[VALOR]', limpo)
        return {"review": limpo}

    chain = (
        RunnableLambda(mascarar_pii)
        | ChatPromptTemplate.from_template("Resuma a reclamação:\n{review}")
        | llm
        | StrOutputParser()
    )
    print(chain.invoke({"review": RUIM}))


def ex4():
    """LIÇÃO: dict no pipe vira RunnableParallel. Ramos CONCORRENTES.
    Três análises da mesma review, ao mesmo tempo."""
    sentimento = ChatPromptTemplate.from_template("Só o sentimento, 1 palavra:\n{review}") | llm | StrOutputParser()
    topicos = ChatPromptTemplate.from_template("Liste os tópicos, separados por vírgula:\n{review}") | llm | StrOutputParser()
    urgencia = ChatPromptTemplate.from_template("Urgência de 1 a 5, só o número:\n{review}") | llm | StrOutputParser()

    r = RunnableParallel(
        sentimento=sentimento,
        topicos=topicos,
        urgencia=urgencia,
    ).invoke({"review": RUIM})

    print(r)


def ex5():
    """LIÇÃO: o passo 2 precisa do resultado do passo 1 E do input original.
    Aqui: identifica o problema, depois escreve a resposta usando os dois."""
    diagnostico = ChatPromptTemplate.from_template(
        "Qual o problema principal? Responda em 5 palavras:\n{review}"
    ) | llm | StrOutputParser()

    chain = (
        {"problema": diagnostico, "review": RunnablePassthrough()}
        | RunnableLambda(lambda d: {"problema": d["problema"], "review": d["review"]["review"]})
        | ChatPromptTemplate.from_template(
            "Problema identificado: {problema}\n\n"
            "Escreva uma resposta empática de suporte para este cliente:\n{review}"
        )
        | llm
        | StrOutputParser()
    )
    print(chain.invoke({"review": RUIM}))


def ex6():
    """LIÇÃO: schema validado em vez de parsing de texto livre.
    É o que transforma chatbot em ferramenta de pipeline.
    Este vira um objeto Python que você grava no banco direto."""
    class Ticket(BaseModel):
        sentimento: Literal["positivo", "negativo", "neutro"]
        categoria: Literal["defeito", "entrega", "atendimento", "duvida", "elogio"]
        urgencia: int = Field(ge=1, le=5, description="1=baixa, 5=crítica")
        quer_reembolso: bool
        resumo: str = Field(description="máximo 10 palavras")

    chain = (
        ChatPromptTemplate.from_template("Classifique este ticket:\n{review}")
        | llm.with_structured_output(Ticket)
    )
    t = chain.invoke({"review": RUIM})
    print(t)
    print(f"→ {t.categoria} | urgência {t.urgencia} | reembolso: {t.quer_reembolso}")


def ex7():
    """LIÇÃO: if/else declarativo dentro da chain.
    Degrau ANTES do LangGraph — branch é DAG, LangGraph tem ciclo e estado."""
    reclamacao = ChatPromptTemplate.from_template(
        "Você é do time de retenção. Responda com pedido de desculpas e solução:\n{review}"
    ) | llm | StrOutputParser()

    elogio = ChatPromptTemplate.from_template(
        "Agradeça e convide a avaliar na loja:\n{review}"
    ) | llm | StrOutputParser()

    duvida = ChatPromptTemplate.from_template(
        "Responda a dúvida técnica de forma objetiva:\n{review}"
    ) | llm | StrOutputParser()

    router = RunnableBranch(
        (lambda x: x["tipo"] == "reclamacao", reclamacao),
        (lambda x: x["tipo"] == "elogio", elogio),
        duvida,     # default — obrigatório
    )

    print(router.invoke({"tipo": "reclamacao", "review": RUIM}))


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[ok] {MODEL} | rate limit: {rate_limiter.requests_per_second} req/s\n")

    ex6()
    # ex2()
    # ex3()
    # ex4()
    # ex5()
    # ex6()
    # ex7()