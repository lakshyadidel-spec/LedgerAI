"""
LedgerAI - Invoice & CFO Agents
-------------------------------
Handles PDF data extraction and the conversational AI CFO interface.
"""

import os
import json
import PyPDF2
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def process_pdf_with_gemini(uploaded_file) -> dict:
    """
    Extracts text from a Streamlit uploaded PDF and uses Gemini 
    to parse it into a strict JSON dictionary.
    """
    try:
        # 1. Extract raw text from the PDF
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text_content = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_content += extracted + "\n"

        if not text_content.strip():
            raise ValueError("Could not extract any text from the PDF. It might be an image-only PDF.")

        # 2. Ask Gemini to structure the data into JSON
        prompt = f"""
        You are a highly accurate data extraction AI. 
        Read the following invoice text and extract the key details.
        
        Return ONLY a raw, valid JSON object with the following exact keys:
        - "vendor_name": (string) The name of the company billing us.
        - "invoice_number": (string) The invoice ID or number.
        - "total_amount": (float) The final total amount due (numbers only, no currency symbols).
        - "due_date": (string) The due date, preferably in YYYY-MM-DD format.

        Invoice Text:
        {text_content}
        """

        # Using 2.5 Flash for speed, and forcing JSON output natively
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Parse the JSON string into a Python dictionary
        extracted_data = json.loads(response.text)
        return extracted_data

    except Exception as e:
        print(f"Error extracting PDF data: {e}")
        # Return safe default values if the extraction fails to prevent app crashes
        return {
            "vendor_name": "Extraction Failed",
            "invoice_number": "N/A",
            "total_amount": 0.0,
            "due_date": "N/A"
        }


def get_cfo_response(messages: list, context_data: str) -> str:
    """
    Acts as the AI CFO, answering user questions based on their bank context.
    """
    # 1. Format the conversation history for Gemini
    formatted_history = ""
    for msg in messages:
        role = "User" if msg["role"] == "user" else "AI CFO"
        formatted_history += f"{role}: {msg['content']}\n"

    # 2. Build the system prompt with the financial context injected
    prompt = f"""
    You are 'Bea', a sharp, highly analytical fractional AI CFO for a startup.
    Your job is to answer the user's financial questions concisely and professionally.

    Here is the company's current financial context (Bank Data & Balances):
    {context_data}

    Here is the conversation history so far:
    {formatted_history}

    Respond directly to the user's latest message as Bea the CFO. Keep it actionable and under 3 paragraphs.
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"System Error: Unable to connect to CFO module. {str(e)}"