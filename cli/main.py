"""Painel CLI para administrar a Licensing API.

Uso:
    licensing-cli --help
    licensing-cli login --base-url http://localhost:8000
    licensing-cli licenses create --customer "Empresa XPTO" --max-activations 2
"""
import json
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

CONFIG_DIR = Path.home() / ".config" / "licensing-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

console = Console()

app = typer.Typer(
    help="Painel CLI da Licensing API (licenciamento de software)",
    no_args_is_help=True,
)
admins_app = typer.Typer(help="Gerenciar administradores", no_args_is_help=True)
licenses_app = typer.Typer(help="Gerenciar licencas", no_args_is_help=True)
app.add_typer(admins_app, name="admins")
app.add_typer(licenses_app, name="licenses")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text())


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _new_client() -> httpx.Client:
    cfg = load_config()
    base_url = cfg.get("base_url")
    if not base_url or not cfg.get("token"):
        console.print("[red]Nao logado. Rode: licensing-cli login[/red]")
        raise typer.Exit(1)
    return httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {cfg['token']}"},
        timeout=30,
    )


def call(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        resp = _new_client().request(method, path, **kwargs)
    except httpx.ConnectError:
        console.print("[red]Nao foi possivel conectar na API.[/red] "
                      "Confira o --base-url do login.")
        raise typer.Exit(1)
    if resp.status_code == 401:
        console.print("[red]Sessao expirada. Rode: licensing-cli login[/red]")
        raise typer.Exit(1)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        console.print(f"[red]Erro {resp.status_code}: {detail}[/red]")
        raise typer.Exit(1)
    return resp


def print_license_row(item: dict, show_key: bool = False) -> None:
    table = Table(title=f"Licenca {item['id']}")
    table.add_column("Campo", style="cyan")
    table.add_column("Valor")
    table.add_row("Cliente", item["customer_name"])
    table.add_row("E-mail", item.get("email") or "-")
    table.add_row("Tier", item["tier"])
    table.add_row("Expira em", item.get("expires_at") or "perpétua")
    table.add_row("Max ativacoes", str(item["max_activations"]))
    table.add_row("Revogada", "sim" if item["revoked"] else "nao")
    table.add_row("Criada em", item["created_at"])
    if show_key:
        table.add_row("Chave", item["key"])
    console.print(table)


# --------------------------------------------------------------------------
# sessao
# --------------------------------------------------------------------------

@app.command()
def login(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, confirmation_prompt=False
    ),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
):
    """Faz login e guarda o token da sessao."""
    try:
        resp = httpx.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=30,
        )
    except httpx.ConnectError:
        console.print(f"[red]Nao foi possivel conectar em {base_url}.[/red]")
        raise typer.Exit(1)
    if resp.status_code != 200:
        console.print("[red]Usuario ou senha invalidos.[/red]")
        raise typer.Exit(1)
    save_config({"base_url": base_url, "token": resp.json()["access_token"]})
    console.print(f"[green]Login ok. API: {base_url}[/green]")


@app.command()
def logout():
    """Remove o token salvo localmente."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    console.print("Logout feito.")


@app.command()
def whoami():
    """Mostra o admin logado."""
    resp = call("GET", "/api/v1/auth/me")
    data = resp.json()
    console.print(f"Admin: [bold]{data['username']}[/bold] (id {data['id']})")


# --------------------------------------------------------------------------
# admins
# --------------------------------------------------------------------------

@admins_app.command("create")
def admin_create(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, confirmation_prompt=True
    ),
):
    """Cria um novo administrador."""
    resp = call(
        "POST",
        "/api/v1/admin/admins",
        json={"username": username, "password": password},
    )
    data = resp.json()
    console.print(f"[green]Admin '{data['username']}' criado (id {data['id']}).[/green]")


@admins_app.command("list")
def admin_list():
    """Lista os administradores."""
    resp = call("GET", "/api/v1/admin/admins")
    rows = resp.json()
    table = Table(title="Administradores")
    table.add_column("ID", style="dim")
    table.add_column("Usuario", style="cyan")
    table.add_column("Criado em")
    for row in rows:
        table.add_row(row["id"], row["username"], row["created_at"])
    console.print(table)


@admins_app.command("delete")
def admin_delete(admin_id: str):
    """Exclui um administrador (nao o proprio usuario)."""
    call("DELETE", f"/api/v1/admin/admins/{admin_id}")
    console.print(f"[green]Admin {admin_id} excluido.[/green]")


@admins_app.command("password")
def admin_password(
    admin_id: str,
    password: str = typer.Option(
        ..., prompt=True, hide_input=True, confirmation_prompt=True
    ),
):
    """Troca a senha de um administrador."""
    call("PATCH", f"/api/v1/admin/admins/{admin_id}", json={"password": password})
    console.print(f"[green]Senha do admin {admin_id} atualizada.[/green]")


# --------------------------------------------------------------------------
# licencas
# --------------------------------------------------------------------------

@licenses_app.command("create")
def license_create(
    customer: str = typer.Option(..., prompt=True),
    email: str | None = typer.Option(None),
    tier: str = typer.Option("standard"),
    max_activations: int = typer.Option(1, min=1),
):
    """Emite uma licenca e mostra a chave assinada."""
    resp = call(
        "POST",
        "/api/v1/admin/licenses",
        json={
            "customer_name": customer,
            "email": email,
            "tier": tier,
            "max_activations": max_activations,
        },
    )
    print_license_row(resp.json(), show_key=True)


@licenses_app.command("list")
def license_list():
    """Lista as licencas."""
    resp = call("GET", "/api/v1/admin/licenses")
    rows = resp.json()
    table = Table(title="Licencas")
    table.add_column("ID", style="dim")
    table.add_column("Cliente", style="cyan")
    table.add_column("Tier")
    table.add_column("Max")
    table.add_column("Revogada")
    table.add_column("Criada em")
    for row in rows:
        table.add_row(
            row["id"],
            row["customer_name"],
            row["tier"],
            str(row["max_activations"]),
            "sim" if row["revoked"] else "nao",
            row["created_at"],
        )
    console.print(table)


@licenses_app.command("show")
def license_show(license_id: str):
    """Mostra o detalhe de uma licenca (sem a chave)."""
    resp = call("GET", f"/api/v1/admin/licenses/{license_id}")
    print_license_row(resp.json())


@licenses_app.command("key")
def license_key(license_id: str):
    """Mostra a chave assinada de uma licenca."""
    resp = call("GET", f"/api/v1/admin/licenses/{license_id}/key")
    print(resp.json()["key"])


@licenses_app.command("revoke")
def license_revoke(
    license_id: str,
    revoke: bool = typer.Option(True, "--revoke/--no-revoke"),
):
    """Revoga ou desrevoga uma licenca."""
    resp = call(
        "PATCH",
        f"/api/v1/admin/licenses/{license_id}",
        json={"revoked": revoke},
    )
    estado = "revogada" if revoke else "desrevogada"
    console.print(f"[green]Licenca {license_id} {estado}.[/green]")
    print_license_row(resp.json())


@licenses_app.command("delete")
def license_delete(license_id: str):
    """Exclui uma licenca (e suas ativacoes)."""
    call("DELETE", f"/api/v1/admin/licenses/{license_id}")
    console.print(f"[green]Licenca {license_id} excluida.[/green]")


@licenses_app.command("activations")
def license_activations(license_id: str):
    """Lista as ativacoes (maquinas) de uma licenca."""
    resp = call("GET", f"/api/v1/admin/licenses/{license_id}/activations")
    rows = resp.json()
    table = Table(title=f"Ativacoes da licenca {license_id}")
    table.add_column("ID", style="dim")
    table.add_column("Maquina", style="cyan")
    table.add_column("Hostname")
    table.add_column("Ativada em")
    table.add_column("Ultima vez")
    table.add_column("Revogada")
    for row in rows:
        table.add_row(
            row["id"],
            row["machine_id"],
            row.get("hostname") or "-",
            row["activated_at"],
            row["last_seen_at"],
            "sim" if row["revoked"] else "nao",
        )
    console.print(table)


@licenses_app.command("revoke-activation")
def license_revoke_activation(license_id: str, activation_id: str):
    """Revoga uma ativacao (libera uma vaga de maquina)."""
    call("DELETE", f"/api/v1/admin/licenses/{license_id}/activations/{activation_id}")
    console.print(f"[green]Ativacao {activation_id} revogada.[/green]")


# --------------------------------------------------------------------------
# operacoes de cliente (publicas)
# --------------------------------------------------------------------------

@app.command()
def activate(
    key: str = typer.Option(..., prompt=True),
    machine: str = typer.Option(..., prompt=True),
    hostname: str | None = typer.Option(None),
):
    """Ativa uma maquina com a chave (como o cliente faria)."""
    resp = call(
        "POST",
        "/api/v1/activate",
        json={"license_key": key, "machine_id": machine, "hostname": hostname},
    )
    data = resp.json()
    console.print(f"[green]Maquina '{data['machine_id']}' ativada (id {data['id']}).[/green]")


@app.command()
def validate(key: str = typer.Option(..., prompt=True)):
    """Valida uma chave no servidor (como o cliente faria)."""
    resp = call("POST", "/api/v1/validate", json={"license_key": key})
    data = resp.json()
    if data["valid"]:
        console.print("[green]Licenca VALIDA.[/green]")
        console.print(f"  Cliente: {data['customer_name']} | Tier: {data['tier']}")
        console.print(f"  Expira: {data.get('expires_at') or 'perpétua'}")
        console.print(f"  Ativacoes ativas: {data['active_activations']}/{data['max_activations']}")
    else:
        console.print(f"[red]Licenca INVALIDA: {data.get('reason')}[/red]")


@app.command()
def stats():
    """Resumo geral (total de licencas e ativacoes)."""
    resp = call("GET", "/api/v1/admin/stats")
    data = resp.json()
    console.print(f"Licencas: [bold]{data['licenses']}[/bold]")
    console.print(f"Ativacoes: [bold]{data['activations']}[/bold]")


if __name__ == "__main__":
    app()
