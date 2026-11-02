"""Stamp page numbers on body pages of the toolkit PDF (skip cover + ending)."""
import io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

SRC = "/home/z/my-project/download/song-timestamp-toolkit.pdf"
W_PT, H_PT = 540.0, 765.0  # 720x1020 px at 96dpi -> 540x765 pt
MUTED = (0.545, 0.522, 0.506)  # #8b8581

reader = PdfReader(SRC)
n = len(reader.pages)
writer = PdfWriter()

for i, page in enumerate(reader.pages):
    if i == 0 or i == n - 1:  # cover and ending page: no visible number
        writer.add_page(page)
        continue
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W_PT, H_PT))
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(*MUTED)
    c.drawCentredString(W_PT / 2, 20, str(i))  # body numbering starts at 1 on page 2
    c.save()
    buf.seek(0)
    overlay = PdfReader(buf).pages[0]
    page.merge_page(overlay)
    writer.add_page(page)

with open(SRC, "wb") as f:
    writer.write(f)
print(f"stamped pages 2..{n-1} with numbers 1..{n-2}; total {n} pages")
