# ──────────────────────────────────────────────────────────────
# PyCrackLab — Dockerfile
# Uso: docker build -t pycracklab . && docker run -it pycracklab
# ──────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Metadados
LABEL description="PyCrackLab — Educational Password Cracking Tool"
LABEL usage="Para fins educacionais apenas"

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Cria diretório de wordlists (usuário pode montar volume)
RUN mkdir -p wordlists

# Aviso de disclaimer no entrypoint
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

# ──────────────────────────────────────────────────────────────
# Exemplos de uso com Docker:
#
# Benchmark:
#   docker run -it pycracklab benchmark --password test123
#
# Brute force:
#   docker run -it pycracklab brute --target abc --charset lowercase --max-len 3
#
# Wordlist com volume:
#   docker run -it -v /path/to/wordlists:/app/wordlists pycracklab \
#     wordlist --hash <hash> --wordlist wordlists/rockyou.txt
# ──────────────────────────────────────────────────────────────
