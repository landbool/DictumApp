def get_menu(callback):
    return [
        ("Подождать (в секундах)", lambda: callback("wait", "1")),
        ("Задать значение переменной", lambda: callback("set_var", "имя_переменной=значение")),
        ("Уведомить (Всплывающее окно)", lambda: callback("notify", "Заголовок|Текст сообщения")),
        ("Запланировать событие (через Х сек)", lambda: callback("schedule", "5|голосовая_команда"))
    ]