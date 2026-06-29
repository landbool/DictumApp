def get_menu(callback):
    return [
        ("Открыть (Программа/Файл/Сайт)", lambda: callback("open", "")),
        ("Закрыть программу", lambda: callback("kill", "")),
        ("Системная команда (Win+R)", lambda: callback("run_system", "")),
        ("Показать окно", lambda: callback("show_window", "")),
        ("Настройка звука / Устройств", lambda: callback("sound_control", "")),
        (".bat скрипт", lambda: callback("run_bat", "")),
        ("Сказать (Светлана Premium)", lambda: callback("say", "")),
        ("Произнести Звук/Аудио", lambda: callback("play_sound", "")),
        ("Выполнить голосовую команду", lambda: callback("run_command", ""))
    ]