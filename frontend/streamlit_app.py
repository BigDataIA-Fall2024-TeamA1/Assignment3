import streamlit as st
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

API_BASE_URL = "http://localhost:8000"  # Set this to match FastAPI server URL

def main():
    st.title("Research Publications Explorer")

    # Initialize session state for modified_answer
    if 'modified_answer' not in st.session_state:
        st.session_state.modified_answer = ""  

    # Fetch document list
    st.subheader("Explore Documents")
    response = requests.get(f"{API_BASE_URL}/documents")
    if response.status_code == 200:
        documents = response.json()
        doc_titles = [doc["title"] for doc in documents]
        selected_title = st.selectbox("Select a document", doc_titles)
        
    else:
        st.error("Failed to retrieve documents")
        return

    # Display document summary and URLs
    if selected_title:
        st.subheader("Document Summary")
        summary_response = requests.get(f"{API_BASE_URL}/documents/{selected_title}/summary")
        if summary_response.status_code == 200:
            data = summary_response.json()
            summary = data.get('summary', "No summary available.")
            image_url = data.get('image_url')
            pdf_url = data.get('pdf_url')

            # 显示摘要
            st.write(summary)
            
            # 显示图片（如果有）
            if image_url:
                st.image(image_url, caption="Document Image")

            # 提供 PDF 下载链接（如果有）
            if pdf_url:
                st.markdown(f"[Download PDF]({pdf_url})", unsafe_allow_html=True)
        else:
            st.error("Failed to retrieve summary")

    # Ask a question and get a formatted answer
    st.subheader("Ask a Question")
    user_question = st.text_input("Enter your question about this document:")
    if st.button("Get Answer"):
        if user_question.strip():
            answer_response = requests.post(f"{API_BASE_URL}/ask", json={
                "question": user_question, 
                "title": selected_title
            })
            if answer_response.status_code == 200:
                answer_data = answer_response.json()
                answer = answer_data.get("answer", "No answer available.")
                
                # 将 **Research Note** 替换为用户输入的问题
                modified_initial_answer = answer.replace("**Research Note**", f"**{user_question}**")
                
                st.write("Generated Answer:")
                st.write(modified_initial_answer, unsafe_allow_html=True)

                # Display answer in Modify and Save section with URLs
                st.subheader("Modify and Save Answer")
                
                # Update session state with modified initial answer and URLs
                st.session_state.modified_answer = (
                    f"{modified_initial_answer}\n\n[Document Image]({answer_data.get('image_url', '#')})\n\n[Download PDF]({answer_data.get('pdf_url', '#')})"
                )

                # Bind text_area to session state
                st.text_area("Edit the generated answer:", key="modified_answer")
            else:
                st.error("Failed to retrieve answer")
        else:
            st.error("Please enter a valid question.")

    # Save the modified answer
    if st.button("Save Modified Answer"):
        # 检查 modified_answer 是否为空
        if st.session_state.modified_answer.strip():
            save_response = requests.post(f"{API_BASE_URL}/save_modified_answer", json={
                "title": selected_title,
                "modified_answer": st.session_state.modified_answer
            })
            if save_response.status_code == 200:
                st.success("Modified answer saved successfully")
            else:
                st.error("Failed to save modified answer")
        else:
            st.error("Please enter a valid modified answer.")

if __name__ == "__main__":
    main()
