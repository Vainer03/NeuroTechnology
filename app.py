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

    # --- МЕРЫ ДЛЯ СЛАБОСЛЫШАЩИХ ---
    st.header("Меры для людей с нарушениями слуха")

    st.subheader("Обеспечение понимания аудиоконтента:")
    st.markdown("""
    - **Полные и точные субтитры:**
        - Весь речевой контент должен сопровождаться синхронизированными субтитрами.
        - **Читаемость субтитров:** Обеспечьте хороший контраст между текстом субтитров и фоном, используйте достаточный размер шрифта.
        - **Описание неречевых звуков:** Включайте в субтитры важные звуковые события, влияющие на понимание (например, `[музыка]`, `[смех]`, `[аплодисменты]`, `[звонок телефона]`).
    - **Текстовые транскрипты:** Предоставляйте полные текстовые версии всего аудиосодержания как отдельный документ. Это полезно для поиска информации и для тех, кому удобнее читать сплошной текст.
    - **Качество звука:** Записывайте аудио в высоком качестве, без фоновых шумов, с четкой и разборчивой речью диктора.
    """)

    st.subheader("Визуальная поддержка и компенсация:")
    st.markdown("""
    - **Визуализация лектора (если применимо):**
        - Если в кадре присутствует лектор или сурдопереводчик, убедитесь, что их лицо, мимика и артикуляция (или жесты) хорошо видны и освещены.
    - **Достаточность визуальной информации на слайдах:**
        - _Отзыв респондента: "Объем визуальной информации на слайдах был недостаточен для полноценного восприятия презентации."_
        - **Рекомендация:** Ключевая информация, озвучиваемая голосом, должна находить отражение на слайдах в виде текста, схем, изображений. Избегайте слайдов, содержащих только заголовок или одно изображение, если при этом озвучивается большой объем важной информации.
    - **Динамическая фокусировка внимания:**
        - _Отзыв респондента: "Динамический визуал стимулирует внимание, способствует восприятию."_
        - **Рекомендация:** Акцентируйте внимание на элементах презентации или видео, о которых идет речь в данный момент. Используйте подсветку, обводку, анимацию появления, изменение размера или другие визуальные приемы для выделения активного элемента.
    - **Визуальные аналоги аудиоинформации:** Используйте диаграммы, инфографику, иллюстрации для дублирования или дополнения информации, передаваемой через аудиоканал.
    """)

    st.subheader("Дополнительные возможности:")
    st.markdown("""
    - **Сурдоперевод:** Для аудитории, использующей язык жестов, рассмотрите возможность включения сурдопереводчика в кадр или предоставления отдельной видеодорожки с переводом.
    - **Разделение аудиодорожек (идеальный вариант):**
        - _Предложение:_ "В идеале — разделять дорожки на этапе подготовки видеоряда и давать возможность выключать их по выбору, позволяя сфокусироваться только на интересующей."
        - **Рекомендация:** Если технически возможно, предоставление отдельных аудиодорожек (например, основная речь, музыкальное сопровождение, аудиодескрипция) позволит пользователю настроить их громкость или отключить ненужные.
    """)

    # --- МЕРЫ ДЛЯ СЛАБОВИДЯЩИХ ---
    st.header("Меры для людей с нарушениями зрения")

    st.subheader("Обеспечение доступности визуального контента:")
    st.markdown("""
    - **Аудиодескрипция (тифлокомментирование):**
        - Описывайте голосом все важные визуальные элементы, которые не передаются через основной звук или текст на экране. Это включает действия, графику, смену сцен, эмоции персонажей (если это важно), ключевую информацию на слайдах, которая не зачитывается.
    - **Читаемость текста:**
        - _Отзыв респондента: "Текст часто был не читаем или требовал усилий."_
        - **Размер шрифта:** Используйте достаточно крупный шрифт. Избегайте мелкого текста, особенно для ключевой информации.
        - **Контрастность текста:**
            - **Рекомендация:** Обеспечьте высокую контрастность между текстом и фоном. Согласно WCAG, соотношение контрастности должно быть:
                - не менее **4.5:1** для обычного текста (до 18pt или 14pt жирный). - не менее **3:1** для крупного текста (18pt и более, или 14pt жирный и более).
            - _Ваше предложение (можно оставить как более строгий вариант): "Текст презентации должен быть контрастным, с соотношением яркостей не менее 7:1 для средних шрифтов (14-24) и 4,5:1 для более крупных шрифтов."_
        - **Шрифты без засечек (Sans-serif):** Используйте простые, читаемые шрифты без засечек (например, Arial, Verdana, Helvetica, Open Sans).
    - **Цветовая контрастность нетекстовых элементов:** Важные графические элементы (иконки, элементы диаграмм) также должны иметь достаточную контрастность с фоном (минимум 3:1). Не используйте только цвет для передачи информации.
    """)

    st.subheader("Структура и навигация:")
    st.markdown("""
    - **Логическая структура контента:**
        - Используйте правильную иерархию заголовков (H1, H2, H3 и т.д.) для структурирования информации. Это критически важно для навигации с помощью скринридеров.
    - **Описание изображений:**
        - Все информативные изображения должны иметь текстовое описание (атрибут `alt` в HTML или описание в окружающем тексте). Декоративные изображения могут иметь пустой `alt`.
    - **Доступность с клавиатуры:** Все интерактивные элементы (кнопки, ссылки, элементы управления плеером) должны быть доступны и управляемы с помощью клавиатуры. Порядок фокуса должен быть логичным.
    """)
    
    st.subheader("Динамика и интерактивность (с учетом доступности):")
    st.markdown("""
    - **Динамическое выделение и увеличение элементов:**
        - _Отзыв респондента: "Динамика стимулирует внимание, способствует восприятию."_
        - _Ваше предложение:_ "Увеличивать элементы презентации, о которых в данный момент идет речь."
        - **Рекомендация:** При обсуждении конкретного элемента на слайде, его можно визуально выделить (например, кратковременно увеличить, подсветить, добавить рамку). Это полезно не только для людей с нарушениями зрения, но и для всех пользователей. Убедитесь, что такое выделение сопровождается аудиодескрипцией, если оно не очевидно из контекста.
    - **Избегайте мигающего контента:** Контент, мигающий чаще 3 раз в секунду, может вызывать приступы у людей с фоточувствительной эпилепсией.
    """)

    st.subheader("Дополнительные возможности (идеальный вариант):")
    st.markdown("""
    - **Кликабельные элементы с озвучиванием:**
        - _Ваше предложение:_ "В идеале — все элементы презентации должны быть кликабельными, с озвучиванием их текста или описания."
        - **Рекомендация:** Для интерактивных презентаций или материалов, где это уместно, предоставление возможности кликнуть на элемент для получения его детального описания или озвучивания может значительно улучшить доступность.
    - **Адаптивный интерфейс:** Если материал отображается в веб-интерфейсе, предусмотрите возможность для пользователя самостоятельно изменять размер шрифта, контрастность и другие параметры отображения.
    """)

