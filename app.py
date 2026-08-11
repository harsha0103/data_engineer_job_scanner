"""Streamlit UI: jobs ranked by fit against your base resume, rubric scores,
tailored resume generation, apply-status tracking, and a chat panel.

Run with: uv run streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.chat import chat as chat_with_agent
from agent.resume_writer import generate_tailored_resume
from storage.applications import VALID_STATUSES, set_status
from storage.jobs import get_jobs_ranked_by_fit
from storage.resume import get_base_resume
from storage.resumes import get_resume_for_job

st.set_page_config(page_title="Data Engineer Job Scanner", layout="wide")
st.title("Data Engineer Job Scanner")

resume = get_base_resume()
if resume is None:
    st.error(
        "No base resume found. Run src/agent/resume_ingest.py against your "
        "resume file first — there's nothing to rank jobs against yet."
    )
    st.stop()

jobs = get_jobs_ranked_by_fit(resume["embedding"])

jobs_tab, chat_tab = st.tabs(["Jobs", "Chat"])

with jobs_tab:
    st.caption(f"Ranking against: {resume['file_path']} (updated {resume['updated_at']:%Y-%m-%d})")

    if not jobs:
        st.info("No embedded jobs yet — run a search sweep first.")
    else:
        st.caption(f"{len(jobs)} jobs ranked by fit")

        for job in jobs:
            col_main, col_status = st.columns([5, 1])

            with col_main:
                posted = f"posted {job['posted_at']:%Y-%m-%d}" if job["posted_at"] else "posted date n/a"
                st.markdown(
                    f"**{job['fit_score']:.0%} semantic fit** — [{job['title']}]({job['url']}) "
                    f"@ {job['company']}  \n"
                    f"{job['source']} · {job['location'] or 'location n/a'} · {posted}"
                )
                if job["overall_score"] is not None:
                    st.markdown(f"Rubric score: **{float(job['overall_score']):.1f}/5** — {job['score_notes']}")

                existing_resume = get_resume_for_job(job["id"])
                gen_col, dl_col = st.columns([1, 3])
                with gen_col:
                    if st.button("Generate tailored resume", key=f"gen_{job['id']}"):
                        with st.spinner("Tailoring resume..."):
                            result = generate_tailored_resume(job["id"])
                        st.success(result["summary_of_changes"])
                        st.rerun()
                with dl_col:
                    if existing_resume:
                        st.caption(f"Tailored resume: {existing_resume['file_path']}")

            with col_status:
                new_status = st.selectbox(
                    "Status",
                    options=sorted(VALID_STATUSES),
                    index=sorted(VALID_STATUSES).index(job["status"]),
                    key=f"status_{job['id']}",
                    label_visibility="collapsed",
                )
                if new_status != job["status"]:
                    set_status(job["id"], new_status)
                    st.rerun()

            st.divider()

with chat_tab:
    st.caption("Ask about your resume, a specific job, or what to change.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for msg in st.session_state.chat_messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("e.g. Which job should I prioritize this week?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        with st.spinner("Thinking..."):
            response = chat_with_agent(st.session_state.chat_messages, resume["resume_text"], jobs)
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        st.chat_message("assistant").write(response)
