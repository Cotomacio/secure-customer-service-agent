"""
Streamlit chat UI for talking to a deployed Ada (any stage / capstone).

Reads which Agent Engine to talk to from the REASONING_ENGINE_ID env var.
Runs locally (`streamlit run app.py`) or on Cloud Run (see Dockerfile).

Auth model:
  - The Cloud Run service uses its own service account to invoke the
    Agent Engine. That SA needs `roles/aiplatform.user` on the project
    (or finer-grained roles/aiplatform.reasoningEngines.user if available).
  - The chat URL itself is left unauthenticated for demos; for production
    bolt on IAP, Cloud Run IAM, or a frontend with Google sign-in.
"""

import os

import streamlit as st
import vertexai


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("LOCATION", "us-central1")
ENGINE_ID = os.environ.get("REASONING_ENGINE_ID", "")
AGENT_DISPLAY_NAME = os.environ.get("AGENT_DISPLAY_NAME", "Ada")


def _engine_resource() -> str:
    return f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"


@st.cache_resource
def get_engine():
    """Cache the vertexai client + engine handle for the life of the process."""
    client = vertexai.Client(
        project=PROJECT_ID,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )
    return client.agent_engines.get(name=_engine_resource())


def render_event(event: dict) -> tuple[str, str]:
    """Turn a stream_query event into (kind, rendered_markdown)."""
    if not isinstance(event, dict):
        return "text", str(event)
    content = event.get("content") or {}
    for part in content.get("parts", []):
        if part.get("text"):
            return "text", part["text"]
        if "function_call" in part:
            fc = part["function_call"]
            args = fc.get("args", {})
            args_str = ", ".join(f"`{k}`={v!r}" for k, v in args.items())
            return "tool_call", f"🔧 **{fc.get('name')}**({args_str})"
        if "function_response" in part:
            fr = part["function_response"]
            return "tool_result", f"↩️ result: `{fr.get('response')}`"
    return "text", ""


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=f"{AGENT_DISPLAY_NAME} — Acme Commerce Support",
    page_icon="🛒",
    layout="centered",
)

st.title(f"🛒 {AGENT_DISPLAY_NAME} — Acme Commerce Support")

# Sidebar — connection info + clear-chat
with st.sidebar:
    st.subheader("Connection")
    if not PROJECT_ID:
        st.error("`GOOGLE_CLOUD_PROJECT` env var not set.")
    elif not ENGINE_ID:
        st.error("`REASONING_ENGINE_ID` env var not set.")
    else:
        st.success("✓ Connected")
        st.code(_engine_resource(), language="text")
    st.divider()
    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.caption(
        "Ada authenticates to each backend (GCS / ServiceNow / OpenWeather / "
        "GitHub) via Agent Identity Auth Manager. No third-party secrets in "
        "Ada's source or container."
    )

if not PROJECT_ID or not ENGINE_ID:
    st.stop()

# Chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = os.environ.get("USER", "web-tester")

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
prompt = st.chat_input(
    f"Ask {AGENT_DISPLAY_NAME} about an order, weather, incidents…"
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call the engine and stream events
    engine = get_engine()
    assistant_buffer: list[str] = []
    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            for event in engine.stream_query(
                message=prompt, user_id=st.session_state.user_id
            ):
                kind, rendered = render_event(event)
                if rendered:
                    assistant_buffer.append(rendered)
                    placeholder.markdown("\n\n".join(assistant_buffer))
        except Exception as e:  # noqa: BLE001
            err = f"❌ Error talking to Ada: `{type(e).__name__}: {e}`"
            assistant_buffer.append(err)
            placeholder.markdown("\n\n".join(assistant_buffer))

    st.session_state.messages.append(
        {"role": "assistant", "content": "\n\n".join(assistant_buffer)}
    )
