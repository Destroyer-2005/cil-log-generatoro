import streamlit as st
import re
import pdfplumber
import pandas as pd
from io import BytesIO
import openai
import os

st.set_page_config(page_title="CIL Log Generator", layout="wide")
st.title("📋 Contract Item List (CIL) Log Generator for Contractors")

uploaded_pdf = st.file_uploader("Upload Specification PDF", type="pdf")

SUBMITTAL_TYPES = [
    "As-Builts", "Attic Stock", "Certificates", "Closeout", "Deferred Submittals",
    "Delegated Design", "Calculations", "Document", "General", "Installation Instructions",
    "LEED Submittals", "Maintenance Data", "Meeting", "Mixed Designs", "Mock-up",
    "O&M Manuals", "Other", "Pay request", "Payroll", "Photos", "Plans", "Prints",
    "Product data", "Product information", "Product Manual", "Qualification data",
    "Quality Assurance", "Reports", "Safety", "Sample", "Schedule", "Shop Drawing",
    "Source/Field Quality Control", "Specification", "Test/Inspections", "Training", "Warranty"
]

SUBMIT_KEYWORDS = [
    "contractor shall", "submit", "furnish", "provide",
    "installation instructions", "warranty", "as-built", "sample", "data"
]

SECTION_PATTERN = re.compile(r"SECTION\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*-\s*(.+)", re.IGNORECASE)

openai.api_key = os.getenv("OPENAI_API_KEY")

def detect_submittal_type(description):
    desc_lower = description.lower()
    for stype in SUBMITTAL_TYPES:
        if stype.lower() in desc_lower:
            return stype
    return ""

def extract_cil_entries(full_text):
    results = []
    section_number = ""
    section_title = ""
    lines = full_text.split("\n")
    for i, line in enumerate(lines):
        match = SECTION_PATTERN.match(line)
        if match:
            section_number = match.group(1) + match.group(2) + match.group(3)
            section_title = match.group(4).strip()
        if any(keyword in line.lower() for keyword in SUBMIT_KEYWORDS):
            desc_lines = [line.strip()]
            for j in range(1, 15):
                if (i + j) < len(lines):
                    next_line = lines[i + j].strip()
                    if next_line == "" or re.match(r"SECTION", next_line, re.IGNORECASE):
                        break
                    desc_lines.append(next_line)
            description = "\n".join(desc_lines)
            submittal_type = detect_submittal_type(description)
            results.append({
                "Submittal Spec Section Number": section_number,
                "Submittal Spec Section Description": section_title,
                "Submittal Number": f"S{len(results)+1:03}",
                "Description": description,
                "Submittal Type": submittal_type
            })
    return results

def summarize_with_gpt(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes technical construction descriptions."},
                {"role": "user", "content": f"Summarize this for a construction log:\n{text}"}
            ],
            max_tokens=100
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "Summary failed"

if uploaded_pdf:
    with st.spinner("📄 Reading and analyzing PDF..."):
        try:
            with pdfplumber.open(uploaded_pdf) as pdf:
                full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

            entries = extract_cil_entries(full_text)
            if entries:
                df = pd.DataFrame(entries)

                with st.expander("🔍 Filter Options"):
                    selected_type = st.selectbox("Submittal Type Filter", ["All"] + SUBMITTAL_TYPES)
                    if selected_type != "All":
                        df = df[df["Submittal Type"] == selected_type]

                if st.checkbox("🧠 Enable AI Description Summarization"):
                    with st.spinner("🔎 Summarizing descriptions with GPT..."):
                        df["Summary"] = df["Description"].apply(summarize_with_gpt)

                st.success(f"✅ Found {len(df)} relevant submittals.")
                edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

                output = BytesIO()
                edited_df.to_excel(output, index=False)
                output.seek(0)
                st.download_button("📥 Download CIL Log (Excel)", output, file_name="CIL_Log.xlsx")
            else:
                st.warning("⚠ No contractor-required submittals found.")
        except Exception as e:
            st.exception("❌ An error occurred while processing the PDF.")
