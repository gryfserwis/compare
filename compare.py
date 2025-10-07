import sys
import os
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import fitz  # PyMuPDF

# Proporcje A4: 210x297mm ≈ 1:1.414
A4_RATIO = 297 / 210  # ≈ 1.414

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

class PDFViewer(tk.Canvas):
    def __init__(self, master, side='left', page_var=None, total_var=None, **kwargs):
        super().__init__(master, **kwargs)
        self.pdf_doc = None
        self.page_num = 0
        self.image_id = None
        self.photo = None
        self.sync_partner = None
        self.current_img = None
        self.side = side  # 'left' or 'right'
        self._syncing = False
        self.page_var = page_var
        self.total_var = total_var
        self.bind('<Configure>', self._on_resize)
        self.grid(row=1, column=0, sticky='nsew')
        master.grid_rowconfigure(1, weight=1)
        master.grid_columnconfigure(0, weight=1)
        self.focus_set()
        self.bind_events()

    def load_pdf(self, file_path):
        self.pdf_doc = fitz.open(file_path)
        self.page_num = 0
        self.show_page()

    def show_page(self):
        if self.pdf_doc:
            page = self.pdf_doc.load_page(self.page_num)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.current_img = img
            self._draw_img()
            if self.page_var is not None:
                self.page_var.set(str(self.page_num + 1))
            if self.total_var is not None:
                self.total_var.set(str(len(self.pdf_doc)))

    def _draw_img(self):
        if self.current_img is None:
            return
        h = self.winfo_height()
        if h < 10:
            h = 600
        orig_w, orig_h = self.current_img.size
        ratio = h / orig_h
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.ANTIALIAS
        img_resized = self.current_img.resize((new_w, new_h), resample)
        self.photo = ImageTk.PhotoImage(img_resized)
        self.delete("all")
        canvas_w = self.winfo_width()
        if self.side == 'left':
            x = canvas_w - new_w if canvas_w > new_w else 0
        else:
            x = 0
        self.image_id = self.create_image(x, 0, anchor='nw', image=self.photo)
        self.config(scrollregion=(0, 0, canvas_w, new_h))

    def scroll_page(self, delta):
        self.goto_page(self.page_num + delta)

    def goto_page(self, page_num):
        if self.pdf_doc:
            new_page = min(max(page_num, 0), len(self.pdf_doc) - 1)
            if new_page != self.page_num:
                self.page_num = new_page
                self.show_page()
                if self.sync_partner and not self._syncing:
                    try:
                        self._syncing = True
                        self.sync_partner._syncing = True
                        self.sync_partner.goto_page(self.page_num)
                    finally:
                        self._syncing = False
                        self.sync_partner._syncing = False

    def goto_first(self):
        self.goto_page(0)

    def goto_last(self):
        if self.pdf_doc:
            self.goto_page(len(self.pdf_doc) - 1)

    def goto_input_page(self, event=None):
        if self.pdf_doc and self.page_var is not None:
            try:
                num = int(self.page_var.get()) - 1
            except Exception:
                num = self.page_num
            self.goto_page(num)

    def _on_resize(self, event):
        self._draw_img()

    def bind_dnd(self, on_drop_callback):
        if DND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', on_drop_callback)

    def bind_events(self):
        self.bind("<Up>", lambda e: self.scroll_page(-1))
        self.bind("<Down>", lambda e: self.scroll_page(1))
        self.bind("<Prior>", lambda e: self.scroll_page(-10))
        self.bind("<Next>", lambda e: self.scroll_page(10))
        self.bind("<Home>", lambda e: self.goto_first())
        self.bind("<End>", lambda e: self.goto_last())
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", lambda e: self.scroll_page(-1))
        self.bind("<Button-5>", lambda e: self.scroll_page(1))
        self.bind("<Button-1>", lambda e: self.focus_set())

    def _on_mousewheel(self, event):
        if event.delta > 0:
            self.scroll_page(-1)
        elif event.delta < 0:
            self.scroll_page(1)

def load_file(viewer):
    file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if file_path:
        viewer.load_pdf(file_path)

def on_drop(event, viewer):
    file_path = event.data.strip('{}')
    if file_path.lower().endswith('.pdf'):
        viewer.load_pdf(file_path)

def main():
    # Minimalne wymiary okna
    min_width = 1000
    min_height = int(min_width / 2 * A4_RATIO)+35

    # Obsługa argumentów
    arg_left = None
    arg_right = None
    if len(sys.argv) >= 3:
        arg_left = sys.argv[1]
        arg_right = sys.argv[2]

    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    root.title("Porównywarka PDF")

    # Ustaw minimalny rozmiar i uruchom program z tym rozmiarem
    root.minsize(min_width, min_height)
    root.geometry(f"{min_width}x{min_height}+{int((root.winfo_screenwidth()-min_width)/2)}+{int((root.winfo_screenheight()-min_height)/2)}")

    frame = ttk.Frame(root)
    frame.pack(fill='both', expand=True)

    # Pola do wpisywania i info tylko dla lewego (oryginał)
    left_page_var = tk.StringVar()
    left_total_var = tk.StringVar(value="--")

    # Lewy panel
    left_panel = ttk.Frame(frame)
    left_panel.grid(row=1, column=0, sticky='nsew')
    left_viewer = PDFViewer(left_panel, width=400, height=600, bg='gray', side='left',
                            page_var=left_page_var, total_var=left_total_var)

    # Prawy panel
    right_panel = ttk.Frame(frame)
    right_panel.grid(row=1, column=2, sticky='nsew')
    right_viewer = PDFViewer(right_panel, width=400, height=600, bg='gray', side='right')

    left_viewer.sync_partner = right_viewer
    right_viewer.sync_partner = left_viewer

    for viewer in (left_viewer, right_viewer):
        viewer.bind_dnd(lambda e, v=viewer: on_drop(e, v))

    # Pasek górny wyśrodkowany
    topbar = ttk.Frame(frame)
    topbar.grid(row=0, column=0, columnspan=3, sticky='ew')
    topbar.columnconfigure(0, weight=1)
    topbar.columnconfigure(1, weight=1)
    topbar.columnconfigure(2, weight=1)

    # Lewy przycisk i pole wpisu
    left_btn = ttk.Button(topbar, text="Wczytaj oryginał", width=22, command=lambda: load_file(left_viewer))
    left_btn.grid(row=0, column=0, sticky='e', padx=(0,10), pady=6)

    center_frame = ttk.Frame(topbar)
    center_frame.grid(row=0, column=1)

    left_entry = ttk.Entry(center_frame, width=5, textvariable=left_page_var, justify='center')
    left_entry.pack(side='left', padx=2)
    left_slash = ttk.Label(center_frame, text="/")
    left_slash.pack(side='left')
    left_total = ttk.Label(center_frame, textvariable=left_total_var, width=5, anchor="w")
    left_total.pack(side='left', padx=(0,8))

    # Obsługa przechodzenia na stronę Enterem
    def goto_left_page(event=None):
        left_viewer.goto_input_page()
    left_entry.bind("<Return>", goto_left_page)

    # Prawy przycisk
    right_btn = ttk.Button(topbar, text="Wczytaj poprawkę", width=22, command=lambda: load_file(right_viewer))
    right_btn.grid(row=0, column=2, sticky='w', padx=(10,0), pady=6)

    # Ustaw proporcje
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(2, weight=1)
    frame.rowconfigure(1, weight=1)
    left_panel.rowconfigure(1, weight=1)
    left_panel.columnconfigure(0, weight=1)
    right_panel.rowconfigure(1, weight=1)
    right_panel.columnconfigure(0, weight=1)

    # Automatyczne ładowanie plików z argumentów (jeśli podano)
    if arg_left and os.path.isfile(arg_left):
        left_viewer.load_pdf(arg_left)
    if arg_right and os.path.isfile(arg_right):
        right_viewer.load_pdf(arg_right)

    root.mainloop()

if __name__ == "__main__":
    main()