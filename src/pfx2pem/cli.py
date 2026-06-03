from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from typing import Optional

import typer
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import CertEntry, load_config
from .converter import convert as do_convert, extract_cnpj, load_pfx

app = typer.Typer(
    name="pfx2pem",
    help="Converte certificados PFX para o formato PEM.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"pfx2pem [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True, help="Exibe a versao"
    ),
) -> None:
    pass


@app.command(name="convert")
def convert_cmd(
    pfx_file: Path = typer.Argument(..., help="Arquivo PFX a converter"),
    password: str = typer.Option(..., "--password", "-p", help="Senha do certificado PFX"),
    output: Path = typer.Option(Path("."), "--output", "-o", help="Diretorio de saida"),
    codes: Optional[list[str]] = typer.Option(
        None, "--code", "-c", help="Codigo(s) de entidade para prefixo dos arquivos (pode repetir)"
    ),
) -> None:
    """Converte um unico arquivo PFX para os formatos _key, _cert, _ca e _all PEM."""
    if not pfx_file.exists():
        console.print(f"[red]Arquivo nao encontrado:[/red] {pfx_file}")
        raise typer.Exit(1)

    console.print(Panel(f"[bold cyan]pfx2pem[/bold cyan] {__version__}", expand=False))
    console.print(f"\n[cyan]Arquivo:[/cyan] {pfx_file.name}")

    try:
        _, certificate, _ = load_pfx(pfx_file, password)
    except Exception as exc:
        console.print(f"[red]Erro ao abrir PFX:[/red] {exc}")
        raise typer.Exit(1)

    cnpj = extract_cnpj(certificate)
    prefix_codes = codes if codes else ([cnpj] if cnpj else [pfx_file.stem])

    if cnpj:
        console.print(f"[cyan]CNPJ:[/cyan]   {cnpj}")
    console.print(f"[cyan]Codigos:[/cyan] {', '.join(prefix_codes)}\n")

    try:
        do_convert(
            pfx_file,
            password,
            prefix_codes,
            output,
            log_fn=lambda url: console.print(f"  [dim]Baixando CA cert: {url}[/dim]"),
        )
    except Exception as exc:
        console.print(f"[red]Erro na conversao:[/red] {exc}")
        raise typer.Exit(1)

    _print_output_table(prefix_codes, output)
    console.print(f"\n[green]Concluido.[/green] Arquivos em: {output.resolve()}")


@app.command()
def batch(
    import_dir: Optional[Path] = typer.Argument(None, help="Diretorio com os arquivos PFX (sobrepoe o config)"),
    config_path: Path = typer.Option(
        Path("config.json"), "--config", "-c", help="Caminho do arquivo config.json"
    ),
) -> None:
    """Converte todos os PFX em um diretorio usando o config.json."""
    if not config_path.exists():
        console.print(f"[red]Config nao encontrado:[/red] {config_path}")
        raise typer.Exit(1)

    try:
        cfg = load_config(config_path)
    except Exception as exc:
        console.print(f"[red]Erro ao ler config:[/red] {exc}")
        raise typer.Exit(1)

    src_dir = import_dir or cfg.import_dir
    pfx_files = sorted(src_dir.glob("*.pfx"))

    console.print(Panel(f"[bold cyan]pfx2pem batch[/bold cyan] {__version__}", expand=False))

    if not pfx_files:
        console.print(f"\n[yellow]Nenhum arquivo PFX encontrado em:[/yellow] {src_dir}")
        raise typer.Exit(0)

    console.print(f"\n[cyan]Encontrados {len(pfx_files)} arquivo(s) PFX[/cyan]\n")

    cert_map = cfg.cert_map
    ok = fail = 0

    for pfx in pfx_files:
        console.rule(f"[dim]{pfx.name}[/dim]", style="dim")
        entry = _resolve_entry(pfx, cert_map)

        if not entry:
            console.print(f"  [yellow]Pulando:[/yellow] sem mapeamento no config para {pfx.name}")
            fail += 1
            continue

        console.print(f"  [cyan]CNPJ:[/cyan]   {entry.cnpj}")
        console.print(f"  [cyan]Codigos:[/cyan] {', '.join(entry.codes)}\n")

        try:
            do_convert(
                pfx,
                entry.password,
                entry.codes,
                cfg.export_dir,
                log_fn=lambda url: console.print(f"  [dim]Baixando CA cert: {url}[/dim]"),
            )
            _print_output_table(entry.codes, cfg.export_dir, indent=2)
            console.print(f"  [green]OK[/green]\n")
            ok += 1
        except Exception as exc:
            console.print(f"  [red]Erro:[/red] {exc}\n")
            fail += 1

    console.rule(style="dim")
    console.print(f"\n[bold]Resultado:[/bold] [green]Sucesso: {ok}[/green]  [red]Falha: {fail}[/red]")
    console.print(f"Arquivos em: {cfg.export_dir.resolve()}\n")

    if fail > 0:
        raise typer.Exit(1)


def _print_output_table(codes: list[str], directory: Path, indent: int = 0) -> None:
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Arquivo", style="green")
    table.add_column("Descricao", style="dim")

    suffixes = [
        ("_key.pem", "Chave privada"),
        ("_cert.pem", "Certificado do cliente"),
        ("_ca.pem", "Cadeia CA (intermediarios + raiz)"),
        ("_all.pem", "Certificado + cadeia CA combinados"),
    ]
    for code in codes:
        for suffix, desc in suffixes:
            table.add_row(f"{code}{suffix}", desc)

    console.print(Padding(table, (0, 0, 0, indent)))


def _resolve_entry(pfx: Path, cert_map: dict[str, CertEntry]) -> CertEntry | None:
    if pfx.stem in cert_map:
        return cert_map[pfx.stem]

    for cnpj, entry in cert_map.items():
        try:
            _, certificate, _ = load_pfx(pfx, entry.password)
            found = extract_cnpj(certificate)
            if found and found in cert_map:
                return cert_map[found]
        except Exception:
            continue

    return None
