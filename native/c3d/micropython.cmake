add_library(usermod_c3d INTERFACE)

target_sources(usermod_c3d INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/c3d.c
    ${CMAKE_CURRENT_LIST_DIR}/c3d_render.c
)

target_include_directories(usermod_c3d INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(usermod INTERFACE usermod_c3d)
