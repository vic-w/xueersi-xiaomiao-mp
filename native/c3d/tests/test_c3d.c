#include "../c3d_render.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define WIDTH 16
#define HEIGHT 16
#define STRIDE (WIDTH * HEIGHT * 2)

static uint16_t pixel(const uint8_t *buffer, int x, int y) {
    uint16_t value;
    memcpy(&value, buffer + ((size_t)y * WIDTH + (size_t)x) * 2,
           sizeof(value));
    return value;
}

int main(void) {
    uint8_t buffer[STRIDE + 1];
    c3d_workspace_t workspace;
    const c3d_vertex_t vertices[] = {
        {-1, -1, 0}, {1, -1, 0}, {1, 1, 0}, {-1, 1, 0},
        {-0.5f, -0.5f, -1}, {0.5f, -0.5f, -1},
        {0.5f, 0.5f, -1}, {-0.5f, 0.5f, -1},
    };
    const c3d_face_t faces[] = {
        {4, {4, 5, 6, 7}, 0x001f},
        {4, {0, 1, 2, 3}, 0xf800},
    };
    const c3d_camera_t camera = {
        .angle_x = 0,
        .angle_y = 0,
        .angle_z = 0,
        .distance = 4,
        .focal = 12,
        .scale = 1,
        .center_x = 8,
        .center_y = 8,
    };

    memset(buffer, 0xcc, sizeof(buffer));
    c3d_clear(buffer, STRIDE, WIDTH, HEIGHT, 0x07e0);
    assert(pixel(buffer, 0, 0) == 0x07e0);
    assert(pixel(buffer, WIDTH - 1, HEIGHT - 1) == 0x07e0);
    assert(buffer[STRIDE] == 0xcc);

    memset(buffer, 0, sizeof(buffer));
    c3d_render_mesh(buffer, STRIDE, WIDTH, HEIGHT, vertices,
                    sizeof(vertices) / sizeof(vertices[0]), faces,
                    sizeof(faces) / sizeof(faces[0]), &camera, &workspace,
                    0, 0);
    assert(pixel(buffer, 8, 8) == 0x001f);
    assert(pixel(buffer, 5, 8) == 0xf800);
    assert(pixel(buffer, 0, 0) == 0);

    c3d_render_mesh(buffer, STRIDE, WIDTH, HEIGHT, vertices,
                    sizeof(vertices) / sizeof(vertices[0]), faces,
                    sizeof(faces) / sizeof(faces[0]), &camera, &workspace,
                    1, 0xffff);
    assert(pixel(buffer, 8, 8) == 0x001f);
    assert(pixel(buffer, 6, 8) == 0xffff);
    assert(pixel(buffer, 0, 0) == 0);
    assert(buffer[STRIDE] == 0);

    /* Invalid buffer length must leave the memory and canary untouched. */
    memset(buffer, 0xa5, sizeof(buffer));
    c3d_clear(buffer, STRIDE - 1, WIDTH, HEIGHT, 0);
    assert(buffer[0] == 0xa5 && buffer[STRIDE - 1] == 0xa5);
    assert(buffer[STRIDE] == 0xa5);

    /* Invalid render destinations must also preserve every byte. */
    c3d_render_mesh(buffer, STRIDE - 1, WIDTH, HEIGHT, vertices, 8, faces,
                    2, &camera, &workspace, 1, 0xffff);
    for (size_t index = 0; index < sizeof(buffer); ++index) {
        assert(buffer[index] == 0xa5);
    }

    /* Behind-camera and extreme projections cannot write outside the frame. */
    const c3d_vertex_t hidden[] = {
        {-1, -1, -5}, {1, -1, -5}, {0, 1, -5},
    };
    const c3d_face_t triangle = {3, {0, 1, 2}, 0xffff};
    memset(buffer, 0, sizeof(buffer));
    buffer[STRIDE] = 0x5a;
    c3d_render_mesh(buffer, STRIDE, WIDTH, HEIGHT, hidden, 3, &triangle,
                    1, &camera, &workspace, 1, 0xffff);
    for (size_t index = 0; index < STRIDE; ++index) {
        assert(buffer[index] == 0);
    }
    c3d_camera_t extreme_camera = camera;
    extreme_camera.scale = 1e30f;
    c3d_render_mesh(buffer, STRIDE, WIDTH, HEIGHT, vertices, 8, faces,
                    2, &extreme_camera, &workspace, 1, 0xffff);
    assert(buffer[STRIDE] == 0x5a);
    extreme_camera.center_x = INFINITY;
    c3d_render_mesh(buffer, STRIDE, WIDTH, HEIGHT, vertices, 8, faces,
                    2, &extreme_camera, &workspace, 1, 0xffff);
    assert(buffer[STRIDE] == 0x5a);

    puts("c3d rasterizer tests passed");
    return 0;
}
