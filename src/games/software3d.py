"""A compact software 3D renderer for MicroPython displays.

It provides camera setup, rotation, projected polygon filling and mesh
drawing, rendering directly to the framebuffer-backed display.
"""

import math

try:
    import c3d as _native_c3d
except ImportError:
    _native_c3d = None


DEG_TO_RAD = 0.017453292519943295


class Software3D:
    def __init__(self, display, width=160, height=128, use_native=True):
        self.display = display
        self.width = width
        self.height = height
        self.center_x = width / 2.0
        self.center_y = height / 2.0
        self.distance = 4.0
        self.focal = self._focal_length(60.0)
        self._native = (
            _native_c3d if use_native and hasattr(display, "buffer") else None
        )
        self.backend = "C" if self._native is not None else "Python"

    def _focal_length(self, fov_degrees):
        return (self.height / 2.0) / math.tan(
            fov_degrees * DEG_TO_RAD / 2.0
        )

    def set_camera(self, distance=4.0, fov_degrees=60.0):
        self.distance = distance
        self.focal = self._focal_length(fov_degrees)

    def clear(self, color=0):
        if self._native is not None:
            self._native.clear(
                self.display.buffer, self.width, self.height, color
            )
            return
        self.display.fill(color)

    def show(self):
        self.display.show()

    def _rotate(self, x, y, z, angle_x, angle_y, angle_z):
        cos_x = math.cos(angle_x)
        sin_x = math.sin(angle_x)
        y, z = y * cos_x - z * sin_x, y * sin_x + z * cos_x

        cos_y = math.cos(angle_y)
        sin_y = math.sin(angle_y)
        x, z = x * cos_y + z * sin_y, -x * sin_y + z * cos_y

        cos_z = math.cos(angle_z)
        sin_z = math.sin(angle_z)
        x, y = x * cos_z - y * sin_z, x * sin_z + y * cos_z
        return x, y, z

    def project(self, vertices, angles=(0.0, 0.0, 0.0), scale=1.0,
                center=None):
        center_x, center_y = center or (self.center_x, self.center_y)
        projected = []
        for x, y, z in vertices:
            x, y, z = self._rotate(
                x * scale,
                y * scale,
                z * scale,
                angles[0],
                angles[1],
                angles[2],
            )
            depth = z + self.distance
            if depth <= 0.12:
                projected.append(None)
                continue
            screen_x = int(center_x + x * self.focal / depth + 0.5)
            screen_y = int(center_y - y * self.focal / depth + 0.5)
            projected.append((screen_x, screen_y, depth))
        return projected

    def prepare_mesh(self, vertices, faces):
        """Prepare a static mesh once, outside the animation loop."""
        if self._native is not None:
            return self._native.Mesh(vertices, faces)
        return vertices, faces

    def draw_prepared_mesh(self, mesh, angles=(0.0, 0.0, 0.0),
                           scale=1.0, center=None, edge_color=None,
                           return_projection=True, cam_pos=None):
        if self._native is not None:
            center_x, center_y = center or (self.center_x, self.center_y)
            args = [
                self.display.buffer,
                self.width,
                self.height,
                mesh,
                angles,
                self.distance,
                self.focal,
                scale,
                (center_x, center_y),
                edge_color,
                return_projection,
            ]
            if cam_pos is not None:
                args.append(tuple(cam_pos))
            return self._native.render_mesh(*args)
        return self.draw_mesh(
            mesh[0], mesh[1], angles, scale, center, edge_color,
            return_projection,
        )

    def draw_mesh(self, vertices, faces, angles=(0.0, 0.0, 0.0),
                  scale=1.0, center=None, edge_color=None,
                  return_projection=True):
        if self._native is not None:
            return self.draw_prepared_mesh(
                self.prepare_mesh(vertices, faces), angles, scale, center,
                edge_color, return_projection,
            )

        projected = self.project(vertices, angles, scale, center)
        ordered = []
        for indices, color in faces:
            points = []
            depth_total = 0.0
            valid = True
            for index in indices:
                point = projected[index]
                if point is None:
                    valid = False
                    break
                points.append((point[0], point[1]))
                depth_total += point[2]
            if valid and len(points) >= 3:
                ordered.append((depth_total / len(points), points, color))

        ordered.sort(key=lambda item: item[0], reverse=True)
        for _, points, color in ordered:
            self.fill_polygon(points, color)
            if edge_color is not None:
                self.stroke_polygon(points, edge_color)
        return projected if return_projection else None

    def fill_polygon(self, points, color):
        point_count = len(points)
        if point_count < 3:
            return

        ys = [point[1] for point in points]
        first_y = max(0, min(ys))
        last_y = min(self.height - 1, max(ys))
        if first_y > last_y:
            return

        for y in range(first_y, last_y + 1):
            left = self.width
            right = -1
            for index in range(point_count):
                x1, y1 = points[index]
                x2, y2 = points[(index + 1) % point_count]
                if y1 == y2:
                    continue
                crosses = (y1 <= y < y2) or (y2 <= y < y1)
                if not crosses:
                    continue
                x = int(x1 + (y - y1) * (x2 - x1) / (y2 - y1) + 0.5)
                if x < left:
                    left = x
                if x > right:
                    right = x

            if right < 0 or left >= self.width:
                continue
            if left < 0:
                left = 0
            if right >= self.width:
                right = self.width - 1
            if right >= left:
                self.display.hline(left, y, right - left + 1, color)

    def stroke_polygon(self, points, color):
        point_count = len(points)
        for index in range(point_count):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % point_count]
            self.display.line(x1, y1, x2, y2, color)
