"""
🎨 Streamlit UI for your AI Agent
===================================
Run with:  streamlit run app.py
"""

import streamlit as st
from agent import run_agent, GEMINI_API_KEY

# ---- Page Config ----
st.set_page_config(page_title="🤖 AI Agent", page_icon="🤖", layout="centered")

st.title("🤖 AI Agent")
st.caption("An intelligent agent that reasons step-by-step and uses tools to solve real problems.")

# ---- Check API Key ----
if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
    st.error("⚠️ Please set your Gemini API key in `agent.py` first!")
    st.info("Get a free key at: https://aistudio.google.com/apikey")
    st.stop()

# ---- Chat History ----
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---- Chat Input ----
if prompt := st.chat_input("Ask me anything..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            response = run_agent(prompt)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
