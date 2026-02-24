"""
cracker/wordlist.py
===================
Ataque por dicionário/wordlist com suporte a grandes arquivos.

Decisão técnica:
    Usamos leitura linha a linha (não carregamos tudo na RAM) para
    suportar wordlists gigantes como rockyou.txt (130MB+).
    O generator pattern garante O(1) de memória independente do tamanho.

    Para detecção automática de tipo de hash, analisamos comprimento
    e prefixo do hash fornecido.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Generator, Optional

import bcrypt
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from utils.hashing import hash_md5, hash_sha1, detect_hash_type

logger = logging.getLogger("pycracklab.wordlist")
console = Console()


# ─────────────────────────────────────────────
# Gerador eficiente de wordlist
# ─────────────────────────────────────────────

def wordlist_generator(path: str) -> Generator[str, None, None]:
    """
    Lê wordlist linha a linha (lazy) para não estourar a memória.
    Ignora linhas vazias e remove espaços laterais.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Wordlist não encontrada: {path}")
    if not file_path.is_file():
        raise ValueError(f"Caminho não é um arquivo: {path}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            word = line.strip()
            if word:
                yield word


def count_lines(path: str) -> int:
    """Conta linhas do arquivo (para barra de progresso)."""
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


# ─────────────────────────────────────────────
# Funções de verificação
# ─────────────────────────────────────────────

def check_candidate(candidate: str, hash_value: str, hash_type: str) -> bool:
    """
    Verifica se o candidato gera o hash alvo.

    Para bcrypt: usa bcrypt.checkpw (timing-safe).
    Para MD5/SHA1: comparação direta de hexdigest.
    """
    try:
        if hash_type == "md5":
            return hash_md5(candidate) == hash_value.lower()
        elif hash_type == "sha1":
            return hash_sha1(candidate) == hash_value.lower()
        elif hash_type == "bcrypt":
            return bcrypt.checkpw(candidate.encode("utf-8"), hash_value.encode("utf-8"))
        else:
            logger.warning("Tipo de hash desconhecido: %s", hash_type)
            return False
    except Exception as exc:
        logger.debug("Erro ao verificar candidato '%s': %s", candidate, exc)
        return False


# ─────────────────────────────────────────────
# WordlistAttack
# ─────────────────────────────────────────────

class WordlistAttack:
    """
    Ataque de dicionário: testa cada palavra da wordlist contra o hash alvo.
    Suporta MD5, SHA1 e bcrypt com detecção automática.
    """

    def __init__(
        self,
        hash_value: str,
        wordlist_path: str,
        hash_type: str = "auto",
    ) -> None:
        self.hash_value = hash_value.strip()
        self.wordlist_path = wordlist_path
        self.hash_type = hash_type

        if not self.hash_value:
            raise ValueError("Hash não pode ser vazio.")

        # Detecção automática
        if self.hash_type == "auto":
            detected = detect_hash_type(self.hash_value)
            if not detected:
                raise ValueError(
                    f"Não foi possível detectar o tipo do hash: '{self.hash_value[:30]}...'\n"
                    "Use --hash-type para especificar manualmente."
                )
            self.hash_type = detected
            console.print(f"[bold cyan]🔍 Tipo de hash detectado: [yellow]{self.hash_type.upper()}[/yellow][/bold cyan]\n")

        logger.info("WordlistAttack criado: hash_type=%s, wordlist=%s", self.hash_type, wordlist_path)

    def _show_config(self, total_lines: int) -> None:
        table = Table(title="⚙  Configuração do Ataque por Wordlist", border_style="blue")
        table.add_column("Parâmetro", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row("Hash alvo", f"{self.hash_value[:40]}{'...' if len(self.hash_value) > 40 else ''}")
        table.add_row("Tipo de hash", self.hash_type.upper())
        table.add_row("Wordlist", self.wordlist_path)
        table.add_row("Entradas estimadas", f"{total_lines:,}")
        console.print(table)
        console.print()

    def run(self) -> Optional[str]:
        """Executa o ataque. Retorna a senha encontrada ou None."""
        total_lines = count_lines(self.wordlist_path)
        self._show_config(total_lines)

        found: Optional[str] = None
        count = 0
        start_time = time.perf_counter()
        last_report = start_time

        # Aviso de performance para bcrypt
        if self.hash_type == "bcrypt":
            console.print(
                Panel(
                    "[yellow]⚠  bcrypt é propositalmente lento (~15-30 hash/s).\n"
                    "   Wordlist attacks em bcrypt são muito ineficientes — isso é uma feature de segurança![/yellow]",
                    border_style="yellow",
                    title="Aviso bcrypt",
                )
            )
            console.print()

        status_line = Text()

        try:
            with Live(status_line, console=console, refresh_per_second=4) as live:
                for word in wordlist_generator(self.wordlist_path):
                    count += 1

                    if check_candidate(word, self.hash_value, self.hash_type):
                        found = word
                        break

                    # Atualiza status a cada ~0.25s
                    now = time.perf_counter()
                    if now - last_report >= 0.25:
                        elapsed = now - start_time
                        speed = int(count / elapsed) if elapsed > 0 else 0
                        pct = (count / total_lines * 100) if total_lines > 0 else 0
                        status_line = Text.from_markup(
                            f"[cyan]🔑 Tentando:[/cyan] [white]{word:<30}[/white]  "
                            f"[green]{count:>10,}[/green] tentativas  "
                            f"[yellow]{speed:>8,}/s[/yellow]  "
                            f"[blue]{pct:5.1f}%[/blue]"
                        )
                        live.update(status_line)
                        last_report = now

        except KeyboardInterrupt:
            console.print("\n[bold yellow]⚡ Interrompido pelo usuário.[/bold yellow]")

        elapsed = time.perf_counter() - start_time
        self._show_result(found, count, elapsed)
        return found

    def _show_result(self, found: Optional[str], attempts: int, elapsed: float) -> None:
        console.print()
        speed = int(attempts / elapsed) if elapsed > 0 else 0
        if found:
            panel = Panel(
                f"[bold green]✅ HASH QUEBRADO![/bold green]\n\n"
                f"  Hash: [dim]{self.hash_value[:60]}[/dim]\n"
                f"  Senha: [bold white]{found}[/bold white]\n"
                f"  Tipo: [cyan]{self.hash_type.upper()}[/cyan]\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo: [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  Velocidade: [magenta]{speed:,} hashes/s[/magenta]",
                border_style="green",
                title="Resultado",
            )
        else:
            panel = Panel(
                f"[bold red]❌ Hash não encontrado na wordlist[/bold red]\n\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo: [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  Velocidade: [magenta]{speed:,} hashes/s[/magenta]\n"
                f"  [dim]Tente uma wordlist maior (ex: rockyou.txt)[/dim]",
                border_style="red",
                title="Resultado",
            )
        console.print(panel)
        logger.info("Resultado wordlist: %s | tentativas=%d | tempo=%.3fs", found or "NÃO ENCONTRADA", attempts, elapsed)
