"""The LCD face as an image (the firmware's neutral expression) and where it sits in the CAD.

Used by the renders (Blender textured quad) and the web viewer (glTF textured quad).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from strido.workspace import build_dir

# LCD window in the front shell (STEP frame, mm): x -26.5..16.5, z 55.5..88.5; the panel glass sits at
# y = -164.2 (inner face of the shell), so the image plane goes 0.1 mm in front of it.
FACE_X_MM = (-25.8, 15.8)
FACE_Z_MM = (56.2, 87.8)
FACE_Y_MM = -164.3
# firmware/strido_esp32s3/src/face.cpp: eyeColour() default, drawEye() size and radius, eye centres
EYE_RGB = (80, 230, 255)
EYE_W, EYE_H, EYE_RADIUS = 78, 96, 22
EYE_DX, EYE_DY = 70, -14
STATUS_RGB = (160, 160, 160)


def face_image(width: int = 320, height: int = 240, status: str = "Strido  7.60V") -> Image.Image:
    """`face::update` with the neutral expression, eyes open: two rounded eyes and the status line."""
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    for sign in (-1, 1):
        cx, cy = width / 2 + sign * EYE_DX, height / 2 + EYE_DY
        box = (cx - EYE_W / 2, cy - EYE_H / 2, cx + EYE_W / 2, cy + EYE_H / 2)
        draw.rounded_rectangle(box, radius=EYE_RADIUS, fill=EYE_RGB)
    draw.text((8, height - 22), status, fill=STATUS_RGB, font=ImageFont.load_default(size=16))
    return image


def corners_mm(offset=(0.0, 0.0, 0.0)) -> list[list[float]]:
    """Quad corners seen from the front, counter-clockwise from the image's bottom-left (+x STEP = viewer's right)."""
    (x0, x1), (z0, z1), y = FACE_X_MM, FACE_Z_MM, FACE_Y_MM
    dx, dy, dz = offset
    return [
        [x0 + dx, y + dy, z0 + dz],
        [x1 + dx, y + dy, z0 + dz],
        [x1 + dx, y + dy, z1 + dz],
        [x0 + dx, y + dy, z1 + dz],
    ]


def face_png() -> Path:
    target = build_dir("render") / "face.png"
    face_image().save(target)
    return target
