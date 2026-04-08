import os
import shutil
from pdf2image import convert_from_path
import pytesseract
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ==========================================
# 📂 FOLDER PATHS (Codespace ke hisaab se relative paths)
# ==========================================
PDF_FOLDER = "pdfs"
OUTPUT_FOLDER = "output"

os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ⚡ Threads (Cloud server par hum isko badha sakte hain, e.g., 6 ya 8)
MAX_WORKERS = 6

lock = threading.Lock()

# ==========================================
# 🔧 FUNCTIONS
# ==========================================
def fix_text(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text

def ocr_page(img, page_no, temp_dir):
    try:
        raw_text = pytesseract.image_to_string(img, lang='hin+eng')
        clean_text = fix_text(raw_text)
        page_text = f"\n--- Page {page_no+1} ---\n{clean_text}\n"
        
        temp_file = os.path.join(temp_dir, f"page_{page_no}.txt")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(page_text)
            
        return page_no, page_text
    except Exception as e:
        return page_no, f"\n--- Page {page_no+1} ---\n[OCR ERROR: {e}]\n"

# ==========================================
# 🚀 MAIN PROCESS
# ==========================================
def process_pdfs():
    # Check if there are PDFs
    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith(".pdf")]
    if not pdf_files:
        print("❌ 'pdfs' folder khali hai. Pehle PDF upload karein.")
        return

    for file in pdf_files:
        pdf_path = os.path.join(PDF_FOLDER, file)
        output_file = os.path.join(OUTPUT_FOLDER, file.replace(".pdf", ".txt"))

        if os.path.exists(output_file):
            print(f"\n✅ Skipping: {file} (Pehle se OCR ho chuka hai)")
            continue

        print(f"\n📄 Processing: {file}")
        temp_dir = os.path.join(OUTPUT_FOLDER, f".tmp_{file}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            print("⏳ Converting PDF to images... (Codespace CPU power in action)")
            images = convert_from_path(pdf_path)
            total_pages = len(images)
            print(f"👉 Total Pages: {total_pages}")

            results = [None] * total_pages
            pages_to_process = []
            completed_pages = 0

            for i in range(total_pages):
                temp_file = os.path.join(temp_dir, f"page_{i}.txt")
                if os.path.exists(temp_file):
                    with open(temp_file, "r", encoding="utf-8") as f:
                        results[i] = f.read()
                    completed_pages += 1
                else:
                    pages_to_process.append(i)

            if completed_pages > 0:
                print(f"🔄 Resuming... {completed_pages}/{total_pages} pages pehle se done hain.")

            if pages_to_process:
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(ocr_page, images[i], i, temp_dir): i 
                        for i in pages_to_process
                    }

                    for future in as_completed(futures):
                        page_no, text = future.result()
                        results[page_no] = text

                        with lock:
                            completed_pages += 1
                            percent = (completed_pages / total_pages) * 100
                            print(f"⚡ Progress: {completed_pages}/{total_pages} ({percent:.1f}%)", end="\r")
                print()

            print("💾 Saving final text file...")
            full_text = "".join(results)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_text)

            shutil.rmtree(temp_dir)
            print(f"🎉 Success! Saved Final: {output_file}")

        except Exception as e:
            print(f"\n❌ Error processing {file}: {e}")

if __name__ == "__main__":
    process_pdfs()
