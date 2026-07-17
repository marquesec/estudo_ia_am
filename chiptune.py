"""
chiptune.py — som 8-bit sem dependência nenhuma
==============================================
Só Windows (usa winsound). Stdlib pura: wave + io + random + threading.
Em Linux/Mac vira no-op silencioso em vez de quebrar.

    python .\chiptune.py     # testa os 6 sons
"""

import io, random, threading, wave

try:
    import winsound
    _HAS_SOUND = True
except ImportError:
    _HAS_SOUND = False

RATE = 22050


def _wav(samples):
    """Empacota amostras 8-bit unsigned (0-255) num WAV na memória."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)          # 1 byte = 8 bits. Literalmente 8-bit.
        w.setframerate(RATE)
        w.writeframes(bytes(samples))
    return buf.getvalue()


def _play(samples):
    """SND_MEMORY nao aceita SND_ASYNC — o winsound proibe a combinacao.
    Entao o PlaySound bloqueia dentro da thread, e o jogo segue aqui fora."""
    if not _HAS_SOUND:
        return
    data = _wav(samples)
    threading.Thread(
        target=lambda: winsound.PlaySound(data, winsound.SND_MEMORY),
        daemon=True,
    ).start()


def _clamp(v):
    return max(0, min(255, int(v)))


def square(freq, ms, vol=0.35, duty=0.5, decay=True):
    """Onda quadrada. O som do canal de pulso do NES.
    duty=0.5 -> quadrado classico. duty=0.25 -> nasal, fino."""
    n = int(RATE * ms / 1000)
    period = RATE / freq if freq else 1
    out = []
    for i in range(n):
        v = 1 if (i % period) < period * duty else -1
        env = (1 - i / n) if decay else 1
        out.append(_clamp(128 + v * vol * 127 * env))
    return out


def noise(ms, vol=0.3, curve=2):
    """Ruido branco com envelope. Passo, tiro e explosao sao todos isto —
    a diferenca esta so no envelope. curve alto = decay rapido."""
    n = int(RATE * ms / 1000)
    return [_clamp(128 + random.uniform(-1, 1) * vol * 127 * (1 - i / n) ** curve)
            for i in range(n)]


def sweep(f1, f2, ms, vol=0.3):
    """Varredura de frequencia. Decolagem, queda, laser."""
    n = int(RATE * ms / 1000)
    out, phase = [], 0.0
    for i in range(n):
        f = f1 + (f2 - f1) * (i / n)
        phase += f / RATE
        v = 1 if (phase % 1) < 0.5 else -1
        out.append(_clamp(128 + v * vol * 127))
    return out


def silence(ms):
    return [128] * int(RATE * ms / 1000)


# ── Os sons do jogo ──────────────────────────────────────────

def passos():
    """Quatro passos. Toca durante o invoke() — preenche a espera da API."""
    s = []
    for _ in range(4):
        s += noise(45, vol=0.22) + silence(115)
    _play(s)


def voo():
    """Decolagem: sobe e some."""
    _play(sweep(180, 900, 500, vol=0.22) + square(900, 120, vol=0.15))


def acerto():
    """Arpejo ascendente. Do-Mi-Sol-Do."""
    s = []
    for f in (523, 659, 784, 1047):
        s += square(f, 70, vol=0.3, decay=False)
    _play(s + square(1047, 140, vol=0.3))


def erro():
    """Buzz descendente, duty estreito = som nasal de erro."""
    _play(square(180, 130, vol=0.3, duty=0.25, decay=False)
          + square(120, 260, vol=0.3, duty=0.25))


def prisao():
    """Fanfarra de vitoria."""
    s = []
    for f, d in ((523, 90), (523, 90), (523, 90), (659, 260),
                 (587, 90), (659, 90), (784, 400)):
        s += square(f, d, vol=0.3, decay=False) + silence(18)
    _play(s)


def fuga():
    """Ela escapou. Descida triste."""
    s = []
    for f in (494, 466, 440, 415):
        s += square(f, 180, vol=0.28, duty=0.25, decay=False)
    _play(s + sweep(415, 100, 600, vol=0.25))


if __name__ == "__main__":
    import time
    for nome, fn in [("passos", passos), ("voo", voo), ("acerto", acerto),
                     ("erro", erro), ("prisao", prisao), ("fuga", fuga)]:
        print(f"♪ {nome}")
        fn()
        time.sleep(1.8)