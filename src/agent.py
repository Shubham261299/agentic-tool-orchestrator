"""
LangGraph ReAct agent using Anthropic Claude.

Architecture:
- create_react_agent builds the graph: LLM -> Tool node -> back to LLM
- The LLM decides which tool(s) to call based on tool docstrings
- Loop continues until the LLM produces a final answer (no tool call)
"""
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from src.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a helpful AI assistant with access to 12 tools.

Your job is to:
1. Understand the user's request
2. Pick the right tool(s) — you can call multiple tools in sequence
3. Use tool outputs to inform your next step
4. Give a clear, concise final answer

Rules:
- Always think step-by-step before calling tools
- Chain tools when needed (e.g., get time -> write to file -> show clipboard)
- When asked to "remember" something, use write_memory
- When asked to "recall" something, use read_memory
- If a tool returns an error, try a different approach
- Be concise — don't repeat tool output verbatim, summarize for the user
"""


def build_agent():
    """Create and return the compiled LangGraph agent."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")

    llm = ChatAnthropic(
        model=CLAUDE_MODEL,
        api_key=ANTHROPIC_API_KEY,
        temperature=0,           # Deterministic for tool use
        max_tokens=2048,
    )

    # create_react_agent returns a compiled graph
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
    )
    return agent


def run_agent(user_input: str) -> dict:
    """
    Run the agent on a user input. Returns a structured dict.

    Returns:
        {
            "final_answer": str,         # The agent's text response
            "tool_calls": list,          # List of {tool, input, output} dicts
            "step_count": int,           # How many reasoning steps
        }
    """
    agent = build_agent()
    result = agent.invoke({"messages": [("user", user_input)]})

    messages = result["messages"]
    tool_calls = []
    final_answer = ""

    for msg in messages:
        msg_type = msg.__class__.__name__

        # Capture tool calls
        if msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "tool": tc["name"],
                    "input": tc.get("args", {}),
                    "output": None,  # Filled below when ToolMessage found
                })

        # Capture tool outputs
        elif msg_type == "ToolMessage":
            # Match output to its tool call
            for tc in reversed(tool_calls):
                if tc["output"] is None:
                    tc["output"] = str(msg.content)[:500]
                    break

        # Final assistant message (no tool calls = final answer)
        if msg_type == "AIMessage" and not getattr(msg, "tool_calls", None):
            final_answer = msg.content if isinstance(msg.content, str) else str(msg.content)

    return {
        "final_answer": final_answer,
        "tool_calls": tool_calls,
        "step_count": len(tool_calls),
    }