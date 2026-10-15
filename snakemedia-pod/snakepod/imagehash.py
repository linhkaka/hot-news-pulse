"""dHash: dấu vân tay 64 bit của ảnh thumbnail, để nhận ra cùng 1 video dù shop khác upload lại."""
import io

from PIL import Image


def dhash(data: bytes) -> str:
    img = Image.open(io.BytesIO(data)).convert("L").resize((9, 8), Image.LANCZOS)
    px = img.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return f"{bits:016x}"


def distance(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()
