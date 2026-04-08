import os
import shutil
from pdf2image import convert_from_path, pdfinfo_from_path
import pytesseract
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ==========================================
# 📂 FOLDER PATHS
# ==========================================
PDF_FOLDER = "pdfs"
OUTPUT_FOLDER = "output"

os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ⚡ TWEAKS FOR BIG FILES
MAX_WORKERS = 2  # RAM bachane ke liye threads kam kar diye
CHUNK_SIZE = 10  # Ek baar mein sirf 10 pages load karega

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
# 🚀 MAIN PROCESS (RAM SAFE)
# ==========================================
def process_pdfs():
    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith(".pdf")]
    if not pdf_files:
        print("❌ 'pdfs' folder khali hai.")
        return

    for file in pdf_files:
        pdf_path = os.path.join(PDF_FOLDER, file)
        output_file = os.path.join(OUTPUT_FOLDER, file.replace(".pdf", ".txt"))

        if os.path.exists(output_file):
            print(f"\n✅ Skipping: {file} (Pehle se done hai)")
            continue

        print(f"\n📄 Processing: {file}")
        temp_dir = os.path.join(OUTPUT_FOLDER, f".tmp_{file}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # ✅ FIXED: Using pdfinfo_from_path
            info = pdfinfo_from_path(pdf_path)
            total_pages = info["Pages"]
            print(f"👉 Total Pages: {total_pages}")
            
            completed_pages = 0
            for i in range(total_pages):
                if os.path.exists(os.path.join(temp_dir, f"page_{i}.txt")):
                    completed_pages += 1
            
            if completed_pages > 0:
                print(f"🔄 Resuming... {completed_pages}/{total_pages} pages ho chuke hain.")

            # PDF ko 10-10 pages ke hisse mein process karna
            for start_page in range(1, total_pages + 1, CHUNK_SIZE):
                end_page = min(start_page + CHUNK_SIZE - 1, total_pages)
                
                # Check karna ki kya is chunk ke pages pehle se process ho gaye hain
                pages_to_process = []
                for i in range(start_page - 1, end_page):
                    if not os.path.exists(os.path.join(temp_dir, f"page_{i}.txt")):
                        pages_to_process.append(i)
                        
                if not pages_to_process:
                    continue 
                    
                print(f"\n⏳ Loading Pages {start_page} to {end_page} into memory...")
                
                images = convert_from_path(pdf_path, first_page=start_page, last_page=end_page)
                
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = {}
                    for abs_page_idx in pages_to_process:
                        img_idx = abs_page_idx - (start_page - 1)
                        futures[executor.submit(ocr_page, images[img_idx], abs_page_idx, temp_dir)] = abs_page_idx

                    for future in as_completed(futures):
                        future.result() 
                        with lock:
                            completed_pages += 1
                            percent = (completed_pages / total_pages) * 100
                            print(f"⚡ Progress: {completed_pages}/{total_pages} ({percent:.1f}%)", end="\r")

            print("\n💾 Saving final text file...")
            full_text = ""
            for i in range(total_pages):
                temp_file = os.path.join(temp_dir, f"page_{i}.txt")
                if os.path.exists(temp_file):
                    with open(temp_file, "r", encoding="utf-8") as f:
                        full_text += f.read()
                        
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(full_text)

            shutil.rmtree(temp_dir)
            print(f"🎉 Success! Saved Final: {output_file}")

        except Exception as e:
            print(f"\n❌ Error processing {file}: {e}")

if __name__ == "__main__":
    process_pdfs()
