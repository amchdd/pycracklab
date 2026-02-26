"""
utils/benchmark.py
==================
Benchmark comparativo de performance entre MD5, SHA1 e bcrypt.

Explicação didática das diferenças de performance:
────────────────────────────────────────────────────

MD5 (~500M–10B hashes/s em GPU):
    - Projetado para VELOCIDADE (verificação de integridade de arquivos).
    - Sem salt nativo, sem fator de custo.
    - Um atacante com GPU RTX 3090 testa ~10 bilhões de MD5/segundo.
    - Uma senha de 8 chars (lowercase+digits) = 36^8 = 2.8 trilhões.
    - Tempo para crack: ~280 segundos. Inaceitável para senha.

SHA1 (~1B–3B hashes/s em GPU):
    - Também projetado para velocidade e integridade.
    - Mesmos problemas do MD5 para armazenamento de senhas.

bcrypt (~15–50 hashes/s em CPU):
    - Projetado ESPECIFICAMENTE para senhas (Niels Provos, 1999).
    - Incorpora salt aleatório automaticamente (contra rainbow tables).
    - Fator de custo adaptável: $12$ = 2^12 = 4096 rounds.
    - Memory-hard por design: dificulta paralelização em GPU/ASIC.
    - A mesma senha de 8 chars levaria ~180 bilhões de segundos com bcrypt.
    - Isso é > 5.700 anos com uma GPU dedicada.

Impacto na segurança real:
    - Um banco de dados vazado com MD5 é comprometido em horas.
    - O mesmo banco com bcrypt(12) levaria décadas para ser quebrado.
    - Por isso frameworks modernos usam bcrypt, Argon2 ou scrypt.
"""

import hashlib
import logging
import time

import bcrypt
from argon2 import PasswordHasher
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dataclasses import dataclass

logger = logging.getLogger("pycracklab.benchmark")
console = Console()


# ─────────────────────────────────────────────
# Estrutura de resultado
# ─────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    algorithm: str
    iterations: int
    elapsed_seconds: float
    hashes_per_second: float
    time_to_crack_8char: str  # Estimativa didática


# ─────────────────────────────────────────────
# Benchmark
# ─────────────────────────────────────────────

class Benchmark:
    """
    Mede velocidade de hashing de MD5, SHA1 e bcrypt.
    Exibe relatório comparativo com estimativas de segurança.
    """

    # Espaço de busca para senha de 8 chars (lowercase + digits = 36^8)
    _SEARCH_SPACE_8CHARS = 36**8  # ~2.8 trilhões

    def __init__(self, password: str = "benchmark_test", iterations: int = 100_000) -> None:
        self.password = password
        self.iterations = iterations
        # bcrypt e Argon2 são MUITO mais lentos — limitamos para não travar a demo
        self.bcrypt_iterations = min(iterations, 50)
        self.argon2_iterations = min(iterations, 30)

    def _benchmark_md5(self) -> BenchmarkResult:
        """Mede velocidade do MD5."""
        pw_bytes = self.password.encode("utf-8")
        start = time.perf_counter()
        for _ in range(self.iterations):
            hashlib.md5(pw_bytes).hexdigest()
        elapsed = time.perf_counter() - start

        hps = self.iterations / elapsed
        # Tempo estimado para quebrar 8 chars com esta velocidade
        seconds_to_crack = self._SEARCH_SPACE_8CHARS / hps
        crack_estimate = self._format_time(seconds_to_crack)

        return BenchmarkResult("MD5", self.iterations, elapsed, hps, crack_estimate)

    def _benchmark_sha1(self) -> BenchmarkResult:
        """Mede velocidade do SHA1."""
        pw_bytes = self.password.encode("utf-8")
        start = time.perf_counter()
        for _ in range(self.iterations):
            hashlib.sha1(pw_bytes).hexdigest()
        elapsed = time.perf_counter() - start

        hps = self.iterations / elapsed
        seconds_to_crack = self._SEARCH_SPACE_8CHARS / hps
        crack_estimate = self._format_time(seconds_to_crack)

        return BenchmarkResult("SHA1", self.iterations, elapsed, hps, crack_estimate)

    def _benchmark_bcrypt(self) -> BenchmarkResult:
        """Mede velocidade do bcrypt (limitado a 50 iterações por ser lento)."""
        pw_bytes = self.password.encode("utf-8")
        # Gera um salt fixo para não contar o custo de gensalt
        salt = bcrypt.gensalt(rounds=12)

        start = time.perf_counter()
        for _ in range(self.bcrypt_iterations):
            bcrypt.hashpw(pw_bytes, salt)
        elapsed = time.perf_counter() - start

        hps = self.bcrypt_iterations / elapsed
        seconds_to_crack = self._SEARCH_SPACE_8CHARS / hps
        crack_estimate = self._format_time(seconds_to_crack)

        return BenchmarkResult("bcrypt (cost=12)", self.bcrypt_iterations, elapsed, hps, crack_estimate)

    def _benchmark_argon2(self) -> BenchmarkResult:
        """Mede velocidade do Argon2id (limitado por ser lento e memory-hard)."""
        ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)
        pw_bytes = self.password.encode("utf-8")

        start = time.perf_counter()
        for _ in range(self.argon2_iterations):
            ph.hash(pw_bytes)
        elapsed = time.perf_counter() - start

        hps = self.argon2_iterations / elapsed
        seconds_to_crack = self._SEARCH_SPACE_8CHARS / hps
        crack_estimate = self._format_time(seconds_to_crack)

        return BenchmarkResult("Argon2id", self.argon2_iterations, elapsed, hps, crack_estimate)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Formata segundos em unidade legível."""
        if seconds < 60:
            return f"{seconds:.1f} segundos"
        elif seconds < 3600:
            return f"{seconds/60:.1f} minutos"
        elif seconds < 86400:
            return f"{seconds/3600:.1f} horas"
        elif seconds < 86400 * 365:
            return f"{seconds/86400:.1f} dias"
        elif seconds < 86400 * 365 * 1000:
            return f"{seconds/(86400*365):.1f} anos"
        else:
            return f"{seconds/(86400*365):.2e} anos"

    def _show_explanation(self) -> None:
        """Exibe explicação educacional antes dos resultados."""
        text = (
            "[bold]Por que bcrypt é propositalmente lento?[/bold]\n\n"
            "• [cyan]MD5 / SHA1[/cyan]: projetados para [bold]velocidade[/bold] — verificação de integridade de arquivos.\n"
            "  → GPUs modernas computam [bold red]bilhões por segundo[/bold red]. Ruim para senhas.\n\n"
            "• [green]bcrypt[/green]: projetado para [bold]custo computacional[/bold] — cada hash é lento por design.\n"
            "  → Fator de custo $12$ = 2^12 = 4.096 rounds de derivação.\n"
            "  → Memory-hard: dificulta paralelização em GPU/ASIC.\n"
            "  → Salt aleatório embutido: elimina ataques de rainbow table.\n\n"
            "[dim]Nota: os valores abaixo são da sua CPU. GPUs são 1000x+ mais rápidas para MD5/SHA1.[/dim]"
        )
        console.print(Panel(text, border_style="blue", title="📚 Contexto Educacional"))
        console.print()

    def run(self) -> list[BenchmarkResult]:
        """Executa benchmark e exibe relatório."""
        console.print(Panel(
            f"[bold]Benchmark de Hashing[/bold]\n"
            f"Senha de teste: [cyan]{self.password}[/cyan]\n"
            f"Iterações MD5/SHA1: [yellow]{self.iterations:,}[/yellow]\n"
            f"Iterações bcrypt: [yellow]{self.bcrypt_iterations}[/yellow] | Argon2id: [yellow]{self.argon2_iterations}[/yellow] (limitados por serem lentos)",
            border_style="blue", title="⚡ Benchmark"
        ))
        console.print()

        self._show_explanation()

        # Executa benchmarks com spinner
        results: list[BenchmarkResult] = []

        with console.status("[bold green]Executando MD5...", spinner="dots"):
            results.append(self._benchmark_md5())
        console.print("[green]✓[/green] MD5 concluído")

        with console.status("[bold green]Executando SHA1...", spinner="dots"):
            results.append(self._benchmark_sha1())
        console.print("[green]✓[/green] SHA1 concluído")

        with console.status("[bold yellow]Executando bcrypt (isso vai demorar ~alguns segundos)...", spinner="dots"):
            results.append(self._benchmark_bcrypt())
        console.print("[green]✓[/green] bcrypt concluído")

        with console.status("[bold yellow]Executando Argon2id...", spinner="dots"):
            results.append(self._benchmark_argon2())
        console.print("[green]✓[/green] Argon2id concluído")

        console.print()
        self._show_report(results)
        self._last_stats = {
            "command": "benchmark",
            "password": self.password,
            "results": [
                {
                    "algorithm": r.algorithm,
                    "iterations": r.iterations,
                    "elapsed_seconds": r.elapsed_seconds,
                    "hashes_per_second": r.hashes_per_second,
                    "time_to_crack_8char": r.time_to_crack_8char,
                }
                for r in results
            ],
        }
        return results

    def _show_report(self, results: list[BenchmarkResult]) -> None:
        """Exibe tabela de resultados e análise."""
        # Tabela principal
        table = Table(title="📊 Resultados do Benchmark", border_style="green", show_lines=True)
        table.add_column("Algoritmo", style="bold cyan", no_wrap=True)
        table.add_column("Iterações", style="white", justify="right")
        table.add_column("Tempo total", style="yellow", justify="right")
        table.add_column("Hashes/segundo", style="bold", justify="right")
        table.add_column("Tempo p/ quebrar 8 chars*", style="red", justify="right")
        table.add_column("Segurança p/ senhas", style="bold", justify="center")

        security_colors = {"MD5": "red", "SHA1": "red", "bcrypt (cost=12)": "green", "Argon2id": "green"}
        security_labels = {"MD5": "❌ NÃO USE", "SHA1": "❌ NÃO USE", "bcrypt (cost=12)": "✅ RECOMENDADO", "Argon2id": "✅ RECOMENDADO"}

        for r in results:
            color = security_colors.get(r.algorithm, "white")
            security = security_labels.get(r.algorithm, "?")
            table.add_row(
                r.algorithm,
                f"{r.iterations:,}",
                f"{r.elapsed_seconds:.4f}s",
                f"[{color}]{r.hashes_per_second:,.0f}[/{color}]",
                f"[{color}]{r.time_to_crack_8char}[/{color}]",
                f"[{color}]{security}[/{color}]",
            )

        console.print(table)

        # Comparação relativa
        md5_result = next((r for r in results if r.algorithm == "MD5"), None)
        bcrypt_result = next((r for r in results if "bcrypt" in r.algorithm), None)

        if md5_result and bcrypt_result and bcrypt_result.hashes_per_second > 0:
            ratio = md5_result.hashes_per_second / bcrypt_result.hashes_per_second
            console.print()
            console.print(Panel(
                f"[bold]Análise de Segurança[/bold]\n\n"
                f"• MD5 é [bold red]{ratio:,.0f}x mais rápido[/bold red] que bcrypt neste hardware.\n"
                f"• Isso significa que um atacante testaria [bold red]{ratio:,.0f}x mais senhas[/bold red] por segundo com MD5.\n"
                f"• [green]bcrypt[/green] e [green]Argon2id[/green] tornam ataques de força bruta [bold]praticamente inviáveis[/bold] para senhas fortes.\n\n"
                f"[dim]* Estimativa para charset lowercase+digits (36 chars), senha de 8 caracteres.[/dim]\n"
                f"[dim]  GPU pode ser 100-1000x mais rápida que CPU para MD5/SHA1.[/dim]\n"
                f"[dim]  Recomendação atual: Argon2id (PHC), bcrypt (cost≥12), ou scrypt.[/dim]",
                border_style="green",
                title="🔐 Conclusão",
            ))

        logger.info("Benchmark concluído: %d algoritmos testados", len(results))

    def get_stats(self) -> dict:
        """Retorna estatísticas da última execução (para --stats-json)."""
        return getattr(self, "_last_stats", {})
