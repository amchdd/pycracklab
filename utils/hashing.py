"""
utils/hashing.py
================
Funções utilitárias de hashing e detecção de tipo.

Centralizar aqui evita duplicação entre módulos e facilita testes.
"""

import hashlib
import re
from typing import Optional


# ─────────────────────────────────────────────
# Funções de hash
# ─────────────────────────────────────────────

def hash_md5(text: str) -> str:
    """Retorna MD5 hexdigest de uma string UTF-8."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def hash_sha1(text: str) -> str:
    """Retorna SHA1 hexdigest de uma string UTF-8."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def hash_sha256(text: str) -> str:
    """Retorna SHA256 hexdigest de uma string UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_sha512(text: str) -> str:
    """Retorna SHA512 hexdigest de uma string UTF-8."""
    return hashlib.sha512(text.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────
# Detecção automática de tipo de hash
# ─────────────────────────────────────────────

_DETECTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    # Argon2 (PHC: $argon2id$v=19$m=...,t=...,p=...$salt$hash)
    ("argon2", re.compile(r"^\$argon2(id|i|d)\$v=\d+\$m=\d+,t=\d+,p=\d+\$.+\$.+$")),
    # bcrypt (prefixo distinto)
    ("bcrypt", re.compile(r"^\$2[aby]\$\d{2}\$.{53}$")),
    # Comprimento exato para os outros
    ("md5",    re.compile(r"^[a-fA-F0-9]{32}$")),
    ("sha1",   re.compile(r"^[a-fA-F0-9]{40}$")),
    ("sha256", re.compile(r"^[a-fA-F0-9]{64}$")),
    ("sha512", re.compile(r"^[a-fA-F0-9]{128}$")),
]


def detect_hash_type(hash_value: str) -> Optional[str]:
    """
    Tenta detectar o tipo de hash baseado em comprimento e padrão.
    Retorna o nome do algoritmo ou None se não reconhecido.
    """
    h = hash_value.strip()
    for name, pattern in _DETECTION_RULES:
        if pattern.match(h):
            return name
    return None


def generate_hash(text: str, algorithm: str) -> str:
    """
    Gera hash de texto para o algoritmo especificado.
    Útil para testes e para gerar hashes de exemplo.
    """
    algorithm = algorithm.lower()
    if algorithm == "md5":
        return hash_md5(text)
    elif algorithm == "sha1":
        return hash_sha1(text)
    elif algorithm == "sha256":
        return hash_sha256(text)
    elif algorithm == "sha512":
        return hash_sha512(text)
    elif algorithm == "bcrypt":
        import bcrypt as _bcrypt
        salt = _bcrypt.gensalt(rounds=12)
        return _bcrypt.hashpw(text.encode("utf-8"), salt).decode("utf-8")
    elif algorithm == "argon2":
        from argon2 import PasswordHasher
        ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)
        return ph.hash(text)
    else:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")
