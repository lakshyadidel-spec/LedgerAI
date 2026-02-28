"""
LedgerAI - Database Management Engine
-------------------------------------
Handles SQLite connection, Multi-Tenant Double-Entry Schema creation, 
and CSV-to-DB migration.
"""

import sqlite3
import pandas as pd
import os

# 🚀 THE FIX: We renamed the database to force a completely fresh build
DB_PATH = "data/ledger_v2.db"
CSV_PATH = "data/bank_statement.csv"

def get_connection():
    """Returns a connection to the SQLite database with Foreign Keys enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes the multi-tenant, double-entry database schema."""
    os.makedirs("data", exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    # --- 1. ENTERPRISE GAAP TABLES ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            entry_date DATE NOT NULL,
            description TEXT,
            reference_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger_lines (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            debit REAL DEFAULT 0.00,
            credit REAL DEFAULT 0.00,
            FOREIGN KEY (entry_id) REFERENCES journal_entries(entry_id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        )
    ''')

    # --- 2. STAGING TABLES ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER DEFAULT 1,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'Unreconciled',
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER DEFAULT 1,
            vendor_name TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            total_amount REAL NOT NULL,
            due_date TEXT,
            reconciliation_status TEXT DEFAULT 'Pending',
            FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

def seed_default_company():
    """Seeds a default company and chart of accounts for MVP testing."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if we already have a company
    cursor.execute("SELECT COUNT(*) FROM companies")
    if cursor.fetchone()[0] == 0:
        # Create Default Company
        cursor.execute("INSERT INTO companies (company_name) VALUES ('LedgerAI Startup')")
        company_id = cursor.lastrowid
        
        # Create Default Chart of Accounts
        default_accounts = [
            (company_id, 'Chase Checking', 'Asset'),
            (company_id, 'Accounts Receivable', 'Asset'),
            (company_id, 'Software Revenue', 'Revenue'),
            (company_id, 'Stripe Processing Fees', 'Expense')
        ]
        
        # Explicit column naming to prevent any schema mismatch errors
        cursor.executemany('''
            INSERT INTO accounts (company_id, account_name, account_type) 
            VALUES (?, ?, ?)
        ''', default_accounts)
        
        print("✅ Seeded Default Company and Chart of Accounts.")
        
    conn.commit()
    conn.close()

def migrate_csv_to_db():
    """Utility function to load dummy CSV data into SQLite for the first time."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM transactions")
    if cursor.fetchone()[0] == 0:
        if os.path.exists(CSV_PATH):
            try:
                df = pd.read_csv(CSV_PATH)
                df.columns = [col.lower() for col in df.columns]
                df['company_id'] = 1 
                df['status'] = 'Unreconciled' 
                df.to_sql('transactions', conn, if_exists='append', index=False)
                print("✅ Migration Successful: CSV data loaded into 'transactions' table.")
            except Exception as e:
                print(f"❌ Migration Error: {e}")
        else:
            print("⚠️ No CSV found. Injecting fallback dummy transactions so the demo works.")
            seed_transactions = [
                (1, '2026-03-10', 'Amazon Web Services', 150.00, 'Debit', 'Unreconciled'),
                (1, '2026-03-12', 'Stripe Payout', 2500.00, 'Credit', 'Unreconciled'),
                (1, '2026-03-15', 'GitHub Copilot', 10.00, 'Debit', 'Unreconciled'),
                (1, '2026-03-18', 'GCP Cloud Compute', 342.50, 'Debit', 'Unreconciled')
            ]
            cursor.executemany('''
                INSERT INTO transactions (company_id, date, description, amount, type, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', seed_transactions)
            
    conn.commit()
    conn.close()

def save_invoice_to_db(vendor_name: str, invoice_number: str, total_amount: float, due_date: str, company_id: int = 1) -> int:
    """Saves the Gemini-extracted invoice data and returns the generated Invoice ID."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO invoices (company_id, vendor_name, invoice_number, total_amount, due_date, reconciliation_status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        ''', (company_id, vendor_name, invoice_number, total_amount, due_date))
        
        invoice_id = cursor.lastrowid # Get the ID of the newly inserted row
        
        conn.commit()
        conn.close()
        print(f"✅ Success: Invoice {invoice_number} saved to DB with ID {invoice_id}.")
        return invoice_id
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return -1

def mark_as_reconciled(invoice_id: int, transaction_id: int) -> None:
    """Updates both the invoice and transaction status to Reconciled."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Update Invoice Status
        cursor.execute("UPDATE invoices SET reconciliation_status = 'Reconciled' WHERE id = ?", (invoice_id,))
        
        # Update Bank Transaction Status
        cursor.execute("UPDATE transactions SET status = 'Reconciled' WHERE id = ?", (transaction_id,))
        
        conn.commit()
        conn.close()
        print(f"🔗 Database Updated: Invoice {invoice_id} linked with Transaction {transaction_id}")
    except Exception as e:
        print(f"❌ Database Update Error: {e}")

# --- Initialize Everything on Import ---
init_db()
seed_default_company()
migrate_csv_to_db()