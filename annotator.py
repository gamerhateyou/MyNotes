"""Tool di annotazione immagini con Canvas Tkinter."""

import tkinter as tk
from tkinter import ttk, colorchooser, simpledialog, messagebox
from PIL import Image, ImageDraw, ImageFont
import os
import math
import image_utils
import platform_utils
from gui.constants import BG_DARK, BG_SURFACE


class AnnotationTool(tk.Toplevel):
    """Finestra per annotare un'immagine con frecce, forme, testo e disegno libero."""

    TOOLS = ["Freccia", "Rettangolo", "Cerchio", "Linea", "Testo", "Disegno libero"]

    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.title("Annota Immagine")
        self.image_path = image_path
        self.result_path = None

        self.pil_image = Image.open(image_path).convert("RGB")
        self.original_size = self.pil_image.size

        screen_w = self.winfo_screenwidth() - 100
        screen_h = self.winfo_screenheight() - 200
        self.display_image = image_utils.resize_contain(self.pil_image, screen_w, screen_h)
        self.display_size = self.display_image.size
        self.scale_x = self.original_size[0] / self.display_size[0]
        self.scale_y = self.original_size[1] / self.display_size[1]

        self.geometry(f"{self.display_size[0] + 20}x{self.display_size[1] + 80}")
        self.configure(bg=BG_SURFACE)
        self.grab_set()

        self.current_tool = "Freccia"
        self.draw_color = "#ff0000"
        self.line_width = 3
        self.annotations = []
        self.drawing = False
        self.start_x = 0
        self.start_y = 0
        self.temp_item = None
        self.freehand_points = []

        self._build_toolbar()
        self._build_canvas()

        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window()

    def _build_toolbar(self):
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill=tk.X)

        self.tool_var = tk.StringVar(value=self.current_tool)
        for tool in self.TOOLS:
            ttk.Radiobutton(toolbar, text=tool, variable=self.tool_var, value=tool,
                            command=self._on_tool_change).pack(side=tk.LEFT, padx=3)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.color_btn = tk.Button(toolbar, text="  ", bg=self.draw_color, width=3,
                                   command=self._pick_color, relief=tk.RAISED)
        self.color_btn.pack(side=tk.LEFT, padx=3)
        ttk.Label(toolbar, text="Spessore:").pack(side=tk.LEFT, padx=(8, 2))
        self.width_var = tk.IntVar(value=3)
        ttk.Spinbox(toolbar, from_=1, to=15, textvariable=self.width_var, width=4).pack(side=tk.LEFT)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        ttk.Button(toolbar, text="Annulla ultimo", command=self._undo).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="Salva", command=self._save).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=3)

    def _build_canvas(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(frame, width=self.display_size[0], height=self.display_size[1],
                                cursor="crosshair", bg=BG_DARK)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.photo = image_utils.pil_to_photo(self.display_image)
        self.canvas_image = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _on_tool_change(self):
        self.current_tool = self.tool_var.get()

    def _pick_color(self):
        color = colorchooser.askcolor(self.draw_color, parent=self, title="Colore annotazione")
        if color[1]:
            self.draw_color = color[1]
            self.color_btn.config(bg=self.draw_color)

    def _on_press(self, event):
        self.drawing = True
        self.start_x = event.x
        self.start_y = event.y
        self.freehand_points = [(event.x, event.y)]

        if self.current_tool == "Testo":
            text = simpledialog.askstring("Testo", "Inserisci testo:", parent=self)
            if text:
                item = self.canvas.create_text(
                    event.x, event.y, text=text, fill=self.draw_color,
                    font=(platform_utils.get_ui_font(), max(12, self.width_var.get() * 4)), anchor=tk.NW
                )
                self.annotations.append(("text", {
                    "x": event.x, "y": event.y, "text": text,
                    "color": self.draw_color, "size": max(12, self.width_var.get() * 4),
                    "item": item
                }))
            self.drawing = False

    def _on_drag(self, event):
        if not self.drawing:
            return

        if self.current_tool == "Disegno libero":
            px, py = self.freehand_points[-1]
            item = self.canvas.create_line(
                px, py, event.x, event.y,
                fill=self.draw_color, width=self.width_var.get(),
                capstyle=tk.ROUND, joinstyle=tk.ROUND
            )
            self.freehand_points.append((event.x, event.y))
            if not self.annotations or self.annotations[-1][0] != "_freehand_active":
                self.annotations.append(("_freehand_active", {"items": [item], "points": list(self.freehand_points),
                                                               "color": self.draw_color, "width": self.width_var.get()}))
            else:
                self.annotations[-1][1]["items"].append(item)
                self.annotations[-1][1]["points"].append((event.x, event.y))
        else:
            if self.temp_item:
                self.canvas.delete(self.temp_item)

            w = self.width_var.get()
            if self.current_tool == "Rettangolo":
                self.temp_item = self.canvas.create_rectangle(
                    self.start_x, self.start_y, event.x, event.y,
                    outline=self.draw_color, width=w
                )
            elif self.current_tool == "Cerchio":
                self.temp_item = self.canvas.create_oval(
                    self.start_x, self.start_y, event.x, event.y,
                    outline=self.draw_color, width=w
                )
            elif self.current_tool in ("Freccia", "Linea"):
                self.temp_item = self.canvas.create_line(
                    self.start_x, self.start_y, event.x, event.y,
                    fill=self.draw_color, width=w,
                    arrow=tk.LAST if self.current_tool == "Freccia" else None,
                    arrowshape=(12, 15, 5)
                )

    def _on_release(self, event):
        if not self.drawing:
            return
        self.drawing = False

        if self.current_tool == "Disegno libero":
            if self.annotations and self.annotations[-1][0] == "_freehand_active":
                entry = self.annotations[-1]
                self.annotations[-1] = ("freehand", entry[1])
            return

        if self.temp_item:
            self.canvas.delete(self.temp_item)
            self.temp_item = None

        w = self.width_var.get()
        coords = (self.start_x, self.start_y, event.x, event.y)

        if self.current_tool == "Rettangolo":
            item = self.canvas.create_rectangle(*coords, outline=self.draw_color, width=w)
            self.annotations.append(("rect", {"coords": coords, "color": self.draw_color, "width": w, "item": item}))
        elif self.current_tool == "Cerchio":
            item = self.canvas.create_oval(*coords, outline=self.draw_color, width=w)
            self.annotations.append(("oval", {"coords": coords, "color": self.draw_color, "width": w, "item": item}))
        elif self.current_tool == "Freccia":
            item = self.canvas.create_line(*coords, fill=self.draw_color, width=w,
                                           arrow=tk.LAST, arrowshape=(12, 15, 5))
            self.annotations.append(("arrow", {"coords": coords, "color": self.draw_color, "width": w, "item": item}))
        elif self.current_tool == "Linea":
            item = self.canvas.create_line(*coords, fill=self.draw_color, width=w)
            self.annotations.append(("line", {"coords": coords, "color": self.draw_color, "width": w, "item": item}))

    def _undo(self):
        if not self.annotations:
            return
        ann_type, params = self.annotations.pop()
        if ann_type == "freehand":
            for item in params["items"]:
                self.canvas.delete(item)
        elif "item" in params:
            self.canvas.delete(params["item"])

    def _get_font(self, size):
        """Carica un font TrueType cross-platform."""
        font_path = platform_utils.get_font_path()
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                pass
        return ImageFont.load_default()

    def _save(self):
        """Render annotations onto the PIL image and save."""
        draw = ImageDraw.Draw(self.pil_image)
        sx, sy = self.scale_x, self.scale_y

        for ann_type, params in self.annotations:
            color = params.get("color", "#ff0000")
            width = max(1, int(params.get("width", 3) * sx))

            if ann_type == "rect":
                c = params["coords"]
                draw.rectangle([c[0]*sx, c[1]*sy, c[2]*sx, c[3]*sy], outline=color, width=width)

            elif ann_type == "oval":
                c = params["coords"]
                draw.ellipse([c[0]*sx, c[1]*sy, c[2]*sx, c[3]*sy], outline=color, width=width)

            elif ann_type == "line":
                c = params["coords"]
                draw.line([c[0]*sx, c[1]*sy, c[2]*sx, c[3]*sy], fill=color, width=width)

            elif ann_type == "arrow":
                c = params["coords"]
                draw.line([c[0]*sx, c[1]*sy, c[2]*sx, c[3]*sy], fill=color, width=width)
                dx = c[2] - c[0]
                dy = c[3] - c[1]
                angle = math.atan2(dy, dx)
                arrow_len = 20 * sx
                x2, y2 = c[2]*sx, c[3]*sy
                for a in [angle + 2.6, angle - 2.6]:
                    ax = x2 + arrow_len * math.cos(a)
                    ay = y2 + arrow_len * math.sin(a)
                    draw.line([x2, y2, ax, ay], fill=color, width=width)

            elif ann_type == "freehand":
                points = [(p[0]*sx, p[1]*sy) for p in params["points"]]
                if len(points) > 1:
                    draw.line(points, fill=color, width=width, joint="curve")

            elif ann_type == "text":
                x, y = params["x"] * sx, params["y"] * sy
                font_size = max(10, int(params["size"] * sx))
                font = self._get_font(font_size)
                draw.text((x, y), params["text"], fill=color, font=font)

        base, ext = os.path.splitext(self.image_path)
        self.result_path = f"{base}_annotated{ext}"
        self.pil_image.save(self.result_path)
        messagebox.showinfo("Salvato", "Immagine annotata salvata.", parent=self)
        self.destroy()
