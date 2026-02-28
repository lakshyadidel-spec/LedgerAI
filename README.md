# LedgerAI ⚖️ | Automated Financial Reconciliation Engine

LedgerAI is an AI-native tool designed to eliminate the manual bottleneck of matching vendor invoices to bank statements. It uses LLMs and contextual logic to automate data entry and reconcile transactions, even when amounts differ slightly due to processing fees (like Stripe or PayPal).

## 🚀 The Core Problem
Founders and accountants waste hours every month cross-referencing PDF invoices with bank CSVs. Manual entry is prone to human error, and hidden transaction fees make exact matching a nightmare.

## ✨ How It Solves the Problem
- **Zero Data Entry:** Ingests unstructured PDF invoices and extracts Vendor Name, Amount, and Due Date automatically using Gemini 2.5 Flash.
- **Smart Reconciliation:** Cross-references the extracted data with bank statements to find exact or contextual matches (handling gateway fees intelligently).
- **Audit-Ready Export:** Generates a 100% reconciled CSV report that can be handed directly to a CA or uploaded to an ERP system.
- **AI CFO Chatbot:** Allows users to query their financial data (runway, burn rate) conversationally.

## 🛠️ Tech Stack
- **Frontend:** Streamlit, Plotly
- **AI Engine:** Google Gemini 2.5 Flash, PyPDF2
- **Data Matching:** Pandas, TheFuzz (Fuzzy String Matching)
- **Database:** SQLite (Multi-tenant architecture ready)
