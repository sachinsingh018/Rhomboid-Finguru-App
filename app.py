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
        return "0"
    return re.sub(r"[₹, ]", "", text)

def extract_value(pattern, text):
    # DOTALL handles broken / wrapped PDF lines
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_date(label_pattern, text):
    """
    Extracts:
    - dd/mm/yyyy
    - OR '-' (for open accounts)
    Works whether date is on same line or next line
    """
    pattern = rf"{label_pattern}\s*(?:\n|\s)+(\d{{2}}/\d{{2}}/\d{{4}}|-)"
    return extract_value(pattern, text)

# ---------- File upload ----------
uploaded_file = st.file_uploader("Upload CIBIL PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Processing PDF..."):
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        accounts = []

        # Split by account blocks
        blocks = re.split(r"\nMember Name\n", full_text)

        for block in blocks[1:]:
            block = "Member Name\n" + block

            # Hard stop to avoid footer noise
            block = block.split("\nPAYMENT STATUS", 1)[0]

            account = {
                "Member Name": extract_value(
                    r"Member Name\s*\n([A-Za-z &]+)", block
                ),
                "Account Type": extract_value(
                    r"Account Type\s*\n([^\n]+)", block
                ),
                "Account Number": extract_value(
                    r"Account Number\s*\n([A-Z0-9/-]+)", block
                ),
                "Ownership": extract_value(
                    r"Ownership\s*\n([A-Za-z]+)", block
                ),
                "Sanctioned Amount (₹)": clean_amount(
                    extract_value(r"Sanctioned Amount ₹([0-9,]+)", block)
                ),
                "Current Balance (₹)": clean_amount(
                    extract_value(r"Current Balance ₹([0-9,]+)", block)
                ),
                "Amount Overdue (₹)": clean_amount(
                    extract_value(r"Amount Overdue ₹([0-9,]+)", block)
                ),

                # ✅ FIXED DATE EXTRACTION
                "Date Opened": extract_date(
                    r"Date\s+Opened\s*/\s*Disbursed", block
                ),
                "Date Closed": extract_date(
                    r"Date\s+Closed", block
                ),
                "Date Reported": extract_date(
                    r"Date\s+Reported\s+And\s+Certified", block
                ),
            }

            # Optional: convert '-' to empty string
            if account["Date Closed"] == "-":
                account["Date Closed"] = ""

            # Validation
            if account["Member Name"] and account["Account Number"]:
                accounts.append(account)

        if not accounts:
            st.error("No valid accounts found. PDF layout may differ.")
        else:
            df = pd.DataFrame(accounts)

            st.success(f"Extracted {len(df)} valid accounts")
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
