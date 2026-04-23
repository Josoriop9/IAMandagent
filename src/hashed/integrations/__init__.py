"""
Hashed SDK — Framework integration adapters.

Available integrations:
  - LangChain: ``from hashed.integrations.langchain import HashedCallbackHandler``
               Requires ``pip install hashed-sdk[langchain]``

  - CrewAI:    ``from hashed.integrations.crewai import wrap_tool, HashedBaseTool``
               Requires ``pip install hashed-sdk[crewai]``

Each integration is a **lazy optional** — importing this package does NOT
require the target framework to be installed.  The ImportError is raised only
when you actually instantiate the integration class.
"""
