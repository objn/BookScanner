"""
Book Scanner GUI Application
--------------------------------
A simple desktop app for Windows 11 that captures pages from any webcam, 
saves each capture as a high‑quality PNG in a local "temp" folder, shows a live preview,
keeps thumbnails of every shot, and can bundle the selected images into a PDF without
deleting originals.

Dependencies (install via pip):
    pip install opencv-python pillow img2pdf

Run:
    python book_scanner.py

Author: OBJN
"""
from __future__ import annotations

import os
import pathlib
import cv2
import img2pdf
from datetime import datetime
from typing import List
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------- CONFIG -----------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
IMAGE_EXT = ".png"  # use lossless PNG for page captures


# ---------- HELPER FUNCTIONS -------------------------------------------------

def next_filename() -> pathlib.Path:
    """Return next running‑number file name in TEMP_DIR (0001.png …)."""
    existing = sorted(TEMP_DIR.glob(f"*{IMAGE_EXT}"))
    if not existing:
        return TEMP_DIR / f"0001{IMAGE_EXT}"
    last_num = int(existing[-1].stem)
    return TEMP_DIR / f"{last_num + 1:04d}{IMAGE_EXT}"


def load_thumbnail(image_path: pathlib.Path, size=(100, 140)) -> ImageTk.PhotoImage:
    """Return Tk‑compatible thumbnail for list display."""
    img = Image.open(image_path)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img)


# ---------- MAIN APP ---------------------------------------------------------

class BookScannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Book Scanner")
        self.geometry("900x700")
        self.minsize(800, 600)

        # Webcam setup (0 = default camera)
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            messagebox.showerror("Camera Error", "Cannot access webcam. Is it connected/in use?")
            self.destroy(); return

        # --- UI Layout ------------------------------------------------------
        self.preview_label = ttk.Label(self)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame for control buttons
        ctl = ttk.Frame(self); ctl.pack(pady=4)
        ttk.Button(ctl, text="📸 Capture (C)", command=self.capture_page).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text="📕 Make Book (PDF)", command=self.make_pdf).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text="📂 Open temp", command=lambda: os.startfile(TEMP_DIR)).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text="🗑️ Delete selected", command=self.delete_selected).pack(side=tk.LEFT, padx=4)

        # Thumbnails list (scrollable)
        thumb_frame = ttk.Frame(self)
        thumb_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.thumb_canvas = tk.Canvas(thumb_frame, height=150)
        hscroll = ttk.Scrollbar(thumb_frame, orient=tk.HORIZONTAL, command=self.thumb_canvas.xview)
        self.thumb_canvas.configure(xscrollcommand=hscroll.set)
        self.thumb_inner = ttk.Frame(self.thumb_canvas)
        self.thumb_canvas.create_window((0, 0), window=self.thumb_inner, anchor="nw")
        self.thumb_canvas.pack(fill=tk.X, side=tk.TOP)
        hscroll.pack(fill=tk.X, side=tk.TOP)
        self.thumb_inner.bind("<Configure>", lambda e: self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all")))

        self.thumbnails: List[ImageTk.PhotoImage] = []  # keep refs
        self.selected_index: int | None = None

        # Key binding
        self.bind("<c>", lambda e: self.capture_page())

        # Initial load
        self.load_existing_images()

        # Live preview update loop
        self.after(0, self.update_preview)

    # -------------------- Camera & Capture ---------------------------------
    def update_preview(self):
        ret, frame = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            w, h = img.size
            # Resize to fit preview area (keep 4:3)
            max_w = self.preview_label.winfo_width() or 800
            max_h = self.preview_label.winfo_height() or 600
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=tk_img)
            self.preview_label.image = tk_img  # keep ref
        self.after(20, self.update_preview)  # ~50 fps

    def capture_page(self):
        ret, frame = self.cap.read()
        if not ret:
            messagebox.showwarning("Capture failed", "No frame captured.")
            return
        filepath = next_filename()
        cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_PNG_COMPRESSION, 0])  # 0 = lossless
        self.add_thumbnail(filepath)

    # -------------------- Thumbnails ---------------------------------------
    def load_existing_images(self):
        for p in sorted(TEMP_DIR.glob(f"*{IMAGE_EXT}")):
            self.add_thumbnail(p)

    def add_thumbnail(self, path: pathlib.Path):
        thumb_img = load_thumbnail(path)
        index = len(self.thumbnails)
        lbl = ttk.Label(self.thumb_inner, image=thumb_img, borderwidth=2, relief="flat")
        lbl.image = thumb_img  # keep ref
        lbl.grid(row=0, column=index, padx=2, pady=2)
        lbl.bind("<Button-1>", lambda e, i=index: self.select_thumbnail(i))
        self.thumbnails.append(thumb_img)

    def select_thumbnail(self, idx: int):
        # visual selection highlight
        for child in self.thumb_inner.winfo_children():
            child.configure(style="TLabel")
        sel_widget = self.thumb_inner.winfo_children()[idx]
        sel_widget.configure(relief="solid")
        self.selected_index = idx

    def delete_selected(self):
        if self.selected_index is None:
            messagebox.showinfo("Select page", "Click a thumbnail first.")
            return
        img_path = sorted(TEMP_DIR.glob(f"*{IMAGE_EXT}"))[self.selected_index]
        if messagebox.askyesno("Delete page?", f"Delete {img_path.name}?"):
            img_path.unlink(missing_ok=True)
            # refresh UI
            for widget in self.thumb_inner.winfo_children():
                widget.destroy()
            self.thumbnails.clear()
            self.selected_index = None
            self.load_existing_images()

    # -------------------- PDF Export ---------------------------------------
    def make_pdf(self):
        images = sorted(TEMP_DIR.glob(f"*{IMAGE_EXT}"))
        if not images:
            messagebox.showinfo("No pages", "No images in temp folder.")
            return
        dest = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", ".pdf")])
        if not dest:
            return
        with open(dest, "wb") as f:
            f.write(img2pdf.convert([str(p) for p in images]))
        messagebox.showinfo("PDF saved", f"Saved {len(images)} pages to {dest}")

    # -------------------- Clean‑up -----------------------------------------
    def on_closing(self):
        if self.cap.isOpened():
            self.cap.release()
        self.destroy()


if __name__ == "__main__":
    app = BookScannerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
