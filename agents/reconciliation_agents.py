"""
LedgerAI - Reconciliation Engine
--------------------------------
Uses Fuzzy String Matching and Gemini 2.5 Flash to link messy bank 
transactions with structured invoice data.
"""

import os
import pandas as pd
from thefuzz import fuzz
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables (GEMINI_API_KEY)
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def reconcile_invoice_with_ai(invoice_data: dict, transactions_df: pd.DataFrame) -> dict:
    """
    Takes an extracted invoice and tries to find its matching bank transaction.
    Returns a dictionary with status, confidence, and the matched transaction data.
    """
    # 1. Check if we even have bank data
    if transactions_df.empty:
        return {"status": "Pending", "reason": "No bank transactions available to match."}

    # Extract clean strings from the invoice data
    inv_vendor = str(invoice_data.get("vendor_name", "")).lower()
    inv_num = str(invoice_data.get("invoice_number", "")).lower()
    inv_amount = float(invoice_data.get("total_amount", 0.0))

    # Loop through every bank transaction to find a match
    for index, txn in transactions_df.iterrows():
        # Only look at Debits (since we are paying a vendor invoice)
        if str(txn['type']).lower() != 'debit':
            continue
            
        txn_desc = str(txn['description']).lower()
        txn_amount = float(txn['amount'])
        
        # --- LAYER 1: FUZZY STRING MATCHING ---
        # Checks how closely the bank description matches the vendor name or invoice number
        vendor_match = fuzz.partial_ratio(inv_vendor, txn_desc)
        num_match = fuzz.partial_ratio(inv_num, txn_desc)
        
        # We take the highest score (e.g., if "INV-1042" matches perfectly, score is 100)
        text_score = max(vendor_match, num_match)
        
        # --- LAYER 2: EXACT MATCH (THE HAPPY PATH) ---
        if inv_amount == txn_amount and text_score > 50:
            return {
                "status": "Exact Match",
                "transaction_id": txn['id'],
                "confidence": "100%",
                "reason": "Exact amount and strong text match found.",
                "matched_data": txn.to_dict()
            }
        
        # --- LAYER 3: AI EDGE-CASE RESOLUTION (FEES/DISCOUNTS) ---
        # What if the amount is slightly off? (e.g., $1000 invoice, but $970 paid due to $30 fee)
        amount_diff = abs(inv_amount - txn_amount)
        # Check if the difference is within a reasonable 5% payment gateway fee limit
        is_within_fee_range = amount_diff > 0 and amount_diff <= (inv_amount * 0.05)
        
        if text_score > 60 and is_within_fee_range:
            # The data looks close, but the math doesn't perfectly align. Ask the CFO (Gemini)!
            prompt = f"""
            You are an expert AI CFO. 
            We have a vendor invoice for '{inv_vendor}' (Invoice #{inv_num}) for ${inv_amount}.
            We have a bank transaction described as '{txn_desc}' for ${txn_amount}.
            
            Is it highly likely that this bank transaction is the payment for this invoice, 
            with the difference (${amount_diff}) being a bank processing fee or minor deduction?
            
            Answer strictly with 'YES' or 'NO', followed by a 1-sentence explanation.
            """
            
            try:
                model = genai.GenerativeModel("gemini-2.5-flash")
                response = model.generate_content(prompt)
                
                # Safely handle the response text to avoid crashes if the API blips
                if response and hasattr(response, 'text'):
                    ai_decision = response.text.strip().upper()
                    
                    if ai_decision.startswith("YES"):
                        return {
                            "status": "AI Reconciled (With Fees)",
                            "transaction_id": txn['id'],
                            "confidence": "90%",
                            "reason": response.text.strip(),
                            "matched_data": txn.to_dict()
                        }
            except Exception as e:
                print(f"Gemini API Error during reconciliation: {e}")
                
    # If the loop finishes and nothing matched
    return {"status": "Pending", "reason": "No matching payment found in bank transactions."}