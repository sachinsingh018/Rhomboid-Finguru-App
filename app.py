import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="CIBIL PDF Extractor", layout="centered")

st.title("📄 CIBIL PDF Account Extractor")
st.write("Upload a CIBIL PDF and download structured account data as CSV or Excel.")

def normalize_text(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

# ---------- Helper functions ----------
def clean_amount(text):
    if not text:
        return ""
    return re.sub(r"[₹, ]", "", text)

def extract_value(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_date(label_pattern, text):
    """
    Robust date extractor:
    - dd/mm/yyyy
    - OR '-'
    Handles inline / wrapped labels
    """
    pattern = rf"{label_pattern}[\s:]*([\d]{{2}}/[\d]{{2}}/[\d]{{4}}|-)"
    return extract_value(pattern, text)

def extract_text_field(label_pattern, text):
    """
    Generic text extractor for collateral fields
    """
    pattern = rf"{label_pattern}[\s:]*([^\n]+)"
    return extract_value(pattern, text)

# ---------- File upload ----------
uploaded_file = st.file_uploader("Upload CIBIL PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Processing PDF..."):
        with pdfplumber.open(uploaded_file) as pdf:
            raw_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            full_text = normalize_text(raw_text)
            # >>> ADD HERE: detect where CLOSED ACCOUNTS section begins
            closed_match = re.search(r"\bCLOSED ACCOUNTS\b", full_text, re.IGNORECASE)
            closed_accounts_pos = closed_match.start() if closed_match else None


        accounts = []

        member_blocks = list(re.finditer(r"\nMember Name\n", full_text))

        for i, match in enumerate(member_blocks):
            start = match.start() + 1
            end = member_blocks[i + 1].start() if i + 1 < len(member_blocks) else len(full_text)

            block = full_text[start:end]
            block = block.split("\nPAYMENT STATUS", 1)[0]


            account_status = "Open"
            if closed_accounts_pos is not None and start > closed_accounts_pos:
                account_status = "Closed"
                
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

                # ---------- Dates ----------
                "Date Opened / Disbursed": extract_date(
                    r"Date\s*Opened\s*/?\s*Disbursed", block
                ),
                "Date of Last Payment": extract_date(
                    r"Date\s*of\s*Last\s*Payment", block
                ),
                "Date Closed": extract_date(
                    r"Date\s*Closed", block
                ),
                "Date Reported And Certified": extract_date(
                    r"Date\s*Reported\s*And\s*Certified", block
                ),
                "Payment Start Date": extract_date(
                    r"Payment\s*Start\s*Date", block
                ),
                "Payment End Date": extract_date(
                    r"Payment\s*End\s*Date", block
                ),

                # ---------- Collateral ----------
                "Value of Collateral": clean_amount(
                    extract_text_field(r"Value\s*of\s*Collateral", block)
                ),
                "Type of Collateral": extract_text_field(
                    r"Type\s*of\s*Collateral", block
                ),
                "Account Status": account_status,

            }

            # Normalize "-" to empty
            for k, v in account.items():
                if v == "-":
                    account[k] = ""

            if account["Member Name"] and account["Account Number"]:
                accounts.append(account)

        if not accounts:
            st.error("No valid accounts found. PDF layout may differ.")
        else:
            df = pd.DataFrame(accounts)

            st.success(f"Extracted {len(df)} valid accounts")
            st.dataframe(df, use_container_width=True)

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
