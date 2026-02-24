"""
cracker/brute.py
================
Implementa ataque de força bruta com suporte a multithreading.

Decisão técnica:
    Usamos itertools.product para gerar candidatos de forma lazy (sem
    carregar tudo na memória). Com multithreading, dividimos o espaço de
    busca entre workers — cada thread processa uma fatia do iterador.

Limitações do Brute Force:
    - Cresce EXPONENCIALMENTE: charset=26, len=8 → 26^8 ≈ 208 bilhões de combinações.
    - Para bcrypt (custo 12) a ~15 hash/s, isso levaria > 400 anos.
    - Prático apenas para senhas curtas (<= 5 chars) com charsets pequenos.
    - MD5/SHA1 são muito mais rápidos (~1M/s), mas ainda assim inviáveis
      para senhas longas e complexas.
"""

import itertools
import logging
import string
import threading
import time
from typing import Generator, Optional

from rich.console import Console
from rich.live import Live
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

logger = logging.getLogger("pycracklab.brute")
console = Console()


# ─────────────────────────────────────────────
# Charsets disponíveis
# ─────────────────────────────────────────────

CHARSETS: dict[str, str] = {
    "lowercase": string.ascii_lowercase,
    "uppercase": string.ascii_uppercase,
    "digits": string.digits,
    "special": string.punctuation,
    "all": string.ascii_letters + string.digits + string.punctuation,
}


def get_charset(name: str, custom: Optional[str] = None) -> str:
    """Retorna o charset a ser usado, priorizando custom se fornecido."""
    if custom:
        # Remove duplicatas mantendo ordem
        seen: set[str] = set()
        return "".join(c for c in custom if not (c in seen or seen.add(c)))  # type: ignore[func-returns-value]
    return CHARSETS.get(name, CHARSETS["lowercase"])


def estimate_combinations(charset: str, min_len: int, max_len: int) -> int:
    """Estima o total de combinações para exibição ao usuário."""
    return sum(len(charset) ** length for length in range(min_len, max_len + 1))


def candidate_generator(charset: str, min_len: int, max_len: int) -> Generator[str, None, None]:
    """Gera candidatos de forma lazy, sem carregar na memória."""
    for length in range(min_len, max_len + 1):
        for combo in itertools.product(charset, repeat=length):
            yield "".join(combo)


# ─────────────────────────────────────────────
# Worker de thread
# ─────────────────────────────────────────────

class _BruteWorker(threading.Thread):
    """Thread worker que verifica uma fatia de candidatos."""

    def __init__(
        self,
        candidates: list[str],
        target: str,
        result_holder: list[Optional[str]],
        lock: threading.Lock,
        counter: list[int],
    ) -> None:
        super().__init__(daemon=True)
        self.candidates = candidates
        self.target = target
        self.result_holder = result_holder
        self.lock = lock
        self.counter = counter

    def run(self) -> None:
        for candidate in self.candidates:
            with self.lock:
                if self.result_holder[0] is not None:
                    return  # Outro worker já encontrou
                self.counter[0] += 1

            if candidate == self.target:
                with self.lock:
                    self.result_holder[0] = candidate
                return


# ─────────────────────────────────────────────
# BruteForceAttack
# ─────────────────────────────────────────────

class BruteForceAttack:
    """
    Realiza ataque de força bruta comparando candidatos com a senha alvo
    em texto claro.

    Nota educacional: Em cenário real, compararíamos o HASH do candidato
    com o hash armazenado, nunca a senha diretamente. Use HashCracker para
    isso. Este módulo ilustra a mecânica pura do brute force.
    """

    def __init__(
        self,
        target: str,
        charset_name: str = "lowercase",
        custom_charset: Optional[str] = None,
        min_len: int = 1,
        max_len: int = 6,
        num_threads: int = 1,
    ) -> None:
        self.target = target
        self.charset = get_charset(charset_name, custom_charset)
        self.min_len = min_len
        self.max_len = max_len
        self.num_threads = max(1, num_threads)

        if not target:
            raise ValueError("O alvo não pode ser vazio.")
        if not self.charset:
            raise ValueError("Charset não pode ser vazio.")
        if min_len < 1 or max_len < min_len:
            raise ValueError("Comprimentos inválidos.")

    def _show_config(self, total: int) -> None:
        """Exibe tabela de configuração antes do ataque."""
        table = Table(title="⚙  Configuração do Ataque", border_style="blue")
        table.add_column("Parâmetro", style="cyan", no_wrap=True)
        table.add_column("Valor", style="green")

        table.add_row("Alvo", f"[bold]{self.target}[/bold]")
        table.add_row("Charset", f"{self.charset[:30]}{'...' if len(self.charset) > 30 else ''}")
        table.add_row("Tamanho charset", str(len(self.charset)))
        table.add_row("Min / Max comprimento", f"{self.min_len} / {self.max_len}")
        table.add_row("Threads", str(self.num_threads))
        table.add_row("Total de combinações", f"{total:,}")

        console.print(table)
        console.print()

    def run(self) -> Optional[str]:
        """Executa o ataque. Retorna a senha encontrada ou None."""
        total = estimate_combinations(self.charset, self.min_len, self.max_len)
        self._show_config(total)

        logger.info(
            "Iniciando brute force: charset=%d chars, len=%d-%d, threads=%d, total=%d",
            len(self.charset), self.min_len, self.max_len, self.num_threads, total
        )

        result: Optional[str] = None
        start_time = time.perf_counter()

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
            task = progress.add_task("Testando...", total=total, speed="0")
            count = 0
            last_update = time.perf_counter()

            if self.num_threads == 1:
                # Single-thread: mais simples e eficiente para iteração lazy
                for candidate in candidate_generator(self.charset, self.min_len, self.max_len):
                    count += 1

                    if candidate == self.target:
                        result = candidate
                        progress.update(task, advance=1)
                        break

                    progress.update(task, advance=1)

                    # Atualiza velocidade a cada 0.5s
                    now = time.perf_counter()
                    if now - last_update >= 0.5:
                        elapsed = now - start_time
                        speed = int(count / elapsed) if elapsed > 0 else 0
                        progress.update(task, speed=f"{speed:,}")
                        last_update = now

            else:
                # Multi-thread: coleta candidatos em lotes e distribui
                result = self._run_multithreaded(total, progress, task, start_time)

        elapsed = time.perf_counter() - start_time
        self._show_result(result, count if self.num_threads == 1 else total, elapsed)
        return result

    def _run_multithreaded(
        self,
        total: int,
        progress: Progress,
        task,  # type: ignore[type-arg]
        start_time: float,
    ) -> Optional[str]:
        """Executa o brute force com múltiplas threads."""
        BATCH_SIZE = 50_000
        result_holder: list[Optional[str]] = [None]
        counter: list[int] = [0]
        lock = threading.Lock()
        batch: list[str] = []
        threads: list[_BruteWorker] = []

        for candidate in candidate_generator(self.charset, self.min_len, self.max_len):
            if result_holder[0] is not None:
                break

            batch.append(candidate)

            if len(batch) >= BATCH_SIZE:
                # Divide lote entre threads
                chunk_size = len(batch) // self.num_threads
                for i in range(self.num_threads):
                    start = i * chunk_size
                    end = start + chunk_size if i < self.num_threads - 1 else len(batch)
                    t = _BruteWorker(batch[start:end], self.target, result_holder, lock, counter)
                    threads.append(t)
                    t.start()

                for t in threads:
                    t.join()

                progress.update(task, advance=len(batch), speed=f"{int(counter[0] / (time.perf_counter() - start_time)):,}")
                threads.clear()
                batch.clear()

        # Processa resto do batch
        if batch and result_holder[0] is None:
            for candidate in batch:
                with lock:
                    counter[0] += 1
                if candidate == self.target:
                    with lock:
                        result_holder[0] = candidate
                    break

        return result_holder[0]

    def _show_result(self, result: Optional[str], attempts: int, elapsed: float) -> None:
        """Exibe resultado final."""
        console.print()
        if result:
            speed = int(attempts / elapsed) if elapsed > 0 else 0
            panel = Panel(
                f"[bold green]✅ SENHA ENCONTRADA![/bold green]\n\n"
                f"  Senha: [bold white]{result}[/bold white]\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo: [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  Velocidade: [magenta]{speed:,} tentativas/s[/magenta]",
                border_style="green",
                title="Resultado",
            )
        else:
            panel = Panel(
                f"[bold red]❌ Senha não encontrada[/bold red]\n\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo: [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  [dim]Tente aumentar max-len ou mudar o charset[/dim]",
                border_style="red",
                title="Resultado",
            )
        console.print(panel)
        logger.info("Resultado: %s | tentativas=%d | tempo=%.3fs", result or "NÃO ENCONTRADA", attempts, elapsed)
