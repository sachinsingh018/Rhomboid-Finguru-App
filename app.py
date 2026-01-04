import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="CIBIL PDF Extractor", layout="centered")

st.title("📄 CIBIL PDF Account Extractor")
st.write("Upload a CIBIL PDF and download structured account data as CSV or Excel.")

# ---------- Helper functions ----------
def clean_amount(text):
    if not text:
        return ""
    return re.sub(r"[₹, ]", "", text)

def extract_value(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

# ---------- File upload ----------
uploaded_file = st.file_uploader("Upload CIBIL PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Processing PDF..."):
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        accounts = []
        blocks = re.split(r"\nMember Name\n", full_text)

        for block in blocks[1:]:
            block = "Member Name\n" + block

            account = {
                "Member Name": extract_value(r"Member Name\s*\n([A-Z &]+)", block),
                "Account Type": extract_value(r"Account Type\s*\n(.+)", block),
                "Account Number": extract_value(r"Account Number\s*\n([A-Z0-9]+)", block),
                "Ownership": extract_value(r"Ownership\s*\n([A-Za-z]+)", block),
                "Sanctioned Amount (₹)": clean_amount(
                    extract_value(r"Sanctioned Amount ₹([0-9,]+)", block)
                ),
                "Current Balance (₹)": clean_amount(
                    extract_value(r"Current Balance ₹([0-9,]+)", block)
                ),
                "Amount Overdue (₹)": clean_amount(
                    extract_value(r"Amount Overdue ₹([0-9,]+)", block)
                ),
                "Date Opened": extract_value(r"Date Opened / Disbursed ([0-9/]+)", block),
                "Date Closed": extract_value(r"Date Closed ([0-9/]+)", block),
                "Date Reported": extract_value(
                    r"Date Reported And Certified ([0-9/]+)", block
                ),
                "Status of loan": extract_value(
                    r"PAYMENT STATUS\s*\n([A-Z: ]+)", block
                ),
            }

            if account["Member Name"]:
                accounts.append(account)

        if not accounts:
            st.error("No accounts found. PDF format may differ.")
        else:
            df = pd.DataFrame(accounts)

            st.success(f"Extracted {len(df)} accounts")
            st.dataframe(df, use_container_width=True)

            # ---------- Downloads ----------
            csv_buffer = BytesIO()
            xlsx_buffer = BytesIO()

            df.to_csv(csv_buffer, index=False)
            df.to_excel(xlsx_buffer, index=False)

            st.download_button(
                "⬇️ Download CSV",
                csv_buffer.getvalue(),
                file_name="cibil_accounts.csv",
                mime="text/csv",
            )

            st.download_button(
                "⬇️ Download Excel",
                xlsx_buffer.getvalue(),
                file_name="cibil_accounts.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
