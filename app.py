# part-1: importing the files
import uuid

import streamlit as st
from src.orchestrator import invoke_agent

# part-2 : configuring the streamlit page
st.set_page_config(
    page_title="Cold-Chain Logistics Assistant",
    page_icon="🚚",
    layout="wide",
)

st.title("🚚 Cold-Chain Logistics Assistant")
st.caption(
    "Ask questions about telemetry, weather, and cold-chain SOPs."
)

# part-3: create session state

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# part-4: Adding a reset button
if st.sidebar.button("Clear conversation"):
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.chat_history = []
    st.rerun()

# part-5: displaying the previous messages
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# part-6: Receiving a new question
user_prompt = st.chat_input("Ask about shipments, weather, or cold-chain procedures...")

# part-7: Send the question to the agent
if user_prompt:
    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing your request..."):
            try:
                result = invoke_agent(
                    user_input=user_prompt,
                    thread_id=st.session_state.thread_id,
                )

                assistant_response = result["messages"][-1].content

                if not isinstance(assistant_response, str):
                    assistant_response = str(assistant_response)

                st.markdown(assistant_response)

            except Exception as error:
                assistant_response = (
                    "I couldn't complete that request. "
                    "Please try again or ask about shipment data, "
                    "corridor weather, or SOP guidance."
                )

                st.error(assistant_response)

    # part-8: saving the assistant response
    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": assistant_response,
        }
    )
