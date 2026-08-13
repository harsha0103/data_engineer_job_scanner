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
from agent.scorer import score_job
from connectors.linkedin import parse_job_url
from embedding.openai_embeddings import embed_text
from storage.applications import VALID_STATUSES, set_status
from storage.jobs import get_jobs_ranked_by_fit, update_embedding, upsert_job
from storage.resume import get_base_resume
from storage.resumes import get_resume_for_job
from storage.scores import upsert_score
from storage.sources import get_source_id

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

    with st.expander("Add a LinkedIn job by URL"):
        st.caption(
            "LinkedIn has no search API we can automate (deliberate, to avoid "
            "ToS-violating scraping) — paste one job posting URL you found "
            "yourself and it'll be fetched, embedded, and scored immediately."
        )
        with st.form("add_linkedin_job", clear_on_submit=True):
            linkedin_url = st.text_input("LinkedIn job URL", label_visibility="collapsed")
            submitted = st.form_submit_button("Add job")

        if submitted and linkedin_url:
            try:
                with st.spinner("Fetching, embedding, and scoring..."):
                    record = parse_job_url(linkedin_url)
                    job_id, was_new = upsert_job(source_id=get_source_id("linkedin"), **record)
                    update_embedding(job_id, embed_text(record["description"]))
                    result = score_job(
                        resume["resume_text"], record["title"], record["company"],
                        record["location"], record["description"],
                    )
                    upsert_score(
                        job_id,
                        overall_score=result.overall_score,
                        skills_match=result.skills_match,
                        level_match=result.level_match,
                        location_match=result.location_match,
                        comp_match=result.comp_match,
                        notes=result.notes,
                    )
            except Exception as e:
                st.error(f"Couldn't add that job: {e}")
            else:
                verb = "Added" if was_new else "Updated"
                st.success(f"{verb}: {record['title']} @ {record['company']}")
                st.rerun()

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
                        # st.rerun() below interrupts this script run immediately, so
                        # anything shown before it (e.g. st.success) would never
                        # actually be seen — stash the result and render it after
                        # the rerun instead, where it survives.
                        st.session_state[f"last_gen_{job['id']}"] = result
                        st.rerun()
                with dl_col:
                    if existing_resume:
                        st.caption(f"Tailored resume: {existing_resume['file_path']}")

                last_gen = st.session_state.get(f"last_gen_{job['id']}")
                if last_gen:
                    with st.expander("What was added to your resume", expanded=True):
                        st.markdown(f"**New summary:** {last_gen['new_summary']}")
                        if last_gen["new_bullets"]:
                            st.markdown("**New bullet points:**")
                            for bullet in last_gen["new_bullets"]:
                                st.markdown(f"- {bullet}")
                        else:
                            st.caption("No new bullets were added, only the summary was rewritten.")
                        if st.button("Dismiss", key=f"dismiss_{job['id']}"):
                            del st.session_state[f"last_gen_{job['id']}"]
                            st.rerun()

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
