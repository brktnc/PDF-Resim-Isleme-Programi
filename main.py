import os
import PyPDF2
import tkinter as tk
from tkinter import filedialog, messagebox  # Import 'messagebox'
import pytesseract
from PIL import Image
import cv2
import fitz  # PyMuPDF library
import threading
import shelve

status_label = None
output_folder = None
num_files_processed = 0

def count_files_in_folder(folder_path):
    num_files = 0
    for entry in os.scandir(folder_path):
        if entry.is_file():
            num_files += 1
        elif entry.is_dir():
            num_files += count_files_in_folder(entry.path)
    return num_files

def process_pdfs_in_folder(folder_path, keywords_to_find, output, progress_dict):
    global num_files_processed
    total_files = count_files_in_folder(folder_path)
    status_label.config(text=f"Toplam dosya sayısı: {total_files}, İşlenen dosya sayısı: 0")

    if not keywords_to_find:
        status_label.config(text="Aramak istediğiniz kelimeleri giriniz.")
        return

    def find_keywords_in_pdf(pdf_file, keywords, output, progress_dict):
        normalized_pdf_file = os.path.normpath(pdf_file)
        if normalized_pdf_file in progress_dict:
            return

        pdf_document = fitz.open(pdf_file)
        num_pages = pdf_document.page_count
        found_keywords = set()

        # Define additional configuration for Turkish OCR
        custom_config = r'--oem 3 --psm 3 -l tur'

        for page_num in range(num_pages):
            pdf_page = pdf_document.load_page(page_num)

            # Use OCR on the entire page with Turkish language config
            image = pdf_page.get_pixmap()
            image_pil = Image.frombytes("RGB", (image.width, image.height), image.samples)

            # Perform OCR on the original image
            page_text = pytesseract.image_to_string(image_pil, config=custom_config)

            # Perform OCR on a magnified version of the image
            magnified_image_pil = image_pil.resize((image.width * 2, image.height * 2), Image.LANCZOS)
            magnified_page_text = pytesseract.image_to_string(magnified_image_pil, config=custom_config)

            # Check if any keyword is found in the OCR results (original and magnified)
            for keyword in keywords:
                if keyword.lower() in page_text.lower() or keyword.lower() in magnified_page_text.lower():
                    found_keywords.add(keyword)

            # Update the status_label to show the current file and page being processed
            status_label.config(text=f"İşlenen Dosya: {os.path.basename(pdf_file)} - Sayfa: {page_num + 1}/{num_pages}")
            status_label_2.config(text=f"Toplam dosya sayısı: {total_files}, İşlenen dosya sayısı: {num_files_processed}")

        pdf_document.close()

        if found_keywords:
            output.write(
                f"Klasör: {os.path.dirname(pdf_file)} - Dosya: {os.path.basename(pdf_file)} - Keywords: {', '.join(found_keywords)}\n")

        progress_dict[normalized_pdf_file] = 1

    for entry in os.scandir(folder_path):
        if entry.is_dir():
            # Recursively process subdirectories and update num_files_processed
            num_files_processed += process_pdfs_in_folder(entry.path, keywords_to_find, output, progress_dict)
        elif entry.is_file() and entry.name.lower().endswith('.pdf'):
            # Update num_files_processed for each PDF file processed
            num_files_processed += 1
            find_keywords_in_pdf(entry.path, keywords_to_find, output, progress_dict)

    return num_files_processed  # Return the total number of files processed

def process_images_in_folder(folder_path, keywords_to_find, output_file, progress_dict):
    global num_files_processed
    for entry in os.scandir(folder_path):
        if entry.is_dir():
            # Recursively process subdirectories and update num_files_processed
            num_files_processed += process_images_in_folder(entry.path, keywords_to_find, output_file, progress_dict)
        elif entry.is_file() and entry.name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
            image_path = entry.path
            if image_path in progress_dict:
                continue

            image_text = pytesseract.image_to_string(Image.open(image_path))
            found_keywords = []

            for keyword in keywords_to_find:
                if keyword.lower() in image_text.lower():
                    found_keywords.append(keyword)

            status_label.config(text=f"İşlenen Dosya: {os.path.basename(image_path)}")

            if found_keywords:
                output_file.write(f"Klasör: {folder_path} - Dosya: {os.path.basename(image_path)} - Keywords: {', '.join(found_keywords)}\n")

            normalized_image_path = os.path.normpath(image_path)
            progress_dict[normalized_image_path] = 1

            # Update num_files_processed for each image file processed
            num_files_processed += 1

    return num_files_processed  # Return the total number of files processed

def select_folder():
    folder_path = filedialog.askdirectory()
    if not folder_path:
        status_label.config(text="Klasör seçilmedi.")
        return

    folder_entry.delete(0, tk.END)
    folder_entry.insert(0, folder_path)

def get_keywords():
    user_input = keywords_entry.get().lower().split(",")
    user_input = [keyword.strip() for keyword in user_input if keyword.strip()]
    if not user_input:
        return None
    return user_input

def select_output_folder():
    global output_folder
    output_folder = filedialog.askdirectory()
    if not output_folder:
        status_label.config(text="Hedef klasör seçilmedi.")
        return None

def process_in_background(folder_path, keywords_to_find):
    global output_folder

    output_file_base = "output"
    output_file = os.path.join(output_folder, f"{output_file_base}.txt")

    # Use progress.shelve to keep track of processed files
    progress_file_path = os.path.join(output_folder, "progress.shelve")


    with shelve.open(progress_file_path, writeback=True) as progress_dict:

        with open(output_file, 'a', encoding='utf-8') as output:
            process_pdfs_in_folder(folder_path, keywords_to_find, output, progress_dict)
            process_images_in_folder(folder_path, keywords_to_find, output, progress_dict)

    # Show a message box to inform the user
    messagebox.showinfo("İşlem Tamamlandı", f"PDF ve resim dosyaları işlendi ve keywordler yazıldı. Toplam dosya sayısı: {num_files_processed}")

    # Re-enable the button after the recursive call
    process_btn.config(state=tk.NORMAL)
    select_folder_btn.config(state=tk.NORMAL)
    select_output_folder_btn.config(state=tk.NORMAL)

def process_pdfs_and_images(root):
    global status_label, folder_entry, keywords_entry, output_folder
    folder_path = folder_entry.get()
    if not folder_path:
        status_label.config(text="Klasör seçilmedi.")
        return

    keywords_to_find = get_keywords()
    if keywords_to_find is None:
        status_label.config(text="Aramak istediğiniz kelimeleri giriniz.")
        return

    process_btn.config(state=tk.DISABLED)
    select_folder_btn.config(state=tk.DISABLED)
    select_output_folder_btn.config(state=tk.DISABLED)

    # Start processing in a new background thread
    processing_thread = threading.Thread(target=process_in_background, args=(folder_path, keywords_to_find))
    processing_thread.daemon = True
    processing_thread.start()

def main():
    global status_label, status_label_2, folder_entry, keywords_entry, process_btn, select_folder_btn, select_output_folder_btn, num_files_processed
    root = tk.Tk()
    root.title("PDF ve Resim İşleme Arayüzü")
    root.geometry("700x320")

    folder_label = tk.Label(root, text="PDF ve resim dosyalarının bulunduğu klasörü seçin:")
    folder_label.pack()

    folder_entry = tk.Entry(root, width=40)
    folder_entry.pack(pady=5)

    select_folder_btn = tk.Button(root, text="Klasör Seç", command=select_folder)
    select_folder_btn.pack(pady=5)

    keywords_label = tk.Label(root, text="Aramak istediğiniz kelimeleri virgülle ayırarak girin:")
    keywords_label.pack()

    keywords_entry = tk.Entry(root, width=40)
    keywords_entry.pack(pady=5)

    select_output_folder_btn = tk.Button(root, text="Output Klasörü Seç", command=select_output_folder)
    select_output_folder_btn.pack(pady=5)

    process_btn = tk.Button(root, text="PDF ve Resimleri İşle ve Keywordler Yazdır", command=lambda: process_pdfs_and_images(root))
    process_btn.pack(pady=10)

    status_label = tk.Label(root, text="", fg="red")
    status_label.pack(pady=5)

    status_label_2 = tk.Label(root, text="", fg="blue")
    status_label_2.pack(pady=5)

    warning_label = tk.Label(root, text="(Alt klasörlerin içindeki dosyaların sayısı dahil değil. Toplam dosya sayısının bir anda düşmesinin sebebi alt klasörlere girmesi!)", fg="blue")
    warning_label.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()
