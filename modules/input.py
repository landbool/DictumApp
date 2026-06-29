def get_menu(callback):
    return [
        ("Клавиатура (Нажать/Зажать/Длинное)", lambda: callback("key", "")),
        ("Управление мышиными действиями", lambda: callback("mouse_action", "")),
        ("Прокрутить колесо мыши", lambda: callback("mouse_scroll", "")),
        ("Напечатать текст", lambda: callback("type", ""))
    ]