"""Streamlit front-end that calls the Python council functions directly."""
import os

import asyncio
import uuid

import streamlit as st

from backend import storage
from backend.council import generate_conversation_title, stage1_collect_responses

#st.sidebar.json(st.secrets)

os.environ['OPENROUTER_API_KEY'] = st.secrets['OPENROUTER_API_KEY']

st.set_page_config(page_title="LLM Council", page_icon="🧠", layout="wide")


def ensure_conversation():
    """Get or create a conversation and keep its id in session state."""
    if "conversation_id" not in st.session_state:
        conversation_id = str(uuid.uuid4())
        storage.create_conversation(conversation_id)
        st.session_state.conversation_id = conversation_id
    return st.session_state.conversation_id


def load_conversation(conversation_id):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        conversation = storage.create_conversation(conversation_id)
    return conversation


def render_assistant_message(message):
    """Render Stage 1 results with tabs per model."""
    #st.markdown("**Stage 1: Individual Responses**")
    responses = message.get("stage1", []) or []
    if not responses:
        st.info("No responses available.")
        return
    tab_labels = [resp["model"].split("/")[-1] or resp["model"] for resp in responses]
    tabs = st.tabs(tab_labels)
    for tab, resp in zip(tabs, responses):
        with tab:
            st.caption(resp["model"])
            st.markdown(resp.get("response", ""))


def main():
    st.title("Multi-LLM")

    conversation_id = ensure_conversation()
    conversation = load_conversation(conversation_id)

    # Sidebar with basic info
    with st.sidebar:
        #st.subheader("Session")
        #st.write(f"Conversation ID: `{conversation_id}`")
        #st.write("Messages:", len(conversation["messages"]))
        if st.button("Start new conversation"):
            st.session_state.pop("conversation_id", None)
            st.rerun()

    # Chat history
    for message in conversation["messages"]:
        role = message.get("role")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(message.get("content", ""))
        elif role == "assistant":
            with st.chat_message("assistant"):
                render_assistant_message(message)

    # Input
    prompt = st.chat_input("Ask your question...")
    if prompt:
        # Add user message
        storage.add_user_message(conversation_id, prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        # Run Stage 1 and display
        with st.chat_message("assistant"):
            with st.spinner("Collecting responses from all models...", show_time=True):
                stage1_results = asyncio.run(stage1_collect_responses(prompt))
            render_assistant_message({"stage1": stage1_results})

        # Optionally update the title on first message
        if len(conversation["messages"]) == 0:
            title = asyncio.run(generate_conversation_title(prompt))
            storage.update_conversation_title(conversation_id, title)

        # Persist assistant message
        storage.add_assistant_message(conversation_id, stage1_results)

        # Refresh to show full history
        st.rerun()


if __name__ == "__main__":
    main()
