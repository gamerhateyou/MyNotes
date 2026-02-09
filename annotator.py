"""Tool di annotazione immagini con QGraphicsView (PySide6)."""

from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent, QMouseEvent
from PIL import Image

import image_utils
import platform_utils
from gui.constants import BG_DARK, BORDER


class AnnotationTool(QDialog):
    """Finestra per annotare un'immagine con frecce, forme, testo e disegno libero."""

    TOOLS = ["Freccia", "Rettangolo", "Cerchio", "Linea", "Testo", "Disegno libero"]

    def __init__(self, parent: QWidget, image_path: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Annota Immagine")
        self.setModal(True)
        self.image_path: str = image_path
        self.result_path: str | None = None

        self.pil_image: Image.Image = Image.open(image_path).convert("RGB")
        self.original_size: tuple[int, int] = self.pil_image.size

        screen = self.screen().availableGeometry()
        screen_w: int = screen.width() - 100
        screen_h: int = screen.height() - 200
        self.display_image: Image.Image = image_utils.resize_contain(self.pil_image, screen_w, screen_h)
        self.display_size: tuple[int, int] = self.display_image.size
        self.scale_x: float = self.original_size[0] / self.display_size[0]
        self.scale_y: float = self.original_size[1] / self.display_size[1]

        self.resize(self.display_size[0] + 20, self.display_size[1] + 100)

        self.current_tool: str = "Freccia"
        self.draw_color: QColor = QColor("#ff0000")
        self.line_width: int = 3
        self.annotations: list[tuple[str, dict[str, Any]]] = []
        self.drawing: bool = False
        self.start_pos: QPointF = QPointF()
        self.temp_item: QGraphicsItem | None = None  # various subclasses assigned
        self.freehand_points: list[QPointF] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self._build_toolbar(layout)
        self._build_view(layout)

        self.exec()

    def _build_toolbar(self, parent_layout: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._tool_group = QButtonGroup(self)
        for i, tool in enumerate(self.TOOLS):
            rb = QRadioButton(tool)
            if i == 0:
                rb.setChecked(True)
            self._tool_group.addButton(rb, i)
            toolbar.addWidget(rb)
        self._tool_group.idClicked.connect(self._on_tool_change)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        toolbar.addWidget(sep1)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.setStyleSheet(f"background-color: {self.draw_color.name()}; border: 1px solid {BORDER};")
        self.color_btn.clicked.connect(self._pick_color)
        toolbar.addWidget(self.color_btn)

        toolbar.addWidget(QLabel("Spessore:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 15)
        self.width_spin.setValue(3)
        toolbar.addWidget(self.width_spin)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        toolbar.addWidget(sep2)

        undo_btn = QPushButton("Annulla ultimo")
        undo_btn.clicked.connect(self._undo)
        toolbar.addWidget(undo_btn)

        toolbar.addStretch()

        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        toolbar.addWidget(cancel_btn)

        save_btn = QPushButton("Salva")
        save_btn.clicked.connect(self._save)
        toolbar.addWidget(save_btn)

        parent_layout.addLayout(toolbar)

    def _build_view(self, parent_layout: QVBoxLayout) -> None:
        self.scene = QGraphicsScene(self)
        self.view = _AnnotationView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setStyleSheet(f"background-color: {BG_DARK};")

        pixmap = image_utils.pil_to_pixmap(self.display_image)
        self._bg_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(QRectF(pixmap.rect()))

        parent_layout.addWidget(self.view)

    def _on_tool_change(self, tool_id: int) -> None:
        self.current_tool = self.TOOLS[tool_id]

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self.draw_color, self, "Colore annotazione")
        if color.isValid():
            self.draw_color = color
            self.color_btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid {BORDER};")

    def _make_pen(self, color: QColor | None = None, width: int | None = None) -> QPen:
        pen = QPen(color or self.draw_color)
        pen.setWidth(width or self.width_spin.value())
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    # --- Mouse event handlers (called from _AnnotationView) ---

    def on_press(self, pos: QPointF) -> None:
        self.drawing = True
        self.start_pos = pos
        self.freehand_points = [pos]

        if self.current_tool == "Testo":
            text, ok = QInputDialog.getText(self, "Testo", "Inserisci testo:")
            if ok and text:
                font_size = max(12, self.width_spin.value() * 4)
                font = QFont(platform_utils.get_ui_font(), font_size)
                item = self.scene.addText(text, font)
                item.setPos(pos)
                item.setDefaultTextColor(self.draw_color)
                self.annotations.append(
                    (
                        "text",
                        {
                            "x": pos.x(),
                            "y": pos.y(),
                            "text": text,
                            "color": self.draw_color.name(),
                            "size": font_size,
                            "items": [item],
                        },
                    )
                )
            self.drawing = False

    def on_drag(self, pos: QPointF) -> None:
        if not self.drawing:
            return

        pen = self._make_pen()

        if self.current_tool == "Disegno libero":
            prev = self.freehand_points[-1]
            item = self.scene.addLine(QLineF(prev, pos), pen)
            self.freehand_points.append(pos)
            if not self.annotations or self.annotations[-1][0] != "_freehand_active":
                self.annotations.append(
                    (
                        "_freehand_active",
                        {
                            "items": [item],
                            "points": list(self.freehand_points),
                            "color": self.draw_color.name(),
                            "width": self.width_spin.value(),
                        },
                    )
                )
            else:
                self.annotations[-1][1]["items"].append(item)
                self.annotations[-1][1]["points"].append(pos)
        else:
            if self.temp_item:
                self.scene.removeItem(self.temp_item)
                self.temp_item = None

            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = pos.x(), pos.y()

            if self.current_tool == "Rettangolo":
                self.temp_item = self.scene.addRect(
                    QRectF(QPointF(min(x1, x2), min(y1, y2)), QPointF(max(x1, x2), max(y1, y2))), pen
                )
            elif self.current_tool == "Cerchio":
                self.temp_item = self.scene.addEllipse(
                    QRectF(QPointF(min(x1, x2), min(y1, y2)), QPointF(max(x1, x2), max(y1, y2))), pen
                )
            elif self.current_tool in ("Freccia", "Linea"):
                self.temp_item = self.scene.addLine(QLineF(self.start_pos, pos), pen)

    def on_release(self, pos: QPointF) -> None:
        if not self.drawing:
            return
        self.drawing = False

        if self.current_tool == "Disegno libero":
            if self.annotations and self.annotations[-1][0] == "_freehand_active":
                entry = self.annotations[-1]
                self.annotations[-1] = ("freehand", entry[1])
            return

        if self.temp_item:
            self.scene.removeItem(self.temp_item)
            self.temp_item = None

        pen = self._make_pen()
        x1, y1 = self.start_pos.x(), self.start_pos.y()
        x2, y2 = pos.x(), pos.y()
        coords = (x1, y1, x2, y2)

        if self.current_tool == "Rettangolo":
            rect = QRectF(QPointF(min(x1, x2), min(y1, y2)), QPointF(max(x1, x2), max(y1, y2)))
            item: QGraphicsItem = self.scene.addRect(rect, pen)
            self.annotations.append(
                (
                    "rect",
                    {
                        "coords": coords,
                        "color": self.draw_color.name(),
                        "width": self.width_spin.value(),
                        "items": [item],
                    },
                )
            )
        elif self.current_tool == "Cerchio":
            item = self.scene.addEllipse(
                QRectF(QPointF(min(x1, x2), min(y1, y2)), QPointF(max(x1, x2), max(y1, y2))), pen
            )
            self.annotations.append(
                (
                    "oval",
                    {
                        "coords": coords,
                        "color": self.draw_color.name(),
                        "width": self.width_spin.value(),
                        "items": [item],
                    },
                )
            )
        elif self.current_tool == "Freccia":
            items = self._draw_arrow(self.start_pos, pos, pen)
            self.annotations.append(
                (
                    "arrow",
                    {
                        "coords": coords,
                        "color": self.draw_color.name(),
                        "width": self.width_spin.value(),
                        "items": items,
                    },
                )
            )
        elif self.current_tool == "Linea":
            item = self.scene.addLine(QLineF(self.start_pos, pos), pen)
            self.annotations.append(
                (
                    "line",
                    {
                        "coords": coords,
                        "color": self.draw_color.name(),
                        "width": self.width_spin.value(),
                        "items": [item],
                    },
                )
            )

    def _draw_arrow(self, start: QPointF, end: QPointF, pen: QPen) -> list[QGraphicsItem]:
        """Draw a line with an arrowhead. Returns list of scene items."""
        items: list[QGraphicsItem] = []
        line = self.scene.addLine(QLineF(start, end), pen)
        items.append(line)

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        angle = math.atan2(dy, dx)
        arrow_len = 15

        p1 = QPointF(end.x() + arrow_len * math.cos(angle + 2.6), end.y() + arrow_len * math.sin(angle + 2.6))
        p2 = QPointF(end.x() + arrow_len * math.cos(angle - 2.6), end.y() + arrow_len * math.sin(angle - 2.6))

        polygon = QPolygonF([end, p1, p2])
        brush = QBrush(pen.color())
        head = self.scene.addPolygon(polygon, pen, brush)
        items.append(head)
        return items

    def _undo(self) -> None:
        if not self.annotations:
            return
        ann_type, params = self.annotations.pop()
        for item in params.get("items", []):
            self.scene.removeItem(item)

    def _get_font(self, size: int) -> Any:
        """Carica un font TrueType cross-platform."""
        from PIL import ImageFont

        font_path = platform_utils.get_font_path()
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except OSError:
                pass
        return ImageFont.load_default()

    def _save(self) -> None:
        """Render annotations onto the PIL image and save."""
        from PIL import ImageDraw

        draw = ImageDraw.Draw(self.pil_image)
        sx, sy = self.scale_x, self.scale_y

        for ann_type, params in self.annotations:
            color = params.get("color", "#ff0000")
            width = max(1, int(params.get("width", 3) * sx))

            if ann_type == "rect":
                c = params["coords"]
                draw.rectangle([c[0] * sx, c[1] * sy, c[2] * sx, c[3] * sy], outline=color, width=width)

            elif ann_type == "oval":
                c = params["coords"]
                draw.ellipse([c[0] * sx, c[1] * sy, c[2] * sx, c[3] * sy], outline=color, width=width)

            elif ann_type == "line":
                c = params["coords"]
                draw.line([c[0] * sx, c[1] * sy, c[2] * sx, c[3] * sy], fill=color, width=width)

            elif ann_type == "arrow":
                c = params["coords"]
                draw.line([c[0] * sx, c[1] * sy, c[2] * sx, c[3] * sy], fill=color, width=width)
                dx = c[2] - c[0]
                dy = c[3] - c[1]
                angle = math.atan2(dy, dx)
                arrow_len = 20 * sx
                x2, y2 = c[2] * sx, c[3] * sy
                for a in [angle + 2.6, angle - 2.6]:
                    ax = x2 + arrow_len * math.cos(a)
                    ay = y2 + arrow_len * math.sin(a)
                    draw.line([x2, y2, ax, ay], fill=color, width=width)

            elif ann_type == "freehand":
                points = [(p.x() * sx, p.y() * sy) for p in params["points"]]
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
        QMessageBox.information(self, "Salvato", "Immagine annotata salvata.")
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class _AnnotationView(QGraphicsView):
    """QGraphicsView that forwards mouse events to the AnnotationTool."""

    def __init__(self, scene: QGraphicsScene, tool: AnnotationTool) -> None:
        super().__init__(scene)
        self._tool: AnnotationTool = tool
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._tool.on_press(self.mapToScene(event.pos()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._tool.on_drag(self.mapToScene(event.pos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._tool.on_release(self.mapToScene(event.pos()))
        super().mouseReleaseEvent(event)
