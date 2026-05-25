"""
FastAPI application exposing the agent + judge as REST endpoints.

Run:
    uvicorn main:app --reload

Then open: http://127.0.0.1:8000/docs
"""
import logging

from fastapi import FastAPI, HTTPException

from src.agent import run_agent
from src.config import CLAUDE_MODEL, HOST, PORT
from src.judge import judge_response
from src.schemas import (
    AgentRequest,
    AgentResponse,
    HealthResponse,
    JudgeRequest,
    JudgeResponse,
)
from src.tools import ALL_TOOLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")

app = FastAPI(
    title="Agentic Tool Orchestrator",
    description="A LangGraph ReAct agent with 12 tools + LLM-as-judge evaluation. Powered by Claude.",
    version="1.0.0",
)


@app.get("/", response_model=HealthResponse)
def health():
    """Health check + system info."""
    return HealthResponse(
        status="ok",
        model=CLAUDE_MODEL,
        tools_loaded=len(ALL_TOOLS),
    )


@app.post("/agent", response_model=AgentResponse)
def agent_endpoint(req: AgentRequest):
    """
    Run the agent on a user input.

    The agent (Claude + LangGraph ReAct) will pick tools, chain them as needed,
    and produce a final answer with full tool-call trace.
    """
    log.info(f"[/agent] input: {req.user_input[:80]}")
    try:
        result = run_agent(req.user_input)
        log.info(f"[/agent] {result['step_count']} tool calls, {len(result['final_answer'])} char answer")
        return AgentResponse(**result)
    except Exception as e:
        log.exception("Agent failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


@app.post("/judge", response_model=JudgeResponse)
def judge_endpoint(req: JudgeRequest):
    """
    Score an agent's response using LLM-as-judge.

    Returns a 0-100 score with reasoning, strengths, and weaknesses.
    Useful for building eval datasets or grading agent quality over time.
    """
    log.info(f"[/judge] judging {len(req.agent_output)} char response")
    try:
        result = judge_response(req.user_input, req.agent_output)
        log.info(f"[/judge] score: {result['score']}/100")
        return JudgeResponse(**result)
    except Exception as e:
        log.exception("Judge failed")
        raise HTTPException(status_code=500, detail=f"Judge error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)