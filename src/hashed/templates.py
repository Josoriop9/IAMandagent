"""
Agent Template Generator for Hashed SDK.

Generates agent scripts for different AI frameworks with
Hashed governance (@core.guard) already integrated.

Supported frameworks:
    - plain:    Pure Python (no external AI framework)
    - langchain: LangChain with OpenAI tools agent
    - crewai:   CrewAI multi-agent crews
    - strands:  Amazon Strands Agents (Bedrock)
    - autogen:  Microsoft AutoGen (AG2) multi-agent
"""

from __future__ import annotations

from typing import Optional


# ============================================================================
# SHARED HELPERS
# ============================================================================

def _build_guard_blocks(agent_pols: dict, global_pols: dict) -> tuple[str, str]:
    """
    Build @core.guard() function blocks and their call blocks from policies.
    Returns (guard_blocks, execute_blocks).
    """
    guard_blocks = ""
    execute_blocks = ""

    all_tools: dict = {}
    for tool, pol in global_pols.items():
        all_tools[tool] = {**pol, "_scope": "global"}
    for tool, pol in agent_pols.items():
        all_tools[tool] = {**pol, "_scope": "agent"}

    if not all_tools:
        return "", ""

    for tool, pol in all_tools.items():
        allowed = pol["allowed"]
        max_amt = pol.get("max_amount")
        scope = pol["_scope"]
        status_comment = "allowed" if allowed else "DENIED by policy"

        if max_amt is not None:
            params = "amount: float"
            execute_arg = "100.0"
            doc_extra = f" (max: ${max_amt})"
        else:
            params = "data: str"
            execute_arg = '"test"'
            doc_extra = ""

        guard_blocks += f'''
    @core.guard("{tool}")
    async def {tool}({params}):
        """{tool} - {status_comment}{doc_extra} [{scope}]"""
        return {{"status": "success", "tool": "{tool}"}}
'''
        execute_blocks += f'''
    try:
        result = await {tool}({execute_arg})
        print(f"  ✓ {tool}: {{result}}")
    except Exception as e:
        print(f"  ✗ {tool}: {{e}}")
'''

    return guard_blocks, execute_blocks


# ============================================================================
# PLAIN TEMPLATE
# ============================================================================

def render_plain(
    name: str,
    agent_type: str,
    identity_file: str,
    agent_pols: dict,
    global_pols: dict,
    interactive: bool,
) -> str:
    """Plain Python template - no external AI framework."""
    guard_blocks, execute_blocks = _build_guard_blocks(agent_pols, global_pols)

    if not guard_blocks:
        guard_blocks = '''
    @core.guard("example_operation")
    async def example_operation(param: str):
        """Example guarded operation."""
        return {"status": "success", "param": param}
'''
        execute_blocks = '''
    result = await example_operation("test")
    print(f"Result: {result}")
'''

    interactive_block = _build_interactive_plain(name) if interactive else ""

    return f'''"""
{name} - Hashed AI Agent (Plain Python)
Auto-generated with policies from .hashed_policies.json
"""

import asyncio
import os
from dotenv import load_dotenv
from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for {name}."""
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("{identity_file}", password)

    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )

    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized\\n")

    # ================================================================
    # Guarded Operations
    # ================================================================
{guard_blocks}
{interactive_block}
    # ================================================================
    # Execute Operations
    # ================================================================
    if not {str(interactive).lower()}:
        print("Running operations...")
{execute_blocks}
    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
'''


def _build_interactive_plain(name: str) -> str:
    return f'''
    # ================================================================
    # Interactive Mode - REPL
    # ================================================================
    print(f"[{name}] Ready. Type 'exit' to quit.\\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            # Route to the appropriate guarded operation
            print(f"Agent: Processing your request...")
            # TODO: add your routing logic here

        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''


# ============================================================================
# LANGCHAIN TEMPLATE
# ============================================================================

def render_langchain(
    name: str,
    agent_type: str,
    identity_file: str,
    agent_pols: dict,
    global_pols: dict,
    interactive: bool,
) -> str:
    """LangChain template with OpenAI tools agent."""
    all_tools: dict = {}
    for tool, pol in global_pols.items():
        all_tools[tool] = {**pol, "_scope": "global"}
    for tool, pol in agent_pols.items():
        all_tools[tool] = {**pol, "_scope": "agent"}

    # Build LangChain @tool decorated functions
    tool_defs = ""
    tool_list = []
    if all_tools:
        for tool_name, pol in all_tools.items():
            allowed = pol["allowed"]
            max_amt = pol.get("max_amount")
            doc = f"{tool_name} - {'allowed' if allowed else 'DENIED'}"
            if max_amt:
                doc += f" (max: ${max_amt})"

            param_type = "float" if max_amt is not None else "str"
            param_name = "amount" if max_amt is not None else "data"

            tool_defs += f'''
@tool
def {tool_name}({param_name}: {param_type}) -> str:
    """{doc}"""
    # Hashed guard is enforced at runtime via HashedCore
    return f"{{{{'{tool_name}' executed with {param_name}={{{param_name}}}}}}}"

'''
            tool_list.append(tool_name)
    else:
        tool_defs = '''
@tool
def example_operation(data: str) -> str:
    """Example tool - replace with your actual tool."""
    return f"Processed: {data}"

'''
        tool_list = ["example_operation"]

    tools_str = ", ".join(tool_list)

    interactive_block = _build_interactive_langchain() if interactive else _build_batch_langchain(tool_list)

    return f'''"""
{name} - Hashed AI Agent (LangChain)
Auto-generated with policies from .hashed_policies.json

Install: pip install "hashed-sdk[langchain]"
"""

import asyncio
import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


# ================================================================
# Hashed Setup
# ================================================================
config = HashedConfig()
password = os.getenv("HASHED_IDENTITY_PASSWORD")
identity = load_or_create_identity("{identity_file}", password)
core = HashedCore(
    config=config,
    identity=identity,
    agent_name="{name}",
    agent_type="{agent_type}"
)


# ================================================================
# Tools with Hashed Guards
# ================================================================
{tool_defs}

# ================================================================
# Agent Setup
# ================================================================

TOOLS = [{tools_str}]

PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are {name}, a helpful {agent_type} agent governed by Hashed policies."),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{{input}}"),
    MessagesPlaceholder("agent_scratchpad"),
])


async def main():
    """Main agent logic for {name}."""
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with LangChain\\n")

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )

    agent = create_openai_tools_agent(llm, TOOLS, PROMPT)
    executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=True)

    # ================================================================
    # Run Agent
    # ================================================================
{interactive_block}

    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
'''


def _build_interactive_langchain() -> str:
    return '''
    print("Agent ready. Type 'exit' to quit.\\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            result = executor.invoke({"input": user_input})
            print(f"Agent: {result['output']}\\n")

        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''


def _build_batch_langchain(tool_list: list) -> str:
    return f'''
    # Run a sample task
    result = executor.invoke({{
        "input": "Run the following tools and report results: {', '.join(tool_list)}"
    }})
    print(f"Result: {{result['output']}}")
'''


# ============================================================================
# CREWAI TEMPLATE
# ============================================================================

def render_crewai(
    name: str,
    agent_type: str,
    identity_file: str,
    agent_pols: dict,
    global_pols: dict,
    interactive: bool,
) -> str:
    """CrewAI template with guarded tools."""
    all_tools: dict = {}
    for tool, pol in global_pols.items():
        all_tools[tool] = {**pol, "_scope": "global"}
    for tool, pol in agent_pols.items():
        all_tools[tool] = {**pol, "_scope": "agent"}

    # Build CrewAI tool classes
    tool_classes = ""
    tool_class_names = []

    if all_tools:
        for tool_name, pol in all_tools.items():
            class_name = "".join(w.capitalize() for w in tool_name.split("_")) + "Tool"
            allowed = pol["allowed"]
            max_amt = pol.get("max_amount")
            doc = f"{tool_name} - {'allowed' if allowed else 'DENIED'}"
            if max_amt:
                doc += f" (max: ${max_amt})"

            param_type = "float" if max_amt is not None else "str"
            param_name = "amount" if max_amt is not None else "data"

            tool_classes += f'''
class {class_name}(BaseTool):
    name: str = "{tool_name}"
    description: str = "{doc}"

    def _run(self, {param_name}: {param_type}) -> str:
        """Execute {tool_name} (enforced by Hashed at runtime)."""
        return f"{tool_name} executed: {{{param_name}}}"

'''
            tool_class_names.append(class_name)
    else:
        tool_classes = '''
class ExampleTool(BaseTool):
    name: str = "example_operation"
    description: str = "Example tool - replace with your actual tool"

    def _run(self, data: str) -> str:
        return f"Processed: {data}"

'''
        tool_class_names = ["ExampleTool"]

    tools_instantiation = "\n    ".join(f"{cls.replace('Tool', '').lower()}_tool = {cls}()" for cls in tool_class_names)
    tools_list = "[" + ", ".join(f"{cls.replace('Tool', '').lower()}_tool" for cls in tool_class_names) + "]"

    interactive_block = _build_interactive_crewai(name) if interactive else _build_batch_crewai(name)

    return f'''"""
{name} - Hashed AI Agent (CrewAI)
Auto-generated with policies from .hashed_policies.json

Install: pip install "hashed-sdk[crewai]"
"""

import asyncio
import os
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


# ================================================================
# Hashed Setup
# ================================================================
config = HashedConfig()
password = os.getenv("HASHED_IDENTITY_PASSWORD")
identity = load_or_create_identity("{identity_file}", password)
core = HashedCore(
    config=config,
    identity=identity,
    agent_name="{name}",
    agent_type="{agent_type}"
)


# ================================================================
# Tools with Hashed Guards
# ================================================================
{tool_classes}

async def main():
    """Main agent logic for {name}."""
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with CrewAI\\n")

    # Instantiate tools
    {tools_instantiation}

    # Define Agent
    agent = Agent(
        role="{agent_type.replace('_', ' ').title()} Agent",
        goal="Complete tasks as {name} with strict policy compliance",
        backstory="You are {name}, a governed AI agent. All actions are audited by Hashed.",
        tools={tools_list},
        llm_config={{
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }},
        verbose=True,
    )

    # ================================================================
    # Run Crew
    # ================================================================
{interactive_block}

    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
'''


def _build_interactive_crewai(name: str) -> str:
    return f'''
    print("{name} ready. Type 'exit' to quit.\\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            task = Task(
                description=user_input,
                expected_output="Complete the requested action and report results.",
                agent=agent,
            )
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
            result = crew.kickoff()
            print(f"Agent: {{result}}\\n")

        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''


def _build_batch_crewai(name: str) -> str:
    return f'''
    task = Task(
        description="Demonstrate your capabilities by running all available tools.",
        expected_output="A summary of all executed operations and their results.",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    print(f"\\n{name} Result:\\n{{result}}")
'''


# ============================================================================
# STRANDS TEMPLATE (Amazon)
# ============================================================================

def render_strands(
    name: str,
    agent_type: str,
    identity_file: str,
    agent_pols: dict,
    global_pols: dict,
    interactive: bool,
) -> str:
    """Amazon Strands Agents template with Bedrock."""
    all_tools: dict = {}
    for tool, pol in global_pols.items():
        all_tools[tool] = {**pol, "_scope": "global"}
    for tool, pol in agent_pols.items():
        all_tools[tool] = {**pol, "_scope": "agent"}

    tool_defs = ""
    tool_list = []

    if all_tools:
        for tool_name, pol in all_tools.items():
            allowed = pol["allowed"]
            max_amt = pol.get("max_amount")
            doc = f"{tool_name} - {'allowed' if allowed else 'DENIED'}"
            if max_amt:
                doc += f" (max: ${max_amt})"

            param_type = "float" if max_amt is not None else "str"
            param_name = "amount" if max_amt is not None else "data"

            tool_defs += f'''
@tool
def {tool_name}({param_name}: {param_type}) -> str:
    """{doc}"""
    return f"{tool_name} completed: {{{param_name}}}"

'''
            tool_list.append(tool_name)
    else:
        tool_defs = '''
@tool
def example_operation(data: str) -> str:
    """Example tool - replace with your actual tool."""
    return f"Processed: {data}"

'''
        tool_list = ["example_operation"]

    tools_str = ", ".join(tool_list)
    interactive_block = _build_interactive_strands(name) if interactive else _build_batch_strands(name, tool_list)

    return f'''"""
{name} - Hashed AI Agent (Amazon Strands)
Auto-generated with policies from .hashed_policies.json

Install: pip install "hashed-sdk[strands]"
Requires: AWS credentials configured (Bedrock access)
"""

import asyncio
import os
from dotenv import load_dotenv

from strands import Agent, tool
from strands.models import BedrockModel

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


# ================================================================
# Hashed Setup
# ================================================================
config = HashedConfig()
password = os.getenv("HASHED_IDENTITY_PASSWORD")
identity = load_or_create_identity("{identity_file}", password)
core = HashedCore(
    config=config,
    identity=identity,
    agent_name="{name}",
    agent_type="{agent_type}"
)


# ================================================================
# Tools with Hashed Guards
# ================================================================
{tool_defs}

async def main():
    """Main agent logic for {name}."""
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with Amazon Strands\\n")

    # Configure Bedrock model
    model = BedrockModel(
        model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )

    # Create Strands agent with tools
    agent = Agent(
        model=model,
        tools=[{tools_str}],
        system_prompt=(
            "You are {name}, a {agent_type} agent governed by Hashed policies. "
            "All your actions are cryptographically audited."
        ),
    )

    # ================================================================
    # Run Agent
    # ================================================================
{interactive_block}

    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
'''


def _build_interactive_strands(name: str) -> str:
    return f'''
    print("{name} ready (Strands). Type 'exit' to quit.\\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            response = agent(user_input)
            print(f"Agent: {{response}}\\n")

        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''


def _build_batch_strands(name: str, tool_list: list) -> str:
    return f'''
    # Demonstrate all available tools
    response = agent(
        "Please demonstrate all available tools: {', '.join(tool_list)}. "
        "Show the result of each operation."
    )
    print(f"Response: {{response}}")
'''


# ============================================================================
# AUTOGEN TEMPLATE (Microsoft)
# ============================================================================

def render_autogen(
    name: str,
    agent_type: str,
    identity_file: str,
    agent_pols: dict,
    global_pols: dict,
    interactive: bool,
) -> str:
    """Microsoft AutoGen (AG2) template."""
    all_tools: dict = {}
    for tool, pol in global_pols.items():
        all_tools[tool] = {**pol, "_scope": "global"}
    for tool, pol in agent_pols.items():
        all_tools[tool] = {**pol, "_scope": "agent"}

    tool_defs = ""
    tool_registrations = ""
    tool_list = []

    if all_tools:
        for tool_name, pol in all_tools.items():
            allowed = pol["allowed"]
            max_amt = pol.get("max_amount")
            doc = f"{tool_name} - {'allowed' if allowed else 'DENIED'}"
            if max_amt:
                doc += f" (max: ${max_amt})"

            param_type = "float" if max_amt is not None else "str"
            param_name = "amount" if max_amt is not None else "data"

            tool_defs += f'''
def {tool_name}({param_name}: {param_type}) -> str:
    """{doc}"""
    return f"{tool_name} executed: {{{param_name}}}"

'''
            tool_registrations += f'''    # Register {tool_name}
    autogen.register_function(
        {tool_name},
        caller=assistant,
        executor=user_proxy,
        name="{tool_name}",
        description="{doc}",
    )
'''
            tool_list.append(tool_name)
    else:
        tool_defs = '''
def example_operation(data: str) -> str:
    """Example operation - replace with your actual function."""
    return f"Processed: {data}"

'''
        tool_registrations = '''    autogen.register_function(
        example_operation,
        caller=assistant,
        executor=user_proxy,
        name="example_operation",
        description="Example operation",
    )
'''
        tool_list = ["example_operation"]

    interactive_block = _build_interactive_autogen(name) if interactive else _build_batch_autogen(name, tool_list)

    return f'''"""
{name} - Hashed AI Agent (Microsoft AutoGen)
Auto-generated with policies from .hashed_policies.json

Install: pip install "hashed-sdk[autogen]"
"""

import asyncio
import os
from dotenv import load_dotenv

import autogen
from autogen import AssistantAgent, UserProxyAgent, config_list_from_json

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


# ================================================================
# Hashed Setup
# ================================================================
config = HashedConfig()
password = os.getenv("HASHED_IDENTITY_PASSWORD")
identity = load_or_create_identity("{identity_file}", password)
core = HashedCore(
    config=config,
    identity=identity,
    agent_name="{name}",
    agent_type="{agent_type}"
)


# ================================================================
# Tools (enforced by Hashed at runtime via HashedCore)
# ================================================================
{tool_defs}

async def main():
    """Main agent logic for {name}."""
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with AutoGen\\n")

    # LLM Configuration
    llm_config = {{
        "config_list": [{{
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": os.getenv("OPENAI_API_KEY"),
        }}],
        "temperature": 0,
    }}

    # Create agents
    assistant = AssistantAgent(
        name="{name.replace(' ', '_')}",
        system_message=(
            "You are {name}, a {agent_type} AI agent governed by Hashed policies. "
            "All your tool calls are cryptographically audited. "
            "Always use available tools to complete tasks."
        ),
        llm_config=llm_config,
    )

    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="{"ALWAYS" if interactive else "NEVER"}",
        max_consecutive_auto_reply={"None" if interactive else "10"},
        code_execution_config=False,
    )

    # Register tools with Hashed governance
{tool_registrations}

    # ================================================================
    # Run AutoGen
    # ================================================================
{interactive_block}

    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
'''


def _build_interactive_autogen(name: str) -> str:
    return f'''
    print("{name} ready (AutoGen). The agent will ask for your input.\\n")
    user_proxy.initiate_chat(
        assistant,
        message="Hello! I am ready to help. What would you like me to do?",
    )
'''


def _build_batch_autogen(name: str, tool_list: list) -> str:
    return f'''
    user_proxy.initiate_chat(
        assistant,
        message=(
            "Please demonstrate the following tools and report the results: "
            "{', '.join(tool_list)}"
        ),
    )
'''


# ============================================================================
# MAIN RENDERER
# ============================================================================

FRAMEWORKS = ["plain", "langchain", "crewai", "strands", "autogen"]

FRAMEWORK_INSTALL = {
    "plain": None,
    "langchain": "pip install 'hashed-sdk[langchain]'",
    "crewai": "pip install 'hashed-sdk[crewai]'",
    "strands": "pip install 'hashed-sdk[strands]'",
    "autogen": "pip install 'hashed-sdk[autogen]'",
}

FRAMEWORK_LABELS = {
    "plain": "Plain Python",
    "langchain": "LangChain (OpenAI Tools Agent)",
    "crewai": "CrewAI (Multi-Agent Crew)",
    "strands": "Amazon Strands Agents (Bedrock)",
    "autogen": "Microsoft AutoGen (AG2)",
}


def render_agent_script(
    framework: str,
    name: str,
    agent_type: str,
    identity_file: str,
    agent_pols: dict,
    global_pols: dict,
    interactive: bool = False,
) -> str:
    """
    Render an agent script for the given framework.

    Args:
        framework: One of plain/langchain/crewai/strands/autogen
        name: Agent display name
        agent_type: Agent type (e.g. finance, assistant)
        identity_file: Path to the .pem identity file
        agent_pols: Per-agent policies dict
        global_pols: Global policies dict
        interactive: Whether to add an interactive REPL loop

    Returns:
        Complete Python script as a string
    """
    renderers = {
        "plain": render_plain,
        "langchain": render_langchain,
        "crewai": render_crewai,
        "strands": render_strands,
        "autogen": render_autogen,
    }

    renderer = renderers.get(framework)
    if not renderer:
        raise ValueError(f"Unknown framework '{framework}'. Choose from: {FRAMEWORKS}")

    return renderer(
        name=name,
        agent_type=agent_type,
        identity_file=identity_file,
        agent_pols=agent_pols,
        global_pols=global_pols,
        interactive=interactive,
    )
