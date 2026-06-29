def get_menu(callback):
    return [
        ("Открыть ссылку в браузере", lambda: callback("open_url", "https://ya.ru")),
        ("Загрузить текст со страницы (GET API)", lambda: callback("web_get_text", "vrn | wttr.in/Voronezh?format=3")),
        ("Отправить данные на сайт (POST API)", lambda: callback("web_post_text", "имя_переменной|https://api.site.com/send|параметр=значение")),
        ("Отправить скриншот в TG", lambda: callback("tg_send_screenshot", "true"))
    ]