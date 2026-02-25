"""
Hashed CLI - Command Line Interface for AI Agent Governance

Professional CLI tool for managing identities, policies, and agents
without needing access to the web dashboard.
"""

import asyncio
import json
import os
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

# Initialize Typer app
app = typer.Typer(
    name="hashed",
    help="🔐 Hashed - AI Agent Governance & Security CLI",
    add_completion=False,
)

# Rich console for beautiful output
console = Console()

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

@app.command()
def init(
    name: str = typer.Option(..., "--name", "-n", help="Agent name"),
    agent_type: str = typer.Option("general", "--type", "-t", help="Agent type"),
    identity_file: str = typer.Option("./secrets/agent_key.pem", "--identity", "-i", help="Identity file path"),
    create_config: bool = typer.Option(True, "--config/--no-config", help="Create .env config file"),
):
    """
    🚀 Initialize a new Hashed agent project.
    
    Creates identity, configuration, and project structure.
    """
    console.print(Panel.fit(
        "[bold cyan]Hashed Agent Initialization[/bold cyan]",
        border_style="cyan"
    ))
    
    try:
        # Create secrets directory
        secrets_dir = Path(identity_file).parent
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
        
        # Display public key
        table = Table(show_header=False, box=box.ROUNDED)
        table.add_row("[cyan]Public Key[/cyan]", identity.public_key_hex)
        table.add_row("[cyan]Agent Name[/cyan]", name)
        table.add_row("[cyan]Agent Type[/cyan]", agent_type)
        console.print(table)
        
        # Create .env file if requested
        if create_config:
            env_file = Path(".env")
            if not env_file.exists():
                env_content = f"""# Hashed Configuration
HASHED_BACKEND_URL=http://localhost:8000
HASHED_API_KEY=your_api_key_here
HASHED_IDENTITY_PASSWORD={password}
HASHED_AGENT_NAME={name}
HASHED_AGENT_TYPE={agent_type}
"""
                env_file.write_text(env_content)
                success(f"Created configuration: {env_file}")
                warning("⚠️  Remember to update HASHED_API_KEY in .env")
            else:
                info(".env file already exists, skipping")
        
        # Create example script
        example_file = Path("agent.py")
        if not example_file.exists():
            example_content = f'''"""
{name} - Hashed AI Agent
"""

import asyncio
from hashed import HashedCore, HashedConfig, load_or_create_identity

async def main():
    """Main agent logic."""
    # Load configuration
    config = HashedConfig()
    
    # Load identity
    identity = load_or_create_identity("{identity_file}")
    
    # Create core
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )
    
    # Initialize
    await core.initialize()
    
    # Define guarded operations
    @core.guard("example_operation")
    async def example_operation(param: str):
        """Example guarded operation."""
        print(f"Executing: {{param}}")
        return {{"status": "success", "param": param}}
    
    # Execute
    result = await example_operation("test")
    print(f"Result: {{result}}")
    
    # Cleanup
    await core.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
'''
            example_file.write_text(example_content)
            success(f"Created example script: {example_file}")
        
        console.print("\n[bold green]✓ Initialization complete![/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. Update .env with your API key")
        console.print("  2. Run: python agent.py")
        console.print("  3. View logs: hashed logs list")
        
    except Exception as e:
        error(f"Initialization failed: {e}")
        raise typer.Exit(1)


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
# POLICY COMMANDS
# ============================================================================

@policy_app.command("add")
def policy_add(
    tool_name: str = typer.Argument(..., help="Tool/operation name"),
    allowed: bool = typer.Option(True, "--allow/--deny", help="Allow or deny"),
    max_amount: Optional[float] = typer.Option(None, "--max-amount", "-m", help="Maximum amount"),
    config_file: str = typer.Option(".hashed_policies.json", "--config", "-c", help="Policy config file"),
):
    """
    ➕ Add a new policy rule.
    
    Defines access control for operations.
    """
    try:
        # Load existing policies
        policies = {}
        config_path = Path(config_file)
        if config_path.exists():
            policies = json.loads(config_path.read_text())
        
        # Add new policy
        policies[tool_name] = {
            "allowed": allowed,
            "max_amount": max_amount,
            "created_at": datetime.now().isoformat()
        }
        
        # Save
        config_path.write_text(json.dumps(policies, indent=2))
        
        success(f"Policy added: {tool_name}")
        console.print(f"  Allowed: [{'green' if allowed else 'red'}]{allowed}[/]")
        if max_amount:
            console.print(f"  Max Amount: [cyan]{max_amount}[/cyan]")
        
    except Exception as e:
        error(f"Failed to add policy: {e}")
        raise typer.Exit(1)


@policy_app.command("list")
def policy_list(
    config_file: str = typer.Option(".hashed_policies.json", "--config", "-c", help="Policy config file"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table/json)"),
):
    """
    📋 List all policies.
    
    Shows current policy configuration.
    """
    try:
        config_path = Path(config_file)
        if not config_path.exists():
            warning("No policies found")
            return
        
        policies = json.loads(config_path.read_text())
        
        if format == "json":
            console.print_json(data=policies)
        else:
            table = Table(title="Policies", box=box.ROUNDED)
            table.add_column("Tool", style="cyan")
            table.add_column("Allowed", style="bold")
            table.add_column("Max Amount", style="yellow")
            table.add_column("Created", style="dim")
            
            for tool_name, policy in policies.items():
                allowed = "✓ Yes" if policy["allowed"] else "✗ No"
                allowed_style = "green" if policy["allowed"] else "red"
                max_amt = str(policy.get("max_amount", "-"))
                created = policy.get("created_at", "-")[:10]
                
                table.add_row(
                    tool_name,
                    f"[{allowed_style}]{allowed}[/]",
                    max_amt,
                    created
                )
            
            console.print(table)
        
    except Exception as e:
        error(f"Failed to list policies: {e}")
        raise typer.Exit(1)


@policy_app.command("remove")
def policy_remove(
    tool_name: str = typer.Argument(..., help="Tool/operation name"),
    config_file: str = typer.Option(".hashed_policies.json", "--config", "-c", help="Policy config file"),
):
    """
    ➖ Remove a policy rule.
    """
    try:
        config_path = Path(config_file)
        if not config_path.exists():
            warning("No policies found")
            return
        
        policies = json.loads(config_path.read_text())
        
        if tool_name not in policies:
            error(f"Policy not found: {tool_name}")
            raise typer.Exit(1)
        
        del policies[tool_name]
        config_path.write_text(json.dumps(policies, indent=2))
        
        success(f"Policy removed: {tool_name}")
        
    except Exception as e:
        error(f"Failed to remove policy: {e}")
        raise typer.Exit(1)


@policy_app.command("test")
def policy_test(
    tool_name: str = typer.Argument(..., help="Tool to test"),
    amount: Optional[float] = typer.Option(None, "--amount", "-a", help="Amount to test"),
    config_file: str = typer.Option(".hashed_policies.json", "--config", "-c", help="Policy config file"),
):
    """
    🧪 Test if an operation would be allowed.
    """
    try:
        config_path = Path(config_file)
        if not config_path.exists():
            info("No policies found - operation would be allowed by default")
            return
        
        policies = json.loads(config_path.read_text())
        policy = policies.get(tool_name)
        
        if not policy:
            info(f"No policy for '{tool_name}' - would use default (allowed)")
            return
        
        # Check allowed
        if not policy["allowed"]:
            console.print(f"[red]✗ DENIED[/red] - Policy explicitly denies '{tool_name}'")
            return
        
        # Check amount
        if amount and policy.get("max_amount"):
            if amount > policy["max_amount"]:
                console.print(f"[red]✗ DENIED[/red] - Amount {amount} exceeds max {policy['max_amount']}")
                return
        
        console.print(f"[green]✓ ALLOWED[/green] - Operation '{tool_name}' would be permitted")
        if amount and policy.get("max_amount"):
            console.print(f"  Amount {amount} is within limit {policy['max_amount']}")
        
    except Exception as e:
        error(f"Failed to test policy: {e}")
        raise typer.Exit(1)


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
                response = await client.get(
                    f"{config.backend_url}/v1/logs",
                    params={"limit": limit, "status": status} if status else {"limit": limit},
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
                    status = log["status"]
                    agent = log.get("agent_name", "Unknown")[:20]
                    
                    status_emoji = {
                        "success": "✓",
                        "denied": "✗",
                        "error": "⚠"
                    }.get(status, "•")
                    
                    status_color = {
                        "success": "green",
                        "denied": "red",
                        "error": "yellow"
                    }.get(status, "white")
                    
                    table.add_row(
                        timestamp,
                        tool,
                        f"[{status_color}]{status_emoji} {status}[/]",
                        agent
                    )
                
                console.print(table)
                
        except Exception as e:
            error(f"Failed to list logs: {e}")
            raise typer.Exit(1)
    
    asyncio.run(_list())


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
