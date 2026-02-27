"""
Hashed CLI - Command Line Interface for AI Agent Governance

Professional CLI tool for managing identities, policies, and agents
without needing access to the web dashboard.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich import box

from hashed import HashedCore, HashedConfig, load_or_create_identity
from hashed.identity import IdentityManager
from hashed.guard import PermissionError
from hashed.templates import render_agent_script, FRAMEWORKS, FRAMEWORK_LABELS, FRAMEWORK_INSTALL

# Initialize Typer app
app = typer.Typer(
    name="hashed",
    help="🔐 Hashed - AI Agent Governance & Security CLI",
    add_completion=False,
)

# Rich console for beautiful output
console = Console()

# Credentials directory
CREDENTIALS_DIR = Path.home() / ".hashed"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"

# Sub-commands
identity_app = typer.Typer(help="🔑 Manage agent identities")
policy_app = typer.Typer(help="🛡️  Manage policies")
agent_app = typer.Typer(help="🤖 Manage agents")
logs_app = typer.Typer(help="📝 View audit logs")

app.add_typer(identity_app, name="identity")
app.add_typer(policy_app, name="policy")
app.add_typer(agent_app, name="agent")
app.add_typer(logs_app, name="logs")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_config() -> HashedConfig:
    """Load configuration from environment."""
    return HashedConfig()


def success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


# ============================================================================
# MAIN COMMANDS
# ============================================================================

def _to_snake_case(name: str) -> str:
    """Convert 'My Agent Name' to 'my_agent_name'."""
    # Replace non-alphanumeric with spaces, then join with underscores
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    return re.sub(r'\s+', '_', cleaned.strip()).lower()


@app.command()
def init(
    name: str = typer.Option(..., "--name", "-n", help="Agent name"),
    agent_type: str = typer.Option("general", "--type", "-t", help="Agent type"),
    framework: str = typer.Option(
        "plain",
        "--framework", "--fw",
        help=f"AI framework: {', '.join(FRAMEWORKS)}",
        show_default=True,
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive", "-i",
        help="Add interactive REPL loop (chat mode in terminal)",
    ),
    create_config: bool = typer.Option(True, "--config/--no-config", help="Create .env config file"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """
    🚀 Initialize a new Hashed agent.

    Creates identity, configuration, and an agent script for your chosen framework.
    Each agent gets its own unique identity file and script.

    Examples:
        hashed init --name "Support Bot" --type assistant
        hashed init --name "Payment Agent" --type finance --framework langchain
        hashed init --name "Research Agent" --type analyst --framework crewai --interactive
        hashed init --name "AWS Agent" --type cloud --framework strands
        hashed init --name "Multi Agent" --type orchestrator --framework autogen --interactive
    """
    # Validate framework
    if framework not in FRAMEWORKS:
        error(f"Unknown framework '{framework}'. Choose from: {', '.join(FRAMEWORKS)}")
        raise typer.Exit(1)

    fw_label = FRAMEWORK_LABELS[framework]
    console.print(Panel.fit(
        f"[bold cyan]Hashed Agent Initialization[/bold cyan]\n"
        f"[dim]Framework: {fw_label}{'  ·  Interactive' if interactive else ''}[/dim]",
        border_style="cyan"
    ))

    try:
        # Derive file names from agent name
        snake_name = _to_snake_case(name)
        identity_file = f"./secrets/{snake_name}_key.pem"
        script_file = f"{snake_name}.py"

        # Create secrets directory
        secrets_dir = Path("./secrets")
        secrets_dir.mkdir(parents=True, exist_ok=True)
        success(f"Created directory: {secrets_dir}")

        # Create .gitignore for secrets
        gitignore_path = secrets_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("*.pem\n*.key\n")
            success(f"Created .gitignore: {gitignore_path}")

        # Generate or load identity
        password = os.getenv("HASHED_IDENTITY_PASSWORD")
        if not password:
            password = typer.prompt("Enter password for identity encryption", hide_input=True)

        identity = load_or_create_identity(identity_file, password)
        success(f"Identity ready: {identity_file}")

        # Display summary table
        table = Table(show_header=False, box=box.ROUNDED)
        table.add_row("[cyan]Public Key[/cyan]", identity.public_key_hex)
        table.add_row("[cyan]Agent Name[/cyan]", name)
        table.add_row("[cyan]Agent Type[/cyan]", agent_type)
        table.add_row("[cyan]Framework[/cyan]", fw_label)
        table.add_row("[cyan]Interactive[/cyan]", "✓ Yes" if interactive else "No")
        table.add_row("[cyan]Identity[/cyan]", identity_file)
        table.add_row("[cyan]Script[/cyan]", script_file)
        console.print(table)

        # Create .env file if requested
        if create_config:
            env_file = Path(".env")
            if not env_file.exists():
                env_content = f"# Hashed Configuration\n"
                env_content += f"HASHED_BACKEND_URL=http://localhost:8000\n"
                env_content += f"HASHED_API_KEY=your_api_key_here\n"
                env_content += f"HASHED_IDENTITY_PASSWORD={password}\n"
                if framework in ("langchain", "crewai", "autogen"):
                    env_content += f"OPENAI_API_KEY=your_openai_key_here\n"
                    env_content += f"OPENAI_MODEL=gpt-4o-mini\n"
                if framework == "strands":
                    env_content += f"AWS_REGION=us-east-1\n"
                    env_content += f"BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0\n"
                env_file.write_text(env_content)
                success(f"Created configuration: {env_file}")
                warning("⚠️  Update HASHED_API_KEY in .env (from: hashed whoami)")
            else:
                info(".env file already exists, skipping")

        # Create agent script
        script_path = Path(script_file)
        if script_path.exists() and not force:
            overwrite = typer.confirm(f"  {script_file} already exists. Overwrite?", default=False)
            if not overwrite:
                info(f"Skipped {script_file}")
            else:
                _write_agent_script(script_path, name, agent_type, identity_file, framework, interactive)
        else:
            _write_agent_script(script_path, name, agent_type, identity_file, framework, interactive)

        # Final instructions
        console.print()
        console.print("[bold green]✓ Agent initialized![/bold green]")

        install_cmd = FRAMEWORK_INSTALL.get(framework)
        console.print(f"\n[cyan]Next steps:[/cyan]")
        step = 1
        if install_cmd:
            console.print(f"  {step}. Install deps: [bold]{install_cmd}[/bold]")
            step += 1
        console.print(f"  {step}. Update .env with your API keys")
        step += 1
        console.print(f"  {step}. Add policies: [bold]hashed policy add <tool> --allow --agent \"{name}\"[/bold]")
        step += 1
        console.print(f"  {step}. Run: [bold]python3 {script_file}[/bold]")
        step += 1
        console.print(f"  {step}. View logs: [bold]hashed logs list[/bold]")

    except Exception as e:
        error(f"Initialization failed: {e}")
        raise typer.Exit(1)


def _write_agent_script(
    path: Path,
    name: str,
    agent_type: str,
    identity_file: str,
    framework: str = "plain",
    interactive: bool = False,
) -> None:
    """Write the agent template script using the templates module."""
    snake_name = _to_snake_case(name)

    # Load policies for this agent
    policies = _load_policies()
    agent_pols = policies.get("agents", {}).get(snake_name, {})
    global_pols = policies.get("global", {})

    content = render_agent_script(
        framework=framework,
        name=name,
        agent_type=agent_type,
        identity_file=identity_file,
        agent_pols=agent_pols,
        global_pols=global_pols,
        interactive=interactive,
    )

    path.write_text(content)
    success(f"Created agent script: {path}")

    fw_label = FRAMEWORK_LABELS.get(framework, framework)
    info(f"  Framework: {fw_label}")
    if interactive:
        info(f"  Mode: Interactive (REPL)")

    total_pols = len(agent_pols) + len(global_pols)
    if total_pols > 0:
        info(f"  Generated {total_pols} @core.guard() tool(s) from policies")
    else:
        info(f"  No policies found → example tool generated")
        info(f"  Add policies: hashed policy add <tool> --allow --agent \"{name}\"")


@app.command()
def version():
    """📦 Show Hashed version."""
    console.print("[cyan]Hashed SDK[/cyan] version [green]0.2.0[/green]")


# ============================================================================
# IDENTITY COMMANDS
# ============================================================================

@identity_app.command("create")
def identity_create(
    output: str = typer.Option("./secrets/agent_key.pem", "--output", "-o", help="Output file path"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Encryption password"),
):
    """
    🔑 Create a new cryptographic identity.
    
    Generates Ed25519 keypair and saves encrypted to file.
    """
    try:
        # Get password
        if not password:
            password = typer.prompt("Enter encryption password", hide_input=True)
            confirm = typer.prompt("Confirm password", hide_input=True)
            if password != confirm:
                error("Passwords don't match")
                raise typer.Exit(1)
        
        # Create directory
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        
        # Generate identity
        identity = load_or_create_identity(output, password)
        
        success(f"Identity created: {output}")
        console.print(f"\n[cyan]Public Key:[/cyan] {identity.public_key_hex}")
        warning("⚠️  Keep this file secure and never commit to git!")
        
    except Exception as e:
        error(f"Failed to create identity: {e}")
        raise typer.Exit(1)


@identity_app.command("show")
def identity_show(
    identity_file: str = typer.Option("./secrets/agent_key.pem", "--file", "-f", help="Identity file path"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Decryption password"),
):
    """
    👁️  Show identity information.
    
    Displays public key and other identity details.
    """
    try:
        # Get password
        if not password:
            password = os.getenv("HASHED_IDENTITY_PASSWORD")
            if not password:
                password = typer.prompt("Enter decryption password", hide_input=True)
        
        # Load identity
        identity = load_or_create_identity(identity_file, password)
        
        # Display
        table = Table(title="Identity Information", box=box.ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("File", identity_file)
        table.add_row("Public Key", identity.public_key_hex)
        table.add_row("Algorithm", "Ed25519")
        
        console.print(table)
        
    except Exception as e:
        error(f"Failed to load identity: {e}")
        raise typer.Exit(1)


@identity_app.command("sign")
def identity_sign(
    message: str = typer.Argument(..., help="Message to sign"),
    identity_file: str = typer.Option("./secrets/agent_key.pem", "--file", "-f", help="Identity file"),
):
    """
    ✍️  Sign a message with identity.
    
    Creates cryptographic signature for verification.
    """
    try:
        password = os.getenv("HASHED_IDENTITY_PASSWORD")
        if not password:
            password = typer.prompt("Enter password", hide_input=True)
        
        identity = load_or_create_identity(identity_file, password)
        signature = identity.sign_message(message)
        
        console.print(f"\n[cyan]Message:[/cyan] {message}")
        console.print(f"[cyan]Signature:[/cyan] {signature.hex()}")
        
    except Exception as e:
        error(f"Failed to sign: {e}")
        raise typer.Exit(1)


# ============================================================================
# POLICY HELPERS
# ============================================================================

POLICY_FILE = ".hashed_policies.json"


def _load_policies(config_file: str = POLICY_FILE) -> dict:
    """Load policy file with global + per-agent structure."""
    config_path = Path(config_file)
    if config_path.exists():
        data = json.loads(config_path.read_text())
        # Migrate old flat format → new structure
        if "global" not in data and "agents" not in data:
            return {"global": data, "agents": {}}
        return data
    return {"global": {}, "agents": {}}


def _save_policies(policies: dict, config_file: str = POLICY_FILE) -> None:
    """Save policy file."""
    Path(config_file).write_text(json.dumps(policies, indent=2))


def _resolve_policy(policies: dict, tool_name: str, agent_name: Optional[str] = None) -> Optional[dict]:
    """Resolve a policy: agent-specific first, then global fallback."""
    if agent_name:
        snake = _to_snake_case(agent_name)
        agent_policies = policies.get("agents", {}).get(snake, {})
        if tool_name in agent_policies:
            return agent_policies[tool_name]
    # Fallback to global
    return policies.get("global", {}).get(tool_name)


# ============================================================================
# POLICY COMMANDS
# ============================================================================

@policy_app.command("add")
def policy_add(
    tool_name: str = typer.Argument(..., help="Tool/operation name"),
    allowed: bool = typer.Option(True, "--allow/--deny", help="Allow or deny"),
    max_amount: Optional[float] = typer.Option(None, "--max-amount", "-m", help="Maximum amount"),
    agent_name: Optional[str] = typer.Option(None, "--agent", help="Agent name (omit for global)"),
    config_file: str = typer.Option(POLICY_FILE, "--config", "-c", help="Policy config file"),
):
    """
    ➕ Add a policy rule (global or per-agent).
    
    Examples:
        hashed policy add send_email --allow                                  # Global
        hashed policy add process_payment --allow -m 500 --agent payment_agent
        hashed policy add delete_data --deny --agent support_bot
    """
    try:
        policies = _load_policies(config_file)
        
        entry = {
            "allowed": allowed,
            "max_amount": max_amount,
            "created_at": datetime.now().isoformat()
        }
        
        if agent_name:
            snake = _to_snake_case(agent_name)
            if snake not in policies["agents"]:
                policies["agents"][snake] = {}
            policies["agents"][snake][tool_name] = entry
            scope = f"agent:{snake}"
        else:
            policies["global"][tool_name] = entry
            scope = "global"
        
        _save_policies(policies, config_file)
        
        success(f"Policy added: {tool_name} ({scope})")
        console.print(f"  Allowed: [{'green' if allowed else 'red'}]{allowed}[/]")
        if max_amount is not None:
            console.print(f"  Max Amount: [cyan]{max_amount}[/cyan]")
        
    except Exception as e:
        error(f"Failed to add policy: {e}")
        raise typer.Exit(1)


@policy_app.command("list")
def policy_list(
    agent_name: Optional[str] = typer.Option(None, "--agent", "-a", help="Filter by agent"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table/json)"),
    config_file: str = typer.Option(POLICY_FILE, "--config", "-c", help="Policy config file"),
):
    """
    📋 List policies (all, global, or per-agent).
    
    Examples:
        hashed policy list                    # All policies
        hashed policy list -a payment_agent   # Only payment_agent
    """
    try:
        policies = _load_policies(config_file)
        
        if output_format == "json":
            console.print_json(data=policies)
            return
        
        global_policies = policies.get("global", {})
        agent_policies = policies.get("agents", {})
        
        has_any = False
        
        # Show global policies
        if global_policies and not agent_name:
            has_any = True
            table = Table(title="🌐 Global Policies", box=box.ROUNDED)
            table.add_column("Tool", style="cyan")
            table.add_column("Allowed", style="bold")
            table.add_column("Max Amount", style="yellow")
            table.add_column("Created", style="dim")
            
            for tool, pol in global_policies.items():
                _add_policy_row(table, tool, pol)
            console.print(table)
        
        # Show agent policies
        agents_to_show = {}
        if agent_name:
            snake = _to_snake_case(agent_name)
            if snake in agent_policies:
                agents_to_show = {snake: agent_policies[snake]}
            else:
                warning(f"No policies for agent '{agent_name}'")
                return
        else:
            agents_to_show = agent_policies
        
        for agent_key, tools in agents_to_show.items():
            if tools:
                has_any = True
                table = Table(title=f"🤖 Agent: {agent_key}", box=box.ROUNDED)
                table.add_column("Tool", style="cyan")
                table.add_column("Allowed", style="bold")
                table.add_column("Max Amount", style="yellow")
                table.add_column("Created", style="dim")
                
                for tool, pol in tools.items():
                    _add_policy_row(table, tool, pol)
                console.print(table)
        
        if not has_any:
            warning("No policies found. Add with: hashed policy add <tool> --allow")
        
    except Exception as e:
        error(f"Failed to list policies: {e}")
        raise typer.Exit(1)


def _add_policy_row(table: Table, tool_name: str, policy: dict) -> None:
    """Add a formatted row to a policy table."""
    allowed = "✓ Yes" if policy["allowed"] else "✗ No"
    style = "green" if policy["allowed"] else "red"
    max_amt = str(policy.get("max_amount")) if policy.get("max_amount") is not None else "-"
    created = policy.get("created_at", "-")[:10]
    table.add_row(tool_name, f"[{style}]{allowed}[/]", max_amt, created)


@policy_app.command("remove")
def policy_remove(
    tool_name: str = typer.Argument(..., help="Tool/operation name"),
    agent_name: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent name (omit for global)"),
    config_file: str = typer.Option(POLICY_FILE, "--config", "-c", help="Policy config file"),
):
    """
    ➖ Remove a policy rule.
    
    Examples:
        hashed policy remove send_email               # Remove global
        hashed policy remove process_payment -a pay    # Remove from agent
    """
    try:
        policies = _load_policies(config_file)
        
        if agent_name:
            snake = _to_snake_case(agent_name)
            agent_pols = policies.get("agents", {}).get(snake, {})
            if tool_name not in agent_pols:
                error(f"Policy not found: {tool_name} (agent: {snake})")
                raise typer.Exit(1)
            del policies["agents"][snake][tool_name]
            if not policies["agents"][snake]:
                del policies["agents"][snake]
        else:
            if tool_name not in policies.get("global", {}):
                error(f"Global policy not found: {tool_name}")
                raise typer.Exit(1)
            del policies["global"][tool_name]
        
        _save_policies(policies, config_file)
        scope = f"agent:{_to_snake_case(agent_name)}" if agent_name else "global"
        success(f"Policy removed: {tool_name} ({scope})")
        
    except Exception as e:
        error(f"Failed to remove policy: {e}")
        raise typer.Exit(1)


@policy_app.command("test")
def policy_test(
    tool_name: str = typer.Argument(..., help="Tool to test"),
    agent_name: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent to test as"),
    amount: Optional[float] = typer.Option(None, "--amount", "-m", help="Amount to test"),
    config_file: str = typer.Option(POLICY_FILE, "--config", "-c", help="Policy config file"),
):
    """
    🧪 Test if an operation would be allowed.
    
    Resolves agent-specific first, then falls back to global.
    
    Examples:
        hashed policy test process_payment -a payment_agent -m 200
        hashed policy test delete_data -a support_bot
    """
    try:
        policies = _load_policies(config_file)
        policy = _resolve_policy(policies, tool_name, agent_name)
        
        scope = f"agent:{_to_snake_case(agent_name)}" if agent_name else "global"
        
        if not policy:
            info(f"No policy for '{tool_name}' ({scope}) → default: [green]ALLOWED[/green]")
            return
        
        # Check allowed
        if not policy["allowed"]:
            console.print(f"[red]✗ DENIED[/red] - Policy denies '{tool_name}' ({scope})")
            return
        
        # Check amount
        if amount is not None and policy.get("max_amount") is not None:
            if amount > policy["max_amount"]:
                console.print(f"[red]✗ DENIED[/red] - Amount ${amount} exceeds max ${policy['max_amount']}")
                return
            console.print(f"[green]✓ ALLOWED[/green] - '{tool_name}' permitted (${amount} ≤ ${policy['max_amount']})")
            return
        
        console.print(f"[green]✓ ALLOWED[/green] - '{tool_name}' permitted ({scope})")
        
    except Exception as e:
        error(f"Failed to test policy: {e}")
        raise typer.Exit(1)


# ============================================================================
# POLICY SYNC (push/pull)
# ============================================================================

def _normalize_name(name: str) -> str:
    """Normalize agent name for matching: remove all non-alphanumeric, lowercase."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _get_sync_credentials() -> tuple:
    """Get API key and backend URL for sync, preferring ~/.hashed/credentials.json."""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Priority: credentials.json > .env > HashedConfig
    creds = load_credentials()
    api_key = None
    backend_url = None
    
    if creds:
        api_key = creds.get("api_key")
        backend_url = creds.get("backend_url")
    
    # Fallback to config (env vars)
    if not api_key or not backend_url:
        config = get_config()
        api_key = api_key or config.api_key
        backend_url = backend_url or config.backend_url
    
    return api_key, backend_url


@policy_app.command("push")
def policy_push(
    config_file: str = typer.Option(POLICY_FILE, "--config", "-c", help="Policy config file"),
):
    """
    ⬆️  Push local policies to backend (JSON → Supabase).
    
    Reads .hashed_policies.json and syncs all policies to the backend.
    Uses credentials from ~/.hashed/credentials.json (from hashed login).
    
    Example:
        hashed policy push
    """
    async def _push():
        try:
            import httpx
            
            api_key, backend_url = _get_sync_credentials()
            if not backend_url or not api_key:
                error("No credentials found. Run: hashed login")
                raise typer.Exit(1)
            
            info(f"Using backend: {backend_url}")
            
            policies = _load_policies(config_file)
            headers = {"X-API-KEY": api_key}
            pushed = 0
            errors_count = 0
            
            async with httpx.AsyncClient(timeout=30) as client:
                # Get existing agents from backend (normalized name → agent_id)
                agents_resp = await client.get(
                    f"{backend_url}/v1/agents", headers=headers
                )
                if not agents_resp.is_success:
                    error(f"Failed to fetch agents: {agents_resp.status_code}")
                    error("Check your credentials: hashed whoami")
                    raise typer.Exit(1)
                
                # Build normalized agent map for flexible matching
                agent_map = {}  # normalized_name → agent_id
                agent_display = {}  # normalized_name → original name
                for a in agents_resp.json().get("agents", []):
                    norm = _normalize_name(a["name"])
                    agent_map[norm] = a["id"]
                    agent_display[norm] = a["name"]
                
                # Push global policies (agent_id = None)
                for tool_name, pol in policies.get("global", {}).items():
                    try:
                        resp = await client.post(
                            f"{backend_url}/v1/policies",
                            headers=headers,
                            json={
                                "tool_name": tool_name,
                                "allowed": pol["allowed"],
                                "max_amount": pol.get("max_amount"),
                                "metadata": {"source": "cli_push"}
                            }
                        )
                        if resp.is_success:
                            pushed += 1
                            success(f"  ✓ {tool_name} (global)")
                        else:
                            warning(f"  ⚠ {tool_name} (global) - {resp.status_code}: may already exist")
                            pushed += 1
                    except Exception as e:
                        error(f"  ✗ {tool_name} (global): {e}")
                        errors_count += 1
                
                # Push agent-specific policies (fuzzy name matching)
                for agent_key, tools in policies.get("agents", {}).items():
                    norm_key = _normalize_name(agent_key)
                    agent_id = agent_map.get(norm_key)
                    
                    if not agent_id:
                        # Show available agents for debugging
                        available = [f"'{v}'" for v in agent_display.values()]
                        warning(f"  Agent '{agent_key}' not found on backend. Skipping.")
                        if available:
                            info(f"    Available agents: {', '.join(available)}")
                        else:
                            info(f"    No agents registered. Run the agent first.")
                        continue
                    
                    matched_name = agent_display.get(norm_key, agent_key)
                    info(f"  Matched '{agent_key}' → '{matched_name}'")
                    
                    for tool_name, pol in tools.items():
                        try:
                            resp = await client.post(
                                f"{backend_url}/v1/policies",
                                params={"agent_id": agent_id},
                                headers=headers,
                                json={
                                    "tool_name": tool_name,
                                    "allowed": pol["allowed"],
                                    "max_amount": pol.get("max_amount"),
                                    "metadata": {"source": "cli_push"}
                                }
                            )
                            if resp.is_success:
                                pushed += 1
                                success(f"  ✓ {tool_name} (agent:{agent_key})")
                            else:
                                warning(f"  ⚠ {tool_name} (agent:{agent_key}) - {resp.status_code}")
                                pushed += 1
                        except Exception as e:
                            error(f"  ✗ {tool_name} (agent:{agent_key}): {e}")
                            errors_count += 1
            
            console.print()
            if pushed > 0:
                success(f"Pushed {pushed} policies to backend")
            if errors_count > 0:
                error(f"{errors_count} policies failed")
                
        except Exception as e:
            error(f"Push failed: {e}")
            raise typer.Exit(1)
    
    console.print(Panel.fit("[bold cyan]Policy Push → Backend[/bold cyan]", border_style="cyan"))
    asyncio.run(_push())


@policy_app.command("pull")
def policy_pull(
    config_file: str = typer.Option(POLICY_FILE, "--config", "-c", help="Policy config file"),
):
    """
    ⬇️  Pull policies from backend to local JSON (Supabase → JSON).
    
    Downloads all policies from backend and saves to .hashed_policies.json
    
    Example:
        hashed policy pull
    """
    async def _pull():
        try:
            import httpx
            
            api_key, backend_url = _get_sync_credentials()
            if not backend_url or not api_key:
                error("No credentials found. Run: hashed login")
                raise typer.Exit(1)
            
            headers = {"X-API-KEY": api_key}
            
            async with httpx.AsyncClient(timeout=30) as client:
                # Get all policies
                pol_resp = await client.get(
                    f"{backend_url}/v1/policies", headers=headers
                )
                if not pol_resp.is_success:
                    error(f"Failed to fetch policies: {pol_resp.status_code}")
                    raise typer.Exit(1)
                
                backend_policies = pol_resp.json().get("policies", [])
                
                # Get agents for name mapping
                agents_resp = await client.get(
                    f"{backend_url}/v1/agents", headers=headers
                )
                agent_id_to_name = {}
                if agents_resp.is_success:
                    for a in agents_resp.json().get("agents", []):
                        agent_id_to_name[a["id"]] = _to_snake_case(a["name"])
            
            # Build local structure
            local = {"global": {}, "agents": {}}
            
            for pol in backend_policies:
                entry = {
                    "allowed": pol["allowed"],
                    "max_amount": pol.get("max_amount"),
                    "created_at": pol.get("created_at", datetime.now().isoformat())
                }
                
                if pol.get("agent_id"):
                    agent_snake = agent_id_to_name.get(pol["agent_id"], "unknown")
                    if agent_snake not in local["agents"]:
                        local["agents"][agent_snake] = {}
                    local["agents"][agent_snake][pol["tool_name"]] = entry
                else:
                    local["global"][pol["tool_name"]] = entry
            
            _save_policies(local, config_file)
            
            global_count = len(local["global"])
            agent_count = sum(len(t) for t in local["agents"].values())
            agents_list = list(local["agents"].keys())
            
            success(f"Pulled {global_count} global + {agent_count} agent policies")
            if agents_list:
                info(f"  Agents: {', '.join(agents_list)}")
            info(f"  Saved to: {config_file}")
            
        except Exception as e:
            error(f"Pull failed: {e}")
            raise typer.Exit(1)
    
    console.print(Panel.fit("[bold cyan]Policy Pull ← Backend[/bold cyan]", border_style="cyan"))
    asyncio.run(_pull())


# ============================================================================
# AGENT COMMANDS
# ============================================================================

@agent_app.command("list")
def agent_list():
    """
    📋 List registered agents (requires backend).
    """
    async def _list():
        try:
            config = get_config()
            
            if not config.backend_url:
                error("Backend URL not configured")
                info("Set HASHED_BACKEND_URL environment variable")
                raise typer.Exit(1)
            
            # Simple HTTP request to backend
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{config.backend_url}/v1/agents",
                    headers={"X-API-KEY": config.api_key or ""}
                )
                
                if not response.is_success:
                    error(f"Failed to fetch agents: {response.status_code}")
                    raise typer.Exit(1)
                
                data = response.json()
                agents = data.get("agents", [])
                
                if not agents:
                    info("No agents registered")
                    return
                
                table = Table(title="Registered Agents", box=box.ROUNDED)
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="yellow")
                table.add_column("Public Key", style="dim")
                table.add_column("Status", style="bold")
                
                for agent in agents:
                    status = "🟢 Active" if agent.get("status") == "active" else "🔴 Inactive"
                    table.add_row(
                        agent["name"],
                        agent.get("agent_type", "-"),
                        agent["public_key"][:16] + "...",
                        status
                    )
                
                console.print(table)
                
        except Exception as e:
            error(f"Failed to list agents: {e}")
            raise typer.Exit(1)
    
    asyncio.run(_list())


@agent_app.command("delete")
def agent_delete(
    name: str = typer.Argument(..., help="Agent name to delete"),
    agent_id: Optional[str] = typer.Option(None, "--id", help="Agent ID (use instead of name)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    🗑️  Delete an agent from the backend (deregisters it).

    Finds the agent by name (or --id) and permanently removes it from
    the Hashed backend. The local .pem identity file is NOT deleted.

    Examples:
        hashed agent delete "Research Agent 4"
        hashed agent delete "Research Agent 4" --yes
        hashed agent delete --id abc123-...
    """
    async def _delete():
        try:
            config = get_config()

            if not config.backend_url:
                error("Backend URL not configured")
                info("Set HASHED_BACKEND_URL environment variable")
                raise typer.Exit(1)

            import httpx
            async with httpx.AsyncClient() as client:
                headers = {"X-API-KEY": config.api_key or ""}

                # Resolve agent_id by name if not provided directly
                resolved_id = agent_id
                resolved_name = name

                if not resolved_id:
                    # Fetch all agents and find by name
                    resp = await client.get(
                        f"{config.backend_url}/v1/agents",
                        headers=headers,
                    )
                    if not resp.is_success:
                        error(f"Failed to fetch agents: {resp.status_code}")
                        raise typer.Exit(1)

                    agents = resp.json().get("agents", [])
                    match = next(
                        (a for a in agents if a["name"].lower() == name.lower()),
                        None,
                    )
                    if not match:
                        error(f"No agent named '{name}' found")
                        info("Run 'hashed agent list' to see all agents")
                        raise typer.Exit(1)

                    resolved_id = match["id"]
                    resolved_name = match["name"]

                # Confirmation prompt
                if not yes:
                    console.print(
                        f"\n[bold red]⚠️  This will permanently delete agent:[/bold red] "
                        f"[cyan]{resolved_name}[/cyan] ([dim]{resolved_id}[/dim])"
                    )
                    confirmed = typer.confirm("Are you sure?")
                    if not confirmed:
                        info("Cancelled.")
                        return

                # Call DELETE endpoint
                resp = await client.delete(
                    f"{config.backend_url}/v1/agents/{resolved_id}",
                    headers=headers,
                )

                if resp.status_code == 404:
                    error(f"Agent '{resolved_name}' not found on backend")
                    raise typer.Exit(1)

                if not resp.is_success:
                    error(f"Failed to delete agent: {resp.status_code} - {resp.text}")
                    raise typer.Exit(1)

                console.print(
                    f"\n[bold green]✓[/bold green] Agent [cyan]{resolved_name}[/cyan] deleted successfully"
                )
                info("Note: the local .pem identity file was NOT removed.")

        except typer.Exit:
            raise
        except Exception as e:
            error(f"Failed to delete agent: {e}")
            raise typer.Exit(1)

    asyncio.run(_delete())


# ============================================================================
# LOGS COMMANDS
# ============================================================================

@logs_app.command("list")
def logs_list(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of logs to show"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """
    📝 View recent audit logs (requires backend).
    """
    async def _list():
        try:
            config = get_config()
            
            if not config.backend_url:
                error("Backend URL not configured")
                raise typer.Exit(1)
            
            import httpx
            async with httpx.AsyncClient() as client:
                # Build params dict
                params = {"limit": limit}
                if status:
                    params["status"] = status
                
                response = await client.get(
                    f"{config.backend_url}/v1/logs",
                    params=params,
                    headers={"X-API-KEY": config.api_key or ""}
                )
                
                if not response.is_success:
                    error(f"Failed to fetch logs: {response.status_code}")
                    raise typer.Exit(1)
                
                data = response.json()
                logs = data.get("logs", [])
                
                if not logs:
                    info("No logs found")
                    return
                
                table = Table(title=f"Recent Logs (last {limit})", box=box.ROUNDED)
                table.add_column("Time", style="dim")
                table.add_column("Tool", style="cyan")
                table.add_column("Status", style="bold")
                table.add_column("Agent", style="yellow")
                
                for log in logs:
                    timestamp = log["timestamp"][:19].replace("T", " ")
                    tool = log["tool_name"]
                    log_status = log["status"]
                    agent = log.get("agent_name", "Unknown")[:20]
                    
                    status_emoji = {
                        "success": "✓",
                        "denied": "✗",
                        "error": "⚠"
                    }.get(log_status, "•")
                    
                    status_color = {
                        "success": "green",
                        "denied": "red",
                        "error": "yellow"
                    }.get(log_status, "white")
                    
                    table.add_row(
                        timestamp,
                        tool,
                        f"[{status_color}]{status_emoji} {log_status}[/]",
                        agent
                    )
                
                console.print(table)
                
        except Exception as e:
            error(f"Failed to list logs: {e}")
            raise typer.Exit(1)
    
    asyncio.run(_list())


# ============================================================================
# CREDENTIALS HELPERS
# ============================================================================

def save_credentials(data: dict) -> None:
    """Save credentials to ~/.hashed/credentials.json"""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    # Restrict file permissions (owner only)
    CREDENTIALS_FILE.chmod(0o600)


def load_credentials() -> Optional[dict]:
    """Load credentials from ~/.hashed/credentials.json"""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        return json.loads(CREDENTIALS_FILE.read_text())
    except Exception:
        return None


def clear_credentials() -> None:
    """Remove credentials file."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


# ============================================================================
# AUTH COMMANDS (Signup, Login, Logout, Whoami)
# ============================================================================

@app.command()
def signup(
    backend_url: str = typer.Option("http://localhost:8000", "--backend", "-b", help="Backend URL"),
):
    """
    📝 Create a new Hashed account and organization.
    
    Signs up, waits for email confirmation, then creates your org + API key.
    """
    import httpx
    import time

    console.print(Panel.fit(
        "[bold cyan]Hashed - Create Account[/bold cyan]",
        border_style="cyan"
    ))

    # Gather info
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)
    confirm_password = typer.prompt("Confirm password", hide_input=True)

    if password != confirm_password:
        error("Passwords don't match")
        raise typer.Exit(1)

    if len(password) < 6:
        error("Password must be at least 6 characters")
        raise typer.Exit(1)

    org_name = typer.prompt("Organization name")

    # Step 1: Call signup endpoint
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{backend_url}/v1/auth/signup",
                json={"email": email, "password": password, "org_name": org_name}
            )

            if response.status_code == 409:
                error("Email already registered. Try: hashed login")
                raise typer.Exit(1)

            if not response.is_success:
                detail = response.json().get("detail", "Signup failed")
                error(detail)
                raise typer.Exit(1)

        success("Account created!")
        console.print(f"\n[yellow]📧 Confirmation email sent to [bold]{email}[/bold][/yellow]")
        console.print("   Please check your inbox and click the confirmation link.\n")

    except httpx.ConnectError:
        error(f"Cannot connect to backend at {backend_url}")
        info("Make sure the server is running: python3 server/server.py")
        raise typer.Exit(1)

    # Step 2: Poll for email confirmation
    console.print("[dim]⏳ Waiting for email confirmation... (press Ctrl+C to skip)[/dim]")

    confirmed = False
    try:
        with httpx.Client(timeout=10) as client:
            for i in range(120):  # Wait up to 6 minutes
                time.sleep(3)
                try:
                    check = client.get(
                        f"{backend_url}/v1/auth/check-confirmation",
                        params={"email": email}
                    )
                    if check.is_success and check.json().get("confirmed"):
                        confirmed = True
                        break
                except Exception:
                    pass

                # Show spinner dots
                dots = "." * ((i % 3) + 1)
                console.print(f"\r[dim]   Checking{dots}   [/dim]", end="")

    except KeyboardInterrupt:
        console.print()
        info("Skipped waiting. After confirming your email, run:")
        console.print("  [bold]hashed login[/bold]")
        raise typer.Exit(0)

    if not confirmed:
        console.print()
        warning("Timed out waiting for confirmation.")
        info("After confirming your email, run: [bold]hashed login[/bold]")
        raise typer.Exit(0)

    # Step 3: Email confirmed! Now login to create org + get API key
    console.print()
    success("Email confirmed! ✅")

    try:
        with httpx.Client(timeout=30) as client:
            login_resp = client.post(
                f"{backend_url}/v1/auth/login",
                json={"email": email, "password": password}
            )

            if not login_resp.is_success:
                error("Auto-login failed. Run: hashed login")
                raise typer.Exit(1)

            data = login_resp.json()

        # Save credentials
        creds = {
            "email": email,
            "org_name": data["org_name"],
            "api_key": data["api_key"],
            "org_id": data["org_id"],
            "backend_url": backend_url,
            "created_at": datetime.now().isoformat()
        }
        save_credentials(creds)

        # Show results
        console.print()
        table = Table(title="🎉 Account Ready!", box=box.ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Email", email)
        table.add_row("Organization", data["org_name"])
        table.add_row("API Key", data["api_key"][:25] + "...")
        table.add_row("Credentials", str(CREDENTIALS_FILE))
        console.print(table)

        console.print("\n[bold green]✓ You're all set![/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. hashed init --name \"My Agent\" --type assistant")
        console.print("  2. python3 agent.py")
        console.print("  3. hashed logs list")

    except Exception as e:
        error(f"Setup failed: {e}")
        info("Run: hashed login")
        raise typer.Exit(1)


@app.command()
def login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email address"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Password"),
    backend_url: str = typer.Option("http://localhost:8000", "--backend", "-b", help="Backend URL"),
):
    """
    🔐 Login to your Hashed account.
    
    Authenticates and saves API key to ~/.hashed/credentials.json
    """
    import httpx

    console.print(Panel.fit(
        "[bold cyan]Hashed - Login[/bold cyan]",
        border_style="cyan"
    ))

    # Get credentials
    if not email:
        email = typer.prompt("Email")
    if not password:
        password = typer.prompt("Password", hide_input=True)

    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{backend_url}/v1/auth/login",
                json={"email": email, "password": password}
            )

            if response.status_code == 401:
                error("Invalid email or password")
                raise typer.Exit(1)
            elif response.status_code == 403:
                error("Email not confirmed. Check your inbox for the confirmation link.")
                raise typer.Exit(1)
            elif not response.is_success:
                detail = response.json().get("detail", "Login failed")
                error(detail)
                raise typer.Exit(1)

            data = response.json()

        # Save credentials
        creds = {
            "email": email,
            "org_name": data["org_name"],
            "api_key": data["api_key"],
            "org_id": data["org_id"],
            "backend_url": backend_url,
            "logged_in_at": datetime.now().isoformat()
        }
        save_credentials(creds)

        success("Login successful!")
        table = Table(show_header=False, box=box.ROUNDED)
        table.add_row("[cyan]Email[/cyan]", email)
        table.add_row("[cyan]Organization[/cyan]", data["org_name"])
        table.add_row("[cyan]API Key[/cyan]", data["api_key"][:25] + "...")
        table.add_row("[cyan]Saved to[/cyan]", str(CREDENTIALS_FILE))
        console.print(table)

    except httpx.ConnectError:
        error(f"Cannot connect to backend at {backend_url}")
        info("Make sure the server is running")
        raise typer.Exit(1)


@app.command()
def logout():
    """
    👋 Logout and remove saved credentials.
    """
    if load_credentials():
        clear_credentials()
        success("Logged out. Credentials removed.")
    else:
        info("Not logged in (no credentials found)")


@app.command()
def whoami():
    """
    👤 Show current logged-in user info.
    """
    creds = load_credentials()
    if not creds:
        error("Not logged in. Run: hashed login")
        raise typer.Exit(1)

    table = Table(title="Current Session", box=box.ROUNDED)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Email", creds.get("email", "-"))
    table.add_row("Organization", creds.get("org_name", "-"))
    table.add_row("API Key", creds.get("api_key", "-")[:25] + "...")
    table.add_row("Backend", creds.get("backend_url", "-"))
    table.add_row("Credentials File", str(CREDENTIALS_FILE))
    console.print(table)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
