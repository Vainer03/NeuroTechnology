import streamlit as st
import os
from video_processing import process_video_with_subtitles # Импортируем нашу функцию

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(
    page_title="Анализ и Рекомендации",
    page_icon="🎬",
    layout="wide"
)

# --- Инициализация Session State ---
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False
if 'transcription_result' not in st.session_state:
    st.session_state.transcription_result = ""
if 'processed_file_name' not in st.session_state:
    st.session_state.processed_file_name = None
if 'output_video_path' not in st.session_state:
    st.session_state.output_video_path = None
if 'processing_error' not in st.session_state:
    st.session_state.processing_error = None
if 'uploader_key' not in st.session_state: # Для сброса file_uploader
    st.session_state.uploader_key = 0

# --- БОКОВАЯ ПАНЕЛЬ ДЛЯ НАВИГАЦИИ ---
st.sidebar.title("Навигация")
app_mode = st.sidebar.selectbox(
    "Выберите раздел:",
    ["Обработка видео", "Рекомендации по разработке"]
)

# --- ФУНКЦИЯ ДЛЯ СБРОСА СОСТОЯНИЯ ОБРАБОТКИ ---
def reset_processing_state():
    st.session_state.processing_done = False
    st.session_state.transcription_result = ""
    st.session_state.processed_file_name = None
    st.session_state.output_video_path = None
    st.session_state.processing_error = None

# --- ОСНОВНОЙ КОНТЕНТ В ЗАВИСИМОСТИ ОТ ВЫБОРА ---
if app_mode == "Обработка видео":
    st.title("Обработка видео с субтитрами")
    st.write("Загрузите видеофайл для генерации и встраивания субтитров.")

    uploaded_file_obj = st.file_uploader(
        "Выберите видеофайл (mp4, mov, avi, mkv)",
        type=["mp4", "mov", "avi", "mkv"],
        key=f"file_uploader_{st.session_state.uploader_key}"
    )

    if uploaded_file_obj is not None and uploaded_file_obj.name != st.session_state.get('uploaded_file_obj_name_cache', None):
        print(f"Загружен новый файл: {uploaded_file_obj.name}. Сброс состояния.")
        reset_processing_state()
        st.session_state.uploaded_file_obj_name_cache = uploaded_file_obj.name # Кэшируем имя для сравнения

    if uploaded_file_obj is not None:
        col_video_display, col_controls = st.columns(2)

        with col_video_display:
            st.subheader("Просмотр видео")
            current_video_to_display = None
            caption_text = ""

            if st.session_state.output_video_path and os.path.exists(st.session_state.output_video_path) and st.session_state.processed_file_name == uploaded_file_obj.name:
                current_video_to_display = st.session_state.output_video_path
                caption_text = "Видео с обработанными субтитрами"
            else:
                current_video_to_display = uploaded_file_obj
                caption_text = "Оригинальное видео"
            
            if current_video_to_display:
                try:
                    st.video(current_video_to_display)
                    st.caption(caption_text)
                except Exception as e_video_display:
                    st.error(f"Не удалось отобразить видео: {e_video_display}")
            
            st.write(f"Загружен файл: {uploaded_file_obj.name}")

        with col_controls:
            st.subheader("Управление и Результаты")

            show_process_button = True
            if st.session_state.processing_done and st.session_state.processed_file_name == uploaded_file_obj.name:
                show_process_button = False # Уже обработано

            if show_process_button:
                if st.button("Обработать и добавить субтитры", key="process_button"):
                    with st.spinner("Идет обработка видео... Это может занять некоторое время."):
                        reset_processing_state() # Сбрасываем перед новой обработкой этого файла
                        st.session_state.uploaded_file_obj_name_cache = uploaded_file_obj.name # Обновляем кэш

                        output_path, transcription, error_message = process_video_with_subtitles(
                            uploaded_file_obj,
                            filename_prefix=f"{os.path.splitext(uploaded_file_obj.name)[0]}_"
                        )

                        if error_message:
                            st.session_state.processing_error = error_message
                        elif output_path and transcription is not None: # Проверяем и transcription
                            st.session_state.output_video_path = output_path
                            st.session_state.transcription_result = transcription
                            st.session_state.processing_done = True
                            st.session_state.processed_file_name = uploaded_file_obj.name
                        else:
                            st.session_state.processing_error = "Произошла неизвестная ошибка или пустая транскрипция."
                        
                        st.rerun()

            if st.session_state.processing_error:
                st.error(f"Ошибка обработки: {st.session_state.processing_error}")

            if st.session_state.processing_done and st.session_state.processed_file_name == uploaded_file_obj.name:
                st.success("Обработка завершена!")
                st.subheader("Транскрипция:")
                st.text_area("", st.session_state.transcription_result, height=200, key="transcription_output")
            
            if st.button("Загрузить другое видео", key="upload_another_button"):
                reset_processing_state()
                st.session_state.uploader_key += 1
                # Очистка кэша имени файла, чтобы при следующей загрузке того же файла он считался "новым" для обработки
                if 'uploaded_file_obj_name_cache' in st.session_state:
                    del st.session_state['uploaded_file_obj_name_cache']
                st.rerun()

    else: 
        if st.session_state.processed_file_name or st.session_state.output_video_path:
            reset_processing_state()
        st.button("Обработать и добавить субтитры", key="process_button_disabled", disabled=True)
        st.info("Пожалуйста, загрузите видеофайл для обработки.")

elif app_mode == "Рекомендации по разработке":
    st.title("Рекомендации по разработке доступных материалов")
    st.header("Для слабослышащих:")
    st.markdown("""
    - **Субтитры:** Всегда предоставляйте точные, синхронизированные субтитры для всего аудиоконтента.
        - Убедитесь, что субтитры легко читаемы (хороший контраст, подходящий размер шрифта).
        - Включайте в субтитры не только речь, но и важные звуковые эффекты (например, "[смех]", "[музыка]", "[звонок телефона]").
    - **Визуальная поддержка:**
        - Если лектор в кадре, убедитесь, что его лицо и артикуляция хорошо видны.
        - Используйте визуальные подсказки, диаграммы, иллюстрации для дублирования или дополнения аудиоинформации.
    - **Качество звука:** Обеспечьте чистый, разборчивый звук без фоновых шумов.
    - **Транскрипты:** Предоставляйте полные текстовые транскрипты видеоматериалов как отдельный документ.
    - **Язык жестов:** Если целевая аудитория использует язык жестов, рассмотрите возможность включения сурдопереводчика в кадр или как отдельную видеодорожку.
    """)
    st.header("Для слабовидящих:")
    st.markdown("""
    - **Аудиодескрипция (тифлокомментирование):** Описывайте голосом важные визуальные элементы, которые не передаются через основной звук (действия, графика, смена сцен, текст на экране, который не зачитывается).
    - **Контрастность:** Обеспечьте высокую контрастность между текстом и фоном, а также между важными графическими элементами. Избегайте использования только цвета для передачи информации.
    - **Размер шрифта и шрифты:** Используйте читаемые шрифты без засечек (sans-serif) достаточного размера. Предоставьте возможность увеличения текста, если это веб-интерфейс.
    - **Структура контента:**
        - Логическая структура заголовков и текста важна для навигации с помощью скринридеров.
        - Описывайте изображения с помощью атрибутов `alt` (в HTML) или в тексте рядом.
    - **Избегайте мигающего контента:** Мигание может вызывать приступы у людей с фоточувствительной эпилепсией и быть просто отвлекающим.
    - **Управление с клавиатуры:** Все интерактивные элементы должны быть доступны и управляемы с клавиатуры.
    - **Четкость изображений:** Используйте изображения высокого разрешения.
    """)