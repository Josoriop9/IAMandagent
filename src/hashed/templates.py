"""
Agent Template Generator for Hashed SDK.

Generates agent scripts for different AI frameworks with
Hashed governance (@core.guard) properly integrated.

The key design principle: @core.guard() decorators are applied
INSIDE main(), AFTER core.initialize() has been called.
This ensures the agent is registered and policies are synced
before any guarded tool is defined or used.

Supported frameworks:
    - plain:    Pure Python (no external AI framework)
    - langchain: LangChain with OpenAI tools agent (StructuredTool)
    - crewai:   CrewAI multi-agent crews (custom BaseTool)
    - strands:  Amazon Strands Agents (Bedrock)
    - autogen:  Microsoft AutoGen (AG2) multi-agent
"""

from __future__ import annotations


# ============================================================================
# SHARED HELPERS
# ============================================================================

def _build_tool_specs(agent_pols: dict, global_pols: dict) -> list[dict]:
    """
    Build a list of tool spec dicts from policies.
    Each dict: {name, allowed, max_amount, param_type, param_name, scope}
    """
    all_tools: dict = {}
    for tool, pol in global_pols.items():
        all_tools[tool] = {**pol, "_scope": "global"}
    for tool, pol in agent_pols.items():
        all_tools[tool] = {**pol, "_scope": "agent"}

    specs = []
    for tool_name, pol in all_tools.items():
        max_amt = pol.get("max_amount")
        specs.append({
            "name": tool_name,
            "allowed": pol["allowed"],
            "max_amount": max_amt,
            "scope": pol["_scope"],
            "param_type": "float" if max_amt is not None else "str",
            "param_name": "amount" if max_amt is not None else "data",
            "status": "allowed" if pol["allowed"] else "DENIED by policy",
        })

    return specs


def _default_spec() -> list[dict]:
    """Return a single example tool spec when no policies exist."""
    return [{
        "name": "example_operation",
        "allowed": True,
        "max_amount": None,
        "scope": "global",
        "param_type": "str",
        "param_name": "data",
        "status": "allowed",
    }]


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
    specs = _build_tool_specs(agent_pols, global_pols) or _default_spec()

    # Build guarded functions
    guard_defs = ""
    call_block = ""
    for s in specs:
        doc_extra = f" (max: ${s['max_amount']})" if s["max_amount"] is not None else ""
        guard_defs += f'''
    @core.guard("{s['name']}")
    async def {s['name']}({s['param_name']}: {s['param_type']}):
        """{s['name']} - {s['status']}{doc_extra} [{s['scope']}]"""
        return {{"status": "success", "tool": "{s['name']}", "{s['param_name']}": {s['param_name']}}}
'''
        arg = "100.0" if s["param_type"] == "float" else '"test"'
        call_block += f'''
    try:
        result = await {s['name']}({arg})
        print(f"  ✓ {s['name']}: {{result}}")
    except Exception as e:
        print(f"  ✗ {s['name']}: {{e}}")
'''

    if interactive:
        run_block = f'''
    # ================================================================
    # Interactive Mode
    # ================================================================
    print("[{name}] Ready. Type 'exit' to quit.\\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            print(f"Agent: Processing '{{user_input}}'...")
            # TODO: route user_input to the appropriate guarded function
        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''
    else:
        run_block = f'''
    # ================================================================
    # Execute Operations
    # ================================================================
    print("Running operations...")
{call_block}'''

    return f'''"""
{name} - Hashed AI Agent (Plain Python)
Auto-generated. Policies sourced from .hashed_policies.json
"""

import asyncio
import os
from dotenv import load_dotenv
from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for {name}."""
    # 1. Setup
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("{identity_file}", password)
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )

    # 2. Initialize (registers agent, syncs policies)
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized\\n")

    # ================================================================
    # Guarded Tools — defined here so @core.guard() has a live core
    # ================================================================
{guard_defs}
{run_block}
    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
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
    """
    LangChain template.
    Tools are defined INSIDE main() so @core.guard() fires after initialization.
    They are then wrapped with StructuredTool.from_function(coroutine=...).
    """
    specs = _build_tool_specs(agent_pols, global_pols) or _default_spec()

    # Build guarded async functions + StructuredTool wrappers
    tool_defs = ""
    tool_list = []
    for s in specs:
        doc_extra = f" (max: ${s['max_amount']})" if s["max_amount"] is not None else ""
        description = f"{s['name']} - {s['status']}{doc_extra}"

        tool_defs += f'''
    # ── {s['name']} ({s['scope']}) ──────────────────────────────────────────
    @core.guard("{s['name']}")
    async def _{s['name']}_fn({s['param_name']}: {s['param_type']}):
        """{description}"""
        # Replace with real implementation
        return f"{s['name']} completed: {{{s['param_name']}}}"

    {s['name']}_tool = StructuredTool.from_function(
        coroutine=_{s['name']}_fn,
        name="{s['name']}",
        description="{description}",
    )
'''
        tool_list.append(f"{s['name']}_tool")

    tools_var = "[" + ", ".join(tool_list) + "]"

    if interactive:
        run_block = '''
    # ================================================================
    # Interactive Chat Loop
    # ================================================================
    print("Agent ready. Type 'exit' to quit.\\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            result = await asyncio.to_thread(
                executor.invoke, {"input": user_input}
            )
            print(f"Agent: {result['output']}\\n")
        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''
    else:
        tool_names = ", ".join(s["name"] for s in specs)
        run_block = f'''
    # ================================================================
    # Batch Execution
    # ================================================================
    result = await asyncio.to_thread(
        executor.invoke,
        {{"input": "Run all available tools and report results: {tool_names}"}}
    )
    print(f"Result: {{result['output']}}")
'''

    return f'''"""
{name} - Hashed AI Agent (LangChain)
Auto-generated. Policies sourced from .hashed_policies.json

Install: pip install "hashed-sdk[langchain]"

Design note: tools are defined inside main() AFTER core.initialize()
so that @core.guard() has a live, registered agent to enforce policies.
"""

import asyncio
import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for {name}."""
    # 1. Setup Hashed
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("{identity_file}", password)
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )

    # 2. Initialize (registers agent + syncs policies)
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with LangChain\\n")

    # ================================================================
    # Guarded Tools — defined here so @core.guard() has a live core
    # StructuredTool.from_function(coroutine=...) bridges async ↔ LangChain
    # ================================================================
{tool_defs}
    TOOLS = {tools_var}

    # 3. LangChain Agent
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are {name}, a {agent_type} agent governed by Hashed policies. "
                   "All tool calls are cryptographically audited."),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{{input}}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_openai_tools_agent(llm, TOOLS, prompt)
    executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=True)

    # ================================================================
    # Run
    # ================================================================
{run_block}
    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
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
    """
    CrewAI template.
    Tools are built as BaseTool subclasses inside main() so that
    @core.guard() is available. _run() bridges sync→async via asyncio.
    """
    specs = _build_tool_specs(agent_pols, global_pols) or _default_spec()

    tool_classes = ""
    tool_instances = []
    for s in specs:
        class_name = "".join(w.capitalize() for w in s["name"].split("_")) + "Tool"
        doc_extra = f" (max: ${s['max_amount']})" if s["max_amount"] is not None else ""
        description = f"{s['name']} - {s['status']}{doc_extra}"

        tool_classes += f'''
    # ── {s['name']} ({s['scope']}) ──────────────────────────────────────────
    @core.guard("{s['name']}")
    async def _{s['name']}_fn({s['param_name']}: {s['param_type']}):
        """{description}"""
        return f"{s['name']} completed: {{{s['param_name']}}}"

    class {class_name}(BaseTool):
        name: str = "{s['name']}"
        description: str = "{description}"

        def _run(self, {s['param_name']}: {s['param_type']}) -> str:
            """Execute {s['name']} with Hashed governance."""
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _{s['name']}_fn({s['param_name']}))
                    return future.result()
            return loop.run_until_complete(_{s['name']}_fn({s['param_name']}))

    {s['name']}_tool = {class_name}()
'''
        tool_instances.append(f"{s['name']}_tool")

    tools_list = "[" + ", ".join(tool_instances) + "]"

    if interactive:
        run_block = f'''
    # ================================================================
    # Interactive Chat Loop
    # ================================================================
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
                expected_output="Complete the task and report results.",
                agent=ai_agent,
            )
            crew = Crew(agents=[ai_agent], tasks=[task], process=Process.sequential)
            result = crew.kickoff()
            print(f"Agent: {{result}}\\n")
        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
'''
    else:
        run_block = f'''
    # ================================================================
    # Batch Execution
    # ================================================================
    task = Task(
        description="Demonstrate all available tools and report results.",
        expected_output="A summary of all executed operations.",
        agent=ai_agent,
    )
    crew = Crew(agents=[ai_agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(f"\\n{name} Result:\\n{{result}}")
'''

    return f'''"""
{name} - Hashed AI Agent (CrewAI)
Auto-generated. Policies sourced from .hashed_policies.json

Install: pip install "hashed-sdk[crewai]"

Design note: tools are defined inside main() AFTER core.initialize()
so that @core.guard() has a live agent. _run() bridges sync ↔ async.
"""

import asyncio
import os
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for {name}."""
    # 1. Setup Hashed
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("{identity_file}", password)
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )

    # 2. Initialize (registers agent + syncs policies)
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with CrewAI\\n")

    # ================================================================
    # Guarded Tools — defined here so @core.guard() has a live core
    # BaseTool._run() bridges sync CrewAI ↔ async Hashed guard
    # ================================================================
{tool_classes}
    TOOLS = {tools_list}

    # 3. CrewAI Agent
    ai_agent = Agent(
        role="{agent_type.replace('_', ' ').title()} Agent",
        goal="Complete tasks as {name} with strict policy compliance",
        backstory="You are {name}, a governed AI agent. All actions are cryptographically audited by Hashed.",
        tools=TOOLS,
        llm="gpt-4o-mini",
        verbose=True,
    )

    # ================================================================
    # Run
    # ================================================================
{run_block}
    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
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
    """
    Amazon Strands Agents template.
    Tools decorated with @tool are created inside main() so @core.guard()
    is available after initialization.
    """
    specs = _build_tool_specs(agent_pols, global_pols) or _default_spec()

    tool_defs = ""
    tool_list = []
    for s in specs:
        doc_extra = f" (max: ${s['max_amount']})" if s["max_amount"] is not None else ""
        description = f"{s['name']} - {s['status']}{doc_extra}"

        tool_defs += f'''
    # ── {s['name']} ({s['scope']}) ──────────────────────────────────────────
    @tool
    @core.guard("{s['name']}")
    async def {s['name']}({s['param_name']}: {s['param_type']}) -> str:
        """{description}"""
        return f"{s['name']} completed: {{{s['param_name']}}}"

'''
        tool_list.append(s["name"])

    tools_str = ", ".join(tool_list)

    if interactive:
        run_block = f'''
    # ================================================================
    # Interactive Chat Loop
    # ================================================================
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
    else:
        run_block = f'''
    # ================================================================
    # Batch Execution
    # ================================================================
    response = agent(
        "Demonstrate all available tools: {', '.join(tool_list)}. Show results for each."
    )
    print(f"Response: {{response}}")
'''

    return f'''"""
{name} - Hashed AI Agent (Amazon Strands)
Auto-generated. Policies sourced from .hashed_policies.json

Install: pip install "hashed-sdk[strands]"
Requires: AWS credentials configured with Bedrock access

Design note: tools are defined inside main() AFTER core.initialize()
so that @core.guard() wraps them with a live, registered agent.
"""

import asyncio
import os
from dotenv import load_dotenv

from strands import Agent, tool
from strands.models import BedrockModel

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for {name}."""
    # 1. Setup Hashed
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("{identity_file}", password)
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )

    # 2. Initialize (registers agent + syncs policies)
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with Amazon Strands\\n")

    # ================================================================
    # Guarded Tools — defined here so @core.guard() has a live core
    # @tool and @core.guard() stack naturally on async functions
    # ================================================================
{tool_defs}
    # 3. Strands Agent
    model = BedrockModel(
        model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )

    agent = Agent(
        model=model,
        tools=[{tools_str}],
        system_prompt=(
            "You are {name}, a {agent_type} agent governed by Hashed policies. "
            "All your actions are cryptographically audited."
        ),
    )

    # ================================================================
    # Run
    # ================================================================
{run_block}
    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
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
    """
    Microsoft AutoGen (AG2) template.
    Tool functions are defined inside main() with @core.guard(),
    then registered via autogen.register_function().
    """
    specs = _build_tool_specs(agent_pols, global_pols) or _default_spec()

    tool_defs = ""
    tool_registrations = ""
    tool_list = []
    for s in specs:
        doc_extra = f" (max: ${s['max_amount']})" if s["max_amount"] is not None else ""
        description = f"{s['name']} - {s['status']}{doc_extra}"

        tool_defs += f'''
    # ── {s['name']} ({s['scope']}) ──────────────────────────────────────────
    @core.guard("{s['name']}")
    async def {s['name']}({s['param_name']}: {s['param_type']}) -> str:
        """{description}"""
        return f"{s['name']} executed: {{{s['param_name']}}}"

'''
        tool_registrations += f'''    autogen.register_function(
        {s['name']},
        caller=assistant,
        executor=user_proxy,
        name="{s['name']}",
        description="{description}",
    )
'''
        tool_list.append(s["name"])

    human_input = "ALWAYS" if interactive else "NEVER"
    max_auto = "None" if interactive else "10"
    intro_msg = (
        "Hello! I am ready to help. What would you like me to do?"
        if interactive
        else f"Demonstrate all tools: {', '.join(tool_list)}"
    )

    return f'''"""
{name} - Hashed AI Agent (Microsoft AutoGen)
Auto-generated. Policies sourced from .hashed_policies.json

Install: pip install "hashed-sdk[autogen]"

Design note: tool functions are defined inside main() AFTER core.initialize()
so that @core.guard() wraps them with a live, registered agent.
"""

import asyncio
import os
from dotenv import load_dotenv

import autogen
from autogen import AssistantAgent, UserProxyAgent

from hashed import HashedCore, HashedConfig, load_or_create_identity

load_dotenv()


async def main():
    """Main agent logic for {name}."""
    # 1. Setup Hashed
    config = HashedConfig()
    password = os.getenv("HASHED_IDENTITY_PASSWORD")
    identity = load_or_create_identity("{identity_file}", password)
    core = HashedCore(
        config=config,
        identity=identity,
        agent_name="{name}",
        agent_type="{agent_type}"
    )

    # 2. Initialize (registers agent + syncs policies)
    await core.initialize()
    print(f"🤖 {name} ({agent_type}) initialized with AutoGen\\n")

    # ================================================================
    # Guarded Tools — defined here so @core.guard() has a live core
    # ================================================================
{tool_defs}
    # 3. AutoGen Agents
    llm_config = {{
        "config_list": [{{
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": os.getenv("OPENAI_API_KEY"),
        }}],
        "temperature": 0,
    }}

    assistant = AssistantAgent(
        name="{name.replace(' ', '_')}",
        system_message=(
            "You are {name}, a {agent_type} AI agent governed by Hashed policies. "
            "All tool calls are cryptographically audited. "
            "Always use the available tools to complete tasks."
        ),
        llm_config=llm_config,
    )

    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="{human_input}",
        max_consecutive_auto_reply={max_auto},
        code_execution_config=False,
    )

    # 4. Register tools with Hashed governance
{tool_registrations}
    # ================================================================
    # Run
    # ================================================================
    user_proxy.initiate_chat(
        assistant,
        message="{intro_msg}",
    )

    await core.shutdown()
    print(f"\\n✓ {name} finished")


if __name__ == "__main__":
    asyncio.run(main())
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
        framework:     One of plain/langchain/crewai/strands/autogen
        name:          Agent display name
        agent_type:    Agent type (e.g. finance, assistant)
        identity_file: Path to the .pem identity file
        agent_pols:    Per-agent policies dict
        global_pols:   Global policies dict
        interactive:   Whether to add an interactive REPL loop

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
        raise ValueError(
            f"Unknown framework '{framework}'. Choose from: {FRAMEWORKS}"
        )

    return renderer(
        name=name,
        agent_type=agent_type,
        identity_file=identity_file,
        agent_pols=agent_pols,
        global_pols=global_pols,
        interactive=interactive,
    )
