#ifndef XIAOMIAO_C3D_RENDER_H
#define XIAOMIAO_C3D_RENDER_H

#include <stddef.h>
#include <stdint.h>

#define C3D_MAX_VERTICES 128
#define C3D_MAX_FACES 64
#define C3D_MAX_FACE_VERTICES 8
#define C3D_MAX_DIMENSION 1024
#define C3D_MAX_COORDINATE 32767

typedef struct {
    float x;
    float y;
    float z;
} c3d_vertex_t;

typedef struct {
    uint8_t count;
    uint8_t indices[C3D_MAX_FACE_VERTICES];
    uint16_t color;
} c3d_face_t;

typedef struct {
    float angle_x;
    float angle_y;
    float angle_z;
    float distance;
    float focal;
    float scale;
    float center_x;
    float center_y;
    /* Camera translation (world-space camera position). After mesh rotation
       the vertex is translated by (-cam_x, -cam_y, -cam_z) so the camera
       can orbit the scene. Default 0 (no translation) keeps old behavior. */
    float cam_x;
    float cam_y;
    float cam_z;
} c3d_camera_t;

typedef struct {
    int x;
    int y;
    float depth;
    int valid;
} c3d_projected_t;

typedef struct {
    float depth;
    size_t face_index;
} c3d_face_order_t;

typedef struct {
    c3d_projected_t projected[C3D_MAX_VERTICES];
    c3d_face_order_t order[C3D_MAX_FACES];
} c3d_workspace_t;

void c3d_clear(uint8_t *buffer, size_t buffer_len, int width, int height,
               uint16_t color);

void c3d_render_mesh(uint8_t *buffer, size_t buffer_len, int width, int height,
                     const c3d_vertex_t *vertices, size_t vertex_count,
                     const c3d_face_t *faces, size_t face_count,
                     const c3d_camera_t *camera, c3d_workspace_t *workspace,
                     int has_edge_color,
                     uint16_t edge_color);

#endif
