#!/usr/bin/env python3
"""
PyCrackLab - Educational Password Cracking Tool
================================================
Uso exclusivamente educacional. Nunca use em sistemas sem autorização.
"""

import argparse
import sys
import logging
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from cracker.brute import BruteForceAttack
from cracker.wordlist import WordlistAttack
from cracker.hash_cracker import HashCracker
from utils.benchmark import Benchmark

console = Console()


# ─────────────────────────────────────────────
# Banner & Aviso Ético
# ─────────────────────────────────────────────

def show_banner() -> None:
    """Exibe banner e aviso ético obrigatório."""
    banner = Text()
    banner.append("  ██████╗ ██╗   ██╗ ██████╗██████╗  █████╗  ██████╗██╗  ██╗\n", style="bold red")
    banner.append("  ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝\n", style="bold red")
    banner.append("  ██████╔╝ ╚████╔╝ ██║     ██████╔╝███████║██║     █████╔╝ \n", style="bold yellow")
    banner.append("  ██╔═══╝   ╚██╔╝  ██║     ██╔══██╗██╔══██║██║     ██╔═██╗ \n", style="bold yellow")
    banner.append("  ██║        ██║   ╚██████╗██║  ██║██║  ██║╚██████╗██║  ██╗\n", style="bold green")
    banner.append("  ╚═╝        ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝\n", style="bold green")
    banner.append("              LAB  —  Educational Password Cracker v1.1\n", style="dim")

    console.print(Panel(banner, border_style="bold blue"))

    warning = (
        "[bold red]⚠  AVISO ÉTICO / ETHICAL WARNING[/bold red]\n\n"
        "Esta ferramenta foi desenvolvida [bold]EXCLUSIVAMENTE para fins educacionais[/bold].\n"
        "Use apenas em sistemas, hashes e senhas [bold green]que você possui ou tem autorização[/bold green].\n"
        "O uso não autorizado contra sistemas de terceiros é [bold red]ilegal[/bold red] e antiético.\n\n"
        "[dim]This tool is for EDUCATIONAL PURPOSES ONLY. Unauthorized use is illegal.[/dim]"
    )
    console.print(Panel(warning, border_style="bold red", padding=(1, 2)))
    console.print()


# ─────────────────────────────────────────────
# CLI — argparse
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pycracklab",
        description="PyCrackLab — Educational Password Cracking Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  # Brute force single-thread
  python main.py brute --target abc --charset lowercase --max-len 4

  # Brute force com multiprocessing (contorna GIL)
  python main.py brute --target abc --charset lowercase --max-len 4 --mode process --workers 4

  # Wordlist attack single
  python main.py wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/common.txt

  # Wordlist attack com multiprocessing
  python main.py wordlist --hash 5f4dcc3b5aa765d61d8327deb882cf99 --wordlist wordlists/common.txt --workers 4

  # Hash cracking automático
  python main.py hash --hash "$2b$12$..." --wordlist wordlists/rockyou_small.txt

  # Benchmark comparativo
  python main.py benchmark --password "test123"
        """,
    )

    parser.add_argument("--log", action="store_true", help="Habilita logging detalhado")
    parser.add_argument("--log-file", default="pycracklab.log", help="Arquivo de log")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── Brute Force ──────────────────────────
    brute_parser = subparsers.add_parser("brute", help="Ataque de força bruta")
    brute_parser.add_argument("--target", required=True, help="Senha alvo em texto claro")
    brute_parser.add_argument(
        "--charset",
        choices=["lowercase", "uppercase", "digits", "special", "all"],
        default="lowercase",
        help="Conjunto de caracteres a usar",
    )
    brute_parser.add_argument("--custom-charset", help="Charset personalizado (ex: 'abc123')")
    brute_parser.add_argument("--min-len", type=int, default=1, help="Comprimento mínimo (default: 1)")
    brute_parser.add_argument("--max-len", type=int, default=6, help="Comprimento máximo (default: 6)")
    brute_parser.add_argument("--threads", type=int, default=1, help="Número de threads/workers (default: 1)")
    brute_parser.add_argument(
        "--mode",
        choices=["single", "thread", "process"],
        default="single",
        help="Modo de execução: single (default), thread (multi-thread), process (multiprocessing, contorna GIL)",
    )
    # Alias --workers para --threads (mais intuitivo com --mode process)
    brute_parser.add_argument("--workers", type=int, dest="threads", help="Alias para --threads")

    # ── Wordlist ─────────────────────────────
    wl_parser = subparsers.add_parser("wordlist", help="Ataque por wordlist")
    wl_parser.add_argument("--hash", required=True, dest="hash_value", help="Hash alvo")
    wl_parser.add_argument("--wordlist", required=True, help="Caminho para wordlist")
    wl_parser.add_argument("--hash-type", choices=["md5", "sha1", "bcrypt", "auto"], default="auto")
    wl_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Workers para multiprocessing (default: 1 = single-thread). Use > 1 para ativar Pool.",
    )
    wl_parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Palavras por chunk enviado a cada worker (default: 500)",
    )

    # ── Hash Cracker ─────────────────────────
    hash_parser = subparsers.add_parser("hash", help="Hash cracking com detecção automática")
    hash_parser.add_argument("--hash", required=True, dest="hash_value", help="Hash alvo")
    hash_parser.add_argument("--wordlist", required=True, help="Caminho para wordlist")

    # ── Benchmark ────────────────────────────
    bench_parser = subparsers.add_parser("benchmark", help="Benchmark de performance de hashing")
    bench_parser.add_argument("--password", default="benchmark_test", help="Senha de teste")
    bench_parser.add_argument("--iterations", type=int, default=100_000, help="Iterações por algoritmo")

    return parser


# ─────────────────────────────────────────────
# Setup logging
# ─────────────────────────────────────────────

def setup_logging(enabled: bool, log_file: str) -> None:
    if not enabled:
        logging.disable(logging.CRITICAL)
        return
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("pycracklab").info("Logging habilitado → %s", log_file)


# ─────────────────────────────────────────────
# Dispatch de comandos
# ─────────────────────────────────────────────

def run_brute(args: argparse.Namespace) -> None:
    attack = BruteForceAttack(
        target=args.target,
        charset_name=args.charset,
        custom_charset=args.custom_charset,
        min_len=args.min_len,
        max_len=args.max_len,
        num_threads=args.threads,
        mode=args.mode,
    )
    attack.run()


def run_wordlist(args: argparse.Namespace) -> None:
    attack = WordlistAttack(
        hash_value=args.hash_value,
        wordlist_path=args.wordlist,
        hash_type=args.hash_type,
        num_workers=args.workers,
        chunk_size=args.chunk_size,
    )
    attack.run()


def run_hash(args: argparse.Namespace) -> None:
    cracker = HashCracker(
        hash_value=args.hash_value,
        wordlist_path=args.wordlist,
    )
    cracker.run()


def run_benchmark(args: argparse.Namespace) -> None:
    bench = Benchmark(password=args.password, iterations=args.iterations)
    bench.run()


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

def main() -> None:
    show_banner()
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(args.log, args.log_file)

    dispatch = {
        "brute": run_brute,
        "wordlist": run_wordlist,
        "hash": run_hash,
        "benchmark": run_benchmark,
    }

    try:
        dispatch[args.command](args)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚡ Interrompido pelo usuário.[/bold yellow]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[bold red]❌ Erro inesperado:[/bold red] {exc}")
        logging.exception("Erro não tratado")
        sys.exit(1)


if __name__ == "__main__":
    main()
