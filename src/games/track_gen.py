"""Procedural track generator.

Emits a JSON-serializable list of segments. Each segment is:
    {"curve": <float -3..3>, "hill": <float -1..1>, "length": <float>}

curve: 0 = straight, negative = left, positive = right.
hill:  0 = flat, negative = downhill, positive = uphill.
length: world units (typical segment ~200).

The generator guarantees a mix of straights, curves, and hills, and never
starts the player on a curve (first few segments are straight).
"""

import random


def generate(segment_count=60, seed=None):
    if seed is not None:
        random.seed(seed)
    segments = []
    # Opening straight so the player gets up to speed.
    for _ in range(4):
        segments.append({"curve": 0.0, "hill": 0.0, "length": 200.0})

    for _ in range(segment_count):
        roll = random.random()
        if roll < 0.35:
            curve = 0.0
            hill = random.uniform(-0.3, 0.3)
            length = random.uniform(150.0, 250.0)
        elif roll < 0.75:
            curve = random.choice((-1, 1)) * random.uniform(0.8, 2.5)
            hill = random.uniform(-0.2, 0.2)
            length = random.uniform(180.0, 320.0)
        else:
            curve = random.uniform(-0.5, 0.5)
            hill = random.uniform(-0.8, 0.8)
            length = random.uniform(150.0, 220.0)
        segments.append({
            "curve": round(curve, 2),
            "hill": round(hill, 2),
            "length": round(length, 1),
        })

    # Closing straight back to the start line.
    for _ in range(3):
        segments.append({"curve": 0.0, "hill": 0.0, "length": 200.0})
    return segments


def total_length(segments):
    return sum(s["length"] for s in segments)
