"""
CARMEN SANDIEGO — LCEL edition
==============================
    python .\carmen.py

O que é do Python: estado, rota, turnos, validação.
O que é do LLM:    escrever pistas a partir de fatos reais.
"""

import os, random, textwrap
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.rate_limiters import InMemoryRateLimiter
from pydantic import BaseModel, Field
from typing import Literal, List

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    temperature=0.8,                    # criatividade aqui é feature
    max_retries=1,
    timeout=60,
    rate_limiter=InMemoryRateLimiter(requests_per_second=0.3, max_bucket_size=1),
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

# ── Os fatos. Isto é GROUNDING: o modelo não inventa, ele veste. ──
CIDADES = {
    "Cairo":     "pirâmides de Gizé, rio Nilo, mercado Khan el-Khalili, árabe, libra egípcia",
    "Tóquio":    "cruzamento de Shibuya, monte Fuji ao longe, iene, sushi, trens-bala",
    "Lima":      "ceviche, ruínas incas próximas, oceano Pacífico, sol peruano, batata",
    "Reykjavik": "gêiseres, aurora boreal, coroa islandesa, vulcões, quase sem árvores",
    "Marrakech": "souks, medina vermelha, chá de menta, dirham, deserto do Saara ao sul",
    "Sydney":    "opera house, praia de Bondi, dólar australiano, cangurus, hemisfério sul",
}

LADROES = [
    {"nome": "Vic the Slick", "cabelo": "ruivo", "hobby": "ópera", "veiculo": "moto"},
    {"nome": "Ima Gumshoe",   "cabelo": "loiro", "hobby": "xadrez", "veiculo": "limusine"},
    {"nome": "Eartha Brute",  "cabelo": "preto", "hobby": "boxe",   "veiculo": "helicóptero"},
]


# ── O schema. Uma chamada devolve as 3 testemunhas de uma vez. ──
class Pista(BaseModel):
    testemunha: str = Field(description="profissão da testemunha, ex: taxista")
    fala: str = Field(description="1-2 frases, oblíquas, sem citar o nome da cidade")

class Rodada(BaseModel):
    pistas: List[Pista] = Field(description="exatamente 3 pistas")


prompt = ChatPromptTemplate.from_template(
    "Você escreve pistas para um jogo estilo Carmen Sandiego.\n"
    "A ladra fugiu de {origem} para o próximo destino.\n\n"
    "FATOS DO DESTINO: {fatos}\n"
    "SUSPEITA: cabelo {cabelo}, gosta de {hobby}, usa {veiculo}\n\n"
    "Escreva 3 testemunhas em {origem} que viram a ladra partir.\n"
    "Cada uma dá UMA pista oblíqua sobre o destino, usando os FATOS acima.\n"
    "NUNCA diga o nome da cidade. Insinue. Uma delas menciona a aparência dela.\n"
    "Tom: noir, curto, com humor."
)

chain = prompt | llm.with_structured_output(Rodada)


def jogar():
    # ── PYTHON decide tudo que é estado. O LLM nunca vê isto. ──
    ladrao = random.choice(LADROES)
    rota = random.sample(list(CIDADES), 4)
    turno, pos, restantes = 0, 0, 8

    print("=" * 60)
    print("  ACME DETECTIVE AGENCY")
    print(f"  Suspeita em fuga. Você tem {restantes} horas.")
    print("=" * 60)

    while pos < len(rota) - 1:
        atual, destino = rota[pos], rota[pos + 1]

        print(f"\n📍 Você está em {atual}  |  ⏰ {restantes}h restantes")
        print("   Ouvindo testemunhas...\n")

        r = chain.invoke({
            "origem": atual,
            "fatos": CIDADES[destino],
            "cabelo": ladrao["cabelo"],
            "hobby": ladrao["hobby"],
            "veiculo": ladrao["veiculo"],
        })

        for p in r.pistas:
            print(f"   🗣️  {p.testemunha.upper()}")
            print(textwrap.fill(p.fala, 56, initial_indent="      ",
                                subsequent_indent="      "))
            print()

        # Opções: o destino certo + 2 errados. Python, não LLM.
        erradas = [c for c in CIDADES if c not in (atual, destino)]
        opcoes = random.sample(erradas, 2) + [destino]
        random.shuffle(opcoes)

        print("   Para onde você voa?")
        for i, c in enumerate(opcoes, 1):
            print(f"     {i}. {c}")

        try:
            escolha = opcoes[int(input("\n   > ")) - 1]
        except (ValueError, IndexError):
            print("   Escolha inválida. Perdeu 1h.")
            restantes -= 1
            continue

        restantes -= 2
        if escolha == destino:
            print(f"\n   ✅ Pista quente! A ladra esteve em {destino}.")
            pos += 1
        else:
            print(f"\n   ❌ Beco sem saída em {escolha}. Rastro esfriou.")

        if restantes <= 0:
            print(f"\n💀 Tempo esgotado. {ladrao['nome']} escapou.")
            return

    # ── O mandado: acertar a cidade não basta. ──
    print(f"\n🎯 Você encurralou a suspeita em {rota[-1]}!")
    print("   Emita o mandado — quem é ela?\n")
    for i, l in enumerate(LADROES, 1):
        print(f"     {i}. {l['nome']} — cabelo {l['cabelo']}, {l['hobby']}, {l['veiculo']}")

    try:
        if LADROES[int(input("\n   > ")) - 1]["nome"] == ladrao["nome"]:
            print(f"\n🏆 PRISÃO EFETUADA. {ladrao['nome']} está detida.")
        else:
            print(f"\n😤 Mandado errado. {ladrao['nome']} fugiu por tecnicalidade.")
    except (ValueError, IndexError):
        print("\n😤 Mandado inválido. Ela fugiu.")


if __name__ == "__main__":
    jogar()