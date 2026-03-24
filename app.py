"""Streamlit web interface for the TechMart Support Agent."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import config
from agent.core import SupportAgent
from rag.engine import RAGEngine
from speech.tts import text_to_speech
from speech.stt import transcribe_audio

# ---- Page Config ----
st.set_page_config(page_title=f"{config.COMPANY_NAME} Support", page_icon="🛒", layout="wide")

# ---- Session State Init ----
if "agent" not in st.session_state:
    rag = None
    if config.RAG_ENABLED:
        try:
            rag = RAGEngine()
            rag.load()
        except Exception:
            rag = None
    st.session_state.agent = SupportAgent(rag_engine=rag)
    st.session_state.chat_history = [
        {"role": "assistant", "content": f"Hello! Welcome to {config.COMPANY_NAME} Customer Support. I'm here to help you today. How can I assist you?"}
    ]
    st.session_state.conversation_ended = False
    st.session_state.audio_key = 0
    st.session_state.last_audio_id = None

agent: SupportAgent = st.session_state.agent

# ---- Sidebar: Extracted Data ----
with st.sidebar:
    st.header("📋 Extracted Information")
    data = agent.get_extracted_data()
    comp = data.completeness()

    st.progress(comp["pct"] / 100, text=f"Data completeness: {comp['pct']:.0f}%")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Order #", data.order_number or "—")
        st.metric("Category", data.problem_category.value if data.problem_category else "—")
    with col2:
        st.metric("Urgency", data.urgency_level.value if data.urgency_level else "—")
        st.metric("Product", data.product_name or "—")

    if data.problem_description:
        st.text_area("Problem Description", data.problem_description, disabled=True, height=80)

    if comp["missing"]:
        st.caption(f"Missing: {', '.join(comp['missing'])}")
    else:
        st.success("All required information collected!")

    st.divider()

    # Conversation controls
    if st.button("🔄 New Conversation", use_container_width=True):
        rag = agent.rag_engine
        st.session_state.agent = SupportAgent(rag_engine=rag)
        st.session_state.chat_history = []
        st.session_state.conversation_ended = False
        st.session_state.audio_key = 0
        st.session_state.last_audio_id = None
        st.rerun()

    if st.button("📝 End & Summarize", use_container_width=True) and not st.session_state.conversation_ended:
        with st.spinner("Generating summary..."):
            record = agent.end_conversation()
            st.session_state.conversation_ended = True
            st.session_state.summary = record.summary
            st.session_state.record = record
        st.rerun()

    if st.session_state.get("conversation_ended") and st.session_state.get("summary"):
        summary = st.session_state.summary
        st.divider()
        st.header("📊 Summary")
        st.write(summary.summary)
        if summary.key_points:
            st.subheader("Key Points")
            for kp in summary.key_points:
                st.write(f"• {kp}")
        if summary.resolution:
            st.subheader("Resolution")
            st.write(summary.resolution)
        if summary.overall_sentiment:
            sval = summary.overall_sentiment
            emoji = {"positive": "😊", "neutral": "😐", "negative": "😟", "frustrated": "😤"}.get(sval, "")
            st.metric("Sentiment", f"{emoji} {sval}")

    st.divider()
    st.caption("TTS & STT")
    tts_on = st.toggle("🔊 Read replies aloud", value=False)
    st.caption(f"Model: {config.LLM_MODEL}")
    st.caption(f"RAG: {'enabled' if config.RAG_ENABLED else 'disabled'}")


# ---- Main Chat Area ----
st.title(f"🛒 {config.COMPANY_NAME} Customer Support")
st.caption("AI-powered support agent — type your message or use voice input below.")

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("sentiment"):
            emoji = {"positive": "😊", "neutral": "😐", "negative": "😟", "frustrated": "😤"}.get(msg["sentiment"], "")
            st.caption(f"Sentiment: {emoji} {msg['sentiment']}")

# Audio input
audio_input = st.audio_input("🎙️ Or speak your message", key=f"audio_in_{st.session_state.audio_key}")
if audio_input and not st.session_state.conversation_ended:
    audio_id = id(audio_input)
    if audio_id != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio_id
        audio_bytes = audio_input.getvalue()
        with st.spinner("Transcribing..."):
            transcribed = transcribe_audio(audio_bytes)
        if transcribed:
            st.session_state.chat_history.append({"role": "user", "content": transcribed})
            with st.spinner("Thinking..."):
                reply = agent.chat(transcribed)
                sentiment = agent.messages[-2].sentiment
                st.session_state.chat_history[-1]["sentiment"] = sentiment.value if sentiment else None
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
            if tts_on:
                audio_data = text_to_speech(reply, config.TTS_VOICE)
                if audio_data:
                    st.audio(audio_data, format="audio/mp3")
            # Reset audio widget so it doesn't re-trigger
            st.session_state.audio_key += 1
            st.rerun()

# Text input
if prompt := st.chat_input("Type your message...", disabled=st.session_state.conversation_ended):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = agent.chat(prompt)
            sentiment = agent.messages[-2].sentiment
            st.session_state.chat_history[-1]["sentiment"] = sentiment.value if sentiment else None
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.write(reply)
            if tts_on:
                audio_data = text_to_speech(reply, config.TTS_VOICE)
                if audio_data:
                    st.audio(audio_data, format="audio/mp3")
    st.rerun()
