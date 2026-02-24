# 🔐 PyCrackLab

> **Educational Password Cracking Tool** — Desenvolvido exclusivamente para fins acadêmicos e de aprendizado em Cybersecurity.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
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
| Ataques de dicionário eficientes (lazy I/O) | `cracker/wordlist.py` |
| Diferença entre MD5, SHA1 e bcrypt | `utils/benchmark.py` + `cracker/hash_cracker.py` |
| Por que bcrypt é propositalmente lento | `utils/benchmark.py` (seção educacional) |
| Detecção automática de tipo de hash | `utils/hashing.py` |
| CLI profissional com argparse + rich | `main.py` |
| Código modular com type hints | Todos os módulos |

---

## 🏗️ Estrutura do Projeto

```
pycracklab/
├── main.py                  # Entry point + CLI (argparse)
├── cracker/
│   ├── brute.py             # Brute force com multithreading
│   ├── wordlist.py          # Ataque por wordlist (lazy I/O)
│   └── hash_cracker.py      # Hash cracker com detecção automática
├── utils/
│   ├── hashing.py           # Funções de hash + detecção de tipo
│   └── benchmark.py         # Benchmark MD5 vs SHA1 vs bcrypt
├── wordlists/
│   └── common.txt           # Wordlist pequena para testes
├── tests/
│   └── test_pycracklab.py   # Suite completa (pytest)
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

---

## 🚀 Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/pycracklab.git
cd pycracklab

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Instale dependências
pip install -r requirements.txt
```

### Via Docker

Build da imagem (no diretório do projeto):
```bash
docker build -t pycracklab .
```

---

## 💻 Exemplos de Uso

### 1. Brute Force

```bash
# Charset padrão (lowercase), comprimento 1-4
python main.py brute --target abc --charset lowercase --min-len 1 --max-len 4

# Charset personalizado com multithreading
python main.py brute --target "a1" --custom-charset "abc123" --max-len 2 --threads 4

# Com charset completo (pode ser lento para senhas longas!)
python main.py brute --target "test" --charset all --max-len 4
```

### 2. Wordlist Attack

```bash
# Gere um hash de exemplo primeiro:
python -c "from utils.hashing import hash_md5; print(hash_md5('password'))"
# → 5f4dcc3b5aa765d61d8327deb882cf99

# Ataque com detecção automática
python main.py wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/common.txt

# SHA1 explícito
python main.py wordlist \
  --hash "5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8" \
  --wordlist wordlists/common.txt \
  --hash-type sha1
```

### 3. Hash Cracking (Detecção Automática)

```bash
# O comando 'hash' detecta automaticamente e explica o algoritmo
python main.py hash \
  --hash 5f4dcc3b5aa765d61d8327deb882cf99 \
  --wordlist wordlists/common.txt

# bcrypt (muito mais lento — demonstração educacional)
python -c "
from utils.hashing import generate_hash
print(generate_hash('test', 'bcrypt'))
"
# Copie o hash gerado e use:
python main.py hash --hash '$2b$12$...' --wordlist wordlists/common.txt
```

### 4. Benchmark Comparativo

```bash
# Compara MD5 vs SHA1 vs bcrypt (extremamente didático!)
python main.py benchmark --password "test123"

# Com mais iterações para resultado mais preciso
python main.py benchmark --password "test123" --iterations 500000
```

### 5. Com Logging

```bash
python main.py --log brute --target hello --charset lowercase --max-len 5
# Gera: pycracklab.log

python main.py --log --log-file meu_log.log benchmark
```

---

## 🧪 Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Com cobertura de código
pytest tests/ -v --cov=. --cov-report=html

# Testes específicos
pytest tests/ -v -k "test_md5"
pytest tests/ -v -k "TestBruteForce"
```

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

Atacante com GPU testando MD5:  10.000.000.000 tentativas/segundo
Atacante com GPU testando bcrypt:        100 tentativas/segundo

Diferença: 100.000.000x mais lento = senha de 8 chars: horas → SÉCULOS
```

### Limitações do Brute Force

O brute force cresce **exponencialmente**:

| Charset | Comprimento | Combinações | Tempo (1M hash/s) |
|---|---|---|---|
| lowercase (26) | 6 chars | 309 milhões | ~5 minutos |
| lowercase (26) | 8 chars | 208 bilhões | ~2,4 dias |
| all (94) | 8 chars | 6 quadrilhões | ~190 anos |
| all (94) | 10 chars | 53 quintilhões | >1M anos |

**Conclusão:** Senhas de 12+ caracteres com charset completo são **imunes** ao brute force, mesmo com hardware moderno.

---

## 🏆 Decisões Técnicas

### 1. Lazy I/O para Wordlists
```python
# ✅ Correto: O(1) memória independente do tamanho do arquivo
def wordlist_generator(path):
    with open(path) as f:
        for line in f:
            yield line.strip()

# ❌ Errado: Carrega 130MB inteiros na RAM
words = open(path).readlines()
```

### 2. bcrypt.checkpw vs comparação direta
```python
# ✅ Correto: timing-safe, extrai salt do hash automaticamente
bcrypt.checkpw(candidate.encode(), stored_hash.encode())

# ❌ Errado: Ignora o salt armazenado no hash bcrypt
hashlib.md5(candidate.encode()).hexdigest() == stored_hash  # só para MD5/SHA1
```

### 3. Modularidade
Cada módulo tem uma única responsabilidade (SRP):
- `hashing.py` → apenas funções de hash
- `brute.py` → apenas lógica de brute force
- `wordlist.py` → apenas lógica de wordlist
- `benchmark.py` → apenas medição de performance

---

## 📋 Recomendações de Segurança

Para armazenamento seguro de senhas em produção, use:

1. **Argon2id** (vencedor da PHC, melhor opção atual)
2. **bcrypt** (cost ≥ 12, amplamente suportado)
3. **scrypt** (alternativa memory-hard)

**Nunca use:** MD5, SHA1, SHA256 sem KDF para senhas.

---

## 📄 Licença

MIT License — veja [LICENSE](LICENSE).

**Lembre-se:** Com grande conhecimento vem grande responsabilidade. Use de forma ética.
