import os
import random

import openpyxl
import openpyxl.cell
import ujson as json
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment

from utils import find_and_replace_wildcards_from_dict, read_json, sleep_for_cool
from utils.environment import env
from utils.generator import Generator
from utils.logger import logger

generator = Generator("https://image.novelai.net/ai/generate-image")


def number_to_letters(n):
    result = ""
    while n >= 0:
        result = chr(n % 26 + ord("A")) + result
        n = n // 26 - 1
    return result


if not os.path.exists(
    xlsx_path := "./plugins/anr_plugin_stories_to_images/模板文件.xlsx"
):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.row_dimensions[1].height = 50
    for row in range(2, 999):
        ws.row_dimensions[row].height = 300
    for col in [number_to_letters(num) for num in range(1000)]:
        ws.column_dimensions[col].width = 40
    ws.append(
        [
            "推文",
            "TAG",
            "图片",
        ]
    )
    alignment = Alignment(horizontal="center", vertical="center", wrapText=True)
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = alignment
    wb.save(xlsx_path)


def open_folder(path):
    os.startfile(os.path.abspath(path))


def open_file(path):
    """用系统默认程序打开指定文件 (如 Excel 工作簿)。"""
    if path and os.path.exists(path):
        os.startfile(os.path.abspath(path))
    else:
        logger.warning(f"文件不存在, 无法打开: {path}")


def main(file_path, images_number):
    with open("./outputs/temp_break.json", "w") as f:
        json.dump({"break": False}, f)

    workbook = openpyxl.load_workbook(file_path)
    # 关闭加载时打开的底层 zip 归档, 避免重复保存到同一路径时出现 "I/O operation on closed file"
    if getattr(workbook, "_archive", None):
        try:
            workbook._archive.close()
        except Exception:
            pass
        workbook._archive = None
    sheet = workbook["Sheet"]
    col_num = 2
    positive = sheet[f"B{col_num}"].value

    num = 1
    try:
        while positive is not None:
            _break = read_json("./outputs/temp_break.json")
            if _break["break"]:
                logger.warning("已停止生成!")
                break

            row_num = ord("C") - 65
            for _ in range(images_number):
                _break = read_json("./outputs/temp_break.json")
                if _break["break"]:
                    break

                try:
                    json_data = read_json("./outputs/temp_last_origin.json")
                except FileNotFoundError:
                    logger.error("未进行一次图片生成!")
                    return "未进行一次图片生成!"

                logger.info(f"正在生成第 {num} 张图片...")
                if json_data.get("model") in ["nai-diffusion-3", "nai-diffusion-furry-3"]:
                    pass
                else:
                    json_data["parameters"]["v4_prompt"]["caption"][
                        "base_caption"
                    ] = positive
                json_data["input"] = positive
                json_data["parameters"]["seed"] = random.randint(1000000000, 9999999999)

                json_data = find_and_replace_wildcards_from_dict(json_data)

                saved_path = None
                retries = 0
                while saved_path is None:
                    _break = read_json("./outputs/temp_break.json")
                    if _break["break"]:
                        logger.warning("已停止生成!")
                        break
                    try:
                        image_data = generator.generate(json_data)
                    except Exception as e:
                        logger.error(f"出现错误: {e}")
                        logger.opt(exception=True).debug("生成异常堆栈:")
                        image_data = None
                    if image_data:
                        saved_path = generator.save(
                            image_data,
                            "text2image/stories2images",
                            json_data["parameters"]["seed"],
                            f"/{col_num - 1}/".join((env.custom_path).rsplit("/", 1)),
                        )
                    else:
                        retries += 1
                        if retries >= 10:
                            logger.warning(f"第 {num + 1} 张图片重试 10 次仍失败, 跳过 (不中断任务)")
                            break
                        sleep_for_cool(5)
                num += 1

                # 单张失败(或已停止): 跳过本张, 用已有图片继续后续操作, 不中断整个任务
                if not saved_path or not os.path.exists(saved_path):
                    logger.warning(f"第 {num - 1} 张图片未生成成功, 跳过")
                    sleep_for_cool(env.cool_time)
                    row_num += 1
                    continue

                try:
                    image = Image(saved_path)
                    w = image.width
                    h = image.height
                    image.width, image.height = 265, int(265 / w * h)
                    sheet.add_image(image, "{}{}".format(number_to_letters(row_num), col_num))
                except Exception as e:
                    logger.warning(f"插入图片失败 (第 {num - 1} 张): {e}")
                    logger.opt(exception=True).debug("插入图片异常堆栈:")

                sleep_for_cool(env.cool_time)

                row_num += 1
            col_num += 1
            positive = sheet[f"B{col_num}"].value
            # 每处理完一列立即保存, 中途出错/停止时已插入的图片不丢失
            try:
                workbook.save(file_path)
            except Exception as e:
                logger.warning(f"保存工作簿失败: {e}")
                logger.opt(exception=True).debug("保存工作簿失败堆栈:")
    except Exception as e:
        logger.error(f"处理过程出错: {e}")
    finally:
        # 无论正常/异常/停止, 最终都对齐并保存一次, 已生成的图片全部保留
        try:
            alignment = Alignment(horizontal="center", vertical="center", wrapText=True)
            for row in sheet.iter_rows():
                for cell in row:
                    cell.alignment = alignment
            workbook.save(file_path)
        except Exception as e:
            logger.warning(f"最终保存工作簿失败: {e}")
            logger.opt(exception=True).debug("最终保存工作簿失败堆栈:")

    logger.success(f"推文生图处理完毕, 打开 {file_path} 以查看结果!")

    return f"推文生图处理完毕, 打开 {file_path} 以查看结果!"
