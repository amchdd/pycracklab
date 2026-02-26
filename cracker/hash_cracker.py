"""
cracker/hash_cracker.py
=======================
Hash cracker com detecção automática de tipo de hash.

Tipos suportados:
    - MD5:    32 chars hexadecimais
    - SHA1:   40 chars hexadecimais
    - SHA256: 64 chars hexadecimais (identificado mas não crackeado por wordlist aqui)
    - bcrypt: começa com $2a$, $2b$ ou $2y$

Decisão técnica:
    bcrypt usa um prefixo padronizado que torna a detecção trivial.
    MD5 e SHA1 são distinguíveis apenas por comprimento — por isso é
    importante validar entradas e tratar ambiguidades.
"""

import logging
import re
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from cracker.wordlist import WordlistAttack
from utils.hashing import detect_hash_type

logger = logging.getLogger("pycracklab.hash_cracker")
console = Console()


# ─────────────────────────────────────────────
# Validação de hashes
# ─────────────────────────────────────────────

_HASH_PATTERNS: dict[str, re.Pattern[str]] = {
    "argon2": re.compile(r"^\$argon2(id|i|d)\$v=\d+\$m=\d+,t=\d+,p=\d+\$.+\$.+$"),
    "md5":    re.compile(r"^[a-fA-F0-9]{32}$"),
    "sha1":   re.compile(r"^[a-fA-F0-9]{40}$"),
    "sha256": re.compile(r"^[a-fA-F0-9]{64}$"),
    "bcrypt": re.compile(r"^\$2[aby]\$\d{2}\$.{53}$"),
}


def validate_hash(hash_value: str) -> tuple[bool, str]:
    """
    Valida o hash e retorna (is_valid, hash_type).
    Retorna (False, "") se não reconhecido.
    """
    for hash_type, pattern in _HASH_PATTERNS.items():
        if pattern.match(hash_value):
            return True, hash_type
    return False, ""


# ─────────────────────────────────────────────
# HashCracker
# ─────────────────────────────────────────────

class HashCracker:
    """
    Hash cracker de alto nível com detecção automática.
    Delega a execução para WordlistAttack após identificar o tipo.
    """

    def __init__(self, hash_value: str, wordlist_path: str) -> None:
        self.hash_value = hash_value.strip()
        self.wordlist_path = wordlist_path

        if not self.hash_value:
            raise ValueError("Hash não pode ser vazio.")

        # Validação e detecção
        is_valid, detected_type = validate_hash(self.hash_value)
        if not is_valid:
            # Última tentativa com detect_hash_type
            detected_type = detect_hash_type(self.hash_value) or ""

        if not detected_type:
            raise ValueError(
                f"Hash inválido ou tipo não suportado: '{self.hash_value[:40]}'\n"
                "Formatos suportados: MD5 (32), SHA1 (40), bcrypt ($2b$...), Argon2 ($argon2id$...)"
            )

        self.hash_type = detected_type
        logger.info("HashCracker: detectado tipo '%s'", self.hash_type)

    def run(self) -> Optional[str]:
        """Executa o crack delegando ao WordlistAttack."""
        console.print(
            Panel(
                f"[bold cyan]🔓 Hash Cracker[/bold cyan]\n\n"
                f"  Hash: [dim]{self.hash_value[:60]}{'...' if len(self.hash_value) > 60 else ''}[/dim]\n"
                f"  Tipo detectado: [bold yellow]{self.hash_type.upper()}[/bold yellow]\n"
                f"  Wordlist: [green]{self.wordlist_path}[/green]",
                border_style="cyan",
                title="Configuração",
            )
        )
        console.print()

        # Exibe explicação do algoritmo detectado
        self._explain_algorithm()

        self._attack = WordlistAttack(
            hash_value=self.hash_value,
            wordlist_path=self.wordlist_path,
            hash_type=self.hash_type,
        )
        result = self._attack.run()
        return result

    def get_stats(self) -> dict:
        """Retorna estatísticas da última execução (delega ao WordlistAttack)."""
        attack = getattr(self, "_attack", None)
        if attack is None:
            return {}
        out = attack.get_stats()
        out["command"] = "hash"
        return out

    def _explain_algorithm(self) -> None:
        """Exibe contexto educacional sobre o algoritmo detectado."""
        explanations = {
            "md5": (
                "[yellow]MD5[/yellow] — 128 bits, projetado em 1991.\n"
                "Considerado [red]criptograficamente quebrado[/red] desde 2004.\n"
                "GPUs modernas computam ~10 [bold]bilhões[/bold] de MD5/segundo.\n"
                "Nunca use para armazenar senhas."
            ),
            "sha1": (
                "[yellow]SHA1[/yellow] — 160 bits, projetado em 1995.\n"
                "Colisões foram demonstradas em 2017 (SHAttered attack).\n"
                "GPUs modernas computam ~3 [bold]bilhões[/bold] de SHA1/segundo.\n"
                "Obsoleto para fins de segurança."
            ),
            "bcrypt": (
                "[green]bcrypt[/green] — Projetado [bold]especificamente[/bold] para senhas (1999).\n"
                "Fator de custo adaptável (ex: $12$ → 2^12 = 4096 iterações).\n"
                "~15-50 hashes/segundo em CPU (vs bilhões do MD5).\n"
                "Resistente a ataques de GPU por design (memory-hard)."
            ),
            "argon2": (
                "[green]Argon2[/green] — Vencedor do PHC (Password Hashing Competition).\n"
                "Variante Argon2id recomendada (híbrida: resiste a side-channel e GPU).\n"
                "Memory-hard e altamente configurável (memória, tempo, paralelismo).\n"
                "Recomendação atual para novos sistemas."
            ),
            "sha256": (
                "[yellow]SHA256[/yellow] — 256 bits, parte da família SHA-2.\n"
                "Criptograficamente seguro para integridade de dados,\n"
                "mas [red]não recomendado puro[/red] para senhas (sem salt/cost factor)."
            ),
        }
        msg = explanations.get(self.hash_type, "Algoritmo desconhecido.")
        console.print(Panel(msg, border_style="dim", title=f"ℹ  Sobre {self.hash_type.upper()}"))
        console.print()
