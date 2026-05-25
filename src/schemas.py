"""Pydantic request/response models for the FastAPI endpoints."""
from typing import Any
from pydantic import BaseModel, Field


# --- /agent endpoint ---
class AgentRequest(BaseModel):
    """Input for the agent endpoint."""
    user_input: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language task for the agent",
        examples=["What's the weather in Pune and tell me a joke"],
    )


class ToolCall(BaseModel):
    tool: str
    input: dict[str, Any]
    output: str | None


class AgentResponse(BaseModel):
    """Output from the agent endpoint."""
    final_answer: str
    tool_calls: list[ToolCall]
    step_count: int


# --- /judge endpoint ---
class JudgeRequest(BaseModel):
    """Input for the judge endpoint."""
    user_input: str = Field(..., min_length=1, max_length=2000)
    agent_output: str = Field(..., min_length=1, max_length=5000)


class JudgeResponse(BaseModel):
    """Output from the judge endpoint."""
    score: int = Field(..., ge=0, le=100)
    reasoning: str
    strengths: list[str]
    weaknesses: list[str]


# --- Health check ---
class HealthResponse(BaseModel):
    status: str
    model: str
    tools_loaded: int