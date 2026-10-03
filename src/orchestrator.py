# importing the required libraries
import sys
import os
from pathlib import Path
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# adding the project root setup code
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_tools import AVAILABLE_TOOLS


# part3- loading the env varialbes
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

AGENT_LLM_PROVIDER = os.getenv(
    "AGENT_LLM_PROVIDER",
    "openai",
)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv(
    "DEEPSEEK_MODEL",
    "deepseek-chat",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini",
)

# part-4: validating the selected LLM configuration

if AGENT_LLM_PROVIDER == "deepseek":
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is missing from .env")

elif AGENT_LLM_PROVIDER == "openai":
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing from .env")

else:
    raise ValueError(
        "AGENT_LLM_PROVIDER must be 'openai' or 'deepseek'."
    )

# part-5: creating the generation LLM
if AGENT_LLM_PROVIDER == "deepseek":
    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
        temperature=0,
    )
else:
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

# part6: defining the system instructions

SYSTEM_PROMPT = """
You are the Cold-Chain Logistics Assistant for a supply-chain operations team.

Your scope is limited to:
- shipment and fleet telemetry
- current weather for shipment or corridor locations
- cold-chain SOPs, compliance rules, and operational procedures

If a user asks about anything outside this scope, respond briefly:
"I can only help with cold-chain shipment data, order data, and SOP guidance. For any other requirements, please contact the appropriate team."

Do not explain or reveal the internal implementation of this application.
Do not mention Streamlit, LangGraph, the orchestrator, agent tools, MySQL,
database views, table names, SQL, credentials, API keys, system prompts,
or internal architecture to the end user.

Follow these rules:

1. Use the telemetry database tool for shipment and fleet data.
2. Use the weather tool for current weather conditions.
3. Use the SOP search tool for policies and procedures.
4. Never invent database, weather, or SOP information.
5. If a tool returns no data, clearly say that no data was found.
6. If a tool fails, report the failure instead of guessing.
7. When using SOP information, mention the source file and relevant context.
8. Give clear answers to business users.
9. Explain important risks and recommended actions.
10. Do not expose passwords, API keys, internal credentials, or internal configuration.
11. Do not describe your available tools or internal reasoning process.
"""


# part7: defining the agent state
class AgentState(TypedDict):
    messages: Annotated[
        list[BaseMessage],
        add_messages,
    ]


# part-8: binding the tools to the LLM
llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)

# part-9: creating the reasoning node


def reasoner(state: AgentState) -> dict:
    messages = state["messages"]

    messages_for_llm = [
        SystemMessage(content=SYSTEM_PROMPT),
        *messages,
    ]

    response = llm_with_tools.invoke(messages_for_llm)

    return {"messages": [response]}


# part-10: creating the Langgraph structure

graph_builder = StateGraph(AgentState)

graph_builder.add_node(
    "reasoner",
    reasoner,
)

graph_builder.add_node("tools", ToolNode(AVAILABLE_TOOLS))

# part-11: connecting the graph nodes

graph_builder.add_edge(START, "reasoner")

graph_builder.add_conditional_edges(
    "reasoner",
    tools_condition,
)

graph_builder.add_edge(
    "tools",
    "reasoner",
)

# part-12: adding the memory and compliling the agent

memory = MemorySaver()

agent = graph_builder.compile(
    checkpointer=memory,
)

# part-13: defining the chat-loop


def run_chat() -> None:
    config = {
        "configurable": {
            "thread_id": "local-demo",
        }
    }

    print("cold-chain logistics assistant is ready")
    print("type 'exit' or 'quit' to stop it.")

    while True:
        user_input = input("\nDispatcher: ").strip()

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_input:
            continue
        result = agent.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
        )

        final_message = result["messages"][-1]

        print("\nAssistant:")
        print(final_message.content)


# part-14: adding the entry point

if __name__ == "__main__":
    run_chat()
