# `c3d` 原生 3D 渲染模块

`native/c3d` 是一个面向本项目 ST7735 RGB565 帧缓冲区的轻量 3D 光栅器。顶点旋转、透视投影、面深度排序、凸多边形填充和边线绘制在 C 中执行，MicroPython 只负责游戏循环、输入和 `display.show()`。

当前实现是 3D 渲染核心，尚未包含纹理、光照、物理、Z-buffer 或近裁剪面切割。模型面应为凸多边形，同一个网格内的面按平均深度从远到近绘制；相互穿插的面可能遮挡错误，不同网格之间也不会自动排序。任何顶点深度不大于 `0.12`、投影非有限数或超出约 ±32767 坐标范围时，包含该顶点的面会跳过。

一个网格最多有 128 个顶点、64 个面，每个面有 3–8 个顶点。每个 `c3d.Mesh` 保存一份模型副本和一个工作区，后者在 ESP32 上约占 2.5 KiB，适合把静态模型准备一次后重复绘制。直接使用现有的 160×128 RGB565 显存，不额外分配第二份 40 KiB 帧缓冲。

## MicroPython API

```python
import c3d

mesh = c3d.Mesh(
    ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)),
    (((0, 1, 2, 3), 0xF800),),
)

c3d.clear(display.buffer, 160, 128, 0x0000)
c3d.render_mesh(
    display.buffer, 160, 128, mesh,
    (angle_x, angle_y, angle_z),
    4.0,                         # camera distance
    110.0,                       # focal length
    1.0,                         # model scale
    (80.0, 64.0),                # screen center
    None,                        # or an RGB565 edge color
    False,                       # omit per-vertex projection results
)
display.show()
```

`vertices` 是 `(x, y, z)` 序列，`faces` 是 `((顶点索引, ...), RGB565颜色)` 序列。角度单位为弧度，颜色范围为 `0..65535`，缓冲区须可写、紧密排列且至少有 `width * height * 2` 字节，布局与 `framebuf.RGB565` 一致。

`Mesh` 会复制传入的数据，因此可以在创建后释放或修改 Python 容器。`render_mesh` 的最后一个参数默认是 `True`，此时返回与旧版 `Software3D.draw_mesh` 兼容的投影列表；动画循环建议传 `False`，避免为这些结果分配 Python 对象。底层 `c3d` 函数使用位置参数。

游戏代码通常使用封装层，它会在检测到原生模块和 `.buffer` 时自动选择 C 后端，否则继续使用纯 Python 后端：

```python
from games.software3d import Software3D

gl = Software3D(display)
mesh = gl.prepare_mesh(vertices, faces)
gl.clear()
gl.draw_prepared_mesh(mesh, (rx, ry, rz), 1.18, (80, 64), 0x0000,
                      return_projection=False)
gl.show()
```

`prepare_mesh()` 应放在动画循环外。纯 Python 后端保存的是原容器引用，为使两种后端行为一致，准备完成后请把模型视为只读；要更新几何数据，可以重新准备网格。原有的 `draw_mesh(vertices, faces, ...)` 调用仍可使用，但在 C 后端会每次重新创建模型。

## 构建 ESP32 固件

当前工程按 MicroPython **v1.28.0** 的用户 C 模块接口组织，ESP32 构建按该版本官方 README 推荐使用 ESP-IDF **v5.5.1**。以下命令适用于 Linux/WSL 的 shell。先准备 MicroPython 源码并激活 ESP-IDF 环境，然后在本工程根目录执行：

Windows 主机建议使用 WSL2 Ubuntu 24.04。在管理员 PowerShell 安装一次并按提示重启 Windows：

```powershell
wsl --install -d Ubuntu-24.04
```

打开 Ubuntu 后，安装主机依赖并下载、安装 ESP-IDF 工具链（ESP-IDF 安装只需做一次）：

```sh
sudo apt update
sudo apt install -y build-essential git wget flex bison gperf python3 python3-pip \
  python3-venv cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
mkdir -p "$HOME/esp"
git clone --branch v5.5.1 --recursive https://github.com/espressif/esp-idf.git \
  "$HOME/esp/esp-idf-v5.5.1"
cd "$HOME/esp/esp-idf-v5.5.1"
./install.sh esp32
```

每次打开新的 Ubuntu 终端时，激活 IDF 环境；然后获取 MicroPython v1.28.0 源码（只需做一次）：

```sh
source "$HOME/esp/esp-idf-v5.5.1/export.sh"
git clone --branch v1.28.0 --depth 1 https://github.com/micropython/micropython.git \
  "$HOME/micropython-1.28.0"
```

在 WSL 中进入 Windows 上的本工程目录（默认 D 盘映射为 `/mnt/d`），构建固件：

```sh
cd /mnt/d/code/codex_ws/xiaomiao/xueersi-xiaomiao-mp
make build-c3d-firmware \
  MICROPYTHON_DIR="$HOME/micropython-1.28.0"
```

该目标会先构建 `mpy-cross`，再构建 `ESP32_GENERIC` 的 `SPIRAM` 变体。`USER_C_MODULES` 指向的是本工程的 `native/micropython.cmake` 文件，而不是目录。固件通常生成在：

```text
micropython/ports/esp32/build-ESP32_GENERIC-SPIRAM/firmware.bin
```

也可以手动执行等价命令：

```sh
make -C /path/to/micropython-1.28.0/mpy-cross
make -C /path/to/micropython-1.28.0/ports/esp32 submodules \
  BOARD=ESP32_GENERIC BOARD_VARIANT=SPIRAM \
  USER_C_MODULES="$PWD/native/micropython.cmake"
make -C /path/to/micropython-1.28.0/ports/esp32 \
  BOARD=ESP32_GENERIC BOARD_VARIANT=SPIRAM \
  USER_C_MODULES="$PWD/native/micropython.cmake"
```

构建目标不会烧录。确认要升级设备后，使用生成的 `firmware.bin` 写入 `0x1000`。下面的 `COMx` 表示 Windows 串口，在 Linux/WSL 中请换成对应的 `/dev/ttyUSB0` 等设备路径：

```sh
esptool --chip esp32 --port COMx write-flash 0x1000 \
  /path/to/micropython/ports/esp32/build-ESP32_GENERIC-SPIRAM/firmware.bin
```

现有 `make write-flash-micron-python` 会擦除整个 Flash 并写回 `bins/` 中的原版固件，不会安装这里生成的 C3D 固件。

已有小喵应用的设备可以更新下面的 Python 文件；全新设备还需上传应用的其余文件并确保 `/games` 目录存在：

```sh
make put_lib PORT=COMx
make put FILE=src/main.py PORT=COMx
ampy --port COMx put src/games/software3d.py /games/software3d.py
ampy --port COMx put src/games/cube_screensaver.py /games/cube_screensaver.py
```

## 验证

不需要硬件即可运行独立 C 光栅器测试和 Python 回退测试：

```sh
make test-c3d
```

也可以直接运行 `python native/c3d/tests/run_native_tests.py`。测试覆盖 RGB565 写入、面深度排序、边线、非法帧缓冲区、隐藏面、极端投影参数和缓冲区哨兵保护。

`native/c3d/tests/micropython_smoke.py` 用真实的 `framebuf` 对照 C 和 Python 的渲染结果，并检查屏幕边界、绑定参数和模型的 GC 生命周期。桌面 MicroPython 构建需要启用 `framebuf` 和本模块；例如在 MSYS2 UCRT64 shell 中构建 Windows 端口：

```sh
make -C /path/to/micropython-1.28.0/ports/windows -j4 \
  FROZEN_MANIFEST= USER_C_MODULES="$PWD/native" \
  CFLAGS_EXTRA="-DMICROPY_PY_FRAMEBUF=1 -DMICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_FLOAT"
/path/to/micropython-1.28.0/ports/windows/build-standard/micropython.exe \
  native/c3d/tests/micropython_smoke.py
```

Windows 端口使用 Makefile，因此这里的 `USER_C_MODULES` 是包含 `c3d/micropython.mk` 的 `native` 目录，区别于 ESP32 的 CMake 文件参数。测试使用与 ESP32 相同的单精度浮点配置，允许边界处少量舍入差异。

已在电脑上通过独立 C 测试及 MicroPython v1.28.0 Windows 端口集成测试。尚未构建 ESP32 固件或在小喵真机验证；实际帧率还取决于 ESP32 的计算和 SPI 刷屏时间。

官方参考：

- [MicroPython ESP32 v1.28.0 README](https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/README.md)
- [MicroPython 用户 C 模块](https://docs.micropython.org/en/latest/develop/cmodules.html)
