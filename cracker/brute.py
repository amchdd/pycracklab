"""
cracker/brute.py
================
Ataque de força bruta com suporte a threading E multiprocessing.

Por que multiprocessing em vez de threading para CPU-bound?
    O GIL (Global Interpreter Lock) do CPython impede que múltiplas
    threads executem bytecode Python simultaneamente. Para tarefas
    CPU-bound como hashing/comparação, threads não trazem ganho real
    de paralelismo — apenas aumentam overhead de context switch.

    multiprocessing cria processos separados, cada um com seu próprio
    GIL, permitindo paralelismo real em múltiplos cores.

    Limitação: o overhead de criar processos e comunicar via Queue/Pipe
    torna multiprocessing MAIS LENTO para espaços de busca pequenos.
    Use --mode process apenas para buscas longas (max-len >= 5).

Estratégia de divisão por prefixos:
    Em vez de dividir um iterador (que não é serializável), cada worker
    recebe um prefixo diferente do charset e busca TODAS as combinações
    com aquele prefixo. Ex: charset="abc", workers=3 → worker0 busca
    a*, worker1 busca b*, worker2 busca c*. Isso elimina comunicação
    contínua entre processos.
"""

import itertools
import logging
import multiprocessing
import os
import string
import threading
import time
from typing import Callable, Generator, Optional

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


def get_charset(name: str, custom: Optional[str] = None, custom_charset: Optional[str] = None) -> str:
    """
    Retorna o charset a ser usado.

    Compatibilidade:
      - aceita tanto `custom` (antigo) quanto `custom_charset` (usado pelos testes/CLI).
      - se ambos forem passados, `custom_charset` tem precedência.
      - remove duplicados preservando a ordem.
    """
    chosen = custom_charset if custom_charset is not None else custom

    if chosen:
        # remove duplicados preservando ordem (dict.fromkeys preserva ordem desde Python 3.7)
        return "".join(dict.fromkeys(chosen))

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
# Worker para multiprocessing (top-level — serializável pelo pickle)
# ─────────────────────────────────────────────

def _mp_worker(
    prefix: str,
    charset: str,
    min_len: int,
    max_len: int,
    target: str,
    result_queue: "multiprocessing.Queue[Optional[str]]",
    stop_event: "multiprocessing.Event",  # type: ignore[type-arg]
    counter: "multiprocessing.Value",  # type: ignore[type-arg]
) -> None:
    """
    Worker de processo: busca candidatos com o prefixo dado.
    Escreve na queue ao encontrar e verifica stop_event para encerrar cedo.
    """
    prefix_len = len(prefix)

    for length in range(max(min_len, prefix_len), max_len + 1):
        suffix_len = length - prefix_len
        if suffix_len < 0:
            continue

        iterable = (prefix + "".join(s) for s in itertools.product(charset, repeat=suffix_len))

        for candidate in iterable:
            if stop_event.is_set():
                return

            with counter.get_lock():
                counter.value += 1

            if candidate == target:
                result_queue.put(candidate)
                stop_event.set()
                return

    # Prefixo exato (length == prefix_len) — testa o prefixo em si
    if min_len <= prefix_len <= max_len:
        pass  # já coberto no loop acima quando suffix_len == 0


def brute_multiprocess(
    target: str,
    charset: str,
    min_len: int,
    max_len: int,
    num_workers: Optional[int] = None,
) -> tuple[Optional[str], int, float]:
    """
    Brute force usando multiprocessing real (contorna o GIL).

    Divide o espaço de busca por prefixos do charset — cada processo
    fica responsável por uma fatia ortogonal do espaço total.

    Returns:
        (resultado, tentativas_totais, tempo_segundos)
    """
    if num_workers is None:
        num_workers = os.cpu_count() or 2

    # Prefixos = primeiros caracteres do charset, distribuídos entre workers
    # Para max_len >= 2: usa o charset completo como prefixos de 1 char
    # Para max_len == 1: divide o charset diretamente
    if max_len == 1:
        prefixes = list(charset)
    else:
        prefixes = list(charset)

    # Se tivermos mais workers que prefixos, limitamos
    num_workers = min(num_workers, len(prefixes))

    # Distribui prefixos entre workers
    prefix_chunks: list[list[str]] = [[] for _ in range(num_workers)]
    for i, p in enumerate(prefixes):
        prefix_chunks[i % num_workers].append(p)

    ctx = multiprocessing.get_context("spawn")
    result_queue: "multiprocessing.Queue[Optional[str]]" = ctx.Queue()
    stop_event = ctx.Event()
    counter = ctx.Value("i", 0)

    processes: list[multiprocessing.Process] = []
    start_time = time.perf_counter()

    # Lança um processo por chunk de prefixos
    for chunk in prefix_chunks:
        for prefix in chunk:
            p = ctx.Process(
                target=_mp_worker,
                args=(prefix, charset, min_len, max_len, target,
                      result_queue, stop_event, counter),
                daemon=True,
            )
            p.start()
            processes.append(p)

    # Aguarda resultado ou término de todos os processos
    result: Optional[str] = None
    while any(p.is_alive() for p in processes):
        try:
            result = result_queue.get(timeout=0.1)
            stop_event.set()
            break
        except Exception:
            pass

    for p in processes:
        p.join(timeout=2)
        if p.is_alive():
            p.terminate()

    elapsed = time.perf_counter() - start_time
    total_attempts = counter.value

    return result, total_attempts, elapsed


# ─────────────────────────────────────────────
# Worker de thread (modo threading — fallback)
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
                    return
                self.counter[0] += 1
            if candidate == self.target:
                with self.lock:
                    self.result_holder[0] = candidate
                return


# ─────────────────────────────────────────────
# BruteForceAttack — API principal (compatível com CLI)
# ─────────────────────────────────────────────

class BruteForceAttack:
    """
    Ataque de força bruta com suporte a três modos:
        - single:  single-thread (default, mais simples)
        - thread:  multi-threading (melhor para I/O bound, limitado pelo GIL)
        - process: multiprocessing real (melhor para CPU-bound, contorna GIL)

    Nota educacional: Em cenário real, comparamos o HASH do candidato
    com o hash armazenado. Este módulo ilustra a mecânica pura do brute force.
    """

    MODES = ("single", "thread", "process")

    def __init__(
        self,
        target: str,
        charset_name: str = "lowercase",
        custom_charset: Optional[str] = None,
        min_len: int = 1,
        max_len: int = 6,
        num_threads: int = 1,
        mode: str = "single",
    ) -> None:
        if not target:
            raise ValueError("O alvo não pode ser vazio.")
        if mode not in self.MODES:
            raise ValueError(f"Modo inválido '{mode}'. Escolha: {self.MODES}")

        self.target = target
        self.charset = get_charset(charset_name, custom_charset)
        self.min_len = min_len
        self.max_len = max_len
        self.mode = mode

        if not self.charset:
            raise ValueError("Charset não pode ser vazio.")
        if min_len < 1 or max_len < min_len:
            raise ValueError("Comprimentos inválidos.")

        # num_threads controla tanto threads quanto processos
        if mode == "process":
            self.num_workers = max(1, num_threads if num_threads > 1 else (os.cpu_count() or 2))
        else:
            self.num_workers = max(1, num_threads)

    def _show_config(self, total: int) -> None:
        mode_labels = {
            "single": "[white]single-thread[/white]",
            "thread": "[cyan]multi-thread[/cyan] [dim](GIL ativo)[/dim]",
            "process": "[green]multiprocessing[/green] [dim](GIL contornado)[/dim]",
        }
        table = Table(title="⚙  Configuração do Ataque", border_style="blue")
        table.add_column("Parâmetro", style="cyan", no_wrap=True)
        table.add_column("Valor", style="green")
        table.add_row("Alvo", f"[bold]{self.target}[/bold]")
        table.add_row("Charset", f"{self.charset[:30]}{'...' if len(self.charset) > 30 else ''}")
        table.add_row("Tamanho charset", str(len(self.charset)))
        table.add_row("Min / Max comprimento", f"{self.min_len} / {self.max_len}")
        table.add_row("Modo", mode_labels[self.mode])
        table.add_row("Workers", str(self.num_workers))
        table.add_row("Total de combinações", f"{total:,}")
        console.print(table)
        console.print()

    def run(self) -> Optional[str]:
        """Executa o ataque no modo configurado."""
        total = estimate_combinations(self.charset, self.min_len, self.max_len)
        self._show_config(total)

        logger.info(
            "Iniciando brute force: mode=%s, charset=%d, len=%d-%d, workers=%d, total=%d",
            self.mode, len(self.charset), self.min_len, self.max_len, self.num_workers, total,
        )

        if self.mode == "process":
            return self._run_multiprocess(total)
        elif self.mode == "thread" and self.num_workers > 1:
            return self._run_with_progress(total, multithreaded=True)
        else:
            return self._run_with_progress(total, multithreaded=False)

    def _run_multiprocess(self, total: int) -> Optional[str]:
        """Delega para brute_multiprocess e exibe resultado."""
        console.print(
            f"[bold green]🚀 Lançando {self.num_workers} processos paralelos...[/bold green]\n"
        )

        with console.status("[bold green]Processando em paralelo...[/bold green]", spinner="dots"):
            result, attempts, elapsed = brute_multiprocess(
                target=self.target,
                charset=self.charset,
                min_len=self.min_len,
                max_len=self.max_len,
                num_workers=self.num_workers,
            )

        self._show_result(result, attempts, elapsed)
        return result

    def _run_with_progress(self, total: int, multithreaded: bool) -> Optional[str]:
        """Executa single-thread ou multi-thread com barra de progresso."""
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

            if not multithreaded:
                for candidate in candidate_generator(self.charset, self.min_len, self.max_len):
                    count += 1
                    progress.update(task, advance=1)
                    if candidate == self.target:
                        result = candidate
                        break
                    now = time.perf_counter()
                    if now - last_update >= 0.5:
                        elapsed = now - start_time
                        speed = int(count / elapsed) if elapsed > 0 else 0
                        progress.update(task, speed=f"{speed:,}")
                        last_update = now
            else:
                result = self._run_multithreaded(total, progress, task, start_time)
                count = total

        elapsed = time.perf_counter() - start_time
        self._show_result(result, count, elapsed)
        return result

    def _run_multithreaded(
        self,
        total: int,
        progress: Progress,
        task,  # type: ignore[type-arg]
        start_time: float,
    ) -> Optional[str]:
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
                chunk_size = len(batch) // self.num_workers
                for i in range(self.num_workers):
                    start = i * chunk_size
                    end = start + chunk_size if i < self.num_workers - 1 else len(batch)
                    t = _BruteWorker(batch[start:end], self.target, result_holder, lock, counter)
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
                elapsed = time.perf_counter() - start_time
                speed = int(counter[0] / elapsed) if elapsed > 0 else 0
                progress.update(task, advance=len(batch), speed=f"{speed:,}")
                threads.clear()
                batch.clear()

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
        console.print()
        speed = int(attempts / elapsed) if elapsed > 0 else 0
        if result:
            panel = Panel(
                f"[bold green]✅ SENHA ENCONTRADA![/bold green]\n\n"
                f"  Senha:      [bold white]{result}[/bold white]\n"
                f"  Modo:       [cyan]{self.mode}[/cyan]\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo:      [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  Velocidade: [magenta]{speed:,} tentativas/s[/magenta]",
                border_style="green",
                title="Resultado",
            )
        else:
            panel = Panel(
                f"[bold red]❌ Senha não encontrada[/bold red]\n\n"
                f"  Tentativas: [cyan]{attempts:,}[/cyan]\n"
                f"  Tempo:      [yellow]{elapsed:.3f}s[/yellow]\n"
                f"  [dim]Tente aumentar max-len ou mudar o charset[/dim]",
                border_style="red",
                title="Resultado",
            )
        console.print(panel)
        logger.info(
            "Resultado: %s | mode=%s | tentativas=%d | tempo=%.3fs",
            result or "NÃO ENCONTRADA", self.mode, attempts, elapsed,
        )