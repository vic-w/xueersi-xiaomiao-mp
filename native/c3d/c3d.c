#include "py/runtime.h"
#include "c3d_render.h"

#include <math.h>

typedef struct {
    mp_obj_base_t base;
    size_t vertex_count;
    size_t face_count;
    c3d_vertex_t *vertices;
    c3d_face_t *faces;
    c3d_workspace_t *workspace;
} c3d_mesh_obj_t;

static float c3d_float(mp_obj_t object) {
    float value = (float)mp_obj_get_float(object);
    if (!isfinite(value)) {
        mp_raise_ValueError(MP_ERROR_TEXT("expected a finite number"));
    }
    return value;
}

static uint16_t c3d_color(mp_obj_t object) {
    mp_int_t value = mp_obj_get_int(object);
    if (value < 0 || value > 65535) {
        mp_raise_ValueError(MP_ERROR_TEXT("color must be 0..65535"));
    }
    return (uint16_t)value;
}

static mp_obj_t c3d_mesh_make_new(const mp_obj_type_t *type, size_t n_args,
                                  size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 2, 2, false);
    mp_obj_t *vertices;
    mp_obj_t *faces;
    size_t vertex_count;
    size_t face_count;
    mp_obj_get_array(args[0], &vertex_count, &vertices);
    mp_obj_get_array(args[1], &face_count, &faces);
    if (vertex_count > C3D_MAX_VERTICES || face_count > C3D_MAX_FACES) {
        mp_raise_ValueError(MP_ERROR_TEXT("mesh exceeds vertex or face limit"));
    }
    c3d_mesh_obj_t *self = mp_obj_malloc(c3d_mesh_obj_t, type);
    self->vertices = NULL;
    self->faces = NULL;
    self->workspace = NULL;
    self->vertex_count = vertex_count;
    self->face_count = face_count;
    self->vertices = m_new(c3d_vertex_t, vertex_count);
    self->faces = m_new(c3d_face_t, face_count);
    self->workspace = m_new_obj(c3d_workspace_t);
    for (size_t index = 0; index < vertex_count; ++index) {
        mp_obj_t *point;
        mp_obj_get_array_fixed_n(vertices[index], 3, &point);
        self->vertices[index].x = c3d_float(point[0]);
        self->vertices[index].y = c3d_float(point[1]);
        self->vertices[index].z = c3d_float(point[2]);
    }
    for (size_t index = 0; index < face_count; ++index) {
        mp_obj_t *face;
        mp_obj_t *indices;
        size_t index_count;
        mp_obj_get_array_fixed_n(faces[index], 2, &face);
        mp_obj_get_array(face[0], &index_count, &indices);
        if (index_count < 3 || index_count > C3D_MAX_FACE_VERTICES) {
            mp_raise_ValueError(MP_ERROR_TEXT("face must have 3..8 vertices"));
        }
        self->faces[index].count = (uint8_t)index_count;
        self->faces[index].color = c3d_color(face[1]);
        for (size_t corner = 0; corner < index_count; ++corner) {
            mp_int_t vertex_index = mp_obj_get_int(indices[corner]);
            if (vertex_index < 0 || (size_t)vertex_index >= vertex_count) {
                mp_raise_ValueError(MP_ERROR_TEXT("face index out of range"));
            }
            self->faces[index].indices[corner] = (uint8_t)vertex_index;
        }
    }
    return MP_OBJ_FROM_PTR(self);
}

static MP_DEFINE_CONST_OBJ_TYPE(
    c3d_mesh_type, MP_QSTR_Mesh, MP_TYPE_FLAG_NONE,
    make_new, c3d_mesh_make_new
    );

static void c3d_get_framebuffer(const mp_obj_t *args, mp_buffer_info_t *buffer,
                                int *width, int *height) {
    mp_int_t w = mp_obj_get_int(args[1]);
    mp_int_t h = mp_obj_get_int(args[2]);
    if (w <= 0 || h <= 0 || w > C3D_MAX_DIMENSION || h > C3D_MAX_DIMENSION) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid framebuffer dimensions"));
    }
    mp_get_buffer_raise(args[0], buffer, MP_BUFFER_RW);
    if (buffer->len < (size_t)w * (size_t)h * 2) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer is too small"));
    }
    *width = (int)w;
    *height = (int)h;
}

static mp_obj_t c3d_clear_call(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t buffer;
    int width;
    int height;
    uint16_t color = c3d_color(args[3]);
    c3d_get_framebuffer(args, &buffer, &width, &height);
    c3d_clear(buffer.buf, buffer.len, width, height, color);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(c3d_clear_fun_obj, 4, 4, c3d_clear_call);

static mp_obj_t c3d_render_mesh_call(size_t n_args, const mp_obj_t *args) {
    if (!mp_obj_is_type(args[3], &c3d_mesh_type)) {
        mp_raise_TypeError(MP_ERROR_TEXT("expected c3d.Mesh"));
    }
    c3d_mesh_obj_t *mesh = MP_OBJ_TO_PTR(args[3]);
    mp_obj_t *angles;
    mp_obj_t *center;
    mp_obj_get_array_fixed_n(args[4], 3, &angles);
    mp_obj_get_array_fixed_n(args[8], 2, &center);
    c3d_camera_t camera = {
        .angle_x = c3d_float(angles[0]),
        .angle_y = c3d_float(angles[1]),
        .angle_z = c3d_float(angles[2]),
        .distance = c3d_float(args[5]),
        .focal = c3d_float(args[6]),
        .scale = c3d_float(args[7]),
        .center_x = c3d_float(center[0]),
        .center_y = c3d_float(center[1]),
        .cam_x = 0.0,
        .cam_y = 0.0,
        .cam_z = 0.0,
    };
    /* Optional 12th arg: cam_pos = (cam_x, cam_y, cam_z). */
    if (n_args >= 12 && args[11] != mp_const_none) {
        mp_obj_t *cam_pos;
        mp_obj_get_array_fixed_n(args[11], 3, &cam_pos);
        camera.cam_x = c3d_float(cam_pos[0]);
        camera.cam_y = c3d_float(cam_pos[1]);
        camera.cam_z = c3d_float(cam_pos[2]);
    }
    if (camera.distance <= 0 || camera.focal <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("distance and focal must be positive"));
    }
    int has_edge_color = args[9] != mp_const_none;
    uint16_t edge_color = has_edge_color ? c3d_color(args[9]) : 0;
    int return_projection = n_args == 10 || mp_obj_is_true(args[10]);
    mp_buffer_info_t buffer;
    int width;
    int height;
    /* Fetch the buffer after all conversions that could execute Python. */
    c3d_get_framebuffer(args, &buffer, &width, &height);
    c3d_render_mesh(buffer.buf, buffer.len, width, height, mesh->vertices,
                    mesh->vertex_count, mesh->faces, mesh->face_count, &camera,
                    mesh->workspace, has_edge_color, edge_color);
    if (!return_projection) {
        return mp_const_none;
    }
    /* Preserve Software3D.draw_mesh's projected-vertices result on demand. */
    mp_obj_t result = mp_obj_new_list(mesh->vertex_count, NULL);
    for (size_t index = 0; index < mesh->vertex_count; ++index) {
        const c3d_projected_t *point = &mesh->workspace->projected[index];
        mp_obj_t value = mp_const_none;
        if (point->valid) {
            mp_obj_t values[3] = {
                mp_obj_new_int(point->x), mp_obj_new_int(point->y),
                mp_obj_new_float(point->depth),
            };
            value = mp_obj_new_tuple(3, values);
        }
        mp_obj_subscr(result, MP_OBJ_NEW_SMALL_INT(index), value);
    }
    return result;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(c3d_render_mesh_fun_obj, 10, 12,
                                           c3d_render_mesh_call);

static const mp_rom_map_elem_t c3d_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_c3d) },
    { MP_ROM_QSTR(MP_QSTR_Mesh), MP_ROM_PTR(&c3d_mesh_type) },
    { MP_ROM_QSTR(MP_QSTR_clear), MP_ROM_PTR(&c3d_clear_fun_obj) },
    { MP_ROM_QSTR(MP_QSTR_render_mesh), MP_ROM_PTR(&c3d_render_mesh_fun_obj) },
};
static MP_DEFINE_CONST_DICT(c3d_module_globals, c3d_module_globals_table);

const mp_obj_module_t c3d_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&c3d_module_globals,
};
MP_REGISTER_MODULE(MP_QSTR_c3d, c3d_user_cmodule);
