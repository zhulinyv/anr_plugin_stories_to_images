import gradio as gr

from plugins.anr_plugin_stories_to_images.utils import main, open_folder
from utils import stop_generate, tk_asksavefile_asy


def plugin():
    with gr.Tab("推文生图"):
        with gr.Row():
            with gr.Column():
                story_input_file = gr.Textbox(label="Excel 文件路径")
                with gr.Row():
                    story_input_text = gr.Textbox(visible=False)
                    story_input_btn = gr.Button("选择文件")
                    story_clear_btn = gr.Button("清除选择")
                story_file_button = gr.Button("打开文件", visible=False)
                story_file_button.click(open_folder, story_input_text, outputs=None)
                story_input_text.change(
                    lambda x: (
                        gr.update(visible=True) if x else gr.update(visible=False)
                    ),
                    inputs=story_input_text,
                    outputs=story_file_button,
                )

                gr.Markdown("使用说明:")
                gr.Markdown(
                    "① 点击打开插件目录按钮, 找到 **模板文件.xlsx** 并复制一份."
                )
                gr.Markdown(
                    "② 打开模板文件, 填写 TAG 列即可, 描述列可以不填, 完成后保存并关闭文件."
                )
                gr.Markdown("③ 在左侧参数设置区域中配置本次生成所使用的参数.")
                gr.Markdown("④ 点击 **开始生成** 按钮, 生成 1 张图片查看效果.")
                gr.Markdown("⑤ **不要跳过**上一步, 完成上述操作后点击推文生图按钮.")
                gr.Markdown(
                    "Tips: 支持使用 vibe, 角色参考, 角色分区, wildcards 等功能."
                )
                gr.Markdown("注意: 停止生成后**无法**从某个位置继续生成.")
                gr.Markdown("注意: 选择同一个 *.xlsx 文件重复生成时, 图片会重叠.")
                gr.Markdown("注意: 生成过程中请勿执行其它使用官网 API 的生成操作.")

            story_clear_btn.click(
                lambda x: x, gr.Textbox(None, visible=False), story_input_text
            )
            story_input_btn.click(
                tk_asksavefile_asy, inputs=[], outputs=[story_input_text]
            )
            story_input_text.change(lambda x: x, story_input_text, story_input_file)

            with gr.Column():
                story_info = gr.Textbox(label="输出信息")
                story_path_button = gr.Button("打开插件目录")
                story_path_button.click(
                    open_folder,
                    gr.Textbox("./plugins/anr_plugin_stories_to_images", visible=False),
                )
                story_generate_button = gr.Button("推文生图")
                story_stop_button = gr.Button("停止生成")
                story_stop_button.click(stop_generate)
                story_images_number = gr.Slider(
                    1, 999, 3, step=1, label="每段 TAG 生成图片的数量"
                )
                story_generate_button.click(
                    main,
                    inputs=[story_input_text, story_images_number],
                    outputs=story_info,
                )
