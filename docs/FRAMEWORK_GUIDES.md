# Hashed SDK — Framework Integration Guides

> Practical, copy-paste examples for the 4 major AI agent frameworks.  
> All examples assume you have run `hashed init` and have a valid `~/.hashed/credentials.json`.

---

## Table of Contents

1. [LangChain](#1-langchain)
2. [CrewAI](#2-crewai)
3. [Amazon Strands](#3-amazon-strands)
4. [AutoGen](#4-autogen)
5. [Framework comparison](#5-framework-comparison)

---

## Prerequisites

```bash
# Core SDK (required for all frameworks)
pip install hashed-sdk

# Install with your framework's extras
pip install "hashed-sdk[langchain]"   # LangChain
pip install "hashed-sdk[crewai]"      # CrewAI
pip install "hashed-sdk[strands]"     # Amazon Strands
pip install "hashed-sdk[autogen]"     # AutoGen

# Secure credential storage (recommended)
pip install "hashed-sdk[secure]"

# Everything at once
pip install "hashed-sdk[all,secure]"
```

```bash
# Initialise (one-time per machine)
hashed init
# → Enter your email + password → credentials saved to ~/.hashed/credentials.json
```

---

## 1. LangChain

**Install:** `pip install "hashed-sdk[langchain]"`

### 1.1 Basic tool governance

```python
"""
LangChain agent with Hashed policy enforcement.

Every tool call is checked against your org's policies before execution.
Denied calls are logged to the audit trail but do NOT raise exceptions by
default — the agent receives a clear denial message and continues.
"""
from hashed import HashedCore
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── 1. Initialise Hashed ─────────────────────────────────────────────────────
core = HashedCore(agent_name="langchain-finance-agent")

# ── 2. Wrap tools with @core.guard() ─────────────────────────────────────────
@tool
@core.guard()
def transfer_funds(amount: float, recipient: str) -> str:
    """Transfer funds to a recipient."""
    # This line only runs if the policy allows it
    return f"Transferred ${amount:.2f} to {recipient}"

@tool
@core.guard()
def query_database(query: str) -> str:
    """Execute a read-only database query."""
    return f"Query result for: {query}"

@tool
@core.guard()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email message."""
    return f"Email sent to {to}: {subject}"

# ── 3. Build the agent ───────────────────────────────────────────────────────
llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [transfer_funds, query_database, send_email]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a financial assistant. Always explain what you are doing."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# ── 4. Run ───────────────────────────────────────────────────────────────────
result = executor.invoke({"input": "Transfer $500 to Alice and notify her by email."})
print(result["output"])
```

### 1.2 Custom policy for a specific tool

```python
# Set a $1,000 max-amount policy on transfer_funds:
#   hashed policy push --tool transfer_funds --max-amount 1000

# After pushing the policy, any transfer > $1,000 will be denied:
result = executor.invoke({"input": "Transfer $5,000 to Bob."})
# Agent receives: "Operation 'transfer_funds' denied by policy: max_amount exceeded"
```

### 1.3 Human-in-the-loop approval

```python
# Push a policy that requires approval for large transfers:
#   hashed policy push --tool transfer_funds --requires-approval --max-amount 500

# The agent will receive:
# "Operation 'transfer_funds' requires human approval (approval_id: <uuid>)"
# Approve via dashboard or: hashed approvals approve <uuid>
```

### 1.4 Viewing the audit trail

```bash
hashed logs list --limit 20
# Shows all tool calls, their status (success/denied), and timestamps
```

---

## 2. CrewAI

**Install:** `pip install "hashed-sdk[crewai]"`

### 2.1 Single agent with governed tools

```python
"""
CrewAI agent with Hashed governance.

CrewAI tools are plain functions; wrap them with @core.guard() before
passing them to the Agent constructor.
"""
from hashed import HashedCore
from crewai import Agent, Task, Crew
from crewai.tools import tool

# ── 1. Initialise Hashed ─────────────────────────────────────────────────────
core = HashedCore(agent_name="crewai-research-agent")

# ── 2. Define governed tools ─────────────────────────────────────────────────
@tool("Web Search")
@core.guard()
def web_search(query: str) -> str:
    """Search the web for information."""
    # Replace with your real search implementation
    return f"Search results for '{query}': ..."

@tool("Write File")
@core.guard()
def write_file(filename: str, content: str) -> str:
    """Write content to a file."""
    with open(filename, "w") as f:
        f.write(content)
    return f"Written {len(content)} bytes to {filename}"

@tool("Execute Code")
@core.guard()
def execute_code(code: str) -> str:
    """Execute Python code in a sandbox."""
    # In production, use a real sandbox (e.g., e2b.dev)
    return f"Code executed: {code[:50]}..."

# ── 3. Create the CrewAI agent ───────────────────────────────────────────────
researcher = Agent(
    role="Research Analyst",
    goal="Research topics thoroughly and produce detailed reports.",
    backstory="Expert analyst with access to web search and file operations.",
    tools=[web_search, write_file, execute_code],
    verbose=True,
    allow_delegation=False,
)

# ── 4. Define tasks and run ──────────────────────────────────────────────────
task = Task(
    description="Research the latest developments in quantum computing and write a summary to quantum_summary.txt",
    expected_output="A 500-word summary saved to quantum_summary.txt",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], verbose=True)
result = crew.kickoff()
print(result)
```

### 2.2 Multi-agent crew with shared governance

```python
"""
Multiple CrewAI agents sharing the same Hashed policy enforcement.
Each agent gets its own HashedCore instance so policies can be
agent-specific (use the same agent_name to share policies).
"""
from hashed import HashedCore
from crewai import Agent, Task, Crew
from crewai.tools import tool

# Separate cores per agent → separate policy sets
analyst_core = HashedCore(agent_name="crewai-analyst")
writer_core = HashedCore(agent_name="crewai-writer")

@tool("Fetch Data")
@analyst_core.guard()
def fetch_data(source: str) -> str:
    """Fetch data from an external source."""
    return f"Data from {source}"

@tool("Publish Report")
@writer_core.guard()
def publish_report(title: str, content: str) -> str:
    """Publish a report to the content management system."""
    return f"Report '{title}' published successfully"

analyst = Agent(
    role="Data Analyst",
    goal="Analyze data from multiple sources",
    backstory="Expert in data analysis",
    tools=[fetch_data],
)

writer = Agent(
    role="Content Writer",
    goal="Write and publish reports",
    backstory="Skilled technical writer",
    tools=[publish_report],
)

# Different policy limits per agent:
# hashed policy push --agent crewai-analyst --tool fetch_data --max-amount 100
# hashed policy push --agent crewai-writer  --tool publish_report --requires-approval

crew = Crew(
    agents=[analyst, writer],
    tasks=[
        Task(description="Fetch Q4 sales data", agent=analyst,
             expected_output="Structured sales data"),
        Task(description="Write and publish Q4 report", agent=writer,
             expected_output="Published report URL"),
    ],
)
result = crew.kickoff()
```

---

## 3. Amazon Strands

**Install:** `pip install "hashed-sdk[strands]"`

### 3.1 Strands agent with governed tools

```python
"""
Amazon Strands agent with Hashed policy enforcement.

Strands tools are functions decorated with @tool from strands.tools.
Wrap with @core.guard() before the @tool decorator.
"""
from hashed import HashedCore
from strands import Agent
from strands.tools import tool

# ── 1. Initialise Hashed ─────────────────────────────────────────────────────
core = HashedCore(agent_name="strands-aws-agent")

# ── 2. Define governed tools ─────────────────────────────────────────────────
# IMPORTANT: @core.guard() goes BEFORE @tool so Hashed wraps the raw function
@core.guard()
@tool
def invoke_lambda(function_name: str, payload: dict) -> dict:
    """Invoke an AWS Lambda function."""
    import boto3
    client = boto3.client("lambda", region_name="us-east-1")
    response = client.invoke(
        FunctionName=function_name,
        Payload=str(payload).encode(),
    )
    return {"status": response["StatusCode"]}

@core.guard()
@tool
def put_s3_object(bucket: str, key: str, content: str) -> str:
    """Write an object to S3."""
    import boto3
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=key, Body=content.encode())
    return f"s3://{bucket}/{key} written successfully"

@core.guard()
@tool
def query_dynamodb(table_name: str, key: dict) -> dict:
    """Query a DynamoDB table."""
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    response = table.get_item(Key=key)
    return response.get("Item", {})

# ── 3. Create and run the Strands agent ─────────────────────────────────────
agent = Agent(
    tools=[invoke_lambda, put_s3_object, query_dynamodb],
    system_prompt=(
        "You are an AWS infrastructure assistant. "
        "Help manage cloud resources efficiently and safely."
    ),
)

response = agent("Process the daily batch job: invoke data-processor Lambda, "
                 "then save the results to s3://my-bucket/results/today.json")
print(response)
```

### 3.2 Governing high-risk AWS operations

```python
# Policies for AWS tools (all operations require approval above thresholds):
# hashed policy push --tool invoke_lambda  --allowed true
# hashed policy push --tool put_s3_object  --allowed true
# hashed policy push --tool query_dynamodb --allowed true

# Block dangerous operations entirely:
# hashed policy push --tool delete_s3_bucket --allowed false

# Require approval for production Lambda invocations:
# hashed policy push --tool invoke_lambda --requires-approval
# → Agent pauses, awaiting human approval at /dashboard/approvals
```

### 3.3 Async Strands agent

```python
"""Strands supports async tools natively."""
import asyncio
from hashed import HashedCore
from strands import Agent
from strands.tools import tool

core = HashedCore(agent_name="strands-async-agent")

@core.guard()
@tool
async def async_query(endpoint: str, params: dict) -> dict:
    """Asynchronously query an API endpoint."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, params=params)
        return response.json()

async def main():
    agent = Agent(tools=[async_query])
    result = await agent.run_async(
        "Query the weather API for New York and return the temperature."
    )
    print(result)

asyncio.run(main())
```

---

## 4. AutoGen

**Install:** `pip install "hashed-sdk[autogen]"`

### 4.1 AutoGen agent with governed function calling

```python
"""
AutoGen agent with Hashed policy enforcement.

AutoGen uses a function_map to register tools.  Wrap each function
with @core.guard() before registering it with the agent.
"""
from hashed import HashedCore
import autogen

# ── 1. Initialise Hashed ─────────────────────────────────────────────────────
core = HashedCore(agent_name="autogen-finance-agent")

# ── 2. Define governed functions ─────────────────────────────────────────────
@core.guard()
def get_stock_price(ticker: str) -> dict:
    """
    Get the current stock price for a ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')

    Returns:
        dict with 'ticker' and 'price' keys
    """
    # Replace with real data provider (e.g., yfinance, polygon.io)
    prices = {"AAPL": 182.50, "GOOGL": 141.20, "MSFT": 415.80}
    return {"ticker": ticker, "price": prices.get(ticker, 0.0)}

@core.guard()
def execute_trade(ticker: str, action: str, quantity: int, price: float) -> dict:
    """
    Execute a stock trade order.

    Args:
        ticker: Stock ticker symbol
        action: 'buy' or 'sell'
        quantity: Number of shares
        price: Limit price per share

    Returns:
        dict with order confirmation
    """
    total = quantity * price
    return {
        "order_id": f"ORD-{ticker}-{action[:3].upper()}",
        "status": "submitted",
        "total_value": total,
    }

@core.guard()
def get_portfolio() -> dict:
    """Get the current portfolio holdings."""
    return {
        "holdings": [
            {"ticker": "AAPL", "shares": 100, "value": 18250.0},
            {"ticker": "MSFT", "shares": 50, "value": 20790.0},
        ],
        "total_value": 39040.0,
    }

# ── 3. Configure AutoGen ─────────────────────────────────────────────────────
config_list = [{"model": "gpt-4o", "api_key": "YOUR_OPENAI_KEY"}]

llm_config = {
    "config_list": config_list,
    "functions": [
        {
            "name": "get_stock_price",
            "description": "Get the current stock price for a ticker symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "execute_trade",
            "description": "Execute a stock trade order",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "action": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "integer"},
                    "price": {"type": "number"},
                },
                "required": ["ticker", "action", "quantity", "price"],
            },
        },
        {
            "name": "get_portfolio",
            "description": "Get current portfolio holdings",
            "parameters": {"type": "object", "properties": {}},
        },
    ],
}

# ── 4. Create agents ─────────────────────────────────────────────────────────
assistant = autogen.AssistantAgent(
    name="FinanceAssistant",
    llm_config=llm_config,
    system_message=(
        "You are a financial trading assistant. "
        "Always check portfolio before trading. "
        "Explain every action clearly."
    ),
)

user_proxy = autogen.UserProxyAgent(
    name="User",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=5,
    function_map={
        "get_stock_price": get_stock_price,
        "execute_trade": execute_trade,
        "get_portfolio": get_portfolio,
    },
)

# ── 5. Start conversation ────────────────────────────────────────────────────
user_proxy.initiate_chat(
    assistant,
    message="What's my portfolio worth? Buy 10 shares of AAPL at market price.",
)
```

### 4.2 AutoGen GroupChat with governance

```python
"""
Multi-agent GroupChat with per-agent policy enforcement.
Each agent gets its own HashedCore → own policy set.
"""
from hashed import HashedCore
import autogen

analyst_core = HashedCore(agent_name="autogen-analyst")
executor_core = HashedCore(agent_name="autogen-executor")

@analyst_core.guard()
def analyze_opportunity(market: str, timeframe: str) -> dict:
    """Analyze a market opportunity."""
    return {"market": market, "recommendation": "buy", "confidence": 0.85}

@executor_core.guard()
def place_order(market: str, size: float, side: str) -> dict:
    """Place a trading order."""
    return {"order_id": "ORD-001", "status": "filled", "size": size}

# Configure agents with different function maps
analyst = autogen.AssistantAgent(
    name="Analyst",
    llm_config={"config_list": [{"model": "gpt-4o", "api_key": "YOUR_KEY"}]},
    system_message="You analyze market opportunities. Do NOT place orders yourself.",
)

executor = autogen.AssistantAgent(
    name="Executor",
    llm_config={"config_list": [{"model": "gpt-4o", "api_key": "YOUR_KEY"}]},
    system_message="You execute orders only when Analyst recommends and User approves.",
)

user_proxy = autogen.UserProxyAgent(
    name="User",
    human_input_mode="TERMINATE",
    function_map={
        "analyze_opportunity": analyze_opportunity,
        "place_order": place_order,
    },
)

groupchat = autogen.GroupChat(
    agents=[user_proxy, analyst, executor],
    messages=[],
    max_round=10,
)
manager = autogen.GroupChatManager(groupchat=groupchat)

user_proxy.initiate_chat(
    manager,
    message="Analyze the BTC-USD opportunity over 1 day and execute if confidence > 0.8",
)
```

---

## 5. Framework Comparison

| Feature | LangChain | CrewAI | Strands | AutoGen |
|---------|-----------|--------|---------|---------|
| **Decorator position** | `@tool` then `@core.guard()` | `@tool` then `@core.guard()` | `@core.guard()` then `@tool` | `@core.guard()` only |
| **Async support** | ✅ | ✅ | ✅ native | ✅ |
| **Multi-agent** | ✅ via chains | ✅ native crew | ✅ | ✅ GroupChat |
| **Hashed install** | `[langchain]` | `[crewai]` | `[strands]` | `[autogen]` |
| **Policy per agent** | ✅ `agent_name=` | ✅ separate core | ✅ separate core | ✅ separate core |

### Key pattern differences

**LangChain** — `@core.guard()` wraps the inner function, `@tool` exposes it:
```python
@tool
@core.guard()
def my_tool(): ...
```

**CrewAI** — same as LangChain:
```python
@tool("Tool Name")
@core.guard()
def my_tool(): ...
```

**Strands** — `@core.guard()` must be OUTERMOST (wraps before `@tool` registers):
```python
@core.guard()   # outer
@tool           # inner
def my_tool(): ...
```

**AutoGen** — no framework-level decorator, just `@core.guard()`:
```python
@core.guard()
def my_function(): ...
# Register in function_map={"my_function": my_function}
```

---

## Policy management across frameworks

All frameworks use the same Hashed CLI for policy management:

```bash
# View current policies
hashed policy list

# Allow a tool (optionally with a max amount for financial ops)
hashed policy add transfer_funds --allow --max-amount 1000

# Require human approval for high-risk tools
# (set requires_approval=true via the dashboard or API directly)
hashed policy add execute_trade --allow

# Block a tool entirely
hashed policy add delete_database --deny

# Sync all local policies to the backend (diff-sync: adds new, removes deleted)
hashed policy push

# View the audit trail
hashed logs list --limit 50

# Approve pending operations via the dashboard
# https://hashed-dashboard.vercel.app → Approvals
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `PermissionError: Operation denied by policy` | Check `hashed policy list` — the policy may block this tool |
| `ConnectionError: Backend unreachable` | In fail-closed mode, agents are denied. Check Railway status |
| `AgentNotFound: No agent registered` | Run `hashed agent list` — check if the agent was registered |
| `InvalidCredentials` | Run `hashed init` to re-authenticate |
| Tool silently allowed (no policy) | Default is allow if no policy exists; push an explicit deny policy |
| Audit logs missing | Check `hashed logs list` — logs may be buffered in WAL; they sync on network restore |

---

## Next steps

- **Dashboard**: View real-time activity at [https://hashed-dashboard.vercel.app](https://hashed-dashboard.vercel.app)
- **API Reference**: See [`docs/API_REFERENCE.md`](API_REFERENCE.md) for direct backend API usage
- **CLI Guide**: See [`docs/CLI_GUIDE.md`](CLI_GUIDE.md) for all available commands
- **Integration Guide**: See [`docs/INTEGRATION.md`](INTEGRATION.md) for backend setup
- **Security extras**: `pip install "hashed-sdk[secure]"` for OS keychain storage
