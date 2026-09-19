import io
import os
import random

import openpyxl
import openpyxl.cell
import ujson as json
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment

from utils import check_stop, find_and_replace_wildcards_from_dict, format_str, read_json, reset_stop, sleep_for_cool
from utils.variable import return_quality_tags
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


def _refresh_image_refs(sheet):
    """保存前用原始字节重建图片 ref, 避免 openpyxl 保存时关闭 BytesIO 后多次保存报 'I/O operation on closed file'。

    首次遇到某张图片时, 把它当前 ref 的原始字节缓存到 img._raw_bytes (BytesIO 可能已关闭, 之后无法再读取);
    之后每次保存前都用缓存字节重建一个新的 BytesIO, 保证可重复保存。
    """
    for img in sheet._images:
        try:
            data = getattr(img, "_raw_bytes", None)
            if data is None:
                ref = img.ref
                if isinstance(ref, io.BytesIO):
                    ref.seek(0)
                    data = ref.read()
                elif isinstance(ref, (str, os.PathLike)) and os.path.exists(os.fspath(ref)):
                    with open(os.fspath(ref), "rb") as f:
                        data = f.read()
                img._raw_bytes = data
            if data is not None:
                img.ref = io.BytesIO(data)
        except Exception as e:
            logger.debug(f"读取图片数据失败: {e}")


def _save_workbook(workbook, file_path, sheet):
    """保存工作簿: 先写临时文件, 成功后再替换原文件 (避免中途失败破坏原文件)。

    若某张图片异常导致保存失败, 自动跳过该图 (工作簿中该位置留空), 不影响其它图片;
    同时保存前重建 BytesIO ref, 避免 openpyxl 多次保存时报 'I/O operation on closed file'。
    """
    tmp_path = file_path + ".tmp"

    def _write():
        _refresh_image_refs(sheet)
        workbook.save(tmp_path)

    try:
        _write()
    except Exception as e:
        logger.warning(f"保存工作簿失败: {e}, 尝试跳过异常图片后重试")
        logger.opt(exception=True).debug("保存工作簿失败堆栈:")
        # 逐张检查: 找出无法生成数据的图片并移除 (位置留空, 不影响其它图片)
        removed = 0
        for img in list(sheet._images):
            try:
                img._data()  # 与保存时相同的图片读取逻辑; 失败说明该图异常
            except Exception:
                sheet._images.remove(img)
                removed += 1
                logger.warning(f"已跳过异常图片: {getattr(img, 'ref', '?')}")
                logger.opt(exception=True).debug("跳过异常图片堆栈:")
        if removed:
            try:
                _write()
            except Exception as e2:
                logger.warning(f"跳过 {removed} 张异常图片后仍保存失败: {e2}")
                logger.opt(exception=True).debug("重试保存失败堆栈:")
                _cleanup_tmp(tmp_path)
                return False
        else:
            _cleanup_tmp(tmp_path)
            return False
    try:
        os.replace(tmp_path, file_path)
        return True
    except PermissionError:
        # 目标文件被占用 (如用 Excel 打开了工作簿): 尝试直接写回, 若仍失败则保留临时文件供恢复
        logger.warning(f"目标文件 {file_path} 正被其他程序占用 (可能用 Excel 打开了工作簿), 尝试直接写回...")
        try:
            _refresh_image_refs(sheet)
            workbook.save(file_path)
            _cleanup_tmp(tmp_path)
            return True
        except Exception as e:
            logger.warning(f"目标文件被占用无法写回, 最新结果已保留到临时文件: {tmp_path}")
            logger.opt(exception=True).debug("直接写回工作簿失败堆栈:")
            logger.info(
                "请关闭占用该文件的程序 (如 Excel) 后, 将临时文件重命名为原文件名即可恢复结果; "
                "或关闭占用程序后重新运行插件。"
            )
            return False
    except Exception as e:
        logger.warning(f"替换工作簿文件失败: {e}")
        logger.opt(exception=True).debug("替换工作簿文件失败堆栈:")
        _cleanup_tmp(tmp_path)
        return False


def _cleanup_tmp(tmp_path):
    """清理临时文件 (若存在)。"""
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass


def main(file_path, images_number):
    reset_stop()  # 重置本任务的停止信号 (生图队列按任务独立管理)

    workbook = openpyxl.load_workbook(file_path)
    # 关闭加载时打开的底层 zip 归档, 避免重复保存到同一路径时出现 "I/O operation on closed file"
    if getattr(workbook, "_archive", None):
        try:
            workbook._archive.close()
        except Exception:
            pass
        workbook._archive = None
    sheet = workbook["Sheet"]
    # 预缓存工作簿中已有图片的原始字节, 避免后续多次保存时 BytesIO 被关闭导致保存失败
    _refresh_image_refs(sheet)
    col_num = 2
    positive = sheet[f"B{col_num}"].value

    num = 1
    try:
        while positive is not None:
            if check_stop():
                logger.warning("已停止生成!")
                break

            row_num = ord("C") - 65
            for _ in range(images_number):
                if check_stop():
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

                # 追加质量标签 (与 generate_images.py generate() 行为一致)
                model = json_data.get("model", "nai-diffusion-4-5-full")
                quality_id = json_data.get("parameters", {}).get("qualityPresetId")
                if quality_id:
                    _qp_map = {"standard": "Standard", "light": "Light", "none": "None"}
                    quality_preset = _qp_map.get(quality_id, "Standard")
                    if quality_preset != "None":
                        tag_text = return_quality_tags(model, quality_preset)
                        if tag_text:
                            json_data["input"] = format_str(f"{json_data['input']}, {tag_text}")

                json_data = find_and_replace_wildcards_from_dict(json_data)

                saved_path = None
                retries = 0
                while saved_path is None:
                    if check_stop():
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
            _save_workbook(workbook, file_path, sheet)
    except Exception as e:
        logger.error(f"处理过程出错: {e}")
        logger.opt(exception=True).debug("处理过程出错堆栈:")
    finally:
        # 无论正常/异常/停止, 最终都对齐并保存一次, 已生成的图片全部保留
        try:
            alignment = Alignment(horizontal="center", vertical="center", wrapText=True)
            for row in sheet.iter_rows():
                for cell in row:
                    cell.alignment = alignment
            _save_workbook(workbook, file_path, sheet)
        except Exception as e:
            logger.warning(f"最终保存工作簿失败: {e}")
            logger.opt(exception=True).debug("最终保存工作簿失败堆栈:")

    logger.success(f"推文生图处理完毕, 打开 {file_path} 以查看结果!")

    return f"推文生图处理完毕, 打开 {file_path} 以查看结果!"