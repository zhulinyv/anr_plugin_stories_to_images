"""推文生图插件: 从 Excel 模板批量生成图片并插入表格。"""
from __future__ import annotations

from plugins.anr_plugin_stories_to_images.utils import main, open_folder
from utils.plugins import Action, Field, Panel, Plugin

PLUGIN_DIR = "./plugins/anr_plugin_stories_to_images"


def register(plugin: Plugin):
    panel = Panel(
        id="stories",
        title="推文生图",
        icon="📝",
        description=(
            "① 点击打开插件目录, 找到 模板文件.xlsx 并复制一份\n"
            "② 打开模板文件, 填写 TAG 列即可, 完成后保存\n"
            "③ 先在左侧主页生成 1 张图片 (用于继承参数)\n"
            "④ 选择填好的 xlsx 文件并点击推文生图\n"
            "Tips: 支持 vibe, 角色参考, 角色分区, wildcards 等功能"
        ),
        fields=[
            Field(id="file", label="Excel 工作簿文件", type="filearea", accept=".xlsx, .xls"),
            Field(id="images_number", label="每段 TAG 生成图片的数量", type="slider", min=1, max=999, step=1, default=3),
        ],
        actions=[
            Action(id="generate", label="📝 推文生图", inputs=["file", "images_number"], handler=lambda v: {"text": main(v.get("file", ""), int(v.get("images_number", 3)))}),
            Action(id="open_dir", label="📂 打开插件目录", inputs=[], handler=lambda v: (open_folder(PLUGIN_DIR), {"text": "已打开插件目录"})[1]),
        ],
    )
    plugin.title = "推文生图"
    plugin.description = "从 Excel 模板批量生成推文配图"
    plugin.icon = "📝"
    plugin.panels.append(panel)
