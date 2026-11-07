from lib.hardware import new_easydisplay, LightSensor, TemperatureSensor
from lib.easymenu import EasyMenu, MenuItem, BackItem, ValueItem, ToggleItem
from lib.easybutton import EasyButton
from lib.wifi_manager import WifiManager
from machine import Pin


wifi_mgr = WifiManager()

def get_ip():
    return wifi_mgr.get_ip()

def get_light_sensor():
    s = LightSensor()
    return f'{s.value()}'

def get_temp_sensor():
    s = TemperatureSensor()
    return f'{s.value()}'

def is_wifi_enabled():
    return wifi_mgr.is_active()

def toggle_wifi_status():
    if wifi_mgr.is_active():
        wifi_mgr.turn_off()
    else:
        wifi_mgr.turn_on()

menuOptions = {
    "title": "智能学习机",
    "layout": [1, 6],
    "spacing": [128, 16],
    "subMenus": [
        {
            "name": "学习",
            "subMenus": [
                {"name": "5以内的加法", "packageName": "learning.arithmetic",
                 "params": {"max_num": 5, "op": "+"}},
                {"name": "5以内的减法", "packageName": "learning.arithmetic",
                 "params": {"max_num": 5, "op": "-"}},
                {"name": "10以内的加法", "packageName": "learning.arithmetic",
                 "params": {"max_num": 10, "op": "+"}},
                {"name": "10以内的减法", "packageName": "learning.arithmetic",
                 "params": {"max_num": 10, "op": "-"}},
                {"name": "1到10加减法", "packageName": "learning.arithmetic"},
                {"name": "加法口诀", "packageName": "learning.addition_table"},
                {"name": "乘法口诀", "packageName": "learning.multiplication_table"},
                {"name": "记单词", "packageName": "learning.word_memorize"},
                {"name": "上级菜单", "type": "back"},
            ]
        },
        {
            "name": "Games",
            "subMenus": [
                {"name": "国际象棋", "packageName": "games.chess"},
                {"name": "秒表", "packageName": "games.stopwatch", "defer": True},
                {"name": "俄罗斯方块", "packageName": "games.tetris"},
                {"name": "恐龙快跑", "packageName": "games.dino_run"},
                {"name": "超级玛丽", "packageName": "games.mario_run"},
                {"name": "极速公路", "packageName": "games.fc_racing"},
                {"name": "毁灭公爵", "packageName": "games.doom"},
                {"name": "推箱子", "packageName": "games.sokoban"},
                {"name": "猜数字", "packageName": "games.guess_number"},
                {"name": "迷宫", "packageName": "games.maze"},
                {"name": "立方体屏保", "packageName": "games.cube_screensaver"},
                {"name": "上级菜单", "type": "back"},
            ]
        },
        {
            "name": "状态",
            "subMenus": [
                {"name": "光照", "type": "value", "value": (get_light_sensor, "r", "c"), "skip": True},
                {"name": "温度", "type": "value", "value": (get_temp_sensor, "r", "c"), "skip": True},
                {"name": "上级菜单", "type": "back"},
            ]
        },
        {
            "name": "设置",
            "subMenus": [
                {
                    "name": "WiFi",
                    "type": "toggle",
                    "status_callback": is_wifi_enabled,
                    "change_callback": toggle_wifi_status,
                    "value_t": "[开]",
                    "value_f": "[关]",
                },
                {"name": "WiFi配置", "packageName": "settings.wifi_setup"},
                {"name": "IP", "type": "value", "value": (get_ip, "r", "c"), "skip": True},
                {"name": "日期时间", "packageName": "settings.time_screen"},
                {"name": "上级菜单", "type": "back"},
            ]
        }
    ]
}


class Context:
    """Shared context for packages, providing access to display and input."""
    def __init__(self):
        self.ed = new_easydisplay()
        self.k_u = EasyButton(Pin(2, Pin.IN, Pin.PULL_UP))
        self.k_d = EasyButton(Pin(13, Pin.IN, Pin.PULL_UP))
        self.k_l = EasyButton(Pin(27, Pin.IN, Pin.PULL_UP))
        self.k_r = EasyButton(Pin(35, Pin.IN, Pin.PULL_UP))
        self.k_a = EasyButton(Pin(34, Pin.IN, Pin.PULL_UP))
        self.k_b = EasyButton(Pin(12, Pin.IN, Pin.PULL_UP))

        menu = self.build_menu(menuOptions)
        self.em = EasyMenu(self.ed, menu)
        self.bind_buttons_to_menu(self.em)

    def bind_buttons_to_menu(self, em):
        self.k_u.down_func = lambda: em.prev()
        self.k_d.down_func = lambda: em.next()
        self.k_l.down_func = None
        self.k_r.down_func = None
        self.k_a.down_func = lambda: em.click()
        self.k_b.down_func = lambda: em.back()

    def common_callback(self, package_name, params=None):
        """Import and run a package module with optional params."""
        import sys
        __import__(package_name)
        mod = sys.modules[package_name]
        if params is not None:
            mod.run(self, params)
        else:
            mod.run(self)

    def defer_callback(self, package_name):
        """Start a package after the current menu interrupt has returned."""
        import micropython
        micropython.schedule(self.run_deferred_callback, package_name)

    def run_deferred_callback(self, package_name):
        self.common_callback(package_name)

    def build_menu(self, cfg):
        is_root = "title" in cfg and "name" not in cfg
        name = cfg.get("name", "")
        title = cfg.get("title", name)

        if is_root:
            item = MenuItem(
                title=(title, "c", 0),
                layout=cfg.get("layout", [1, 6]),
                spacing=cfg.get("spacing", [128, 16]),
            )
        else:
            item = MenuItem(
                name=name,
                title=(title, "c", 0),
                layout=cfg.get("layout", [1, 6]),
                spacing=cfg.get("spacing", [128, 16]),
            )

        for sub in cfg.get("subMenus", []):
            item_type = sub.get("type", "menu")
            if item_type == "back":
                item.add(BackItem(sub["name"]))
            elif item_type == "toggle":
                item.add(ToggleItem(
                    sub["name"],
                    sub["status_callback"],
                    sub.get("change_callback"),
                    value_t=sub.get("value_t", "[*]"),
                    value_f=sub.get("value_f", "[ ]"),
                ))
            elif item_type == "value":
                item.add(ValueItem(
                    sub["name"],
                    value=sub.get("value", ""),
                    skip=sub.get("skip", False),
                ))
            elif "subMenus" in sub:
                item.add(self.build_menu(sub))
            elif "packageName" in sub:
                pkg = sub["packageName"]
                params = sub.get("params")
                if sub.get("defer"):
                    item.add(MenuItem(sub["name"],
                        callback=lambda p=pkg: self.defer_callback(p)))
                elif params:
                    item.add(MenuItem(sub["name"],
                        callback=lambda p=pkg, ps=params: self.common_callback(p, ps)))
                else:
                    item.add(MenuItem(sub["name"],
                        callback=lambda p=pkg: self.common_callback(p)))
            else:
                item.add(MenuItem(
                    sub["name"],
                    callback=sub.get("callback", None),
                ))

        return item

    def run(self):
        self.em.show()


ctx = Context()
ctx.run()
