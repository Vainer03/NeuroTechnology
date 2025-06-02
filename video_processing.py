import os
import re
import whisper
import moviepy as mp
from moviepy.video.tools.subtitles import SubtitlesClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import traceback
import textwrap

whisper_model = None

# Загружает модель OpenAI Whisper один раз и сохраняет в глобальной переменной whisper_model.
def load_whisper_model(model_name="base"):
    global whisper_model
    if whisper_model is None:
        print(f"Загрузка модели Whisper: {model_name}...")
        try:
            whisper_model = whisper.load_model(model_name)
            print("Модель Whisper успешно загружена.")
        except Exception as e:
            print(f"Ошибка при загрузке модели Whisper: {e}")
            traceback.print_exc()
            raise
    return whisper_model

# Преобразует время в секундах в строку формата ЧЧ:ММ:СС,мс для SRT-файлов.
def format_timestamp_srt(seconds):
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)
    hours = milliseconds // 3_600_000; milliseconds -= hours * 3_600_000
    minutes = milliseconds // 60_000; milliseconds -= minutes * 60_000
    seconds_val = milliseconds // 1_000; milliseconds -= seconds_val * 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds_val:02d},{milliseconds:03d}"

# Обрабатывает аудиофайл через Whisper. Генерирует .srt файл с таймингами субтитров. Возвращает путь к созданному .srt и полный текст транскрипции.
def generate_srt_from_audio_whisper(audio_path, language=None):
    try:
        model = load_whisper_model()
        absolute_audio_path = os.path.abspath(audio_path)
        print(f"Передача в Whisper аудиофайла (абсолютный путь): {absolute_audio_path}")
        if not os.path.exists(absolute_audio_path):
            print(f"ОШИБКА: Файл {absolute_audio_path} не найден прямо перед вызовом transcribe!")
            return None, None

        options = {"language": language} if language else {}
        result = model.transcribe(absolute_audio_path, verbose=False, **options)

        srt_filename_base = os.path.splitext(absolute_audio_path)[0]
        srt_filename = srt_filename_base + ".srt"
        full_transcription = result["text"]

        with open(srt_filename, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(result["segments"]):
                start_time = segment["start"]; end_time = segment["end"]
                text = segment["text"].strip()
                if not text: continue
                start_srt = format_timestamp_srt(start_time); end_srt = format_timestamp_srt(end_time)
                srt_file.write(f"{i + 1}\n")
                srt_file.write(f"{start_srt} --> {end_srt}\n")
                srt_file.write(f"{text}\n\n")

        print(f"SRT файл успешно создан: {srt_filename}")
        return srt_filename, full_transcription
    except Exception as e:
        print(f"Ошибка при генерации SRT: {e}")
        traceback.print_exc()
        return None, None

# Парсит содержимое .srt файла в структуру, пригодную для MoviePy: [((start_time_sec, end_time_sec), "text"), ...]
def parse_srt_content(srt_string):
    subs = []
    pattern = re.compile(r"(\d+)\s*\n"
                         r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n"
                         r"((?:[^\n]+\n?)+)", re.MULTILINE)

    def srt_time_to_seconds(time_str):
        time_str = time_str.replace(',', '.'); parts = time_str.split(':')
        h = int(parts[0]); m = int(parts[1]); s_ms_part = parts[2].split('.');
        s = int(s_ms_part[0]); ms = int(s_ms_part[1])
        return h * 3600 + m * 60 + s + ms / 1000.0

    for match in pattern.finditer(srt_string):
        try:
            start_time = srt_time_to_seconds(match.group(2)); end_time = srt_time_to_seconds(match.group(3))
            text = match.group(4).strip().replace('\r\n', '\n').replace('\r', '\n')
            if text: subs.append(((start_time, end_time), text))
        except Exception as e:
            print(f"Ошибка парсинга блока SRT: '{match.group(0)}' -> {e}")
            continue

    if not subs and srt_string.strip():
        print("ПРЕДУПРЕЖДЕНИЕ: Не удалось распарсить SRT содержимое.")
    return subs


# Рендерит текст субтитров в виде изображения (numpy.array) с автоматическим переносом строк и подгонкой размера шрифта под доступную область.
def render_text_with_pillow(
    text_to_render,
    image_width,
    image_height,
    font_path_or_name='arial.ttf',
    font_size=24,
    text_color=(0,0,0,255),
    bg_color=(255,255,255,0),
    line_spacing_pt=4,
    padding_horizontal_ratio=0.03,
    padding_vertical_ratio=0.1,
    align_text="center"
):
    try:

        current_font_size = font_size

        min_font_size = 10

        padding_x_pixels = int(image_width * padding_horizontal_ratio)
        padding_y_pixels = int(image_height * padding_vertical_ratio)
        max_text_height = image_height - 2 * padding_y_pixels

        while True:
            # Пытаемся загрузить шрифт текущего размера
            try:
                font = ImageFont.truetype(font_path_or_name, current_font_size)
            except IOError:
                font = ImageFont.load_default()
            if not font:
                raise ValueError("Не удалось загрузить шрифт для Pillow")

            img = Image.new('RGBA', (image_width, image_height), bg_color)
            draw = ImageDraw.Draw(img)

            # Оцениваем приблизительную ширину символа
            try:
                bbox_char = font.getbbox("Ww") if hasattr(font, 'getbbox') else (0,0,font.getsize("Ww")[0], font.getsize("Ww")[1])
                avg_char_width_approx = (bbox_char[2] - bbox_char[0]) / 2.0 if bbox_char else current_font_size * 0.6
                if avg_char_width_approx == 0:
                    avg_char_width_approx = current_font_size * 0.6
            except Exception:
                avg_char_width_approx = current_font_size * 0.6

            text_area_width_pixels = image_width - 2 * padding_x_pixels
            chars_per_line = int(text_area_width_pixels / avg_char_width_approx)
            chars_per_line = max(chars_per_line, 10)

            wrapped_text = textwrap.fill(text_to_render, width=chars_per_line,
                                         break_long_words=False,
                                         replace_whitespace=True,
                                         drop_whitespace=True)
            if not wrapped_text:
                wrapped_text = text_to_render

            # Получаем реальный размер блока текста
            try:
                bbox = draw.multiline_textbbox((padding_x_pixels, padding_y_pixels), wrapped_text,
                                               font=font, spacing=line_spacing_pt,
                                               align=align_text, anchor="la")
                block_height = bbox[3] - bbox[1]
            except Exception:
                # Для старых версий Pillow, грубая оценка: count_lines * (прим. высота строки)
                num_lines = len(wrapped_text.split('\n'))
                block_height = num_lines * current_font_size * 1.2 + (num_lines - 1) * line_spacing_pt

            # Если текст по высоте больше доступного, уменьшаем размер шрифта и пробуем снова
            if block_height > max_text_height and current_font_size > min_font_size:
                current_font_size -= 2
                continue
            break

        # Теперь рисуем окончательный текст
        # Переинициализируем img и draw, чтобы не было пересечений
        img = Image.new('RGBA', (image_width, image_height), bg_color)
        draw = ImageDraw.Draw(img)

        # Вычисляем точные координаты для центрирования
        try:
            bbox = draw.multiline_textbbox((padding_x_pixels, padding_y_pixels), wrapped_text,
                                           font=font, spacing=line_spacing_pt,
                                           align=align_text, anchor="la")
            block_width = bbox[2] - bbox[0]
            block_height = bbox[3] - bbox[1]

            text_x = (image_width - block_width) / 2 if align_text == "center" else (
                     image_width - block_width - padding_x_pixels if align_text == "right" else padding_x_pixels)
            text_x = max(text_x, padding_x_pixels)

            text_y = (image_height - block_height) / 2
            text_y = max(text_y, padding_y_pixels)

            draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill=text_color,
                                spacing=line_spacing_pt, align=align_text, anchor="la")
        except Exception:
            current_y_manual = padding_y_pixels
            lines = wrapped_text.split('\n')
            line_heights_manual = []
            total_h_manual = 0
            for line in lines:
                try:
                    bbox_line = font.getbbox(line) if hasattr(font, 'getbbox') else (0,0,font.getsize(line)[0], font.getsize(line)[1])
                    h_line = bbox_line[3] - bbox_line[1]
                except:
                    h_line = current_font_size
                line_heights_manual.append(h_line)
                total_h_manual += h_line
            if len(lines) > 1:
                total_h_manual += (len(lines) - 1) * line_spacing_pt
            current_y_manual = (image_height - total_h_manual) / 2
            current_y_manual = max(current_y_manual, padding_y_pixels)

            for i, line in enumerate(lines):
                try:
                    bbox_line = font.getbbox(line) if hasattr(font, 'getbbox') else (0,0,font.getsize(line)[0], font.getsize(line)[1])
                    w_line = bbox_line[2] - bbox_line[0]
                except:
                    w_line = 0
                if align_text == "center":
                    line_x_manual = (image_width - w_line) / 2
                elif align_text == "right":
                    line_x_manual = image_width - w_line - padding_x_pixels
                else:
                    line_x_manual = padding_x_pixels
                draw.text((line_x_manual, current_y_manual), line, font=font, fill=text_color)
                current_y_manual += line_heights_manual[i] + line_spacing_pt

        return np.array(img)

    except Exception as e:
        print(f"Ошибка при рендеринге текста с Pillow: '{text_to_render}' -> {e}")
        traceback.print_exc()
        return np.zeros((image_height, image_width, 4), dtype=np.uint8)

# Добавляет субтитры в виде плашки под оригинальным видео.
def add_subtitles_to_video(video_path, srt_path, output_path, subtitle_bar_height_percent=15):
    video_clip_obj = None; final_clip_with_bar_obj = None; final_video_obj = None
    subtitles_clip_obj = None; white_bar_clip_obj = None; srt_file_reader = None
    try:
        print(f"Начало add_subtitles_to_video для: {os.path.basename(video_path)}")
        if not os.path.exists(video_path):
            print(f"ОШИБКА: video_path {video_path} не найден!")
            return None
        if not os.path.exists(srt_path):
            print(f"ОШИБКА: srt_path {srt_path} не найден!")
            return None

        video_clip_obj = mp.VideoFileClip(video_path)
        original_width, original_height = video_clip_obj.size

        # Рассчитываем высоту плашки
        subtitle_bar_height_calculated = int(original_height * (subtitle_bar_height_percent / 100.0))
        min_bar_height = max(50, int(original_height * 0.10))
        subtitle_bar_height = max(subtitle_bar_height_calculated, min_bar_height)
        subtitle_bar_height = min(subtitle_bar_height, int(original_height * 0.25))

        if subtitle_bar_height % 2 != 0:
            subtitle_bar_height += 1

        print(f"Оригинальная высота: {original_height}, Высота плашки субтитров (выровнена по 2): {subtitle_bar_height}")
        new_height = original_height + subtitle_bar_height

        white_bar_clip_obj = mp.ColorClip(
            size=(original_width, subtitle_bar_height),
            color=(255, 255, 255),
            is_mask=False,
            duration=video_clip_obj.duration
        )
        positioned_white_bar = white_bar_clip_obj.with_position((0, original_height))

        final_clip_with_bar_obj = mp.CompositeVideoClip(
            [video_clip_obj, positioned_white_bar],
            size=(original_width, new_height)
        )

        def generator(txt):
            text_image_width = original_width
            text_image_height = subtitle_bar_height

            # Задаём исходный размер шрифта, а потом он будет уменьшаться, если нужно
            target_font_size = max(12, int(subtitle_bar_height * 0.30))
            if subtitle_bar_height < 70:
                target_font_size = max(10, int(subtitle_bar_height * 0.40))

            print(f"Рендеринг субтитра: '{txt[:30]}...' с начальным font_size={target_font_size}")
            font_for_pillow = 'arial.ttf'
            img_array = render_text_with_pillow(
                txt, text_image_width, text_image_height,
                font_path_or_name=font_for_pillow,
                font_size=target_font_size,
                text_color=(0, 0, 0, 255),
                bg_color=(255, 255, 255, 0),
                line_spacing_pt=int(target_font_size * 0.25),
                padding_horizontal_ratio=0.03,
                padding_vertical_ratio=0.1,
                align_text="center"
            )
            return mp.ImageClip(img_array, is_mask=False, transparent=True)

        # SRT
        try:
            with open(srt_path, 'r', encoding='utf-8') as srt_file_reader:
                srt_content_as_string = srt_file_reader.read()
        except Exception as e:
            print(f"Ошибка чтения SRT файла: {e}")
            return None

        if not srt_content_as_string.strip():
            print("ОШИБКА: SRT файл пуст.")
            return None

        parsed_subtitles = parse_srt_content(srt_content_as_string)
        if not parsed_subtitles:
            print("ОШИБКА: Не удалось извлечь субтитры из SRT.")
            return None

        subtitles_clip_obj = SubtitlesClip(
            subtitles=parsed_subtitles,
            make_textclip=generator,
            font="Arial"
        )

        sub_x_position = 0
        sub_y_position = original_height

        positioned_subtitles = subtitles_clip_obj.with_position((sub_x_position, sub_y_position))

        # Финальный клип
        final_video_obj = mp.CompositeVideoClip(
            [final_clip_with_bar_obj, positioned_subtitles],
            size=(original_width, new_height)
        ).with_audio(video_clip_obj.audio)

        print(f"Начало записи видео в: {output_path}")

        ffmpeg_additional_params = [
            '-pix_fmt', 'yuv420p',
            '-movflags', 'faststart'
        ]

        final_video_obj.write_videofile(
            output_path,
            codec="libx264",
            audio=True,
            audio_codec="aac",
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            preset="medium",
            threads=os.cpu_count() or 1,
            ffmpeg_params=ffmpeg_additional_params,
            logger='bar'
        )

        print(f"Видео с субтитрами успешно создано: {output_path}")
        return output_path

    except Exception as e:
        print(f"Ошибка при добавлении субтитров на видео: {e}")
        traceback.print_exc()
        return None

    finally:
        if video_clip_obj:
            video_clip_obj.close()
        if white_bar_clip_obj:
            white_bar_clip_obj.close()
        if final_clip_with_bar_obj:
            final_clip_with_bar_obj.close()
        if subtitles_clip_obj and hasattr(subtitles_clip_obj, 'close') and callable(subtitles_clip_obj.close):
            subtitles_clip_obj.close()
        if final_video_obj:
            final_video_obj.close()

# Основной рабочий процесс для загрузки видеофайла, извлечения аудио, генерации субтитров и финального видеофайла с субтитрами.
def process_video_with_subtitles(input_video_file_obj, filename_prefix="processed_"):
    temp_dir = "temp_files"; output_dir = "output_videos"
    os.makedirs(temp_dir, exist_ok=True); os.makedirs(output_dir, exist_ok=True)
    base_name, _ = os.path.splitext(input_video_file_obj.name)
    file_identity_tuple = (input_video_file_obj.name, input_video_file_obj.size)
    hash_str = str(hash(file_identity_tuple)).replace('-', 'N')[:8]
    unique_suffix = str(os.getpid()) + "_" + hash_str

    temp_video_filename = f"{filename_prefix}{base_name}_{unique_suffix}.mp4"
    temp_video_path = os.path.join(temp_dir, temp_video_filename)
    file_bytes = input_video_file_obj.read()
    with open(temp_video_path, "wb") as f:
        f.write(file_bytes)

    temp_audio_path = os.path.splitext(temp_video_path)[0] + "_extracted_audio.wav"
    try:
        with mp.VideoFileClip(temp_video_path) as video_clip_for_audio:
            video_clip_for_audio.audio.write_audiofile(temp_audio_path, codec='pcm_s16le')
        print(f"Аудио извлечено: {temp_audio_path}")
        if not os.path.exists(temp_audio_path):
            print(f"КРИТИЧЕСКАЯ ОШИБКА: Аудиофайл {temp_audio_path} не найден!")
            return None, f"Аудиофайл {temp_audio_path} не найден!", None
    except Exception as e:
        print(f"Ошибка при извлечении аудио: {e}")
        traceback.print_exc()
        return None, f"Ошибка извлечения аудио: {e}", None

    srt_file_path, full_transcription = generate_srt_from_audio_whisper(temp_audio_path)
    if not srt_file_path or full_transcription is None:
        error_msg_srt = "Ошибка генерации субтитров"
        if full_transcription is None and srt_file_path:
            error_msg_srt += " или пустая транскрипция."
        return None, error_msg_srt, None

    final_video_output_filename = f"{filename_prefix}{base_name}_{unique_suffix}_with_subs.mp4"
    final_video_output_path = os.path.join(output_dir, final_video_output_filename)
    if os.path.exists(final_video_output_path):
        try:
            os.remove(final_video_output_path)
        except Exception as e_rem:
            print(f"Не удалось удалить старый файл {final_video_output_path}: {e_rem}")

    processed_video_with_subs_path = add_subtitles_to_video(
        os.path.abspath(temp_video_path),
        srt_file_path,
        os.path.abspath(final_video_output_path)
    )


    if not processed_video_with_subs_path:
        return None, full_transcription, "Ошибка встраивания субтитров в видео."
    return processed_video_with_subs_path, full_transcription, None
