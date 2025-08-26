import streamlit as st
import logging
import time
# import os
from rag_core import get_rag_response

# --- Logging Setup ---
# This logs interactions and feedback to a file.
logging.basicConfig(level=logging.INFO, filename='app_log.txt', format='%(asctime)s - %(message)s')



# Set the Streamlit page configuration.
st.set_page_config(page_title="Legal Assistant")
st.title("⚖️ Legal Assistant")

# --- Session State ---
# Initialize the chat message history.
if "messages" not in st.session_state:
    st.session_state.messages = []


# --- Chat Interface ---
# Display previous messages in the chat history.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "feedback" in message:
            st.write(f"Feedback: {message['feedback']}")

# Handle user input from the chat box.
if prompt := st.chat_input("Ask a question about legal documents..."):
    start_time = time.time()
    
    # Add the user's message to the chat history.
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get the RAG response from the backend.
    response, retrieved_context = get_rag_response(prompt)
    
    # Log the interaction for monitoring purposes.
    latency = time.time() - start_time
    logging.info(f"Query: {prompt} | Latency: {latency:.2f}s | Context: {retrieved_context[:100]}... | Response: {response}")

    # Display the assistant's response.
    with st.chat_message("assistant"):
        st.markdown(response)
        
        # --- User Feedback for Monitoring ---
        # Provide buttons for user feedback.
        col1, col2 = st.columns(2)
        thumbs_up = col1.button("👍 Correct")
        thumbs_down = col2.button("👎 Incorrect")
        
        # Handle feedback button clicks.
        
        if thumbs_up:
                
                st.session_state.messages[-1]["feedback"] = "Positive"
                logging.info(f"Feedback for '{prompt}': Positive")
                st.success("Thanks for the feedback!")
                feedback = "Positive"
        elif thumbs_down:
                st.session_state.messages[-1]["feedback"] = "Negative"
                logging.info(f"Feedback for '{prompt}': Negative")
                st.error("Thank you. This data will be used to improve the model.")
                feedback = "Negative"
              
           
    # Add the assistant's message to the chat history.
    st.session_state.messages.append({"role": "assistant", "content": response, "feedback": "None"})
