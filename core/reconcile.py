import pandas as pd
import json

def match_invoice_to_bank(ai_invoice_json: str, bank_csv_path: str):
    # 1. AI ka JSON data read karo
    invoice_data = json.loads(ai_invoice_json)
    ai_vendor = invoice_data['vendor_name']
    ai_amount = float(invoice_data['total_amount'])
    
    # 2. Bank Statement (CSV) read karo
    try:
        df = pd.read_csv(bank_csv_path)
    except FileNotFoundError:
        return {"status": "error", "message": "bank_statement.csv file nahi mili!"}

    # 3. Match karne ka logic
    match_found = df[df['Amount'] == ai_amount]
    
    if not match_found.empty:
        # Match mil gaya! Bank entry ki details nikaalo
        date = match_found.iloc[0]['Date']
        desc = match_found.iloc[0]['Description']
        return {
            "status": "success", 
            "message": f"✅ Payment Matched! ₹{ai_amount} aapke account se {date} ko '{desc}' ke naam par cut chuke hain."
        }
    else:
        # Match nahi mila (Unpaid)
        return {
            "status": "warning", 
            "message": f"⚠️ ALERT: ₹{ai_amount} ka koi transaction bank mein nahi mila. '{ai_vendor}' ki payment pending hai!"
        }