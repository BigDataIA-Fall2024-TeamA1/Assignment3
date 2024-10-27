import streamlit as st
import requests
from dotenv import load_dotenv
import os

load_dotenv()

API_BASE_URL = "http://localhost:8000"  # Adjust to your FastAPI server

def main():
    st.title("CFA Research Publications Explorer")

    # Get document list
    response = requests.get(f"{API_BASE_URL}/documents/")
    if response.status_code == 200:
        documents = response.json()
    else:
        st.error("Failed to retrieve documents")
        return

    # Document selection
    doc_titles = [doc['title'] for doc in documents]
    selected_title = st.selectbox("Select a document", doc_titles)

    # Display document details
    doc_response = requests.get(f"{API_BASE_URL}/documents/{selected_title}")
    if doc_response.status_code == 200:
        doc = doc_response.json()
        st.header(doc['title'])
        if doc['image_url']:
            st.image(doc['image_url'])
        st.write("Summary:")
        st.write(doc['summary'] if doc['summary'] else "No summary available.")
        st.write(f"[Download PDF]({doc['pdf_url']})")
    else:
        st.error("Failed to retrieve document details")
        return

    # Ask a question
    st.subheader("Ask a question")
    user_question = st.text_input("Enter your question about this document:")
    if st.button("Get Answer"):
        if user_question.strip():
            answer_response = requests.post(f"{API_BASE_URL}/ask", json={
                "title": selected_title,
                "question": user_question
            })
            if answer_response.status_code == 200:
                answer = answer_response.json()['answer']
                st.write("Answer:")
                st.write(answer)
            else:
                st.error("Failed to retrieve answer")
        else:
            st.error("Please enter a valid question.")

    # Add new research note
    st.subheader("Add Research Note")
    note_text = st.text_area("Enter your research note:")
    if st.button("Save Research Note"):
        if note_text.strip():
            save_response = requests.post(f"{API_BASE_URL}/save_note", json={
                "title": selected_title,
                "note_text": note_text
            })
            if save_response.status_code == 200:
                st.success("Research note saved successfully")
            else:
                st.error("Failed to save research note")
        else:
            st.error("Please enter a valid research note.")

    # Search research notes (optional, if you have implemented the related endpoint)
    # st.subheader("Search Research Notes")
    # search_query = st.text_input("Search within research notes:")
    # if st.button("Search Notes"):
    #     if search_query.strip():
    #         search_response = requests.get(f"{API_BASE_URL}/search_research_notes/", params={
    #             "title": selected_title,
    #             "query": search_query
    #         })
    #         if search_response.status_code == 200:
    #             search_results = search_response.json()
    #             if search_results:
    #                 st.write("Search Results:")
    #                 for note in search_results:
    #                     st.markdown(f"- {note['note_text']} (Created on {note['created_at']})")
    #             else:
    #                 st.write("No matching research notes found.")
    #         else:
    #             st.error("Failed to search research notes")
    #     else:
    #         st.error("Please enter a valid search query.")

if __name__ == "__main__":
    main()
