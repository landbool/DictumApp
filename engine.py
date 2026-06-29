import os, time, subprocess, pyautogui, pygetwindow as gw, psutil, webbrowser, winreg, random, threading, requests, json, re
import asyncio
import edge_tts
from pygame import mixer
import keyboard
import ctypes    # Наш прямой мост в контроллер ввода Windows
import cv2       # Напрямую задействуем ядро компьютерного зрения
import numpy as np # Для байтового кодирования путей OneDrive и кириллицы
from PIL import Image, ImageGrab # Захват панорамы всех мониторов

pyautogui.FAILSAFE = False

try: mixer.init()
except Exception as e: print(f"Предупреждение инициализации звука: {e}")

# Глобальное хранилище переменных макросов Dictum
DICTUM_VARIABLES = {}
ACTIVE_KEY_PRESSERS = {}

# 🔥 ДОБАВЛЕНО: Потоковый замок для безопасного доступа к переменным из параллельных макросов
variables_lock = threading.Lock()

# 🔥 АППАРАТНАЯ КАРТА ВИРТУАЛЬНЫХ КОДОВ (VK_CODES) ДЛЯ ИГНОРИРОВАНИЯ РАСКЛАДКИ WINDOWS
VK_MAP = {
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46, 'g': 0x47, 'h': 0x48,
    'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50,
    'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
    'y': 0x59, 'z': 0x5A, 
    'ctrl': 0x11, 'control': 0x11, 
    'alt': 0x12, 
    'shift': 0x10, 
    'win': 0x5B, 'windows': 0x5B,
    'delete': 0x2E, 'backspace': 0x08, 'enter': 0x0D, 'space': 0x20, 'tab': 0x09
}

# Системные константы Windows для переключения языковых слоев
WM_INPUTLANGCHANGEREQUEST = 0x0050
HWND_BROADCAST = 0xFFFF

def _force_english_layout():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.PostMessageA(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, 0x04090409)
    except: pass

def _check_and_download_nircmd():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    nircmd_exe = os.path.join(current_dir, "nircmd.exe")
    if not os.path.exists(nircmd_exe):
        try:
            import zipfile
            url = "https://www.nirsoft.net/utils/nircmd-x64.zip"
            r = requests.get(url, timeout=10)
            zip_path = os.path.join(current_dir, "nircmd.zip")
            with open(zip_path, "wb") as f: f.write(r.content)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extract("nircmd.exe", current_dir)
            if os.path.exists(zip_path): os.remove(zip_path)
        except Exception as e: print(f"Не удалось подгрузить NirCmd: {e}")
    return nircmd_exe

def _say_edge_premium(target_input):
    try:
        file_path = str(target_input).strip()
        if file_path.startswith("{") and file_path.endswith("}"):
            try:
                data = json.loads(file_path)
                if "path" in data and data["path"]: file_path = data["path"].strip()
            except: pass
        if os.path.exists(file_path) and file_path.lower().endswith('.mp3'):
            sound = mixer.Sound(file_path); duration = sound.get_length(); sound.play()
            time.sleep(duration - 0.5 if duration > 0.6 else duration)
    except Exception as e: print(f"Ошибка Say: {e}")

def _play_audio_file(file_path):
    try:
        file_path = str(file_path).strip()
        if os.path.exists(file_path):
            sound = mixer.Sound(file_path); sound.play(); time.sleep(sound.get_length())
    except Exception as e: print(f"Ошибка воспроизведения файла: {e}")

def _send_hardware_down(key_str):
    try:
        vk_code = VK_MAP.get(key_str.strip().lower())
        if vk_code: ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        else: keyboard.press(key_str.strip().lower())
    except Exception as e: print(f"Ошибка аппаратного зажатия {key_str}: {e}")

def _send_hardware_up(key_str):
    try:
        vk_code = VK_MAP.get(key_str.strip().lower())
        if vk_code: ctypes.windll.user32.keybd_event(vk_code, 0, 0x0002, 0)
        else: keyboard.release(key_str.strip().lower())
    except Exception as e: print(f"Ошибка аппаратного отпускания {key_str}: {e}")

def _spammer_thread(key_str):
    while ACTIVE_KEY_PRESSERS.get(key_str, False):
        _send_hardware_down(key_str)
        time.sleep(0.01)
        _send_hardware_up(key_str)
        time.sleep(0.03)


class DictumEngine:
    main_gui_ref = None 
    last_tg_chat_id = "560492813"

    @staticmethod
    def _load_saved_tg_chat_id():
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            log_path = os.path.join(current_dir, "dictum_tg_session.json")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("last_chat_id", DictumEngine.last_tg_chat_id)
        except: pass
        return DictumEngine.last_tg_chat_id

    @staticmethod
    def find_shortcut(name):
        clean_name = name.replace(".exe", "").replace(".EXE", "")
        reg_paths = [f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{name}", f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{clean_name}.exe"]
        for base in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for rel in reg_paths:
                try:
                    with winreg.OpenKey(base, rel) as key: return winreg.QueryValue(key, None)
                except: continue
        return None

    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ИНТЕРПРЕТАТОРА ПЕРЕМЕННЫХ И УСЛОВИЙ ---
    @staticmethod
    def _substitute_vars(text):
        if not text: return ""
        result = str(text)
        matches = re.findall(r'\{([A-Za-z0-9_А-Яа-яёЁ]+)\}', result)
        
        # 🔥 ФИКС: Защищаем пакетное чтение из словаря переменной
        with variables_lock:
            for var_name in matches:
                actual_val = DICTUM_VARIABLES.get(var_name, "")
                result = result.replace(f"{{{var_name}}}", str(actual_val))
        return result

    @staticmethod
    def _check_if_active(val):
        val = DictumEngine._substitute_vars(val).lower().strip()
        try:
            # 1. Проверяем заголовок активного окна на переднем плане
            active_win = gw.getActiveWindow()
            if active_win and val in active_win.title.lower():
                return True
            # 2. Проверяем имя исполняемого файла процесса активного окна
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value > 0:
                proc = psutil.Process(pid.value)
                if val in proc.name().lower():
                    return True
        except: pass
        return False

    @staticmethod
    def _check_if_proc(val):
        val = DictumEngine._substitute_vars(val).lower().strip()
        try:
            for proc in psutil.process_iter(['name']):
                if val in proc.info['name'].lower():
                    return True
        except Exception as proc_err: 
            print(f"[Dictum Engine] Ошибка сканирования процессов: {proc_err}")
        return False

    @staticmethod
    def _check_if_site(val):
        val = DictumEngine._substitute_vars(val).lower().strip()
        try:
            active_win = gw.getActiveWindow()
            if active_win and val in active_win.title.lower():
                return True
        except: pass
        return False

    @staticmethod
    def _check_if_var(val):
        val = DictumEngine._substitute_vars(val)
        operators = ["==", "!=", ">=", "<=", ">", "<", "="]
        for op in operators:
            if op in val:
                left, right = [x.strip() for x in val.split(op, 1)]
                
                # 🔥 ФИКС: Безопасное извлечение значения под замком
                with variables_lock:
                    left_val = str(DICTUM_VARIABLES.get(left, left)).strip().lower()
                    
                right_val = right.strip().lower()
                
                try:
                    l_num = float(left_val)
                    r_num = float(right_val)
                    if op in ["==", "="]: return l_num == r_num
                    elif op == "!=": return l_num != r_num
                    elif op == ">=": return l_num >= r_num
                    elif op == "<=": return l_num <= r_num
                    elif op == ">": return l_num > r_num
                    elif op == "<": return l_num < r_num
                except:
                    if op in ["==", "="]: return left_val == right_val
                    elif op == "!=": return left_val != right_val
                    else: return False
        return False

    # --- КРАСИВЫЙ СТЕКЛЯННЫЙ ТОСТ С ПЛАВНОЙ АНИМАЦИЕЙ ---
    @staticmethod
    def _show_custom_toast(title, message):
        if not DictumEngine.main_gui_ref: 
            print(f"[Dictum Notification] {title}: {message}")
            return
            
        def _create_toast_gui(t, m):
            import customtkinter as ctk
            try:
                toast = ctk.CTkToplevel(DictumEngine.main_gui_ref)
                toast.withdraw()  # Временно скрываем для предотвращения рывков позиционирования
                toast.overrideredirect(True)
                toast.attributes("-topmost", True)
                toast.configure(fg_color="#14161D")
                toast.attributes("-alpha", 0.0)  # Стартуем с нулевой видимости для анимации
                
                # Слегка увеличим высоту (с 95 до 105), чтобы крупный заголовок не зажимал текст
                tw, th = 340, 105
                screen_width = toast.winfo_screenwidth()
                screen_height = toast.winfo_screenheight()
                
                x_pos = screen_width - tw - 25
                y_pos = screen_height - th - 65
                toast.geometry(f"{tw}x{th}+{x_pos}+{y_pos}")
                
                border_frame = ctk.CTkFrame(toast, fg_color="transparent", border_width=1, border_color="#007AFF", corner_radius=12)
                border_frame.pack(fill="both", expand=True, padx=2, pady=2)
                
                # 🔥 ИСПРАВЛЕНИЕ: Молния удалена, шрифт увеличен до 14pt для солидности
                lbl_title = ctk.CTkLabel(border_frame, text=t.upper(), font=("Segoe UI Bold", 14), text_color="#007AFF")
                lbl_title.pack(anchor="w", padx=15, pady=(12, 2))
                
                lbl_msg = ctk.CTkLabel(border_frame, text=m, font=("Segoe UI Semibold", 12), text_color="#E5E7EB", justify="left", wraplength=310)
                lbl_msg.pack(anchor="w", padx=15, pady=(0, 12))
                
                toast.deiconify()  # Прогружаем окно в менеджер окон ОС

                # 🔥 ДОБАВЛЕНИЕ ЗВУКА: Воспроизводим аудиофайл прямо в момент появления тоста
                try:
                    # Корректно определяем путь к папке sounds относительно текущего файла
                    engine_dir = os.path.dirname(os.path.abspath(__file__))
                    sound_path = os.path.join(engine_dir, "sounds", "notification.mp3")
                    
                    if os.path.exists(sound_path):
                        sound = mixer.Sound(sound_path)
                        sound.play()  # Запускается в фоновом потоке pygame, UI не фризит!
                except Exception as sound_err:
                    print(f"Предупреждение: не удалось сыграть звук тоста: {sound_err}")
                
                # 🔥 АНИМАЦИЯ ПЛАВНОГО ПОЯВЛЕНИЯ И ЗАТУХАНИЯ (60 FPS)
                def fade_in(current_alpha=0.0):
                    if not toast.winfo_exists(): return
                    if current_alpha < 1.0:
                        current_alpha += 0.08  # Шаг появления
                        toast.attributes("-alpha", min(current_alpha, 1.0))
                        toast.after(16, lambda: fade_in(current_alpha))
                    else:
                        # Как только уведомление полностью проявилось, держим его 3.5 секунды
                        toast.after(3500, lambda: fade_out(1.0))
                        
                def fade_out(current_alpha=1.0):
                    if not toast.winfo_exists(): return
                    if current_alpha > 0.0:
                        current_alpha -= 0.08  # Шаг исчезновения
                        toast.attributes("-alpha", max(current_alpha, 0.0))
                        toast.after(16, lambda: fade_out(current_alpha))
                    else:
                        toast.destroy()  # Полное уничтожение виджета после затухания
                        
                fade_in()  # Инициализация цепочки анимации
                
            except Exception as e:
                print(f"Ошибка отрисовки тоста: {e}")

        DictumEngine.main_gui_ref.after(0, lambda: _create_toast_gui(title, message))


    # --- ГЛАВНОЕ ЯДРО ИНТЕРПРЕТАТОРА СЦЕНАРИЕВ ---
    @staticmethod
    def execute(script_str):
        lines = []
        for l in script_str.split('\n'):
            l = l.strip()
            if l and ':' in l:
                cmd, val = [x.strip() for x in l.split(':', 1)]
                lines.append((cmd, val))
                
        if not lines: return

        # Шаг 1: 🔥 Строим ультимативную таблицу переходов (Jump Table) для условий и циклов
        jumps = {}
        block_stack = []
        
        for idx, (cmd, val) in enumerate(lines):
            if cmd in ["if_active", "if_proc", "if_site", "if_var", "loop", "loop_while", "random_block"]:
                block_stack.append((cmd, idx))
            elif cmd == "else":
                if block_stack:
                    parent_cmd, parent_idx = block_stack.pop()
                    jumps[parent_idx] = idx + 1 # Если If ложен — прыгаем на строчку ПОСЛЕ else
                    block_stack.append(("else", idx))
            elif cmd == "end":
                if block_stack:
                    parent_cmd, parent_idx = block_stack.pop()
                    if parent_cmd in ["loop", "loop_while"]:
                        jumps[idx] = parent_idx # Конец цикла возвращает указатель в его начало
                        jumps[parent_idx] = idx + 1 # Начало цикла прыгает за пределы end при выходе
                    else:
                        jumps[parent_idx] = idx + 1 # Конец ветки условий

        # 🔥 СВЕРХНАДЕЖНЫЙ ФИКС: Если пользователь забыл поставить КОНЕЦ БЛОКА (end), 
        # авто-закрываем блоки концом самого скрипта! Теперь Discord.exe не будет срабатывать ложно!
        while block_stack:
            parent_cmd, parent_idx = block_stack.pop()
            jumps[parent_idx] = len(lines)

        # Хранилище счетчиков запущенных циклов
        loop_counters = {}
        ptr = 0
        
        # Шаг 2: Потоковый запуск интерпретатора
        while ptr < len(lines):
            cmd, val = lines[ptr]
            
            # --- УПРАВЛЯЮЩИЕ КОМАНДЫ ДВИЖКА ---
            if cmd == "loop":
                if ptr not in loop_counters:
                    try: loop_counters[ptr] = int(DictumEngine._substitute_vars(val))
                    except: loop_counters[ptr] = 0
                    
                if loop_counters[ptr] <= 0:
                    ptr = jumps.get(ptr, ptr + 1) # Выходим из цикла
                    if ptr in loop_counters: del loop_counters[ptr]
                    continue
                else:
                    loop_counters[ptr] -= 1
                    ptr += 1
                    continue
                    
            elif cmd == "loop_while":
                cond_met = DictumEngine._check_if_var(val)
                if not cond_met:
                    ptr = jumps.get(ptr, ptr + 1) # Выходим из цикла
                else:
                    ptr += 1
                continue
                
            elif cmd.startswith("if_"):
                cond_met = False
                if cmd == "if_active": cond_met = DictumEngine._check_if_active(val)
                elif cmd == "if_proc": cond_met = DictumEngine._check_if_proc(val)
                elif cmd == "if_site": cond_met = DictumEngine._check_if_site(val)
                elif cmd == "if_var":  cond_met = DictumEngine._check_if_var(val)
                
                if not cond_met:
                    ptr = jumps.get(ptr, ptr + 1) # Перепрыгиваем блок на else или end
                else:
                    ptr += 1
                continue
                
            elif cmd == "else":
                ptr = jumps.get(ptr, ptr + 1)
                continue
                
            elif cmd == "end":
                ptr = jumps.get(ptr, ptr + 1) if ptr in jumps else ptr + 1
                continue
                
            elif cmd == "break":
                target = None
                for loop_idx in list(jumps.keys()):
                    if lines[loop_idx][0] in ["loop", "loop_while"] and jumps[loop_idx] > ptr:
                        target = jumps[loop_idx]
                        if loop_idx in loop_counters: del loop_counters[loop_idx]
                        break
                ptr = target if target is not None else ptr + 1
                continue

            # --- ИСПОЛНИТЕЛЬНЫЕ КОМАНДЫ ДВИЖКА ---
            try:
                if cmd == "open":
                    val = DictumEngine._substitute_vars(val)
                    if any(x in val.lower() for x in [".ru", ".com", ".net", "http", "www."]): webbrowser.open(val if val.lower().startswith("http") else "http://" + val)
                    else:
                        found_path = DictumEngine.find_shortcut(val)
                        if found_path: os.startfile(found_path)
                        else: os.system(f'start "" "{val}"')
                        
                elif cmd == "open_url":
                    val = DictumEngine._substitute_vars(val)
                    webbrowser.open(val if val.lower().startswith("http") else "https://" + val)
                    
                elif cmd == "kill": 
                    val = DictumEngine._substitute_vars(val)
                    os.system(f'taskkill /F /IM "{val}" /T')
                    
                elif cmd == "wait": 
                    val = DictumEngine._substitute_vars(val)
                    time.sleep(float(val))
                    
                elif cmd == "say": _say_edge_premium(val)
                elif cmd == "play_sound": _play_audio_file(val)
                
                elif cmd == "key":
                    _force_english_layout(); time.sleep(0.02)
                    keys = [k.strip().lower() for k in val.split('+')]
                    
                    # 🔥 ФИКС: Если макрос запрашивает блокировку ПК, вызываем нативный WinAPI метод
                    if 'win' in keys and 'l' in keys:
                        ctypes.windll.user32.LockWorkStation()
                    else:
                        for k in keys: _send_hardware_down(k)
                        time.sleep(0.02)
                        for k in reversed(keys): _send_hardware_up(k)
                        
                elif cmd == "key_down":
                    _force_english_layout(); time.sleep(0.02)
                    keys = [k.strip().lower() for k in val.split('+')]
                    
                    # 🔥 ФИКС: Продублируем проверку и для режима зажатия клавиш
                    if 'win' in keys and 'l' in keys:
                        ctypes.windll.user32.LockWorkStation()
                    else:
                        for k in keys: _send_hardware_down(k)
                        
                elif cmd == "key_up":
                    for k in [k.strip().lower() for k in val.split('+')]: _send_hardware_up(k)
                        
                elif cmd == "key_long":
                    _force_english_layout(); time.sleep(0.02)
                    for k in [k.strip().lower() for k in val.split('+')]:
                        ACTIVE_KEY_PRESSERS[k] = True
                        threading.Thread(target=_spammer_thread, args=(k,), daemon=True).start()
                    time.sleep(1.5)
                    for k in [k.strip().lower() for k in val.split('+')]:
                        ACTIVE_KEY_PRESSERS[k] = False
                        _send_hardware_up(k)
                        
                elif cmd == "type": 
                    val = DictumEngine._substitute_vars(val)
                    keyboard.write(val)
                    
                elif cmd == "mouse_scroll": 
                    val = DictumEngine._substitute_vars(val)
                    pyautogui.scroll(int(val.strip()))
                    
                elif cmd == "show_window":
                    val = DictumEngine._substitute_vars(val).strip()
                    if val:
                        windows = gw.getWindowsWithTitle(val)
                        if windows:
                            win = windows[0]
                            try:
                                if win.isMinimized: win.restore()
                                win.activate()
                            except Exception as e1:
                                try:
                                    hwnd = win._hWnd
                                    ctypes.windll.user32.ShowWindow(hwnd, 9)
                                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                                except Exception as e2:
                                    print(f"[Dictum Engine] Ошибка WinAPI вывода окна {val}: {e1} -> {e2}")
                        else:
                            # 2. Попробуем найти по названию исполняемого файла (процесса)
                            for win in gw.getAllWindows():
                                try:
                                    hwnd = win._hWnd
                                    pid = ctypes.c_ulong()
                                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                                    if pid.value > 0:
                                        proc = psutil.Process(pid.value)
                                        if val.lower() in proc.name().lower():
                                            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                                            break
                                except:
                                    pass

                elif cmd == "tg_send_screenshot":
                    # 🔥 ФИКС 1: Токен берётся из .env, если в val нет символа ':' (признак настоящего токена)
                    default_token = os.getenv("TG_BOT_TOKEN")
                    bot_token = val.strip() if val and ":" in val else default_token
                    
                    # 🔥 ФИКС 2: Динамически подгружаем актуальный chat_id из сохранённой сессии бота
                    current_chat_id = DictumEngine._load_saved_tg_chat_id()
                    
                    def _screenshot_worker(token, chat_id):
                        try:
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            temp_scr_path = os.path.join(current_dir, "live_desktop_screenshot.png")
                            screenshot = ImageGrab.grab(all_screens=True)
                            screenshot.save(temp_scr_path, "PNG")
                            if os.path.exists(temp_scr_path):
                                url = f"https://api.telegram.org/bot{token}/sendPhoto"
                                # Используем переданный в аргументы chat_id
                                requests.post(url, data={"chat_id": chat_id, "caption": "Dictum: 📸 Снимок экрана"}, files={"photo": open(temp_scr_path, "rb")}, timeout=15)
                                try: os.remove(temp_scr_path)
                                except: pass
                        except Exception as e: 
                            print(f"Ошибка скриншота: {e}")
                            
                    # Запускаем поток, передавая проверенный токен и реальный chat_id
                    threading.Thread(target=_screenshot_worker, args=(bot_token, current_chat_id), daemon=True).start()
                
                elif cmd == "sound_control":
                    parts = [x.strip() for x in val.split('|')]
                    s_mode = parts[0]
                    s_arg = parts[1] if len(parts) > 1 else ""
                    
                    nircmd_bin = _check_and_download_nircmd()
                    if os.path.exists(nircmd_bin):
                        if s_mode == "volume_mute":
                            subprocess.Popen([nircmd_bin, "stdvol", "toggle"], creationflags=subprocess.CREATE_NO_WINDOW)
                        elif s_mode == "volume_set":
                            clean_arg = s_arg.replace("%", "").strip()
                            sys_volume = int(float(clean_arg) * 655.35)
                            subprocess.Popen([nircmd_bin, "setsysvolume", str(sys_volume)], creationflags=subprocess.CREATE_NO_WINDOW)
                        elif s_mode == "volume_add":
                            clean_arg = s_arg.replace("%", "").strip()
                            sys_delta = int(float(clean_arg) * 655.35)
                            subprocess.Popen([nircmd_bin, "changesysvolume", str(sys_delta)], creationflags=subprocess.CREATE_NO_WINDOW)
                        elif s_mode == "audio_switch":
                            subprocess.Popen([nircmd_bin, "setdefaultsounddevice", s_arg, "1"], creationflags=subprocess.CREATE_NO_WINDOW)
                            subprocess.Popen([nircmd_bin, "setdefaultsounddevice", s_arg, "2"], creationflags=subprocess.CREATE_NO_WINDOW)
                
                elif cmd == "mouse_action":
                    parts = [x.strip() for x in val.split('|')]; m_mode = parts[0]; p1 = parts[1] if len(parts) > 1 else ""; p2 = parts[2] if len(parts) > 2 else ""
                    ctypes.windll.user32.SetProcessDPIAware()
                    v_left = ctypes.windll.user32.GetSystemMetrics(76)
                    v_top = ctypes.windll.user32.GetSystemMetrics(77)
                    
                    if m_mode == "mouse_image_search":
                        if p1 and os.path.exists(p1):
                            try:
                                # 🔥 Повышаем точность по умолчанию до 0.8 и считываем p2 при наличии!
                                threshold = 0.8
                                if p2:
                                    try: threshold = float(p2)
                                    except: pass
                                
                                with open(p1, "rb") as img_file:
                                    chunk = np.frombuffer(img_file.read(), dtype=np.uint8)
                                    template = cv2.imdecode(chunk, cv2.IMREAD_COLOR)
                                    
                                if template is not None:
                                    screenshot = ImageGrab.grab(all_screens=True)
                                    screen_np = np.array(screenshot)
                                    screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                                    
                                    res = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
                                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                                    
                                    if max_val >= threshold:
                                        h, w = template.shape[:2]
                                        pyautogui.moveTo(v_left + max_loc[0] + w // 2, v_top + max_loc[1] + h // 2, duration=0.3)
                            except Exception as img_err: print(f"Ошибка поиска изображения: {img_err}")
                    elif m_mode == "mouse_click":
                        btn = p2.lower().strip() if p2 else "left"
                        if p1 == "click": pyautogui.click(button=btn)
                        elif p1 == "down": pyautogui.mouseDown(button=btn)
                        elif p1 == "up": pyautogui.mouseUp(button=btn)
                        elif p1 == "long": pyautogui.mouseDown(button=btn); time.sleep(1.2); pyautogui.mouseUp(button=btn)
                    elif m_mode in ["mouse_move", "mouse_move_relative", "mouse_move_curve"]:
                        x, y = 0, 0
                        if ',' in p1: x, y = [int(c.strip()) for c in p1.split(',', 1)]
                        if m_mode == "mouse_move": pyautogui.moveTo(x, y, duration=0.2)
                        elif m_mode == "mouse_move_relative": pyautogui.moveRel(x, y, duration=0.2)

                elif cmd == "set_var":
                    if "=" in val:
                        var_name, var_val = [x.strip() for x in val.split("=", 1)]
                        var_val = DictumEngine._substitute_vars(var_val)
                        try:
                            if any(op in var_val for op in ["+", "-", "*", "/"]) and all(c.isdigit() or c in "+-*/. ()" for c in var_val):
                                computed_val = str(eval(var_val))
                            else:
                                computed_val = var_val
                        except Exception as eval_err:
                            print(f"[Dictum Engine] Ошибка математического вычисления {var_name}: {eval_err}")
                            computed_val = var_val
                            
                        # 🔥 ФИКС: Строго монопольная запись переменной в память
                        with variables_lock:
                            DICTUM_VARIABLES[var_name] = computed_val

                elif cmd == "web_get_text":
                    if "|" in val:
                        var_name, url = [x.strip() for x in val.split("|", 1)]
                        url = DictumEngine._substitute_vars(url)
                        def _get_worker(v_name, target_url):
                            try:
                                headers = {'User-Agent': 'Mozilla/5.0'}
                                r = requests.get(target_url, headers=headers, timeout=10)
                                # 🔥 ФИКС: Безопасное сохранение текста под замком
                                with variables_lock:
                                    DICTUM_VARIABLES[v_name] = r.text.strip()
                            except Exception as web_err:
                                with variables_lock:
                                    DICTUM_VARIABLES[v_name] = f"Error: {web_err}"
                        threading.Thread(target=_get_worker, args=(var_name, url), daemon=True).start()

                elif cmd == "web_post_text":
                    if val.count("|") >= 2:
                        var_name, url, payload = [x.strip() for x in val.split("|", 2)]
                        url = DictumEngine._substitute_vars(url)
                        payload = DictumEngine._substitute_vars(payload)
                        def _post_worker(v_name, target_url, data_body):
                            try:
                                data_dict = {}
                                if "=" in data_body:
                                    for item in data_body.split("&"):
                                        if "=" in item:
                                            k, v = item.split("=", 1)
                                            data_dict[k] = v
                                headers = {'User-Agent': 'Mozilla/5.0'}
                                r = requests.post(target_url, headers=headers, data=data_dict if data_dict else data_body, timeout=10)
                                # 🔥 ФИКС: Безопасное сохранение ответа под замком
                                with variables_lock:
                                    DICTUM_VARIABLES[v_name] = r.text.strip()
                            except Exception as web_err:
                                with variables_lock:
                                    DICTUM_VARIABLES[v_name] = f"Error: {web_err}"
                        threading.Thread(target=_post_worker, args=(var_name, url, payload), daemon=True).start()

                elif cmd == "notify":
                    val = DictumEngine._substitute_vars(val)
                    title_text, message_text = "Dictum", val
                    if "|" in val:
                        title_text, message_text = [x.strip() for x in val.split("|", 1)]
                    DictumEngine._show_custom_toast(title_text, message_text)

                elif cmd == "schedule":
                    if "|" in val:
                        delay_sec, phrase_cmd = [x.strip() for x in val.split("|", 1)]
                        delay_sec = float(DictumEngine._substitute_vars(delay_sec))
                        phrase_cmd = DictumEngine._substitute_vars(phrase_cmd)
                        
                        def _scheduled_trigger():
                            if DictumEngine.main_gui_ref:
                                for key in DictumEngine.main_gui_ref.data:
                                    if phrase_cmd.lower() in [p.strip() for p in key.split('|')]:
                                        DictumEngine.execute(DictumEngine.main_gui_ref.data[key]['script'])
                                        break
                                        
                        threading.Timer(delay_sec, _scheduled_trigger).start()

            except Exception as e: 
                print(f"Ошибка команды {cmd}: {e}")
                
            ptr += 1