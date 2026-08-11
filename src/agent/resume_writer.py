"""Generates a tailored resume for one job — reorders/re-emphasizes the base
resume's actual content toward what the job asks for. Never invents
experience, skills, employers, or credentials that aren't already in the
base resume; the prompt is explicit about that constraint since a fabricated
resume is worse than no tailoring at all.
"""

import re
from pathlib import Path
from uuid import UUID

import docx
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI

from storage.jobs import get_job
from storage.resume import get_base_resume
from storage.resumes import insert_resume

_MODEL = "gpt-4o-mini"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "resumes"


class TailoredResume(BaseModel):
    resume_text: str = Field(
        description=(
            "The complete tailored resume, plain text, ready to lay out as a document. "
            "Reorder, re-emphasize, and rephrase the candidate's ACTUAL experience toward "
            "this job — do not invent skills, employers, titles, dates, or achievements "
            "that aren't already present in the base resume."
        )
    )
    summary_of_changes: str = Field(
        description="2-4 sentences: what was reordered/emphasized/trimmed vs the base resume, and why"
    )


_writer = ChatOpenAI(model=_MODEL, temperature=0.2).with_structured_output(TailoredResume)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")[:40]


def _write_docx(resume_text: str, out_path: Path) -> None:
    doc = docx.Document()
    for line in resume_text.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    doc.save(out_path)


def generate_tailored_resume(job_id: UUID) -> dict:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"No job found with id {job_id}")

    resume = get_base_resume()
    if resume is None:
        raise ValueError("No base resume found — run resume_ingest.py first")

    prompt = f"""You are tailoring a candidate's resume for a specific job. You must only
reorder, re-emphasize, and rephrase what is ALREADY in the base resume below.
Do not add skills, employers, job titles, dates, or achievements that aren't
already present — fabricating experience is worse than not tailoring at all.

BASE RESUME:
{resume['resume_text']}

TARGET JOB:
Title: {job['title']}
Company: {job['company']}

Description:
{job['description']}

Produce the tailored resume text."""

    result = _writer.invoke(prompt)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_slugify(job['company'])}_{_slugify(job['title'])}_{str(job_id)[:8]}.docx"
    out_path = OUTPUT_DIR / filename
    _write_docx(result.resume_text, out_path)

    resume_id = insert_resume(job_id, str(out_path), result.summary_of_changes)
    return {
        "resume_id": resume_id,
        "file_path": str(out_path),
        "summary_of_changes": result.summary_of_changes,
    }
