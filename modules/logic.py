def get_menu(callback):
    return [
        ("Если активна программа", lambda: callback("if_active", "")),
        ("Если запущена программа", lambda: callback("if_proc", "")),
        ("Если открыт веб-сайт", lambda: callback("if_site", "")),
        ("Если значение переменной", lambda: callback("if_var", "имя_переменной=значение")),
        ("Блок случайного действия", lambda: callback("random_block", "")),
        ("Цикл (Количество раз)", lambda: callback("loop", "5")),
        ("Цикл Пока (Условие)", lambda: callback("loop_while", "имя_переменной=значение")),
        ("Прервать цикл", lambda: callback("break", "")),
        ("Иначе", lambda: callback("else", "")),
        ("Конец блока", lambda: callback("end", ""))
    ]