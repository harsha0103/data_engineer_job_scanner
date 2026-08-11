"""Chat over the candidate's resume and current job list — answers questions
like "should I apply to X" or "what should I change for Y."

No retrieval/chunking needed (same reasoning as the rest of this project):
one resume plus a few dozen job summaries comfortably fits in a single
context window, so everything is stuffed into the system prompt directly
rather than building a retrieval layer for a dataset this small.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

_MODEL = "gpt-4o-mini"
_llm = ChatOpenAI(model=_MODEL, temperature=0.3)


def _format_job(j: dict) -> str:
    line = f"- {j['title']} @ {j['company']} ({j['source']}) — semantic fit {j['fit_score']:.0%}, status: {j['status']}"
    if j.get("overall_score") is not None:
        line += f", rubric score {float(j['overall_score']):.1f}/5 — {j['score_notes']}"
    return line


def build_system_prompt(resume_text: str, jobs: list[dict]) -> str:
    jobs_summary = "\n".join(_format_job(j) for j in jobs) or "(no jobs stored yet)"
    return f"""You are a career-advice assistant helping a candidate with their data
engineering job search. Be direct and specific — if their resume has a real
gap for a role, say so plainly; don't be encouraging just for its own sake.

CANDIDATE'S RESUME:
{resume_text}

CURRENT JOB LIST (ranked by fit):
{jobs_summary}

Answer the candidate's questions about their resume, specific jobs, or what
to change. Reference specific jobs/companies from the list when relevant."""


def chat(messages: list[dict], resume_text: str, jobs: list[dict]) -> str:
    """messages: [{'role': 'user'|'assistant', 'content': str}, ...]"""
    system = SystemMessage(content=build_system_prompt(resume_text, jobs))
    history = [
        HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
        for m in messages
    ]
    response = _llm.invoke([system] + history)
    return response.content
