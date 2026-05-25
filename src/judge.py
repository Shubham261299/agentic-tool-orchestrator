"""
LLM-as-Judge evaluation.

Pattern: A second LLM call evaluates whether the agent's output satisfies
the user's request. Returns a score (0-100) and reasoning.

This is the canonical 'eval' pattern for LLM apps — used by LangSmith,
Ragas, OpenAI Evals, etc.
"""
import json
import re

from langchain_anthropic import ChatAnthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

JUDGE_PROMPT = """You are an impartial evaluator scoring an AI agent's response.

USER REQUEST:
{user_input}

AGENT'S RESPONSE:
{agent_output}

Evaluate the agent's response on these criteria:
1. Correctness — did it actually answer the question / complete the task?
2. Completeness — did it address every part of the request?
3. Clarity — is the response easy to understand?
4. Tool use appropriateness — did it use the right tools? (skip if unknown)

Respond ONLY in this exact JSON format, no other text:
{{
  "score": <integer 0-100>,
  "reasoning": "<one paragraph explaining the score>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<weakness 1 or empty if perfect>"]
}}

Scoring guide:
- 90-100: Excellent. Fully addresses the request, clear, no issues.
- 70-89: Good. Mostly correct, minor gaps.
- 50-69: Acceptable. Partial answer, noticeable issues.
- 30-49: Poor. Major gaps or incorrect.
- 0-29: Failed. Did not address the request.
"""


def judge_response(user_input: str, agent_output: str) -> dict:
    """
    Use Claude as a judge to score an agent's response.

    Returns:
        {
            "score": int (0-100),
            "reasoning": str,
            "strengths": list[str],
            "weaknesses": list[str],
        }
    """
    llm = ChatAnthropic(
        model=CLAUDE_MODEL,
        api_key=ANTHROPIC_API_KEY,
        temperature=0,           # Judges should be deterministic
        max_tokens=600,
    )

    prompt = JUDGE_PROMPT.format(user_input=user_input, agent_output=agent_output)
    response = llm.invoke(prompt)
    text = response.content.strip() if isinstance(response.content, str) else str(response.content)

    # Extract JSON (model may wrap in code fences sometimes)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {
            "score": 0,
            "reasoning": f"Judge returned unparseable response: {text[:200]}",
            "strengths": [],
            "weaknesses": ["Judge parsing failed"],
        }

    try:
        parsed = json.loads(match.group(0))
        # Validate shape
        return {
            "score": int(parsed.get("score", 0)),
            "reasoning": parsed.get("reasoning", ""),
            "strengths": parsed.get("strengths", []),
            "weaknesses": parsed.get("weaknesses", []),
        }
    except Exception as e:
        return {
            "score": 0,
            "reasoning": f"JSON parse error: {e}",
            "strengths": [],
            "weaknesses": ["Judge returned malformed JSON"],
        }