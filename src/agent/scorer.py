"""Rubric-based job fit scoring — the 4-dimension breakdown embedd.job_scores
was actually designed for (skills/level/location/comp), not just the raw
cosine similarity used for ranking in get_jobs_ranked_by_fit().

Cosine similarity answers "does this description read like this resume."
This answers "should this candidate apply" — level fit, location/remote fit,
and comp fit aren't things embedding similarity captures well (a wildly
overqualified or underqualified posting can still read as semantically very
similar text), so this makes a dedicated LLM call per job instead.
"""

from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI

_MODEL = "gpt-4o-mini"


class JobScore(BaseModel):
    skills_match: float = Field(
        ge=1, le=5, description="How well the candidate's skills/experience match what the job requires"
    )
    level_match: float = Field(
        ge=1, le=5, description="How well the job's seniority expectations match the candidate's actual level"
    )
    location_match: float = Field(
        ge=1,
        le=5,
        description=(
            "How workable the job's location/remote policy is for the candidate. "
            "Score 5 if remote or clearly compatible; lower if it requires relocation "
            "or onsite presence far from where the candidate is based."
        ),
    )
    comp_match: float = Field(
        ge=1,
        le=5,
        description="How reasonable the listed compensation is for the candidate's experience level. Score 3 if no compensation is listed.",
    )
    overall_score: float = Field(
        ge=1, le=5, description="Overall fit combining all four factors, weighted by your judgment"
    )
    notes: str = Field(
        description="1-3 sentences: the strongest reason this is a good fit, and the biggest gap or concern"
    )


_scorer = ChatOpenAI(model=_MODEL, temperature=0).with_structured_output(JobScore)


def score_job(resume_text: str, job_title: str, company: str, location: str | None, job_description: str) -> JobScore:
    prompt = f"""You are evaluating job fit for a candidate applying to data engineering roles.

CANDIDATE'S RESUME:
{resume_text}

JOB POSTING:
Title: {job_title}
Company: {company}
Location: {location or "not listed"}

Description:
{job_description}

Score this job's fit for the candidate on each dimension of the rubric."""
    return _scorer.invoke(prompt)
