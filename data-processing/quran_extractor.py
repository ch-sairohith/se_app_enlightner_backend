# ================================
# 📌 Quran Verse Extractor with Gemini + Firestore (Local Machine)
# ================================

# Install once via terminal:
# pip install PyPDF2 google-generativeai firebase-admin

import os
import json
import PyPDF2
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# ================================
# 1. File Paths (replace with your local paths)
# ================================
quran_pdf_path = r"C:\se_app_project\data-processing\quran.pdf"
firebase_key_path = r"C:\se_app_project\data-processing\serviceAccountKey.json"

# ================================
# 2. Gemini API Setup
# ================================
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
genai.configure(api_key="AIzaSyCeLWRjRbTH-diAj8ZbxxcEF5vWG-ufYjE")

# ================================
# 3. Firebase Firestore Init
# ================================
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ================================
# 4. PDF Reader
# ================================
def extract_batches(pdf_path, batch_size=3):
    """Extracts text from the PDF in batches of pages with carryover buffer."""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        num_pages = len(reader.pages)

        buffer = ""
        for start in range(0, num_pages, batch_size):
            end = min(start + batch_size, num_pages)
            text = ""

            for i in range(start, end):
                text += reader.pages[i].extract_text() + "\n"

            yield buffer + text, start + 1, end
            buffer = text[-500:]  # carryover context


# ================================
# 5. Gemini Prompt
# ================================
def process_with_gemini(batch_text, chapter_num, batch_num):
    """Sends text to Gemini and returns structured verse data."""
    prompt = f"""
You are a Quran verse analyzer.  
Extract each verse and return data in this exact format (no explanations, no markdown, no extra symbols):

topicId : <chapter_verse>
topicName: <short topic name>
verse: <chapter:verse>
scriptureText: <actual verse text>
religion: Islam
qualities: <comma-separated qualities>
meaning: <single descriptive paragraph, plain string — no JSON>
book: Quran
chapter: <chapter number>
tags: <comma-separated tags>

Text to analyze:
{batch_text}
"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    return response.text.strip() if response.text else ""


# ================================
# 6. Main Loop
# ================================
all_outputs = []
for i, (batch_text, start_page, end_page) in enumerate(extract_batches(quran_pdf_path, batch_size=3), start=1):
    print(f"\n📖 Processing Pages {start_page}-{end_page}...\n")
    structured_text = process_with_gemini(batch_text, chapter_num=i, batch_num=i)

    print("📌 Gemini Output:\n", structured_text)
    all_outputs.append(structured_text)

# ================================
# 7. Save to Firestore? (yes/no once at end)
# ================================
choice = input("\n✅ Do you want to save ALL verses to Firestore? (yes/no): ").strip().lower()
if choice == "yes":
    for output in all_outputs:
        for block in output.split("\n\n"):
            if not block.strip():
                continue

            # Parse fields manually
            data = {}
            for line in block.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    data[key.strip()] = value.strip()

            if "chapter" in data and "verse" in data:
                doc_id = f"quran_chapter_{data['chapter']}verse{data['verse'].replace(':','_')}"
                db.collection("quran_verses").document(doc_id).set(data)

    print("✅ All verses saved to Firestore successfully!")
else:
    print("⚠ Skipped saving to Firestore.")
