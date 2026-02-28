"""
LedgerAI - Visual Analytics Engine
----------------------------------
Renders Plotly charts and KPIs using data directly from SQLite.
"""

import pandas as pd
import plotly.express as px
import streamlit as st
from core.db import get_connection

def render_financial_dashboard():
    try:
        # 1. Connect to DB and fetch data using SQL (Filtered for active tenant)
        conn = get_connection()
        query = "SELECT * FROM transactions WHERE company_id = 1"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            st.warning("⚠️ No transactions found in the database.")
            return

        # 2. Data Formatting
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date') # Crucial for accurate time-series line charts!
        
        # 3. Math Engine: Calculate Top-Level Metrics
        total_spent = df[df['type'].str.lower() == 'debit']['amount'].sum()
        total_received = df[df['type'].str.lower() == 'credit']['amount'].sum()
        net_cash_flow = total_received - total_spent
        
        # --- UI: KPI Metrics ---
        st.markdown("### 📊 Real-Time Financial Overview")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Income", f"${total_received:,.2f}")
        col2.metric("Total Burn (Expenses)", f"${total_spent:,.2f}")
        col3.metric("Net Cash Flow", f"${net_cash_flow:,.2f}", delta=float(net_cash_flow))
        
        st.divider()

        # --- UI: Charts ---
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            # Cash Flow Trend
            daily_flow = df.groupby('date')['amount'].sum().reset_index()
            fig_line = px.line(
                daily_flow, 
                x='date', 
                y='amount', 
                title='Daily Transaction Volume', 
                markers=True,
                line_shape='spline'
            )
            st.plotly_chart(fig_line, use_container_width=True)

        with col_chart2:
            # Expense Breakdown
            expenses = df[df['type'].str.lower() == 'debit']
            
            # Safety check in case there are no expenses yet
            if not expenses.empty:
                fig_pie = px.pie(
                    expenses, 
                    values='amount', 
                    names='description', 
                    title='Expense Breakdown', 
                    hole=0.4
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No expense data available for breakdown.")

    except Exception as e:
        st.error(f"Error generating dashboard from Database: {e}")