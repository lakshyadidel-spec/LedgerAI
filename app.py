"""
LedgerAI - Main Application Entry Point
---------------------------------------
Handles UI routing, component rendering, and session state management.
"""

import os
import pandas as pd
import streamlit as st
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# --- Internal Modules ---
# Note: Importing from core.db will automatically trigger init_db() and seed data!
from core.db import get_connection, save_invoice_to_db, mark_as_reconciled
from core.analytics import render_financial_dashboard
from agents.invoice_agents import get_cfo_response, process_pdf_with_gemini
from agents.reconciliation_agents import reconcile_invoice_with_ai

def init_session_state() -> None:
    """Initialize required Streamlit session state variables."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def load_financial_context() -> str:
    """
    Loads and formats bank data from SQLite to serve as context for the AI Agent.
    Strictly filters for the active tenant (company_id = 1).
    """
    try:
        conn = get_connection()
        # Multi-Tenancy Update: Only fetch transactions for Company 1
        df = pd.read_sql_query("SELECT * FROM transactions WHERE company_id = 1", conn)
        conn.close()
        
        if df.empty:
            return "System Warning: Database is empty. No financial context available."
            
        total_balance = df['amount'].sum()
        recent_txns = df.tail(10).to_string(index=False)
        return f"Current Balance: ${total_balance:,.2f}\nRecent Transactions:\n{recent_txns}"
    except Exception as e:
        return f"System Error reading database: {str(e)}"


def render_header() -> None:
    """Renders the application header."""
    st.set_page_config(page_title="LedgerAI | AI CFO", layout="wide")
    st.title("⚖️ LedgerAI Dashboard")
    st.markdown("**Your Fractional AI CFO — Powered by Gemini**")
    st.divider()


def render_invoice_processor() -> None:
    """Renders the PDF Upload, extraction, and automated Reconciliation UI."""
    st.subheader("📄 AI Invoice Processing & Reconciliation")
    uploaded_file = st.file_uploader("Upload Vendor PDF Invoice", type="pdf")

    if uploaded_file:
        try:
            # 1. AI Extraction Pipeline
            with st.spinner("Extracting data with Gemini..."):
                extracted_data = process_pdf_with_gemini(uploaded_file)
            
            # Safely parse the amount
            try:
                raw_amount = str(extracted_data.get("total_amount", 0)).replace("$", "").replace(",", "").strip()
                amount_float = float(raw_amount)
            except ValueError:
                amount_float = 0.0

            # 2. Persist to Database and get the Invoice ID
            invoice_id = save_invoice_to_db(
                vendor_name=extracted_data.get("vendor_name", "Unknown"),
                invoice_number=extracted_data.get("invoice_number", "N/A"),
                total_amount=amount_float,
                due_date=extracted_data.get("due_date", "Unknown")
            )
            
            # 3. UI Presentation of Extracted JSON
            st.success("Invoice successfully processed and saved to Database!")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Vendor", extracted_data.get("vendor_name", "Unknown"))
            col2.metric("Invoice #", extracted_data.get("invoice_number", "N/A"))
            col3.metric("Amount", f"${amount_float:,.2f}")
            col4.metric("Due Date", extracted_data.get("due_date", "Unknown"))
            
            # 4. AI-Driven Reconciliation Engine
            conn = get_connection()
            transactions_df = pd.read_sql_query("SELECT * FROM transactions WHERE company_id = 1", conn)
            conn.close()
            
            st.divider()
            with st.spinner("Running AI fuzzy matching and edge-case resolution..."):
                recon_result = reconcile_invoice_with_ai(extracted_data, transactions_df)
            
            # Display the AI's verdict dynamically
            if recon_result.get("status") in ["Exact Match", "AI Reconciled (With Fees)"]:
                st.success(f"✅ **Reconciliation Status: {recon_result.get('status')}**")
                
                # Show AI reasoning for edge-cases
                if recon_result.get("status") == "AI Reconciled (With Fees)" and "reason" in recon_result:
                    st.info(f"🧠 **AI Reasoning:** {recon_result.get('reason')}")
                    
                st.write("**Matched Bank Transaction:**")
                st.json(recon_result.get("matched_data", {}))
                
                # IMPORTANT: Actually update the database status to Reconciled
                if invoice_id != -1 and "transaction_id" in recon_result:
                    mark_as_reconciled(invoice_id, recon_result["transaction_id"])
                    
            else:
                st.warning(f"⚠️ **Reconciliation Status: {recon_result.get('status', 'Unmatched')}**")
                st.write(recon_result.get("reason", "No matching payment found in bank transactions."))

        except Exception as e:
            st.error(f"An error occurred while processing the invoice: {e}")

    st.divider()

def render_export_section() -> None:
    """Renders the export button for the accountant's report."""
    st.subheader("📥 Export Accountant Report")
    st.write("Download the fully reconciled invoice data for your CA or ERP system.")
    
    try:
        conn = get_connection()
        # Fetching invoices with their reconciliation status
        query = """
            SELECT invoice_number, vendor_name, total_amount, due_date, reconciliation_status 
            FROM invoices 
            WHERE company_id = 1
        """
        df_export = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_export.empty:
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Reconciled CSV",
                data=csv,
                file_name="ledgerai_reconciled_report.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.info("No invoice data available to export yet. Process an invoice first!")
    except Exception as e:
        st.error(f"Failed to generate export: {e}")


def render_ai_cfo_chat(context_data: str) -> None:
    """Renders the conversational interface for financial queries."""
    st.subheader("🤖 Chat with Bea (AI CFO)")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Query your burn rate, expenses, or runway...")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.spinner("Analyzing financial data..."):
            ai_response = get_cfo_response(
                messages=st.session_state.chat_history, 
                context_data=context_data
            )
            
        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant"):
            st.write(ai_response)


def main() -> None:
    """Main execution block."""
    init_session_state()
    render_header()
    
    # Section 1: Visual Intelligence
    render_financial_dashboard()
    st.divider()
    
    # Section 2: Core Processing MVP
    render_invoice_processor()
    
    # Section 3: Export Data (The Handshake)
    render_export_section()
    st.divider()
    
    # Section 4: AI Assistant Interface
    financial_context = load_financial_context()
    render_ai_cfo_chat(financial_context)


if __name__ == "__main__":
    main()