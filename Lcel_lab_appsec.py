"""
LCEL LAB — v3 (com rate limiter, sem pendurar)
==============================================
Rode UM exercício por vez. Descomente só o que quer no final.

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

MODEL = "gemini-3.5-flash"     # sem thinking = mais rápido que o 3.5

# ── O FIX ────────────────────────────────────────────────────
# Segura as chamadas ANTES de sair. Token bucket.
# 0.2 req/s = 1 chamada a cada 5 segundos.
# Se ainda estourar, baixa pra 0.1 (1 a cada 10s).
rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.2,
    check_every_n_seconds=0.1,
    max_bucket_size=1,
)

llm = ChatGoogleGenerativeAI(
    model=MODEL,
    temperature=0,
    max_retries=1,             # 429 na cara em 2s, não silêncio de 5min
    timeout=60,
    rate_limiter=rate_limiter,
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

VULN = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)
"""

SAFE = """
def get_user(user_id):
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
"""


# ─────────────────────────────────────────────────────────────
def ex1():
    """1 chamada só (antes eu fazia 3 — desperdício meu).
    LIÇÃO: llm devolve AIMessage, não str. O parser só extrai .content.
    E repara: o parser invocado FORA do pipe. Ele é só mais um Runnable."""
    prompt = ChatPromptTemplate.from_template(
        "Em uma frase: que vulnerabilidade tem este código?\n{code}"
    )
    msg = (prompt | llm).invoke({"code": VULN})
    print("SEM parser →", type(msg))
    print("COM parser →", type(StrOutputParser().invoke(msg)))
    print(StrOutputParser().invoke(msg))


def ex2():
    """LIÇÃO: batch e stream de graça. Você não escreveu paralelismo."""
    chain = (
        ChatPromptTemplate.from_template(
            "Classifique em 1 palavra — VULNERÁVEL ou SEGURO:\n{code}"
        )
        | llm
        | StrOutputParser()
    )
    print(chain.batch([{"code": VULN}, {"code": SAFE}]))

    for pedaco in chain.stream({"code": VULN}):
        print(pedaco, end="", flush=True)
    print()


def ex3():
    """LIÇÃO: qualquer função vira Runnable. Pré-processa antes do modelo ver."""
    def mascarar(payload: dict) -> dict:
        import re
        limpo = re.sub(r'(api_key|password)\s*=\s*["\'][^"\']+["\']',
                       r'\1="[REDACTED]"', payload["code"])
        return {"code": limpo}

    chain = (
        RunnableLambda(mascarar)
        | ChatPromptTemplate.from_template("Analise:\n{code}")
        | llm
        | StrOutputParser()
    )
    print(chain.invoke({"code": 'api_key = "sk-secret-123"\n' + VULN}))


def ex4():
    """LIÇÃO: dict no pipe vira RunnableParallel. Ramos concorrentes."""
    cwe = ChatPromptTemplate.from_template("Só o CWE ID:\n{code}") | llm | StrOutputParser()
    fix = ChatPromptTemplate.from_template("Só o código corrigido:\n{code}") | llm | StrOutputParser()

    r = RunnableParallel(cwe=cwe, correcao=fix).invoke({"code": VULN})
    print(r["cwe"])
    print(r["correcao"])


def ex5():
    """LIÇÃO: passo 2 precisa do resultado do passo 1 E do input original."""
    achar = ChatPromptTemplate.from_template("Nomeie a vuln em 3 palavras:\n{code}") | llm | StrOutputParser()

    chain = (
        {"vuln": achar, "code": RunnablePassthrough()}
        | RunnableLambda(lambda d: {"vuln": d["vuln"], "code": d["code"]["code"]})
        | ChatPromptTemplate.from_template(
            "A vuln é: {vuln}\nEscreva o teste unitário que a prova, para:\n{code}"
        )
        | llm
        | StrOutputParser()
    )
    print(chain.invoke({"code": VULN}))


def ex6():
    """LIÇÃO: schema validado em vez de parsing de texto livre.
    É o que transforma chatbot em ferramenta de pipeline."""
    class Finding(BaseModel):
        cwe: str = Field(description="ID do CWE, ex: CWE-89")
        severidade: Literal["baixa", "media", "alta", "critica"]
        linha: int
        exploravel: bool
        fix_sugerido: str

    chain = (
        ChatPromptTemplate.from_template("Você é um revisor AppSec. Analise:\n{code}")
        | llm.with_structured_output(Finding)
    )
    r = chain.invoke({"code": VULN})
    print(r)
    print(r.cwe, "|", r.severidade, "| explorável:", r.exploravel)


def ex7():
    """LIÇÃO: if/else declarativo. Degrau antes do LangGraph —
    branch é DAG, LangGraph tem ciclo e estado."""
    py = ChatPromptTemplate.from_template("Revisor Python, foco injection:\n{code}") | llm | StrOutputParser()
    js = ChatPromptTemplate.from_template("Revisor JS, foco XSS:\n{code}") | llm | StrOutputParser()
    generico = ChatPromptTemplate.from_template("Revisor genérico:\n{code}") | llm | StrOutputParser()

    router = RunnableBranch(
        (lambda x: x["lang"] == "python", py),
        (lambda x: x["lang"] == "js", js),
        generico,
    )
    print(router.invoke({"lang": "python", "code": VULN}))


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[ok] {MODEL} | rate limit: {rate_limiter.requests_per_second} req/s\n")

    ex1()
    # ex2()
    # ex3()
    # ex4()
    # ex5()
    # ex6()
    # ex7()