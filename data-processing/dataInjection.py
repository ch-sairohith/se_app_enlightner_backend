# --- 1. IMPORTS ---
import os
import json 
import time
import google.generativeai as genai
import fitz # PyMuPDF
import re
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# --- 2. INITIALIZE SERVICES ---
def initialize_services():
    """Initializes Firebase and Gemini clients for a local environment."""
    load_dotenv()
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            print("✅ Firebase initialized successfully.")
        except Exception as e:
            print(f"🔥 Firebase initialization failed: {e}")
            return None, None
    db = firestore.client()
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            print("🔥 GEMINI_API_KEY not found in your .env file.")
            return db, None
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        print("✅ Gemini model initialized successfully.")
        return db, model
    except Exception as e:
        print(f"🔥 Gemini initialization failed: {e}")
        return db, None

# --- 3. AI & PDF FUNCTIONS ---
def extract_text_from_pages(pdf_doc, start_page, end_page):
    """Reads a specific range of pages from an open PDF document."""
    text = ""
    for page_num in range(start_page - 1, end_page):
        if page_num < len(pdf_doc):
            page = pdf_doc.load_page(page_num)
            text += page.get_text("text") + "\n"
    return text

def process_text_chunk(text_chunk, model):
    """Extracts and verifies verse data from a text chunk."""
    prompt = f"""
    You are a theological data analyst. I have a chunk of text from the "Bhagavad-gītā As It Is". Your task is to:
    1. Find every complete "TEXT" section within this chunk.
    2. For each section, create a JSON object with keys: verse, topicName, scriptureText, meaning, qualities, and tags.
    3. IMPORTANT: The 'verse' number MUST be the number that comes directly after the word "TEXT" (e.g., for "TEXT 36", the verse is 36).
    4. IMPORTANT: You MUST generate a descriptive 'topicName' for every single verse. Do not leave it blank or as "None".

    Respond with a valid JSON object containing a single key "verses", which is a list of all the verse objects you created. Also include a key "carry_over_context" with any incomplete text from the very end of the chunk.

    Text Chunk to Analyze:
    ---
    {text_chunk}
    ---
    """
    try:
        response = model.generate_content(prompt)
        json_string = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(json_string)
    except Exception as e:
        print(f"   🔥 Gemini processing error: {e}")
        return {"verses": [], "carry_over_context": ""}

# --- 4. MAIN FUNCTION ---
def process_chapter_in_batches(pdf_name, book_name, religion_name, chapter_number, start_page, end_page, collection_name='scripture_verses', batch_size=3):
    db, model = initialize_services()
    if not model or not db:
        return

    try:
        pdf_doc = fitz.open(pdf_name)
        print(f"📖 PDF '{pdf_name}' opened successfully.")
    except Exception as e:
        print(f"🔥 Could not open PDF: {e}")
        return

    all_final_verses = []
    carry_over_context = ""

    for page_num in range(start_page, end_page + 1, batch_size):
        batch_start = page_num
        batch_end = min(page_num + batch_size - 1, end_page)
        
        print(f"\n--- Processing Batch: Pages {batch_start} to {batch_end} ---")
        
        batch_text = extract_text_from_pages(pdf_doc, batch_start, batch_end)
        full_chunk_to_process = carry_over_context + " " + batch_text

        analysis_result = process_text_chunk(full_chunk_to_process, model)

        if analysis_result and "verses" in analysis_result and len(analysis_result['verses']) > 0:
            print(f"   ✅ Found and verified {len(analysis_result['verses'])} verse(s) in this batch.")
            all_final_verses.extend(analysis_result['verses'])
        else:
            print("   ...No complete verses found in this batch.")
            
        carry_over_context = analysis_result.get("carry_over_context", "")
        print(f"   ...Carry-over context for next batch: '{carry_over_context[:50]}...'")
        time.sleep(5)

    pdf_doc.close()
    
    if not all_final_verses:
        print("\nNo verses were extracted. Exiting.")
        return
        
    for verse in all_final_verses:
        verse['chapter'] = chapter_number
        verse['topicId'] = f"gita_chapter_{chapter_number}_verse_{verse.get('verse', 'N/A')}"

    output_filename = f"chapter_{chapter_number}_review.txt"
    print(f"\n--- Writing review file: {output_filename} ---")
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(f"--- Review for {book_name} - Chapter {chapter_number} ---\n\n")
        for verse in all_final_verses:
            f.write(f"ID: {verse.get('topicId', 'N/A')}, Name: {verse.get('topicName', 'N/A')}\n")
    print(f"✅ Review file created successfully.")
    
    print("\n--- MANUAL CORRECTION AND UPLOAD ---")
    print(f"Please review the file '{output_filename}'.")
    
    while True:
        user_input = input("Enter a topicId to correct, type 'ok' to upload, or 'cancel' to exit: ").lower()
        
        if user_input == 'ok':
            batch = db.batch()
            for verse in all_final_verses:
                doc_id = verse.get('topicId')
                if not doc_id or 'N/A' in doc_id: continue
                verse['book'] = book_name
                verse['religion'] = religion_name
                doc_ref = db.collection(collection_name).document(doc_id)
                batch.set(doc_ref, verse)
            
            batch.commit()
            print(f"\n✅ Successfully saved {len(all_final_verses)} documents to Firestore.")
            break
            
        elif user_input == 'cancel':
            print("Upload cancelled.")
            break
            
        else:
            verse_found = False
            for verse in all_final_verses:
                if verse.get('topicId') == user_input:
                    verse_found = True
                    try:
                        new_chapter = int(input(f"Enter new chapter for '{user_input}': "))
                        new_verse = int(input(f"Enter new verse for '{user_input}': "))
                        new_id = f"gita_chapter_{new_chapter}_verse_{new_verse}"
                        verse['topicId'] = new_id
                        verse['chapter'] = new_chapter
                        verse['verse'] = new_verse
                        print(f"Updated ID to: {new_id}")
                        break
                    except ValueError:
                        print("Invalid number. Please try again.")
            if not verse_found:
                print("ID not found. Please try again.")

# --- 5. RUN THE SCRIPT ---
process_chapter_in_batches(
    pdf_name="bhagavad_gita.pdf",
    book_name="Bhagavad Gita",
    religion_name="hinduism",
    chapter_number=18,
    start_page=534,
    end_page=582 
)