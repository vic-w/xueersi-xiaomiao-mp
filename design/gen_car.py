"""Generate a sleek sports-car (coupe) mesh as car_model.json.

Axes: +x right, +y up, nose -z (points down the road, away from viewer),
tail +z (faces the chase camera).

Run: python gen_car.py
Emits ../src/games/car_model.json
"""

import json

VERTS = []
FACES = []


def box(cx, cy, cz, sx, sy, sz, color_name, faces=(0, 1, 2, 3, 4, 5)):
    base = len(VERTS)
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    VERTS.extend([
        (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
        (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1),
    ])
    all_faces = [
        ((base + 0, base + 3, base + 2, base + 1), color_name),  # bottom
        ((base + 4, base + 5, base + 6, base + 7), color_name),  # top
        ((base + 0, base + 1, base + 5, base + 4), color_name),  # nose (-z)
        ((base + 3, base + 2, base + 6, base + 7), color_name),  # tail (+z)
        ((base + 0, base + 4, base + 7, base + 3), color_name),  # left
        ((base + 1, base + 2, base + 6, base + 5), color_name),  # right
    ]
    for fi in faces:
        FACES.append(all_faces[fi])


def frustum(cx, cy, cz, sx_bot, sz_bot, sx_top, sz_top, h,
            color_name, faces=(0, 1, 2, 3, 4, 5)):
    base = len(VERTS)
    y0, y1 = cy - h / 2, cy + h / 2
    x0b, x1b = cx - sx_bot / 2, cx + sx_bot / 2
    z0b, z1b = cz - sz_bot / 2, cz + sz_bot / 2
    x0t, x1t = cx - sx_top / 2, cx + sx_top / 2
    z0t, z1t = cz - sz_top / 2, cz + sz_top / 2
    VERTS.extend([
        (x0b, y0, z0b), (x1b, y0, z0b), (x1b, y0, z1b), (x0b, y0, z1b),
        (x0t, y1, z0t), (x1t, y1, z0t), (x1t, y1, z1t), (x0t, y1, z1t),
    ])
    all_faces = [
        ((base + 0, base + 3, base + 2, base + 1), color_name),
        ((base + 4, base + 5, base + 6, base + 7), color_name),
        ((base + 0, base + 1, base + 5, base + 4), color_name),
        ((base + 3, base + 2, base + 6, base + 7), color_name),
        ((base + 0, base + 4, base + 7, base + 3), color_name),
        ((base + 1, base + 2, base + 6, base + 5), color_name),
    ]
    for fi in faces:
        FACES.append(all_faces[fi])


# --- Sports car (coupe) ---
# Main hull: low and wide.
box(0, 0.28, 0.0, 1.7, 0.45, 3.8, "body", faces=(1, 2, 3, 4, 5))
# Lower nose wedge.
box(0, 0.20, -1.6, 1.5, 0.28, 0.9, "body", faces=(1, 2, 4, 5))
# Greenhouse: dark tinted cabin, tapering roof.
frustum(0, 0.62, -0.15, 1.35, 2.3, 1.15, 1.9, 0.55, "glass",
        faces=(1, 2, 3, 4, 5))
# Rear engine deck.
box(0, 0.50, 1.35, 1.5, 0.22, 0.9, "body", faces=(1, 3, 4, 5))
# Small lip spoiler.
box(0, 0.62, 1.80, 1.5, 0.07, 0.28, "body", faces=(1, 3))
# Taillight strip (faces chase camera).
box(0, 0.42, 1.94, 1.4, 0.10, 0.06, "taillight", faces=(3,))
# Headlight strip (faces away, rarely visible).
box(0, 0.32, -2.02, 1.3, 0.10, 0.06, "headlight", faces=(2,))
# Wheels.
for wx, wz in ((-0.78, -1.25), (0.78, -1.25), (-0.78, 1.25), (0.78, 1.25)):
    outer = 4 if wx < 0 else 5
    box(wx, 0.26, wz, 0.32, 0.52, 0.50, "wheel", faces=(1, 2, 3, outer))


model = {
    "name": "sports_car",
    "description": "Sleek coupe sports car. +x right, +y up, nose -z, tail +z (toward chase camera).",
    "vertices": [[round(x, 3), round(y, 3), round(z, 3)] for x, y, z in VERTS],
    "faces": [[list(indices), color] for indices, color in FACES],
}

with open("../src/games/car_model.json", "w") as f:
    json.dump(model, f, indent=2)

print(f"vertices: {len(VERTS)} / 128")
print(f"faces: {len(FACES)} / 64")
assert len(VERTS) <= 128 and len(FACES) <= 64
print("wrote ../src/games/car_model.json")
