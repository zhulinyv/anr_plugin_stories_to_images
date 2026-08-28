"""推文生图插件: 从 Excel 模板批量生成图片并插入表格。"""
from __future__ import annotations

from plugins.anr_plugin_stories_to_images.utils import main, open_file, open_folder
from utils.plugins import Action, Field, Panel, Plugin

PLUGIN_DIR = "./plugins/anr_plugin_stories_to_images"


def register(plugin: Plugin):
    panel = Panel(
        id="stories",
        title="推文生图",
        icon="📝",
        fields=[
            Field(id="usage", label="使用说明", type="info", default=(
                "① 点击打开插件目录按钮, 找到 模板文件.xlsx 并复制一份.\n"
                "② 打开模板文件, 填写 TAG 列即可, 描述列可以不填, 完成后保存并关闭文件.\n"
                "③ 在左侧参数设置区域中配置本次生成所使用的参数.\n"
                "④ 点击 开始生成 按钮, 生成 1 张图片查看效果.\n"
                "⑤ 不要跳过上一步, 完成上述操作后点击推文生图按钮.\n"
                "Tips: 支持使用 vibe, 角色参考, 角色分区, wildcards 等功能.\n"
                "注意: 停止生成后无法从某个位置继续生成.\n"
                "注意: 选择同一个 *.xlsx 文件重复生成时, 图片会重叠.\n"
                "注意: 生成过程中请勿执行其它使用官网 API 的生成操作."
            )),
            Field(id="file", label="Excel 工作簿文件", type="filearea", accept=".xlsx, .xls", no_drag=True, direct_path=True, placeholder="点击选择 Excel 工作簿文件 (.xlsx / .xls)", column="right"),
            Field(id="images_number", label="每段 TAG 生成图片的数量", type="slider", min=1, max=999, step=1, default=3, column="right"),
        ],
        actions=[
            Action(id="generate", label="📝 推文生图", inputs=["file", "images_number"], show_output=False, handler=lambda v: {"text": main(v.get("file", ""), int(v.get("images_number", 3)))}),
            Action(id="open_dir", label="📂 打开插件目录", inputs=[], show_output=False, stop=False, handler=lambda v: (open_folder(PLUGIN_DIR), {})[1]),
            Action(id="open_file", label="📂 打开文件", inputs=["file"], show_output=False, stop=False, handler=lambda v: (open_file(v.get("file", "")), {})[1]),
        ],
    )
    plugin.title = "推文生图"
    plugin.description = "从 Excel 模板批量生成推文配图"
    plugin.icon = "📝"
    plugin.panels.append(panel)
