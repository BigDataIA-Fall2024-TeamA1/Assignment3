import streamlit as st
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

API_BASE_URL = "http://localhost:8000"  # Set this to match your FastAPI server URL

# Define all publications with their titles and image URLs
image_publications = [
    {"title": "An Introduction to Alternative Credit", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/an-introduction-to-alt-credit_v2.jpg"},
    {"title": "Beyond Active and Passive Investing: The Customization of Finance", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/cover-beyond-active-and-passive.jpg"},
    {"title": "2023 International Guide to Cost of Capital", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Cover-from-2023-International-Guide-to-Cost-of-Capital_CFA-Kroll-Final.jpg"},
    {"title": "Bookstaber RF 2022", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Cover-from-Bookstaber_RF_2022_Online.png"},
    {"title": "Investment Luminaries and Their Insights", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Cover-from-Investment-Luminaries-and-Their-Insights-25-Years-of-the-Research-Foundation-Vertin-Award.png"},
    {"title": "ME Markets RF Brief 2022", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Cover-from-ME_Markets_RF_Brief_2022_Online.png"},
    {"title": "Revisiting the Equity Risk Premium", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Cover-from-Revisiting-the-Equity-Risk-Premium_Online.jpg"},
    {"title": "Investment Horizon", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/cover-investment-horizon.jpg"},
    {"title": "Investment Model Validation", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/cover-investment-model-validation.jpg"},
    {"title": "Private Equity", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/cover-private-equity.jpg"},
    {"title": "Handbook of AI and Big Data Applications in Investments", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Handbook-of-AI-and-Big-Data-Applications-in-Investments_Front-Cover.jpg"},
    {"title": "Horan RF Brief 2022", "image_url": "https://cfa-publications-bucket.s3.us-east-2.amazonaws.com/images/Horan_RF_Brief_2022_Cover.png"},
]

def main():
    # Set the page layout to wide
    st.set_page_config(layout="wide")  # Set the layout to wide for better visuals
    st.title("Research Publications Explorer")

    # Initialize session state for selected publication and modified_answer
    if 'selected_title' not in st.session_state:
        st.session_state.selected_title = None  # Initialize with None
    if 'modified_answer' not in st.session_state:
        st.session_state.modified_answer = ""
    if 'research_notes' not in st.session_state:
        st.session_state.research_notes = []

    # Fetch document list
    st.subheader("Explore Documents")
    response = requests.get(f"{API_BASE_URL}/documents")
    if response.status_code == 200:
        documents = response.json()
        # All publication titles for dropdown
        doc_titles = [doc["title"] for doc in documents]
    else:
        st.error("Failed to retrieve documents")
        return

    # Sidebar for Publications Grid View
    st.sidebar.header("📖 Publications Grid View")
    st.sidebar.write("Click on an image to select a publication:")

    # Display the images in pairs side by side for publications with images only
    cols = st.sidebar.columns(2)  # Create two columns for side by side display
    for i, pub in enumerate(image_publications):
        col_index = i % 2  # Determine which column to use
        with cols[col_index]:
            if st.button(pub["title"], key=pub["title"]):  # Button to select the publication
                st.session_state.selected_title = pub["title"]  # Update selected title
            st.image(pub["image_url"], caption=pub["title"], width=100)  # Set width to 100px for smaller images

    # Main area: Selected Publication Details
    if st.session_state.selected_title is None and doc_titles:
        st.session_state.selected_title = doc_titles[0]  # Default selection if none chosen

    # Dropdown to select a document including all publications
    selected_title_dropdown = st.selectbox(
        "Select a document", 
        doc_titles, 
        index=doc_titles.index(st.session_state.selected_title) if st.session_state.selected_title in doc_titles else 0
    )

    # Fetch document summary for the selected title
    summary_response = requests.get(f"{API_BASE_URL}/documents/{selected_title_dropdown}/summary")
    if summary_response.status_code == 200:
        data = summary_response.json()
        summary = data.get('summary', "No summary available.")
        image_url = data.get('image_url')
        pdf_url = data.get('pdf_url')

        # Display document summary
        st.markdown("<h4>📄 Document Summary</h4>", unsafe_allow_html=True)
        st.write(summary)

        # Display the image if available
        if image_url:
            st.image(image_url, caption="Document Image", width=200)
        else:
            st.write("No image available for this document.")

        # PDF download link
        if pdf_url:
            st.markdown(f"[📥 Download PDF]({pdf_url})", unsafe_allow_html=True)

        # Fetch and display existing research notes
        st.markdown("<h4>📝 Existing Research Notes</h4>", unsafe_allow_html=True)
        notes_response = requests.get(f"{API_BASE_URL}/view_research_notes/{selected_title_dropdown}")
        if notes_response.status_code == 200:
            notes_data = notes_response.json()
            st.session_state.research_notes = notes_data.get("notes", [])
            if st.session_state.research_notes:
                for note in st.session_state.research_notes:
                    st.write(f"- {note}")
            else:
                st.write("No research notes available.")
        else:
            st.error("Failed to retrieve research notes")

        # Ask a question and get an answer
        st.markdown("<h4>❓ Ask a Question</h4>", unsafe_allow_html=True)
        user_question = st.text_input("Enter your question about this document:")
        if st.button("Get Answer"):
            if user_question.strip():
                answer_response = requests.post(f"{API_BASE_URL}/ask", json={
                    "question": user_question,
                    "title": selected_title_dropdown
                })
                if answer_response.status_code == 200:
                    answer_data = answer_response.json()
                    answer = answer_data.get("answer", "No answer available.")
                    modified_initial_answer = answer.replace("**Research Note**", f"**{user_question}**")
                    st.write("Generated Answer:")
                    st.write(modified_initial_answer, unsafe_allow_html=True)
                    st.session_state.modified_answer = modified_initial_answer
                    st.text_area("Edit the generated answer:", key="modified_answer")
                else:
                    st.error("Failed to retrieve answer")
            else:
                st.error("Please enter a valid question.")

        # Save the modified answer
        if st.button("Save Modified Answer"):
            if st.session_state.modified_answer.strip():
                save_response = requests.post(f"{API_BASE_URL}/save_modified_answer", json={
                    "title": selected_title_dropdown,
                    "modified_answer": st.session_state.modified_answer
                })
                if save_response.status_code == 200:
                    st.success("Modified answer saved successfully")
                    notes_response = requests.get(f"{API_BASE_URL}/view_research_notes/{selected_title_dropdown}")
                    if notes_response.status_code == 200:
                        notes_data = notes_response.json()
                        st.session_state.research_notes = notes_data.get("notes", [])
                else:
                    st.error("Failed to save modified answer")
            else:
                st.error("Please enter a valid modified answer.")

        # Search within research notes
        st.markdown("<h4>🔍 Search Research Notes</h4>", unsafe_allow_html=True)
        search_query = st.text_input("Enter a search term for research notes:")
        if st.button("Search Notes"):
            if search_query.strip():
                search_response = requests.get(
                    f"{API_BASE_URL}/search_research_notes/{selected_title_dropdown}",
                    params={"query": search_query.strip()}
                )
                if search_response.status_code == 200:
                    search_results = search_response.json().get("matching_notes", [])
                    if search_results:
                        st.write("Search Results:")
                        for result in search_results:
                            st.write(f"- {result}")
                    else:
                        st.write("No matching research notes found.")
                else:
                    st.error("Failed to search research notes")

        # Search full text of the document
        st.markdown("<h4>🔍 Search Full Text of the Document</h4>", unsafe_allow_html=True)
        full_text_query = st.text_input("Enter a search term for the full text of the document:")
        if st.button("Search Full Text"):
            if full_text_query.strip():
                full_text_response = requests.get(
                    f"{API_BASE_URL}/search_full_text/{selected_title_dropdown}",
                    params={"query": full_text_query.strip()}
                )
                if full_text_response.status_code == 200:
                    full_text_results = full_text_response.json().get("results", "No results found.")
                    st.write(full_text_results)
                else:
                    st.error("Failed to search full text")
    else:
        st.error("Failed to retrieve summary")

if __name__ == "__main__":
    main()
