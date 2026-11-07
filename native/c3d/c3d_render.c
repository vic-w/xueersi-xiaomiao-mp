#include "c3d_render.h"

#include <math.h>
#include <string.h>

static int c3d_valid_buffer(const uint8_t *buffer, size_t length,
                            int width, int height) {
    return buffer != NULL && width > 0 && height > 0 &&
           width <= C3D_MAX_DIMENSION && height <= C3D_MAX_DIMENSION &&
           length >= (size_t)width * (size_t)height * 2;
}

static void c3d_put_pixel(uint8_t *buffer, size_t buffer_len, int width,
                          int height, int x, int y, uint16_t color) {
    size_t offset;

    if (x < 0 || y < 0 || x >= width || y >= height) {
        return;
    }
    offset = ((size_t)y * (size_t)width + (size_t)x) * 2;
    if (offset + 1 >= buffer_len) {
        return;
    }
    /* Match framebuf.RGB565, including hosts with a different byte order. */
    memcpy(buffer + offset, &color, sizeof(color));
}

static void c3d_hline(uint8_t *buffer, size_t buffer_len, int width, int height,
                      int x, int y, int line_width, uint16_t color) {
    int end = x + line_width;
    int clipped_start = x < 0 ? 0 : x;
    int clipped_end = end > width ? width : end;
    int current;

    if (y < 0 || y >= height || clipped_start >= clipped_end) {
        return;
    }
    for (current = clipped_start; current < clipped_end; ++current) {
        c3d_put_pixel(buffer, buffer_len, width, height, current, y, color);
    }
}

static void c3d_line(uint8_t *buffer, size_t buffer_len, int width, int height,
                     int x0, int y0, int x1, int y1, uint16_t color) {
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int sx = x0 < x1 ? 1 : -1;
    int dy = y1 > y0 ? y0 - y1 : y1 - y0;
    int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;

    for (;;) {
        c3d_put_pixel(buffer, buffer_len, width, height, x0, y0, color);
        if (x0 == x1 && y0 == y1) {
            break;
        }
        {
            int twice_error = 2 * error;
            if (twice_error >= dy) {
                error += dy;
                x0 += sx;
            }
            if (twice_error <= dx) {
                error += dx;
                y0 += sy;
            }
        }
    }
}

static void c3d_fill_polygon(uint8_t *buffer, size_t buffer_len, int width,
                             int height, const c3d_projected_t *projected,
                             const c3d_face_t *face) {
    int first_y = height - 1;
    int last_y = 0;
    uint8_t index;

    for (index = 0; index < face->count; ++index) {
        const c3d_projected_t *point = &projected[face->indices[index]];
        if (point->y < first_y) {
            first_y = point->y;
        }
        if (point->y > last_y) {
            last_y = point->y;
        }
    }
    if (first_y < 0) {
        first_y = 0;
    }
    if (last_y >= height) {
        last_y = height - 1;
    }
    if (first_y > last_y) {
        return;
    }

    for (; first_y <= last_y; ++first_y) {
        int left = width;
        int right = -1;
        for (index = 0; index < face->count; ++index) {
            const c3d_projected_t *p1 = &projected[face->indices[index]];
            const c3d_projected_t *p2 =
                &projected[face->indices[(index + 1) % face->count]];
            int x;

            if (p1->y == p2->y ||
                !((p1->y <= first_y && first_y < p2->y) ||
                  (p2->y <= first_y && first_y < p1->y))) {
                continue;
            }
            x = (int)(p1->x + (float)(first_y - p1->y) *
                                  (float)(p2->x - p1->x) /
                                  (float)(p2->y - p1->y) + 0.5f);
            if (x < left) {
                left = x;
            }
            if (x > right) {
                right = x;
            }
        }
        if (right >= 0 && left < width) {
            if (left < 0) {
                left = 0;
            }
            if (right >= width) {
                right = width - 1;
            }
            if (right >= left) {
                c3d_hline(buffer, buffer_len, width, height, left, first_y,
                           right - left + 1, face->color);
            }
        }
    }
}

static void c3d_swap_order(c3d_face_order_t *left, c3d_face_order_t *right) {
    c3d_face_order_t temporary = *left;
    *left = *right;
    *right = temporary;
}

void c3d_clear(uint8_t *buffer, size_t buffer_len, int width, int height,
               uint16_t color) {
    int y;
    int x;

    if (!c3d_valid_buffer(buffer, buffer_len, width, height)) {
        return;
    }
    for (y = 0; y < height; ++y) {
        for (x = 0; x < width; ++x) {
            c3d_put_pixel(buffer, buffer_len, width, height, x, y, color);
        }
    }
}

void c3d_render_mesh(uint8_t *buffer, size_t buffer_len, int width, int height,
                     const c3d_vertex_t *vertices, size_t vertex_count,
                     const c3d_face_t *faces, size_t face_count,
                     const c3d_camera_t *camera, c3d_workspace_t *workspace,
                     int has_edge_color,
                     uint16_t edge_color) {
    c3d_projected_t *projected = workspace->projected;
    c3d_face_order_t *order = workspace->order;
    float cos_x = cosf(camera->angle_x);
    float sin_x = sinf(camera->angle_x);
    float cos_y = cosf(camera->angle_y);
    float sin_y = sinf(camera->angle_y);
    float cos_z = cosf(camera->angle_z);
    float sin_z = sinf(camera->angle_z);
    size_t vertex_index;
    size_t face_index;

    if (vertex_count > C3D_MAX_VERTICES || face_count > C3D_MAX_FACES ||
        !c3d_valid_buffer(buffer, buffer_len, width, height)) {
        return;
    }

    for (vertex_index = 0; vertex_index < vertex_count; ++vertex_index) {
        float x = vertices[vertex_index].x * camera->scale;
        float y = vertices[vertex_index].y * camera->scale;
        float z = vertices[vertex_index].z * camera->scale;
        float depth;
        float rotated_x;
        float rotated_y;
        float rotated_z;

        rotated_y = y * cos_x - z * sin_x;
        rotated_z = y * sin_x + z * cos_x;
        y = rotated_y;
        z = rotated_z;
        rotated_x = x * cos_y + z * sin_y;
        rotated_z = -x * sin_y + z * cos_y;
        x = rotated_x;
        z = rotated_z;
        rotated_x = x * cos_z - y * sin_z;
        rotated_y = x * sin_z + y * cos_z;
        x = rotated_x;
        y = rotated_y;

        /* Camera translation: move world so camera sits at origin. */
        x -= camera->cam_x;
        y -= camera->cam_y;
        z -= camera->cam_z;

        depth = z + camera->distance;
        projected[vertex_index].depth = depth;
        projected[vertex_index].valid = isfinite(depth) && depth > 0.12f;
        if (projected[vertex_index].valid) {
            float screen_x = camera->center_x + x * camera->focal / depth + 0.5f;
            float screen_y = camera->center_y - y * camera->focal / depth + 0.5f;
            /* Bound conversions and line drawing work for extreme inputs. */
            if (!isfinite(screen_x) || !isfinite(screen_y) ||
                fabsf(screen_x) > C3D_MAX_COORDINATE ||
                fabsf(screen_y) > C3D_MAX_COORDINATE) {
                projected[vertex_index].valid = 0;
            } else {
                projected[vertex_index].x = (int)screen_x;
                projected[vertex_index].y = (int)screen_y;
            }
        }
    }

    for (face_index = 0; face_index < face_count; ++face_index) {
        const c3d_face_t *face = &faces[face_index];
        float depth_total = 0.0f;
        int valid = face->count >= 3 && face->count <= C3D_MAX_FACE_VERTICES;
        uint8_t index;

        for (index = 0; valid && index < face->count; ++index) {
            if (face->indices[index] >= vertex_count ||
                !projected[face->indices[index]].valid) {
                valid = 0;
            } else {
                depth_total += projected[face->indices[index]].depth;
            }
        }
        if (valid) {
            order[face_index].depth = depth_total / (float)face->count;
            order[face_index].face_index = face_index;
        } else {
            order[face_index].depth = -1.0f;
            order[face_index].face_index = face_index;
        }
    }

    /* Stable insertion sort preserves input order for equal-depth faces. */
    for (face_index = 1; face_index < face_count; ++face_index) {
        size_t cursor = face_index;
        while (cursor > 0 && order[cursor - 1].depth < order[cursor].depth) {
            c3d_swap_order(&order[cursor - 1], &order[cursor]);
            --cursor;
        }
    }

    for (face_index = 0; face_index < face_count; ++face_index) {
        const c3d_face_t *face;
        uint8_t index;
        if (order[face_index].depth < 0.0f) {
            continue;
        }
        face = &faces[order[face_index].face_index];
        c3d_fill_polygon(buffer, buffer_len, width, height, projected, face);
        if (has_edge_color) {
            for (index = 0; index < face->count; ++index) {
                const c3d_projected_t *p1 =
                    &projected[face->indices[index]];
                const c3d_projected_t *p2 =
                    &projected[face->indices[(index + 1) % face->count]];
                c3d_line(buffer, buffer_len, width, height, p1->x, p1->y,
                         p2->x, p2->y, edge_color);
            }
        }
    }
}
