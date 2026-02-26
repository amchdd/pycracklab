"""
cracker/wordlist.py
===================
Ataque por dicionário/wordlist com leitura lazy E processamento por chunks
via multiprocessing.Pool.

Decisão técnica — chunking com Pool:
    Em vez de processar palavra por palavra (single-thread) ou carregar
    tudo na RAM (inviável para rockyou.txt de 130MB+), lemos o arquivo
    em blocos (chunks) de N linhas e distribuímos cada bloco para um
    worker do Pool. O worker recebe uma função `check_func` que sabe
    comparar candidato × hash.

    Limitação bcrypt: bcrypt.checkpw é ~15/s por design. Paralelizar
    com N workers dá N×15/s — mas bcrypt também é memory-hard, então
    múltiplos workers concorrentes em RAM limitada podem degradar.
    Para bcrypt, modo single ainda é recomendado didaticamente.

Arquitetura:
    wordlist_generator()     → lazy line reader (O(1) memória)
    _chunk_generator()       → agrupa linhas em lotes
    _worker_check_chunk()    → função top-level (picklável) para Pool
    wordlist_multiprocess()  → orquestra Pool + early termination
    WordlistAttack.run()     → usa multiprocess se --workers > 1
"""

import logging
import multiprocessing
import time
from functools import partial
from pathlib import Path
from typing import Callable, Optional, Generator

import bcrypt
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from utils.hashing import hash_md5, hash_sha1, detect_hash_type

logger = logging.getLogger("pycracklab.wordlist")
console = Console()


# ─────────────────────────────────────────────
# Leitura lazy da wordlist
# ─────────────────────────────────────────────

def wordlist_generator(path: str) -> Generator[str, None, None]:
    """
    Lê wordlist linha a linha (lazy) — O(1) memória.
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


def _chunk_generator(
    gen: Generator[str, None, None], chunk_size: int
) -> Generator[list[str], None, None]:
    """Agrupa itens de um generator em listas de tamanho fixo."""
    chunk: list[str] = []
    for item in gen:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def count_lines(path: str) -> int:
    """Conta linhas do arquivo (para estimativa de progresso)."""
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
    bcrypt/argon2 usam verificação timing-safe; salt extraído do próprio hash.
    """
    try:
        if hash_type == "md5":
            return hash_md5(candidate) == hash_value.lower()
        elif hash_type == "sha1":
            return hash_sha1(candidate) == hash_value.lower()
        elif hash_type == "bcrypt":
            return bcrypt.checkpw(candidate.encode("utf-8"), hash_value.encode("utf-8"))
        elif hash_type == "argon2":
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            ph.verify(hash_value, candidate.encode("utf-8"))
            return True
        else:
            logger.warning("Tipo de hash desconhecido: %s", hash_type)
            return False
    except Exception as exc:
        logger.debug("Erro ao verificar candidato '%s': %s", candidate, exc)
        return False


def _worker_check_chunk(
    chunk: list[str],
    hash_value: str,
    hash_type: str,
) -> Optional[str]:
    """
    Função top-level (picklável pelo multiprocessing) que verifica
    uma lista de candidatos. Retorna o primeiro match ou None.
    """
    for candidate in chunk:
        if check_candidate(candidate, hash_value, hash_type):
            return candidate
    return None


# ─────────────────────────────────────────────
# wordlist_multiprocess — processamento paralelo
# ─────────────────────────────────────────────

def wordlist_multiprocess(
    wordlist_path: str,
    hash_value: str,
    hash_type: str,
    num_workers: int = 4,
    chunk_size: int = 500,
    on_chunk_done: Optional[Callable[[int], None]] = None,
) -> tuple[Optional[str], int, float]:
    """
    Ataque por wordlist com multiprocessing.Pool.

    Lê o arquivo em chunks e distribui para workers paralelos.
    Termina assim que qualquer worker encontrar o match.

    on_chunk_done(checked_so_far) é chamado após cada chunk processado (para progresso).

    Returns:
        (resultado, tentativas_totais, tempo_segundos)
    """
    start_time = time.perf_counter()
    total_checked = 0
    result: Optional[str] = None

    worker_fn = partial(_worker_check_chunk, hash_value=hash_value, hash_type=hash_type)

    ctx = multiprocessing.get_context("spawn")

    with ctx.Pool(processes=num_workers) as pool:
        gen = wordlist_generator(wordlist_path)
        chunks = _chunk_generator(gen, chunk_size)

        for chunk_result in pool.imap_unordered(worker_fn, chunks, chunksize=1):
            total_checked += chunk_size
            if on_chunk_done:
                on_chunk_done(total_checked)
            if chunk_result is not None:
                result = chunk_result
                pool.terminate()
                break

    elapsed = time.perf_counter() - start_time
    return result, total_checked, elapsed


# ─────────────────────────────────────────────
# WordlistAttack — API principal
# ─────────────────────────────────────────────

class WordlistAttack:
    """
    Ataque de dicionário contra um hash alvo.
    Suporta MD5, SHA1 e bcrypt com detecção automática.
    Modo padrão: single-thread (lazy).
    Com --workers > 1: multiprocessing.Pool com chunking.
    """

    def __init__(
        self,
        hash_value: str,
        wordlist_path: str,
        hash_type: str = "auto",
        num_workers: int = 1,
        chunk_size: int = 500,
    ) -> None:
        self.hash_value = hash_value.strip()
        self.wordlist_path = wordlist_path
        self.hash_type = hash_type
        self.num_workers = max(1, num_workers)
        self.chunk_size = chunk_size

        if not self.hash_value:
            raise ValueError("Hash não pode ser vazio.")

        if self.hash_type == "auto":
            detected = detect_hash_type(self.hash_value)
            if not detected:
                raise ValueError(
                    f"Não foi possível detectar o tipo do hash: '{self.hash_value[:30]}...'\n"
                    "Use --hash-type para especificar manualmente."
                )
            self.hash_type = detected
            console.print(
                f"[bold cyan]🔍 Tipo de hash detectado: [yellow]{self.hash_type.upper()}[/yellow][/bold cyan]\n"
            )

        logger.info(
            "WordlistAttack: hash_type=%s, workers=%d, wordlist=%s",
            self.hash_type, self.num_workers, wordlist_path,
        )

    def _show_config(self, total_lines: int) -> None:
        mode_label = (
            f"[green]multiprocessing[/green] ({self.num_workers} workers, "
            f"chunk={self.chunk_size})"
            if self.num_workers > 1
            else "[white]single-thread[/white]"
        )
        table = Table(title="⚙  Configuração do Ataque por Wordlist", border_style="blue")
        table.add_column("Parâmetro", style="cyan")
        table.add_column("Valor", style="green")
        table.add_row("Hash alvo", f"{self.hash_value[:50]}{'...' if len(self.hash_value) > 50 else ''}")
        table.add_row("Tipo de hash", self.hash_type.upper())
        table.add_row("Wordlist", self.wordlist_path)
        table.add_row("Entradas estimadas", f"{total_lines:,}")
        table.add_row("Modo", mode_label)
        console.print(table)
        console.print()

    def run(self) -> Optional[str]:
        """Executa o ataque. Retorna a senha encontrada ou None."""
        total_lines = count_lines(self.wordlist_path)
        self._show_config(total_lines)

        if self.hash_type == "bcrypt":
            console.print(
                Panel(
                    "[yellow]⚠  bcrypt é propositalmente lento (~15-30 hash/s).\n"
                    "   Multiprocessing ajuda linearmente, mas o custo computacional\n"
                    "   por hash permanece alto — isso é uma feature de segurança![/yellow]",
                    border_style="yellow",
                    title="Aviso bcrypt",
                )
            )
            console.print()

        if self.num_workers > 1:
            return self._run_multiprocess()
        else:
            return self._run_single()

    def _run_multiprocess(self) -> Optional[str]:
        """Usa wordlist_multiprocess com barra de progresso."""
        console.print(
            f"[bold green]🚀 Iniciando com {self.num_workers} workers paralelos...[/bold green]\n"
        )

        total_lines = count_lines(self.wordlist_path)
        total_chunks = max(1, (total_lines + self.chunk_size - 1) // self.chunk_size)

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[cyan]{task.fields[speed]}/s"),
            TimeElapsedColumn(),
            console=console,
        )

        with progress:
            task = progress.add_task("Processando chunks...", total=total_chunks, speed="0")
            chunks_done = [0]  # list para closure

            def on_chunk(checked: int) -> None:
                chunks_done[0] += 1
                speed = int(checked / (time.perf_counter() - getattr(on_chunk, "_t0", time.perf_counter())))
                progress.update(task, advance=1, speed=f"{speed:,}")

            on_chunk._t0 = time.perf_counter()

            result, attempts, elapsed = wordlist_multiprocess(
                wordlist_path=self.wordlist_path,
                hash_value=self.hash_value,
                hash_type=self.hash_type,
                num_workers=self.num_workers,
                chunk_size=self.chunk_size,
                on_chunk_done=on_chunk,
            )

        self._show_result(result, attempts, elapsed)
        return result

    def _run_single(self) -> Optional[str]:
        """Processamento single-thread com barra de progresso."""
        found: Optional[str] = None
        count = 0
        start_time = time.perf_counter()
        total_lines = count_lines(self.wordlist_path)

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[cyan]{task.fields[speed]}/s"),
            TimeElapsedColumn(),
            console=console,
        )

        try:
            with progress:
                task = progress.add_task("Testando palavras...", total=total_lines or 1, speed="0")
                last_update = start_time
                for word in wordlist_generator(self.wordlist_path):
                    count += 1
                    progress.update(task, advance=1)
                    if check_candidate(word, self.hash_value, self.hash_type):
                        found = word
                        break
                    now = time.perf_counter()
                    if now - last_update >= 0.5 and total_lines > 0:
                        speed = int(count / (now - start_time))
                        progress.update(task, speed=f"{speed:,}")
                        last_update = now
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
                f"  Hash:       [dim]{self.hash_value[:60]}[/dim]\n"
                f"  Senha:      [bold white]{found}[/bold white]\n"
                f"  Tipo:       [cyan]{self.hash_type.upper()}[/cyan]\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo:      [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  Velocidade: [magenta]{speed:,} hashes/s[/magenta]",
                border_style="green",
                title="Resultado",
            )
        else:
            panel = Panel(
                f"[bold red]❌ Hash não encontrado na wordlist[/bold red]\n\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo:      [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  Velocidade: [magenta]{speed:,} hashes/s[/magenta]\n"
                f"  [dim]Tente uma wordlist maior (ex: rockyou.txt)[/dim]",
                border_style="red",
                title="Resultado",
            )
        self._last_stats = {
            "command": "wordlist",
            "found": found is not None,
            "password": found,
            "attempts": attempts,
            "elapsed_seconds": elapsed,
            "hashes_per_second": int(attempts / elapsed) if elapsed > 0 else 0,
            "hash_type": self.hash_type,
            "workers": self.num_workers,
        }
        console.print(panel)
        logger.info(
            "Resultado wordlist: %s | workers=%d | tentativas=%d | tempo=%.3fs",
            found or "NÃO ENCONTRADA", self.num_workers, attempts, elapsed,
        )

    def get_stats(self) -> dict:
        """Retorna estatísticas da última execução (para --stats-json)."""
        return getattr(self, "_last_stats", {})
