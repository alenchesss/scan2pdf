import io
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
import img2pdf
from pypdf import PdfReader, PdfWriter


BG          = "#eaf2fb"
PANEL       = "#ffffff"
ROW         = "#ffffff"
ROW_SEL     = "#cfe2f7"
BTN         = "#5b9bd5"
BTN_ACTIVE  = "#4a86c5"
BTN_TEXT    = "#ffffff"
ACCENT      = "#1f4e79"
TEXT        = "#2b3a4a"
BORDER      = "#c4d8ef"


FONT_FAMILY = "Montserrat"
FONT        = (FONT_FAMILY, 12)
FONT_SMALL  = (FONT_FAMILY, 10)
FONT_TITLE  = (FONT_FAMILY, 16, "bold")
FONT_ROW_NUM = (FONT_FAMILY, 13, "bold")
FONT_BTN    = (FONT_FAMILY, 18)

BTN_RADIUS  = 18

THUMB = 72


def _pil_font(font_spec, scale):
    #Подобрать TTF Montserrat для отрисовки текста кнопки через Pillow
    weight = font_spec[2] if len(font_spec) > 2 else "normal"
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    fname = "Montserrat-Bold.ttf" if weight == "bold" else "Montserrat-Regular.ttf"
    path = os.path.join(base, "fonts", fname)
    try:
        return ImageFont.truetype(path, int(font_spec[1] * scale))
    except Exception:
        return ImageFont.load_default()


class RoundButton(tk.Label):
    # Кнопка со сглаженными закруглёнными углами

    _SCALE = 4

    def __init__(self, parent, text, command, font=None,
                 bg_color=None, fg_color=None, hover_color=None,
                 radius=BTN_RADIUS, padx=18, pady=10):
        font = font or FONT_BTN
        bg_color = bg_color or BTN
        fg_color = fg_color or BTN_TEXT
        hover_color = hover_color or BTN_ACTIVE

        f = tkfont.Font(family=font[0], size=font[1],
                        weight=font[2] if len(font) > 2 else "normal")
        w = f.measure(text) + padx * 2
        h = f.metrics("linespace") + pady * 2
        radius = min(radius, h // 2, w // 2)

        parent_bg = parent["bg"]
        self._normal_img = self._render(w, h, radius, bg_color, fg_color,
                                        text, font, parent_bg)
        self._hover_img = self._render(w, h, radius, hover_color, fg_color,
                                       text, font, parent_bg)

        super().__init__(parent, image=self._normal_img, bg=parent_bg,
                         bd=0, highlightthickness=0, cursor="hand2")

        self.command = command
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self.configure(image=self._hover_img))
        self.bind("<Leave>", lambda e: self.configure(image=self._normal_img))

    def _render(self, w, h, radius, fill, text_color, text, font, parent_bg):
        s = self._SCALE
        img = Image.new("RGB", (w * s, h * s), parent_bg)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, w * s - 1, h * s - 1],
                               radius=radius * s, fill=fill)

        pil_font = _pil_font(font, s)
        bbox = draw.textbbox((0, 0), text, font=pil_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w * s - tw) / 2 - bbox[0], (h * s - th) / 2 - bbox[1]),
                  text, font=pil_font, fill=text_color)

        img = img.resize((w, h), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    def _on_click(self, _event):
        if self.command:
            self.command()


class PageItem:
    # Одна страница: путь к файлу и накопленный поворот
    def __init__(self, path):
        self.path = path
        self.rotation = 0
        self.thumb_cache = None

    @property
    def name(self):
        return os.path.basename(self.path)


def build_pdf(items, output_path):
    # Собрать PDF из списка PageItem в заданном порядке

    paths = [it.path for it in items]
    pdf_bytes = img2pdf.convert(paths)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for it, page in zip(items, reader.pages):
        if it.rotation % 360 != 0:
            page.rotate(it.rotation % 360)
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)


class App:
    def __init__(self, root):
        self.root = root
        self.items = []          # список PageItem
        self.selected = None     # индекс выбранной страницы
        self.row_widgets = []    # ссылки на строки

        # Состояние перетаскивания строк
        self._drag_index = None
        self._drag_active = False
        self._drag_start_y = 0
        self._ghost = None
        self._ghost_size = (0, 0)

        root.title("Scan2PDF — сборка PDF из сканов")
        root.configure(bg=BG)

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        win_w = min(1000, int(screen_w * 0.6))
        win_h = min(760, int(screen_h * 0.75))
        win_w = max(win_w, 900)
        win_h = max(win_h, 600)
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        root.minsize(900, 560)

        self._build_ui()
        self._render()

    def _build_ui(self):
        header = tk.Label(self.root, text="Сборка PDF из отсканированных страниц",
                          bg=BG, fg=ACCENT, font=FONT_TITLE, anchor="w")
        header.pack(fill="x", padx=16, pady=(14, 8))

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=16)

        self._button(bar, "Добавить файлы", self.add_files).pack(side="left")
        tk.Frame(bar, width=16, bg=BG).pack(side="left")
        self._button(bar, "Повернуть на 90°", self.rotate_selected).pack(side="left", padx=(0, 4))
        self._button(bar, "Удалить из списка", self.remove_selected).pack(side="left", padx=(0, 4))

        wrap = tk.Frame(self.root, bg=BORDER, bd=0)
        wrap.pack(fill="both", expand=True, padx=16, pady=12)

        self.canvas = tk.Canvas(wrap, bg=PANEL, highlightthickness=1,
                                highlightbackground=BORDER)
        scroll = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_frame = tk.Frame(self.canvas, bg=PANEL)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.list_frame, anchor="nw")

        self.list_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Прокрутка колесом мыши
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        # Перетаскивание строк мышью
        self.canvas.bind_all("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind_all("<ButtonRelease-1>", self._on_drag_release)

        # Нижняя панель
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=16, pady=(0, 14))

        self.status = tk.Label(bottom, text="", bg=BG, fg=TEXT,
                               font=FONT_SMALL, anchor="w")
        self.status.pack(side="left")

        save_btn = self._button(bottom, "Сохранить PDF", self.save_pdf)
        save_btn.pack(side="right")

    def _button(self, parent, text, command):
        return RoundButton(parent, text, command, font=FONT_BTN)

    def _on_frame_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _thumbnail(self, item):
        if item.thumb_cache and item.thumb_cache[0] == item.rotation:
            return item.thumb_cache[1]
        try:
            img = Image.open(item.path)
            img = ImageOps.exif_transpose(img)
            if item.rotation:
                img = img.rotate(-item.rotation, expand=True)
            img.thumbnail((THUMB, THUMB))
            photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None
        item.thumb_cache = (item.rotation, photo)
        return photo

    def _render(self):
        for w in self.row_widgets:
            w["frame"].destroy()
        self.row_widgets = []

        if not self.items:
            empty = tk.Label(self.list_frame,
                             text="Список пуст. Нажмите «Добавить файлы», "
                                  "чтобы выбрать отсканированные JPEG.",
                             bg=PANEL, fg=TEXT, font=FONT, pady=24)
            empty.pack(fill="x")
            self.row_widgets.append({"frame": empty})
        else:
            for idx, item in enumerate(self.items):
                if self._drag_active and idx == self.selected:
                    self._render_placeholder_row()
                else:
                    self._render_row(idx, item)

        self._update_status()
        self._on_frame_configure()
        self.list_frame.update_idletasks()

    def _render_row(self, idx, item):
        selected = (idx == self.selected)
        bg = ROW_SEL if selected else ROW

        row = tk.Frame(self.list_frame, bg=bg, cursor="hand2",
                       highlightthickness=1, highlightbackground=BORDER)
        row.pack(fill="x", padx=1, pady=1)

        num = tk.Label(row, text=str(idx + 1), bg=bg, fg=ACCENT,
                       font=FONT_ROW_NUM, width=3)
        num.pack(side="left", padx=(8, 4), pady=8)

        photo = self._thumbnail(item)
        thumb = tk.Label(row, image=photo, bg=bg, width=THUMB, height=THUMB)
        thumb.image = photo  # удерживаем ссылку от сборщика мусора
        thumb.pack(side="left", padx=8, pady=6)

        info = "" if item.rotation == 0 else f"   (поворот {item.rotation}°)"
        name = tk.Label(row, text=item.name + info, bg=bg, fg=TEXT,
                        font=FONT, anchor="w", justify="left")
        name.pack(side="left", fill="x", expand=True, padx=4)

        for w in (row, num, thumb, name):
            w.bind("<Button-1>", lambda e, i=idx: self._on_row_press(i, e))

        self.row_widgets.append({"frame": row})

    def _render_placeholder_row(self):
        h = THUMB + 14
        c = tk.Canvas(self.list_frame, height=h, bg=PANEL, highlightthickness=0)
        c.pack(fill="x", padx=1, pady=1)

        def draw(_event=None):
            c.delete("ph")
            w = max(c.winfo_width(), 8)
            c.create_rectangle(3, 3, w - 3, h - 3, fill=ROW_SEL,
                               outline=ACCENT, width=2, dash=(6, 4), tags="ph")

        c.bind("<Configure>", draw)
        self.row_widgets.append({"frame": c})

    def select(self, idx):
        self.selected = idx
        self._render()

    # Перетаскивание строк
    def _on_row_press(self, idx, event):
        self.select(idx)
        self._drag_index = idx
        self._drag_active = False
        self._drag_start_y = event.y_root

    def _on_drag_motion(self, event):
        if self._drag_index is None:
            return

        if not self._drag_active:
            # Небольшой порог, чтобы случайный клик не запускал drag
            if abs(event.y_root - self._drag_start_y) < 4:
                return
            self._drag_active = True
            self.canvas.config(cursor="fleur")
            self._create_ghost(self.items[self._drag_index])
            self._render()

        self._update_ghost_position(event)

        canvas_y = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())
        target = self._row_index_at(canvas_y)
        if target is not None and target != self._drag_index:
            item = self.items.pop(self._drag_index)
            self.items.insert(target, item)
            self._drag_index = target
            self.selected = target
            self._render()

    def _on_drag_release(self, _event):
        if self._drag_active:
            self._drag_active = False
            self.canvas.config(cursor="")
            self._destroy_ghost()
            self._render()
        self._drag_index = None

    def _create_ghost(self, item):
        ghost = tk.Toplevel(self.root)
        ghost.overrideredirect(True)
        try:
            ghost.attributes("-topmost", True)
        except Exception:
            pass
        try:
            ghost.attributes("-alpha", 0.9)
        except Exception:
            pass

        card = tk.Frame(ghost, bg=ROW_SEL, highlightthickness=2,
                        highlightbackground=ACCENT, highlightcolor=ACCENT)
        card.pack()

        photo = self._thumbnail(item)
        thumb = tk.Label(card, image=photo, bg=ROW_SEL, width=THUMB, height=THUMB)
        thumb.image = photo
        thumb.pack(side="left", padx=8, pady=6)

        info = "" if item.rotation == 0 else f"   (поворот {item.rotation}°)"
        name = tk.Label(card, text=item.name + info, bg=ROW_SEL, fg=TEXT,
                        font=FONT, anchor="w")
        name.pack(side="left", padx=(0, 14), pady=6)

        ghost.update_idletasks()
        self._ghost = ghost
        self._ghost_size = (ghost.winfo_width(), ghost.winfo_height())

    def _update_ghost_position(self, event):
        if self._ghost is None:
            return
        w, h = self._ghost_size
        x = event.x_root - w // 2
        y = event.y_root - h - 12
        self._ghost.geometry(f"+{x}+{y}")

    def _destroy_ghost(self):
        if self._ghost is not None:
            self._ghost.destroy()
            self._ghost = None

    def _row_index_at(self, canvas_y):
        rows = self.row_widgets
        if not rows or not self.items:
            return None

        first = rows[0]["frame"]
        last = rows[-1]["frame"]
        if canvas_y <= first.winfo_y():
            return 0
        if canvas_y >= last.winfo_y() + last.winfo_height():
            return len(rows) - 1

        for i, w in enumerate(rows):
            frame = w["frame"]
            top = frame.winfo_y()
            bottom = top + frame.winfo_height()
            if top <= canvas_y < bottom:
                return i
        return None

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Выберите JPEG-файлы",
            filetypes=[("Изображения JPEG", "*.jpg *.jpeg *.JPG *.JPEG"),
                       ("Все файлы", "*.*")])
        for p in paths:
            self.items.append(PageItem(p))
        if paths and self.selected is None:
            self.selected = 0
        self._render()

    def rotate_selected(self):
        i = self.selected
        if i is None:
            return
        self.items[i].rotation = (self.items[i].rotation + 90) % 360
        self._render()

    def remove_selected(self):
        i = self.selected
        if i is None:
            return
        del self.items[i]
        if not self.items:
            self.selected = None
        else:
            self.selected = min(i, len(self.items) - 1)
        self._render()

    def save_pdf(self):
        if not self.items:
            messagebox.showinfo("Нет страниц",
                                "Сначала добавьте хотя бы один JPEG-файл.")
            return
        out = filedialog.asksaveasfilename(
            title="Сохранить PDF",
            defaultextension=".pdf",
            filetypes=[("PDF-документ", "*.pdf")])
        if not out:
            return
        try:
            build_pdf(self.items, out)
        except Exception as e:
            messagebox.showerror("Ошибка при сборке PDF", str(e))
            return
        messagebox.showinfo("Готово",
                            f"PDF сохранён:\n{out}\n\nСтраниц: {len(self.items)}")

    def _update_status(self):
        n = len(self.items)
        if n == 0:
            self.status.config(text="Страниц: 0")
        else:
            self.status.config(text=f"Страниц: {n}")


def _load_custom_fonts():
    # Загрузить Montserrat из папки fonts/ для текущего процесса
    if sys.platform != "win32":
        return False

    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    fonts_dir = os.path.join(base, "fonts")
    files = ["Montserrat-Regular.ttf", "Montserrat-Bold.ttf"]

    if not all(os.path.exists(os.path.join(fonts_dir, f)) for f in files):
        return False

    try:
        import ctypes
        FR_PRIVATE = 0x10
        ok = True
        for fname in files:
            path = os.path.join(fonts_dir, fname)
            added = ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)
            if added == 0:
                ok = False
        return ok
    except Exception:
        return False


def _enable_high_dpi():
    # Сообщить Windows, что приложение поддерживает высокий DPI
    try:
        import ctypes
        # 2 = Per-monitor DPI aware (наиболее корректный режим)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    _enable_high_dpi()

    if not _load_custom_fonts():
        global FONT_FAMILY, FONT, FONT_SMALL, FONT_TITLE, FONT_ROW_NUM, FONT_BTN
        FONT_FAMILY = "Segoe UI"
        FONT        = (FONT_FAMILY, 12)
        FONT_SMALL  = (FONT_FAMILY, 10)
        FONT_TITLE  = (FONT_FAMILY, 16, "bold")
        FONT_ROW_NUM = (FONT_FAMILY, 13, "bold")
        FONT_BTN    = (FONT_FAMILY, 12)

    root = tk.Tk()

    try:
        import ctypes
        dpi = ctypes.windll.user32.GetDpiForWindow(root.winfo_id())
        root.tk.call("tk", "scaling", dpi / 72)
    except Exception:
        pass

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()