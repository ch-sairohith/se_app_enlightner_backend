
# ==============================================================
# 📌 Bible Verse Extractor with Gemini + Firestore (Path Input) - V3
# ==============================================================
#
# INSTRUCTIONS:
# 1. Run this script in your terminal.
# 2. When prompted, paste your Gemini API Key and press Enter.
# 3. When prompted, paste the FULL FILE PATH to your Firebase serviceAccountKey.json file and press Enter.
# 4. When prompted, paste the FULL FILE PATH to your Bible JSON file and press Enter.
#    (This script assumes a JSON structure like: {"Genesis": {"1": {"1": "Verse text...", ...}}})
#
# Install dependencies once via terminal:
# pip install google-generativeai firebase-admin

import json
import time
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# ================================
# 1. Runtime Input Collection
# ================================
print("--- Setup: Please provide the required information ---")

# Get Gemini API Key from terminal
GEMINI_API_KEY = input("🔑 Enter your Gemini API Key and press Enter: ").strip()

# Get Firebase Credentials using a file path
print("\n🔑 Please provide the full path to your Firebase Service Account JSON file.")
firebase_key_path = input("C:\se_app_project\data-processing\serviceAccountKey.json").strip()

# Get Bible JSON data using a file path
print("\n📖 Please provide the full path to your Bible JSON file.")
bible_json_path = input("C:\se_app_project\data-processing\Bible.pdf").strip()


print("\n--- ✅ Setup Complete. Starting processing... ---\n")

# ================================
# 2. API and Database Initialization
# ================================
try:
    # --- Gemini API Setup ---
    genai.configure(api_key=GEMINI_API_KEY)

    # --- Firebase Firestore Init ---
    cred = credentials.Certificate(firebase_key_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    # --- Parse Bible Data from selected file ---
    with open(bible_json_path, 'r', encoding='utf-8') as f:
        bible_data = json.load(f)

except FileNotFoundError as e:
    print(f"❌ Error: A file was not found. Please double-check the path you provided. Details: {e}")
    exit()
except json.JSONDecodeError as e:
    print(f"❌ Error: The selected JSON file is not formatted correctly. Details: {e}")
    exit()
except Exception as e:
    print(f"❌ An error occurred during initialization: {e}")
    exit()

# ================================
# 3. Bible Data Reader
# ================================
def extract_bible_chunks(data):
    """
    Generator function to yield chapters from the Bible JSON data.
    Each yielded item is a "chunk" to be processed.
    """
    for book, chapters in data.items():
        for chapter, verses in chapters.items():
            # Format the chapter text for the prompt
            chapter_text = f"Book: {book}, Chapter: {chapter}\n"
            for verse_num, text in verses.items():
                chapter_text += f"{verse_num}. {text}\n"
            yield book, chapter, chapter_text

# ================================
# 4. Gemini Prompt for Bible
# ================================
def process_with_gemini(book_name, chapter_num, chapter_text):
    """Sends Bible chapter text to Gemini and returns structured verse data."""
    prompt = f"""
You are a Bible verse analyzer.
Extract each verse from the provided text and return the data in this exact format for each verse.
Do not include explanations, markdown, or any extra symbols.

topicId: <BookName_ChapterNumber_VerseNumber>
topicName: <A short, descriptive topic name for the verse>
verse: <BookName Chapter:VerseNumber>
scriptureText: <The actual verse text>
religion: Christianity
qualities: <Comma-separated qualities or virtues found in the verse>
meaning: <A single descriptive paragraph explaining the verse's meaning. Must be a plain string.>
book: <Book Name>
chapter: <Chapter Number>
tags: <Comma-separated tags relevant to the verse content>

---
Text to analyze:
{chapter_text}
---
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"⚠ Error calling Gemini API: {e}")
        return "" # Return empty string on error to avoid crashing the loop

# ================================
# 5. Main Processing Loop
# ================================
all_gemini_outputs = []
print("🔥 Starting to process Bible chapters with Gemini...\n")

total_chunks = sum(len(chapters) for chapters in bible_data.values())
processed_count = 0

for book, chapter, text_chunk in extract_bible_chunks(bible_data):
    processed_count += 1
    print(f"📖 Processing {book} Chapter {chapter} ({processed_count}/{total_chunks})...")
    structured_text = process_with_gemini(book, chapter, text_chunk)

    if structured_text:
        print(f"✅ Received structured data for {book} {chapter}.")
        all_gemini_outputs.append(structured_text)
    else:
        print(f"⚠ No output from Gemini for {book} {chapter}. Skipping.")
    
    time.sleep(1) # Add a 1-second delay to avoid hitting API rate limits
    print("-" * 20)

# ================================
# 6. Save to Firestore
# ================================
if not all_gemini_outputs:
    print("❌ No data was processed from Gemini. Nothing to save.")
else:
    choice = input("\n✅ Do you want to save ALL processed verses to Firestore? (yes/no): ").strip().lower()
    if choice == "yes":
        verse_count = 0
        collection_ref = db.collection("bible_verses")
        print("\n💾 Saving verses to Firestore...")
        for output in all_gemini_outputs:
            # Each verse block is separated by a double newline
            for block in output.split("\n\n"):
                if not block.strip():
                    continue

                # --- ROBUST PARSING LOGIC ---
                # Handles multi-line values, especially for the 'meaning' field.
                data = {}
                last_key = None
                for line in block.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        data[key] = value.strip()
                        last_key = key
                    elif last_key and line.strip():
                        # This is a continuation of the previous line's value (e.g., a multi-line paragraph)
                        data[last_key] += " " + line.strip()
                
                # Use topicId for a unique and descriptive document ID
                if "topicId" in data:
                    # Sanitize topicId for Firestore: replace invalid characters
                    doc_id_raw = data['topicId'].replace(" ", "").replace(":", "").replace("/", "_")
                    doc_id = f"bible_{doc_id_raw}"
                    collection_ref.document(doc_id).set(data)
                    verse_count += 1
                else:
                    print(f"⚠ Skipping block due to missing 'topicId':\n{block}\n")

        print(f"\n✨ Success! Saved {verse_count} verses to the 'bible_verses' collection in Firestore.")
    else:
        print("🔵 Skipped saving to Firestore as requested.")