# ─────────────────────────────────────────────────────────────────────────────
# PyCrackLab — Multi-stage Dockerfile
#
# Stage 1 (builder): instala todas as dependências de build (gcc, libffi, etc.)
#                    compila pacotes nativos (bcrypt precisa de C)
# Stage 2 (runtime): copia apenas o resultado do build + código fonte
#                    imagem final menor, sem ferramentas de compilação
#
# Por que multi-stage?
#   - builder: ~450MB (com gcc, headers, etc.)
#   - runtime: ~130MB (só o necessário para rodar)
#   - Reduz superfície de ataque e tempo de pull em produção
#
# Build:  docker build -t pycracklab .
# Run:    docker run -it pycracklab benchmark --password test123
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Dependências de sistema necessárias para compilar bcrypt e cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências em diretório isolado
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL description="PyCrackLab — Educational Password Cracking Tool"
LABEL purpose="Educational use only"

WORKDIR /app

# Copia apenas os pacotes instalados do builder (sem gcc, headers, etc.)
COPY --from=builder /install /usr/local

# Copia código fonte
COPY . .

# Cria diretório para wordlists (montar via -v para usar wordlists externas)
RUN mkdir -p wordlists

# Usuário não-root para boa prática de segurança
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

# ─────────────────────────────────────────────────────────────────────────────
# Exemplos de uso:
#
# Benchmark:
#   docker run -it pycracklab benchmark --password "test123"
#
# Brute force:
#   docker run -it pycracklab brute --target abc --charset lowercase --max-len 3
#
# Brute force com multiprocessing:
#   docker run -it pycracklab brute --target abc --mode process --workers 4 --max-len 4
#
# Wordlist (Linux/macOS):
#   docker run -it -v /path/to/wordlists:/app/wordlists pycracklab \
#     wordlist --hash <hash> --wordlist wordlists/rockyou.txt
#
# Wordlist (Windows PowerShell):
#   docker run -it -v ${PWD}/wordlists:/app/wordlists pycracklab `
#     wordlist --hash <hash> --wordlist wordlists/rockyou.txt
#
# Wordlist com multiprocessing:
#   docker run -it -v ${PWD}/wordlists:/app/wordlists pycracklab `
#     wordlist --hash <hash> --wordlist wordlists/rockyou.txt --workers 4
# ─────────────────────────────────────────────────────────────────────────────
