# 🔐 PyCrackLab

> **Educational Password Cracking Tool** — Desenvolvido exclusivamente para fins acadêmicos e de aprendizado em Cybersecurity.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/amchdd/pycracklab/actions/workflows/ci.yml/badge.svg)](https://github.com/amchdd/pycracklab/actions/workflows/ci.yml)
[![Educational](https://img.shields.io/badge/purpose-educational%20only-red.svg)]()

---

## ⚠️ Aviso Ético / Ethical Warning

**PT-BR:** Esta ferramenta foi criada **exclusivamente para fins educacionais**. Use apenas em sistemas, hashes e senhas que você **criou ou tem autorização explícita** para testar. O uso não autorizado contra sistemas de terceiros é **ilegal** e pode resultar em sanções criminais.

**EN:** This tool is for **educational purposes only**. Only use it on systems, hashes, and passwords you **own or have explicit permission** to test. Unauthorized use is **illegal**.

---

## 📚 O que você aprende com este projeto

| Conceito | Onde está implementado |
|---|---|
| Brute force e complexidade exponencial | `cracker/brute.py` |
| Multiprocessing para contornar o GIL | `cracker/brute.py` → `brute_multiprocess()` |
| Wordlist com chunking + Pool paralelo | `cracker/wordlist.py` → `wordlist_multiprocess()` |
| Diferença entre MD5, SHA1 e bcrypt | `utils/benchmark.py` + `cracker/hash_cracker.py` |
| Por que bcrypt é propositalmente lento | `utils/benchmark.py` (seção educacional) |
| Detecção automática de tipo de hash | `utils/hashing.py` |
| CLI profissional com argparse + rich | `main.py` |
| Docker multi-stage para imagem enxuta | `Dockerfile` |
| CI/CD com GitHub Actions | `.github/workflows/ci.yml` |

---

## 🏗️ Estrutura do Projeto

```
pycracklab/
├── main.py                     # Entry point + CLI (argparse)
├── cracker/
│   ├── brute.py                # Brute force: single / thread / multiprocessing
│   ├── wordlist.py             # Wordlist: lazy I/O + chunking com Pool
│   └── hash_cracker.py        # Hash cracker com detecção automática
├── utils/
│   ├── hashing.py              # Funções de hash + detecção de tipo
│   └── benchmark.py            # Benchmark MD5 vs SHA1 vs bcrypt
├── wordlists/
│   └── common.txt              # Wordlist pequena para testes
├── tests/
│   └── test_pycracklab.py      # Suite completa (pytest)
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: pytest + lint
├── requirements.txt            # Dependências pinadas
├── Dockerfile                  # Multi-stage build
├── .dockerignore
├── .gitignore
└── README.md
```

---

## 🚀 Instalação

```bash
# Clone o repositório
git clone https://github.com/amchdd/pycracklab.git
cd pycracklab

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# Instale dependências (versões pinadas para reprodutibilidade)
pip install -r requirements.txt
```

---

## 🐳 Docker (Multi-stage Build)

O Dockerfile usa **dois stages**:
- `builder`: compila dependências nativas (bcrypt precisa de gcc/libffi)
- `runtime`: copia apenas os pacotes compilados — imagem final ~130MB

```bash
# Build da imagem
docker build -t pycracklab .

# Benchmark
docker run -it pycracklab benchmark --password "test123"

# Brute force simples
docker run -it pycracklab brute --target abc --charset lowercase --max-len 3

# Brute force com multiprocessing
docker run -it pycracklab brute --target abc --mode process --workers 4 --max-len 4

# Wordlist — montando volume com wordlists externas
# Linux/macOS:
docker run -it -v $(pwd)/wordlists:/app/wordlists pycracklab \
  wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/rockyou.txt

# Windows (PowerShell):
docker run -it -v ${PWD}/wordlists:/app/wordlists pycracklab `
  wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/rockyou.txt

# Wordlist com multiprocessing dentro do container
docker run -it -v ${PWD}/wordlists:/app/wordlists pycracklab `
  wordlist --hash <hash> --wordlist wordlists/rockyou.txt --workers 4
```

> **Nota Windows:** use `${PWD}` no PowerShell ou `%cd%` no CMD para o caminho absoluto do diretório atual.

---

## 💻 Exemplos de Uso

### 1. Brute Force

```bash
# Single-thread (default)
python main.py brute --target abc --charset lowercase --max-len 4

# Multi-thread (limitado pelo GIL — didático)
python main.py brute --target abc --charset lowercase --max-len 4 --mode thread --workers 4

# Multiprocessing real (contorna o GIL — melhor para CPU-bound)
python main.py brute --target abc --charset lowercase --max-len 5 --mode process --workers 4

# Charset personalizado
python main.py brute --target "a1" --custom-charset "abc123" --max-len 2 --mode process
```

### 2. Wordlist Attack

```bash
# Gere um hash de exemplo primeiro:
python -c "from utils.hashing import hash_md5; print(hash_md5('password'))"
# → 5f4dcc3b5aa765d61d8327deb882cf99

# Single-thread com detecção automática
python main.py wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/common.txt

# Multiprocessing com 4 workers e chunks de 1000 palavras
python main.py wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 \
  --wordlist wordlists/common.txt --workers 4 --chunk-size 1000

# SHA1 explícito
python main.py wordlist \
  --hash "5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8" \
  --wordlist wordlists/common.txt --hash-type sha1
```

### 3. Hash Cracking (Detecção Automática)

```bash
python main.py hash --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/common.txt

# Gerar hash bcrypt para testar:
python -c "from utils.hashing import generate_hash; print(generate_hash('test', 'bcrypt'))"
python main.py hash --hash '$2b$12$...' --wordlist wordlists/common.txt
```

### 4. Benchmark Comparativo

```bash
python main.py benchmark --password "test123"
python main.py benchmark --password "test123" --iterations 500000
```

### 5. Com Logging

```bash
python main.py --log brute --target hello --charset lowercase --max-len 5
python main.py --log --log-file debug.log wordlist --hash <hash> --wordlist wordlists/common.txt
```

---

## 🧪 Testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura de código
pytest tests/ -v --cov=cracker --cov=utils --cov-report=html
# Relatório HTML em: htmlcov/index.html

# Testes específicos
pytest tests/ -v -k "test_md5"
pytest tests/ -v -k "TestBruteForce"
```

---

## ⚡ Profiling e Benchmark de Performance

### cProfile — onde meu código passa o tempo?

```bash
# Perfila o benchmark completo
python -m cProfile -s cumulative main.py benchmark --password "test123" 2>&1 | head -30

# Perfila o brute force e salva para análise
python -m cProfile -o brute_profile.prof main.py brute --target abcd --max-len 4
python -c "import pstats; p = pstats.Stats('brute_profile.prof'); p.sort_stats('cumulative'); p.print_stats(15)"
```

### pytest-benchmark — microbenchmarks automáticos

```bash
# Instalar (já incluso no requirements.txt)
# pip install pytest-benchmark

# Rodar apenas benchmarks
pytest tests/ --benchmark-only -v

# Comparar runs (salva baseline)
pytest tests/ --benchmark-save=baseline
pytest tests/ --benchmark-compare=baseline
```

> **Dica didática:** use `cProfile` para encontrar gargalos reais antes de paralelizar.
> Paralelismo sem profiling prévia é otimização prematura.

---

## 🔀 Threading vs Multiprocessing — Quando usar cada um?

| Situação | Recomendado | Por quê |
|---|---|---|
| Brute force curto (max-len ≤ 4) | `--mode single` | Overhead de processo > ganho |
| Brute force longo (max-len ≥ 5) | `--mode process` | Paralelismo real, sem GIL |
| Wordlist pequena (< 10k palavras) | `--workers 1` | Overhead de spawn > ganho |
| Wordlist grande (> 100k palavras) | `--workers 4+` | Ganho real com Pool |
| Hash bcrypt (qualquer caso) | Workers baixos | Já é memory-hard por design |

---

## 📊 MD5 vs SHA1 vs bcrypt — Análise Educacional

| Algoritmo | Velocidade (CPU) | Velocidade (GPU) | Para senhas? |
|---|---|---|---|
| **MD5** | ~500M/s | ~10B/s | ❌ Não use |
| **SHA1** | ~300M/s | ~3B/s | ❌ Não use |
| **bcrypt (cost=12)** | ~15-50/s | ~100/s* | ✅ Recomendado |

*bcrypt é memory-hard, dificultando GPU/ASIC.

### Por que bcrypt é lento?

```
bcrypt(cost=12) = 2^12 = 4.096 rounds de derivação
                + salt aleatório embutido (sem rainbow tables)
                + memory-hard (resiste a GPU/ASIC)

Atacante com GPU testando MD5:    10.000.000.000 tentativas/segundo
Atacante com GPU testando bcrypt:            100 tentativas/segundo

Diferença: 100.000.000x mais lento = senha de 8 chars: horas → SÉCULOS
```

### Limitações do Brute Force

| Charset | Comprimento | Combinações | Tempo (1M hash/s) |
|---|---|---|---|
| lowercase (26) | 6 chars | 309 milhões | ~5 minutos |
| lowercase (26) | 8 chars | 208 bilhões | ~2,4 dias |
| all (94) | 8 chars | 6 quadrilhões | ~190 anos |
| all (94) | 10 chars | 53 quintilhões | >1M anos |

---

## 🏆 Decisões Técnicas

### 1. Multiprocessing por prefixos (não por chunks de iterador)
O `itertools.product` não é serializável pelo pickle — não pode ser enviado entre processos. A solução foi dividir o espaço de busca por **prefixos**: cada processo recebe um caractere inicial diferente e busca todas as combinações com aquele prefixo, eliminando comunicação contínua.

### 2. `imap_unordered` para early termination na wordlist
`Pool.imap_unordered` retorna resultados na ordem que ficam prontos (não na ordem de envio). Isso permite detectar o match assim que qualquer worker termina, sem esperar os demais.

### 3. Lazy I/O + chunking
```python
# O(1) memória: lê linha a linha
def wordlist_generator(path): ...

# Agrupa em lotes para enviar ao Pool
def _chunk_generator(gen, chunk_size): ...
```

### 4. bcrypt.checkpw vs comparação direta
```python
# ✅ Correto: timing-safe, extrai salt automaticamente
bcrypt.checkpw(candidate.encode(), stored_hash.encode())

# ❌ Errado para bcrypt: ignora o salt embutido no hash
hashlib.md5(candidate.encode()).hexdigest() == stored_hash
```

---

## 📋 Recomendações de Segurança

Para armazenamento seguro de senhas em produção:

1. **Argon2id** — vencedor da PHC, melhor opção atual
2. **bcrypt** — cost ≥ 12, amplamente suportado
3. **scrypt** — alternativa memory-hard

**Nunca use:** MD5, SHA1 ou SHA256 puro para senhas.

---

## 📄 Licença

MIT License — veja [LICENSE](LICENSE).

**Lembre-se:** Com grande conhecimento vem grande responsabilidade. Use de forma ética.
