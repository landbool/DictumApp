import os, json, threading, time, sys, subprocess, hashlib, traceback, re, math
import customtkinter as ctk
import paho.mqtt.client as mqtt
from tkinter import Menu, filedialog, Toplevel
import psutil
from PIL import Image, ImageTk 
import cv2 
from modules.ui_launcher import UIMacroLauncher

# Импортируем наши UI-модули
from modules.ui_keyboard import UIKeyboardCard
from modules.ui_mouse import UIMouseCard
from modules.ui_sound import UISoundCard  
from modules.ui_saver import UISaver
from modules.ui_notify import UINotifyCard
from modules.ui_settings import UISettingsView
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SYSTEM_TOPIC = "dictum_global_system_hub" # Общий сервисный канал для авторизации ТГ
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictum_bridge_v12.json")
MQTT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictum_mqtt_config.json")
BROKER = "broker.emqx.io"

# Динамически загружаем топик пользователя, если он сохранён в настройках
if os.path.exists(MQTT_FILE):
    try:
        with open(MQTT_FILE, "r", encoding="utf-8") as f:
            ALICE_TOPIC = json.load(f).get("mqtt_topic", "default_topic")
    except:
        ALICE_TOPIC = "default_topic"
else:
    ALICE_TOPIC = "default_topic"

# --- СИСТЕМА АВТОМАТИЧЕСКОГО СБОРА КРАШ-РЕПОРТОВ ---
def crash_logger_hook(exc_type, exc_value, exc_traceback):
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictum_crash_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== CRASH REPORT DICTUM ===\n")
        f.write(f"Время сбоя: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Версия Python: {sys.version}\n")
        f.write("-----------------------------------\n")
        f.write(error_msg)
        f.write("\n===================================\n")
    subprocess.Popen(["notepad.exe", report_path])
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = crash_logger_hook
threading.excepthook = lambda args: crash_logger_hook(args.exc_type, args.exc_value, args.exc_traceback)

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path: sys.path.append(current_dir)

try:
    from engine import DictumEngine
    from modules import logic, system, tools, input as dev_input, web
except ImportError as e:
    print(f"Критическая ошибка модулей!\nДетали: {e}"); time.sleep(5); sys.exit()

# --- ТЕМНАЯ СИНТАКСИЧЕСКАЯ ПАЛИТРА ---
ACCENT = "#007AFF"          
ACCENT_PURPLE = "#AF52DE"   
ACCENT_GREEN = "#34C759"    
D_BG = "#07080B"            
D_SIDE = "#0F1016"          
D_CARD = "#141724"          
D_BORDER = "#1F2438"        

SYSTEM_PROCESS_BLOCKLIST = {
    "system idle process", "system", "registry", "smss.exe", "csrss.exe", 
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe", 
    "memory compression", "memcompression", "searchhost.exe", "searchindexer.exe", 
    "taskhostw.exe", "conhost.exe", "dllhost.exe", "audiodg.exe", "spoolsv.exe", 
    "sihost.exe", "smartscreen.exe", "winlogon.exe", "dwm.exe", "ctfmon.exe", 
    "comsurrogate.exe", "explorer.exe", "filecoauth.exe", "officeclicktorun.exe", 
    "openconsole.exe", "windowsterminal.exe", "widgets.exe", "aggregatorhost.exe", 
    "applicationframehost.exe", "amneziavpn-service.exe", "crashpad_handler.exe",
    "msedgewebview2.exe", "appactions.exe", "lockapp.exe", "mpdefendercoreservice.exe",
    "msmpeng.exe", "nvdisplay.container.exe", "nissrv.exe"
}

DICTUM_PROCESS_CACHE = []

def _update_process_cache():
    global DICTUM_PROCESS_CACHE
    try:
        current_procs = set()
        for p in psutil.process_iter(['name', 'exe']):
            try:
                name = p.info['name']
                exe_path = p.info['exe']
                if not name: continue
                name_lower = name.lower()
                if name_lower in SYSTEM_PROCESS_BLOCKLIST: continue
                if ".tmp" in name_lower or "setup" in name_lower or "install" in name_lower: continue
                system_keywords = ["host", "service", "worker", "broker", "agent", "telemetry", "helper", "manager", "listener", "overlay", "daemon", "handler", "coauth", "clicktorun", "console", "terminal", "widget", "patch", "update", "upgrade"]
                if any(kw in name_lower for kw in system_keywords): continue
                if exe_path:
                    exe_lower = exe_path.lower()
                    if "c:\\windows" in exe_lower or "system32" in exe_lower or "syswow64" in exe_lower: continue
                    if "nvidia" in exe_lower or "amd" in exe_lower or "intel" in exe_lower: continue
                current_procs.add(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        DICTUM_PROCESS_CACHE = sorted(list(current_procs))
    except Exception as cache_err:
        print(f"[Dictum Optimizer] Ошибка сбора кэша процессов: {cache_err}")

_update_process_cache()

def _background_process_spy():
    while True:
        time.sleep(12)
        _update_process_cache()

threading.Thread(target=_background_process_spy, daemon=True).start()

RU_TO_EN_KEYBOARD = {
    'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
    'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
    'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.', '.': '/'
}

def fix_layout_string(text):
    return "".join(RU_TO_EN_KEYBOARD.get(char, char) for char in str(text).lower())

def fix_mouse_value_on_load(val):
    s = str(val).strip()
    if ":" in s: s = s.split(":", 1)[1].strip()
    return s

def transliterate_text(text):
    TRANSLIT_DICT = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    result = []
    for char in str(text).lower().strip(): result.append(TRANSLIT_DICT.get(char, char))
    clean_str = "".join(result)
    clean_str = re.sub(r'[^a-z0-9_]', '_', clean_str)
    return re.sub(r'_+', '_', clean_str).strip('_')

def pre_generate_voice(text):
    try:
        import asyncio, edge_tts
        cache_dir = os.path.join(current_dir, "cached_voices")
        if not os.path.exists(cache_dir): os.makedirs(cache_dir)
        latin_name = transliterate_text(text)
        clean_text = str(text).strip().lower()
        file_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()[:6]
        cached_file = os.path.join(cache_dir, f"{latin_name[:30]}_{file_hash}.mp3")
        
        if not os.path.exists(cached_file):
            voice = "ru-RU-SvetlanaNeural"
            async def _amake_wave():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(cached_file)
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            try: loop.run_until_complete(_amake_wave())
            finally: loop.close()
        return cached_file
    except Exception as e: print(f"Ошибка предгенерации звука: {e}"); return None

def add_entry_context_menu(entry_widget):
    menu = Menu(entry_widget, tearoff=0, bg=D_SIDE, fg="white", activebackground=ACCENT)
    menu.add_command(label="Вырезать", command=lambda: entry_widget.focus_get().event_generate("<<Cut>>"))
    menu.add_command(label="Копировать", command=lambda: entry_widget.focus_get().event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: entry_widget.focus_get().event_generate("<<Paste>>"))
    menu.add_command(label="Удалить", command=lambda: entry_widget.focus_get().event_generate("<<Clear>>"))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: entry_widget.focus_get().event_generate("<<SelectAll>>"))
    entry_widget.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))

def delete_voice_by_path(file_path):
    try:
        if file_path and os.path.exists(file_path): os.remove(file_path)
    except Exception as e: print(f"[Dictum Optimizer] Не удалось удалить аудио-кэш: {e}")

class CTkScrollableDropdown(ctk.CTkToplevel):
    def __init__(self, attach_widget, values, command):
        super().__init__(attach_widget.winfo_toplevel())
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=D_SIDE)
        
        self.update_idletasks()
        x = attach_widget.winfo_rootx()
        y = attach_widget.winfo_rooty() + attach_widget.winfo_height() + 2
        w = max(attach_widget.winfo_width(), 200)
        h = 280
        
        self.geometry(f"{w}x{h}+{x}+{y}")
        frame = ctk.CTkFrame(self, fg_color=D_SIDE, border_width=1, border_color=D_BORDER, corner_radius=12)
        frame.pack(fill="both", expand=True)
        
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent", corner_radius=10, scrollbar_button_color="#222638")
        scroll.pack(fill="both", expand=True, padx=2, pady=2)
        
        for val in values:
            btn = ctk.CTkButton(scroll, text=val, anchor="w", fg_color="transparent", text_color="#E5E7EB", hover_color=ACCENT, height=30, font=("Segoe UI Semibold", 11), command=lambda v=val: [command(v), self.destroy()])
            btn.pack(fill="x", pady=1, padx=2)
            
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.after(10, self.focus)

class DictumSplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, video_path, on_finish, speed_factor=2, vector_duration=1.5):
        super().__init__(parent)
        self.parent = parent
        self.video_path = video_path
        self.on_finish = on_finish
        self.speed_factor = speed_factor       
        self.vector_duration = vector_duration 
        
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color="#0A0A0A")
        
        self.width = 800
        self.height = 450
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - self.width) // 2
        y = (sh - self.height) // 2
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")

        if os.name == 'nt':
            try:
                import ctypes
                self.update_idletasks() 
                hwnd = self.winfo_id()
                rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, self.width + 1, self.height + 1, 32, 32)
                ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
            except Exception as e: print(f"Не удалось применить скругление заставки: {e}")
        
        self.canvas = ctk.CTkCanvas(self, width=self.width, height=self.height, bg="#0A0A0A", bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.cap = None
        if os.path.exists(self.video_path):
            try: self.cap = cv2.VideoCapture(self.video_path)
            except Exception as e: print(f"Не удалось инициализировать видеодекодер: {e}"); self.cap = None
                
        if self.cap and self.cap.isOpened(): self.play_video_frame()
        else: self.wave_phase = 0.0; self.start_time = time.time(); self.animate_vector_logo()
            
    def play_video_frame(self):
        if not self.winfo_exists(): return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.resize(frame, (self.width, self.height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            self.photo = ImageTk.PhotoImage(image=img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
            
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / (fps * self.speed_factor)) if fps > 0 else int(33 / self.speed_factor)
            self.after(max(1, delay), self.play_video_frame)
        else:
            if self.cap: self.cap.release()
            self.close_splash()
            
    def animate_vector_logo(self):
        if not self.winfo_exists(): return
        elapsed = time.time() - self.start_time
        if elapsed > self.vector_duration: self.close_splash(); return
        self.canvas.delete("all")
        cx, cy = self.width // 2, self.height // 2 - 25
        
        time_scale = 3.0 / self.vector_duration if self.vector_duration > 0 else 1.0
        d_opacity = min(1.0, (elapsed * time_scale) / 0.8) 
        wave_opacity = min(1.0, max(0.0, ((elapsed * time_scale) - 0.4) / 0.8)) 
        text_opacity = min(1.0, max(0.0, ((elapsed - 0.8) * time_scale) / 0.8)) 
        d_val = int(255 * d_opacity)
        d_color = f"#{d_val:02x}{d_val:02x}{d_val:02x}"
        glow_r = int(90 + 5 * math.sin(elapsed * 4 * time_scale))
        if elapsed > 0.1: self.canvas.create_oval(cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r, fill="#0F172A", outline="")
        
        self.canvas.create_line(cx - 45, cy - 55, cx + 5, cy - 55, fill=d_color, width=9, capstyle="round")
        self.canvas.create_line(cx - 45, cy + 55, cx + 5, cy + 55, fill=d_color, width=9, capstyle="round")
        self.canvas.create_line(cx - 45, cy - 55, cx - 45, cy + 55, fill=d_color, width=9, capstyle="round")
        self.canvas.create_arc(cx - 45, cy - 55, cx + 55, cy + 55, start=-90, extent=180, style="arc", outline=d_color, width=9)
        if wave_opacity > 0:
            self.wave_phase += 0.09 * time_scale 
            points_blue, points_cyan = [], []
            for x in range(cx - 75, cx + 75, 2):
                damp = max(0.0, 1.0 - (abs(x - cx) / 80.0) ** 2) 
                y_blue = cy - 2 + 14 * math.sin(0.045 * (x - cx) - self.wave_phase) * damp
                points_blue.extend([x, y_blue])
                y_cyan = cy - 5 + 14 * math.sin(0.045 * (x - cx) - self.wave_phase + 0.6) * damp
                points_cyan.extend([x, y_cyan])
            blue_color = f"#002b{text_opacity:02x}"
            cyan_color = f"#00{int(229 * wave_opacity):02x}{int(229 * wave_opacity):02x}"
            self.canvas.create_line(*points_blue, fill=blue_color, width=9, smooth=True)
            self.canvas.create_line(*points_cyan, fill=cyan_color, width=4, smooth=True)
        if text_opacity > 0:
            self.canvas.create_text(cx, cy + 105, text="Dictum", font=("Segoe UI", 36, "bold"), fill=f"#{int(255 * text_opacity):02x}{int(255 * text_opacity):02x}{int(255 * text_opacity):02x}")
        self.canvas.create_arc(cx - 135, cy - 135, cx + 135, cy + 135, start=90, extent=-360 * (elapsed / self.vector_duration), style="arc", outline=ACCENT, width=2)
        self.after(16, self.animate_vector_logo) 
        
    def close_splash(self): self.destroy(); self.on_finish()

class ActionBlock(ctk.CTkFrame):
    def __init__(self, master, type_name, value, delete_callback, drag_callback, indent=0):
        super().__init__(master, corner_radius=12, border_width=1, border_color=D_BORDER, fg_color=D_CARD)
        self.type_label = type_name
        self.drag_callback = drag_callback  
        self.widgets_to_cleanup = [] 
        self.accent_line = None
        
        self.pack(fill="x", pady=3, padx=(15 + (indent * 35), 15))

        self.handle = ctk.CTkLabel(self, text=" ≡ ", font=("Arial", 18), cursor="fleur", text_color="gray35")
        self.handle.pack(side="left", padx=(10, 5))
        self.handle.bind("<Button-1>", lambda e: [self.lift(), setattr(self, 'start_y', e.y_root)])
        self.handle.bind("<B1-Motion>", self._on_drag)

        ctk.CTkButton(self, text="✕", width=26, height=26, font=("Arial", 11), fg_color="transparent", hover_color="#FF453A", text_color="gray50", command=lambda: delete_callback(self)).pack(side="right", padx=10)
        
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(side="left", fill="x", expand=True)

        self.badge_colors = {
            "key": ACCENT, "mouse_action": ACCENT, "mouse_scroll": ACCENT, "type": ACCENT,
            "if_active": ACCENT_PURPLE, "if_proc": ACCENT_PURPLE, "if_site": ACCENT_PURPLE, "if_var": ACCENT_PURPLE,
            "loop": ACCENT_PURPLE, "loop_while": ACCENT_PURPLE, "random_block": ACCENT_PURPLE, "break": ACCENT_PURPLE, "else": ACCENT_PURPLE, "end": ACCENT_PURPLE,
            "open": ACCENT_GREEN, "kill": ACCENT_GREEN, "play_sound": ACCENT_GREEN, "say": ACCENT_GREEN, "sound_control": ACCENT_GREEN, "notify": ACCENT_GREEN
        }
        current_theme_color = self.badge_colors.get(type_name.lower().strip(), ACCENT)

        self.render_card_contents(type_name, value)
        self.update_accent_line(indent, current_theme_color)

    def update_accent_line(self, indent, color=ACCENT_PURPLE):
        if self.accent_line: self.accent_line.destroy(); self.accent_line = None
        if indent > 0:
            self.accent_line = ctk.CTkFrame(self, width=2, fg_color=color)
            self.accent_line.place(relx=0, rely=0.1, relheight=0.8, x=-8)

    def render_card_contents(self, type_name, value):
        for w in self.widgets_to_cleanup: w.destroy()
        self.widgets_to_cleanup.clear()

        if type_name in ["mouse_click", "mouse_click_down", "mouse_click_up", "mouse_click_long", "mouse_move", "mouse_move_relative", "mouse_move_curve"]:
            value = f"{type_name} | {fix_mouse_value_on_load(value)}" if value and '|' not in str(value) else f"{type_name}"
            type_name = "mouse_action"; self.type_label = "mouse_action"
        elif type_name in ["key", "key_down", "key_up", "key_long"]:
            value = f"{type_name} | {value}" if value and '|' not in str(value) else f"{type_name}"
            type_name = "key"; self.type_label = "key"

        ru_cmd_names = {
            "say": "СКАЗАТЬ", "wait": "ПАУЗА", "key": "КЛАВИАТУРА", "mouse_action": "МЫШЬ",
            "mouse_scroll": "ПРОКРУТКА", "type": "ПЕЧАТЬ ТЕКСТА", "open": "ОТКРЫТЬ", "kill": "ЗАКРЫТЬ",
            "play_sound": "ЗВУК", "if_active": "ЕСЛИ АКТИВНА", "if_proc": "ЕСЛИ ЗАПУЩЕНА",
            "if_site": "ЕСЛИ САЙТ", "if_var": "ЕСЛИ ПЕРЕМЕННАЯ", "loop": "ЦИКЛ", "loop_while": "ЦИКЛ ПОКА",
            "random_block": "СЛУЧАЙНО", "break": "ПРЕРВАТЬ", "else": "ИНАЧЕ", "end": "КОНЕЦ БЛОКА",
            "run_system": "СИСТЕМА", "show_window": "Показать окно", "sound_control": "ГРОМКОСТЬ",
            "run_bat": "BAT СКРИПТ", "run_command": "КОМАНДА", "open_url": "Открыть ссылку",
            "tg_send_screenshot": "Отправить скриншот в TG"
        }
        
        display_name = ru_cmd_names.get(type_name.lower().strip(), type_name.upper())

        current_theme_color = self.badge_colors.get(type_name.lower().strip(), ACCENT)
        lbl = ctk.CTkLabel(self.content_frame, text=f"  {display_name}  ", font=("Segoe UI Variable Display", 10, "bold"), text_color="#FFFFFF", fg_color=current_theme_color, corner_radius=6, height=22)
        lbl.pack(side="left", padx=(0, 8)); self.widgets_to_cleanup.append(lbl)

        entry_kwargs = {"height": 32, "corner_radius": 8, "fg_color": "#090A0F", "border_color": D_BORDER, "border_width": 1}

        if type_name == "key":
            self.inner_card = UIKeyboardCard(self.content_frame, value, self._sync_inner_value, fix_layout_string, add_context_menu_fn=add_entry_context_menu)
            self.inner_card.pack(side="left", fill="x", expand=True)
            self.widgets_to_cleanup.append(self.inner_card)

        elif type_name == "mouse_action":
            self.inner_card = UIMouseCard(self.content_frame, value, lambda: None, add_context_menu_fn=add_entry_context_menu)
            self.inner_card.pack(side="left", fill="x", expand=True)
            self.widgets_to_cleanup.append(self.inner_card)

        elif type_name == "sound_control":
            self.inner_card = UISoundCard(self.content_frame, value, self._sync_inner_value, fix_layout_string, add_context_menu_fn=add_entry_context_menu)
            self.inner_card.pack(side="left", fill="x", expand=True)
            self.val_entry = self.inner_card.val_entry

        elif type_name in ["open", "kill", "if_proc", "if_active", "show_window"]:
            clean_val = str(value).split(':', 1)[1].strip() if ':' in str(value) else str(value).strip()
            procs = DICTUM_PROCESS_CACHE
            
            self.val_entry = ctk.CTkEntry(self.content_frame, placeholder_text="Впиши имя процесса или нажми Обзор...", font=("Segoe UI", 12), **entry_kwargs)
            if clean_val: self.val_entry.insert(0, clean_val)
            self.val_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
            self.widgets_to_cleanup.append(self.val_entry)
            
            btn_drop = ctk.CTkButton(self.content_frame, text=clean_val if clean_val else "Выбрать программу...", width=160, height=32, font=("Segoe UI Semibold", 11), fg_color="#0A0B0F", border_width=1, border_color=D_BORDER, hover_color="#171A26", anchor="w", corner_radius=8)
            btn_drop.configure(command=lambda b=btn_drop: CTkScrollableDropdown(b, procs, lambda choice: [self.val_entry.delete(0, 'end'), self.val_entry.insert(0, choice), b.configure(text=choice)]))
            btn_drop.pack(side="left", padx=2)
            self.widgets_to_cleanup.append(btn_drop)
            
            btn_browse = ctk.CTkButton(self.content_frame, text="📂 Обзор", width=70, height=32, font=("Segoe UI Bold", 11), fg_color=D_BORDER, hover_color=ACCENT, corner_radius=8, command=self._browse_executable_file)
            btn_browse.pack(side="left", padx=2); self.widgets_to_cleanup.append(btn_browse)

        elif type_name == "notify":
            self.inner_card = UINotifyCard(self.content_frame, value, lambda: None, add_context_menu_fn=add_entry_context_menu)
            self.inner_card.pack(side="left", fill="x", expand=True)
            self.widgets_to_cleanup.append(self.inner_card)

        elif type_name == "tg_send_screenshot":
            lbl_info = ctk.CTkLabel(self.content_frame, text="Делает снимок всех мониторов и отправляет в Telegram", font=("Segoe UI Semibold", 12), text_color="gray45")
            lbl_info.pack(side="left", padx=5); self.widgets_to_cleanup.append(lbl_info)

        elif type_name == "play_sound":
            clean_display_text = str(value).strip().split(":", 1)[1].strip() if ":" in str(value) else str(value).strip()
            self.val_entry = ctk.CTkEntry(self.content_frame, placeholder_text="Выбери аудиофайл через Обзор...", font=("Segoe UI", 12), **entry_kwargs)
            if clean_display_text and clean_display_text != "SNAPSHOT": self.val_entry.insert(0, clean_display_text)
            self.val_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
            self.widgets_to_cleanup.append(self.val_entry)
            add_entry_context_menu(self.val_entry)
            
            std_sounds = ["Выбрать звук...", "click.wav", "notification.mp3", "error.mp3", "success.wav", "alarm.mp3", "beep.wav", "coin.wav", "level_up.mp3", "chime.wav"]
            drop_sounds = ctk.CTkOptionMenu(self.content_frame, values=std_sounds, width=130, height=32, corner_radius=8, fg_color="#0A0B0F", button_color="#171A26", command=lambda choice: self.val_entry.delete(0, 'end') or self.val_entry.insert(0, f"sounds/{choice}") if choice != "Выбрать звук..." else None)
            c_f = clean_display_text.split("/")[-1].split("\\")[-1]
            drop_sounds.set(c_f if c_f in std_sounds else "Стандартные")
            drop_sounds.pack(side="left", padx=2); self.widgets_to_cleanup.append(drop_sounds)
            
            btn_browse = ctk.CTkButton(self.content_frame, text="📂 Обзор", width=70, height=32, font=("Segoe UI Bold", 11), fg_color=D_BORDER, hover_color=ACCENT, corner_radius=8, command=lambda: [f_path := filedialog.askopenfilename(title="Выбери аудиофайл", filetypes=[("Аудио файлы", "*.mp3 *.wav *.ogg")]), f_path and [self.val_entry.delete(0, 'end'), self.val_entry.insert(0, os.path.normpath(f_path))]])
            btn_browse.pack(side="left", padx=2); self.widgets_to_cleanup.append(btn_browse)

        else:
            hint = "Впиши параметры макроса..."
            if type_name == "mouse_scroll": hint = "Впиши шаги прокрутки (например: 3 или -3)..."
            elif type_name == "type": hint = "Впиши текст, который программа напечатает..."
            elif type_name == "say": hint = "Впиши текст, который озвучит Светлана..."
            elif type_name == "wait": hint = "Впиши время ожидания в секундах..."
            
            clean_display_text = str(value).strip()
            if type_name == "say" and clean_display_text.startswith("{") and clean_display_text.endswith("}"):
                try: clean_display_text = json.loads(clean_display_text).get("text", "").strip()
                except: pass

            self.val_entry = ctk.CTkEntry(self.content_frame, placeholder_text=hint, font=("Segoe UI", 12), **entry_kwargs)
            if clean_display_text and clean_display_text != "SNAPSHOT": self.val_entry.insert(0, clean_display_text)
            self.val_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
            self.widgets_to_cleanup.append(self.val_entry)
            add_entry_context_menu(self.val_entry)

    def _sync_inner_value(self):
        if hasattr(self, 'inner_card') and hasattr(self, 'val_entry'):
            m, v = self.inner_card.get_values()
            self.val_entry.delete(0, 'end'); self.val_entry.insert(0, f"{m} | {v}")

    def _browse_executable_file(self):
        file_path = filedialog.askopenfilename(title="Выберите файл", filetypes=[("Исполняемые файлы", "*.exe *.lnk *.bat"), ("Все файлы", "*.*")])
        if file_path: self.val_entry.delete(0, 'end'); self.val_entry.insert(0, os.path.normpath(file_path))

    def _on_drag(self, e):
        if abs(e.y_root - self.start_y) > 40: self.drag_callback(self, 1 if e.y_root > self.start_y else -1); self.start_y = e.y_root

class DictumBridge(ctk.CTk):
    def __init__(self):
        super().__init__()
        DictumEngine.main_gui_ref = self
        self.title("Dictum")
        
        self.action_area = None
        self.phrase_inputs_container = None
        self.mqtt_client = None  
        
        width, height = 1180, 860
        self.geometry(f"{width}x{height}+{(self.winfo_screenwidth() - width) // 2}+{(self.winfo_screenheight() - height) // 2}")
        self.configure(fg_color=D_BG)
        ctk.set_appearance_mode("dark")
        self.withdraw()
        
        self.data = self.load_data()
        self.current_actions = []
        self.phrase_entries = []
        self.current_editing_key = None
        
        # 🔥 Инициализируем живую переменную для динамической смены подписок Алисы
        self.current_alice_topic = ALICE_TOPIC
        
        self.setup_ui()
        self.views["cmds"].pack(fill="both", expand=True)
        self.refresh_list()
        
        self.splash = DictumSplashScreen(self, os.path.join(current_dir, "img/startup.mp4"), self.show_main_app_smoothly, speed_factor=1.75, vector_duration=1.5)
        threading.Thread(target=self.start_mqtt, daemon=True).start()

    def show_main_app_smoothly(self):
        self.deiconify()
        self.dynamic_win_api_patch()
        self.attributes("-alpha", 0.0)
        self.fade_in_transition(0.0)
        
    def dynamic_win_api_patch(self):
        if os.name == 'nt':
            try:
                import ctypes
                self.update_idletasks()
                hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)
                and_mask = (ctypes.c_ubyte * 32)(*([0xFF] * 32))
                xor_mask = (ctypes.c_ubyte * 32)(*([0x00] * 32))
                h_blank_icon = ctypes.windll.user32.CreateIcon(0, 16, 16, 1, 1, and_mask, xor_mask)
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, h_blank_icon)
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, h_blank_icon)
                dark = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
            except Exception as win_api_err: print(f"WinAPI Icon patch failed: {win_api_err}")

    def fade_in_transition(self, current_alpha):
        if current_alpha < 1.0:
            current_alpha += 0.08
            self.attributes("-alpha", min(current_alpha, 1.0))
            self.after(15, lambda: self.fade_in_transition(current_alpha))
        else: self.attributes("-alpha", 1.0)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        
        nav = ctk.CTkFrame(self, height=55, fg_color="#0C0E14", corner_radius=0, border_width=1, border_color="#161924")
        nav.grid(row=0, column=0, sticky="ew")
        
        self.btn_cmds = ctk.CTkButton(nav, text="📦 КОМАНДЫ", fg_color="transparent", text_color="#FFFFFF", font=("Segoe UI Variable Display", 12, "bold"), hover_color="#181B26", width=140, height=36, corner_radius=8, command=lambda: self.show_view("cmds"))
        self.btn_cmds.pack(side="left", padx=10)
        
        self.btn_settings = ctk.CTkButton(nav, text="⚙️ НАСТРОЙКИ", fg_color="transparent", text_color="gray60", font=("Segoe UI Variable Display", 12, "bold"), hover_color="#181B26", width=140, height=36, corner_radius=8, command=lambda: self.show_view("settings"))
        self.btn_settings.pack(side="left", padx=10)

        self.btn_logs = ctk.CTkButton(nav, text="📟 ЖУРНАЛ", fg_color="transparent", text_color="gray60", font=("Segoe UI Variable Display", 12, "bold"), hover_color="#181B26", width=140, height=36, corner_radius=8, command=lambda: self.show_view("logs"))
        self.btn_logs.pack(side="left")
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=0, sticky="nsew", padx=20, pady=15)
        
        self.view_cmds_root = ctk.CTkFrame(self.container, fg_color="transparent")
        self.list_pane = ctk.CTkFrame(self.view_cmds_root, fg_color="transparent")
        self.list_pane.pack(fill="both", expand=True)
        
        ctk.CTkButton(self.list_pane, text="+ Создать команду", fg_color=ACCENT, hover_color="#0062CC", height=42, font=("Segoe UI Variable Display", 12, "bold"), corner_radius=10, command=self.open_editor).pack(fill="x", pady=(0, 15))
        
        self.scroll = ctk.CTkScrollableFrame(self.list_pane, fg_color=D_BG, border_width=0, corner_radius=0, scrollbar_button_color="#1F2335", scrollbar_button_hover_color=ACCENT)
        self.scroll.pack(fill="both", expand=True)

        self.edit_pane = ctk.CTkFrame(self.view_cmds_root, fg_color="transparent")
        tbar = ctk.CTkFrame(self.edit_pane, height=54, fg_color="#0C0E14", border_width=1, border_color=D_BORDER, corner_radius=12)
        tbar.pack(fill="x", pady=(0, 15)); tbar.pack_propagate(False)
        
        ctk.CTkButton(tbar, text="←", width=38, height=32, font=("Segoe UI Variable", 13, "bold"), fg_color="#1A1D29", hover_color="#242938", text_color="#E5E7EB", corner_radius=8, command=self.close_editor).pack(side="left", padx=(10, 5))
        
        self.add_dropdown(tbar, "❓ Условия", logic.get_menu(self.add_block))
        self.add_dropdown(tbar, "⚔️ Система", system.get_menu(self.add_block))
        self.add_dropdown(tbar, "🛠️ Опции", tools.get_menu(self.add_block))
        self.add_dropdown(tbar, "🖱️ Периферия", dev_input.get_menu(self.add_block))
        self.add_dropdown(tbar, "🌐 Сеть API", web.get_menu(self.add_block))
        
        self.btn_save = ctk.CTkButton(tbar, text="СОХРАНИТЬ", fg_color="#248A3D", hover_color="#1E7A31", width=110, height=34, font=("Segoe UI Variable Display", 11, "bold"), corner_radius=8, command=self.save_macro)
        self.btn_save.pack(side="right", padx=10, pady=10)
        
        self.body_editor = ctk.CTkFrame(self.edit_pane, fg_color="transparent")
        self.body_editor.pack(fill="both", expand=True)
        
        self.phrase_area = ctk.CTkScrollableFrame(self.body_editor, width=260, fg_color=D_SIDE, border_width=1, border_color=D_BORDER, corner_radius=14, scrollbar_button_color="#1A1D29")
        self.phrase_area.pack(side="left", fill="y", padx=(0, 12))
        
        self.v_logs = ctk.CTkTextbox(self.container, font=("Consolas", 12), fg_color=D_SIDE, text_color="#34C759", border_width=1, border_color=D_BORDER, corner_radius=14, padx=15, pady=15)
        
        self.v_settings = UISettingsView(self.container, bg_color=D_BG, border_color=D_BORDER, side_color=D_SIDE, accent_color=ACCENT)
        self.views = {"cmds": self.view_cmds_root, "logs": self.v_logs, "settings": self.v_settings}

    def add_dropdown(self, master, icon, items):
        btn = ctk.CTkButton(master, text=icon, width=115, height=32, fg_color="transparent", hover_color="#181B26", text_color="gray65", font=("Segoe UI Semibold", 11), corner_radius=8)
        btn.pack(side="left", padx=2, pady=10)
        m = Menu(self, tearoff=0, bg=D_SIDE, fg="white", font=("Segoe UI", 10), activebackground=ACCENT, bd=0)
        for label, cmd in items: m.add_command(label=f"  {label}  ", command=cmd)
        btn.bind("<Button-1>", lambda e: m.post(e.x_root, e.y_root))

    def add_phrase_input(self, content=""):
        target_parent = self.phrase_inputs_container if self.phrase_inputs_container else self.phrase_area
        f = ctk.CTkFrame(target_parent, fg_color="transparent")
        f.pack(fill="x", pady=2, padx=4)
        e = ctk.CTkEntry(f, placeholder_text="Фраза вызова...", height=32, corner_radius=6, fg_color="#07080B", border_color=D_BORDER)
        if content: e.insert(0, content)
        e.pack(side="left", fill="x", expand=True, padx=(0, 2))
        ctk.CTkButton(f, text="✕", width=22, height=32, fg_color="transparent", text_color="gray40", hover_color="#FF453A", command=lambda: [f.destroy(), self.phrase_entries.remove(e)]).pack(side="right")
        self.phrase_entries.append(e); add_entry_context_menu(e)

    def add_block(self, t, v): 
        new_block = ActionBlock(self.action_area, t, v, self.remove_block, self.move_block)
        self.current_actions.append(new_block)
        self.recalculate_indents()
        
    def recalculate_indents(self):
        indent = 0
        for b in self.current_actions:
            if b.type_label in ["end", "break"]: indent = max(0, indent - 1)
            new_padx = (15 + (indent * 35), 15)
            b.pack_forget(); b.pack(fill="x", pady=3, padx=new_padx)
            
            current_theme_color = b.badge_colors.get(b.type_label.lower().strip(), ACCENT)
            if hasattr(b, 'update_accent_line'): b.update_accent_line(indent, current_theme_color)
            if b.type_label in ["if_active", "if_proc", "if_site", "if_var", "loop", "loop_while", "random_block"]: indent += 1

    def move_block(self, b, d):
        idx = self.current_actions.index(b); new = idx + d
        if 0 <= new < len(self.current_actions): self.current_actions[idx], self.current_actions[new] = self.current_actions[new], self.current_actions[idx]; self.recalculate_indents()

    def remove_block(self, b):
        b.destroy()
        if b in self.current_actions: self.current_actions.remove(b)
        self.recalculate_indents()

    def save_macro(self):
        ph = [e.get().strip().lower() for e in self.phrase_entries if e.get().strip()]
        if not ph: return
        extracted_actions = []
        for b in self.current_actions:
            cmd_type = b.type_label
            if cmd_type == "key" and hasattr(b, "inner_card"):
                mode, val = b.inner_card.get_values()
                extracted_actions.append({"type": "key_card", "mode": mode, "val": val})
            elif cmd_type == "mouse_action" and hasattr(b, "inner_card"):
                extracted_actions.append({"type": "mouse_card", "val": b.inner_card.get_values()})
            elif cmd_type == "notify" and hasattr(b, "inner_card"):
                t_val, m_val = b.inner_card.get_values()
                extracted_actions.append({"type": "notify_card", "title": t_val, "msg": m_val})
            else:
                cmd_val = b.val_entry.get().strip() if hasattr(b, 'val_entry') and b.val_entry.winfo_exists() else getattr(b, 'stored_value', "")
                extracted_actions.append({"type": "normal", "cmd_type": cmd_type, "val": cmd_val})
        if hasattr(self, 'btn_save'): self.btn_save.configure(text="ЗАПИСЬ...", state="disabled", fg_color="#444444")
        
        def worker():
            try:
                new_key, msg = UISaver.save_macro_to_json(DATA_FILE, self.current_editing_key, ph, extracted_actions, self.data, pre_generate_voice, delete_voice_by_path)
                self.after(0, lambda: self._on_save_complete(new_key, msg))
            except: self.after(0, lambda: self._on_save_complete(None, "Ошибка"))
        threading.Thread(target=worker, daemon=True).start()

    def sync_commands_to_bot(self):
        """ Отправляет список фраз вызова серверному боту через MQTT """
        if self.mqtt_client and self.mqtt_client.is_connected():
            current_dir = os.path.dirname(os.path.abspath(__file__))
            session_file = os.path.join(current_dir, "dictum_tg_session.json")
            if os.path.exists(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        phone = json.load(f).get("phone", "").strip().replace("+", "").replace(" ", "")
                        if phone:
                            # Собираем все ключи (фразы вызова макросов)
                            commands_keys = list(self.data.keys())
                            payload = json.dumps(commands_keys, ensure_ascii=False)
                            # Публикуем в сервисный топик авторизации
                            from main import SYSTEM_TOPIC
                            self.mqtt_client.publish(SYSTEM_TOPIC, f"tg_cmd_sync_macros::{phone}::{payload}")
                except Exception as e:
                    print(f"[Sync] Ошибка сборки макросов для бота: {e}")

    def _on_save_complete(self, new_key, msg):
        if hasattr(self, 'btn_save'): self.btn_save.configure(text="СОХРАНИТЬ", state="normal", fg_color="#248A3D")
        self.sync_commands_to_bot()
        if new_key: self.close_editor()

    def delete_macro(self, phrase_key):
        if phrase_key not in self.data: return
        confirm_window = ctk.CTkToplevel(self)
        confirm_window.title("Удаление"); confirm_window.geometry("380x150"); confirm_window.resizable(False, False); confirm_window.configure(fg_color=D_BG)
        confirm_window.transient(self); confirm_window.grab_set(); confirm_window.update_idletasks()
        confirm_window.geometry(f"+{self.winfo_x() + (self.winfo_width()//2) - 190}+{self.winfo_y() + (self.winfo_height()//2) - 75}")
        ctk.CTkLabel(confirm_window, text=f"Удалить команду {phrase_key.upper()}?", font=("Segoe UI Semibold", 13), text_color="#E5E7EB").pack(pady=(25, 15))
        btn_frame = ctk.CTkFrame(confirm_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25)
        
        def _confirmed_delete():
            del self.data[phrase_key]
            with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(self.data, f, indent=4)
            confirm_window.destroy(); self.refresh_list()
        ctk.CTkButton(btn_frame, text="Отмена", width=150, height=36, fg_color="#1C1E26", hover_color="#2A2F3D", command=confirm_window.destroy, corner_radius=8).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Удалить", width=150, height=36, fg_color="#FF453A", hover_color="#FF3B30", command=_confirmed_delete, corner_radius=8).pack(side="right")

    def refresh_list(self):
        for w in self.scroll.winfo_children(): w.destroy()
        preview_translate = {"wait": "Пауза", "key": "Клавиши", "type": "Печать", "open": "Открыть", "kill": "Закрыть", "say": "Речь", "play_sound": "Звук", "mouse_action": "Мышь", "notify": "Уведомление"}

        for idx, p in enumerate(sorted(self.data.keys())):
            f = ctk.CTkFrame(self.scroll, height=68, fg_color=D_SIDE, border_width=1, border_color=D_BORDER, corner_radius=12)
            f.pack(fill="x", pady=4, padx=15); f.pack_propagate(False)
            
            marker = ctk.CTkFrame(f, width=3, fg_color=ACCENT, corner_radius=2)
            marker.pack(side="left", fill="y", padx=(12, 0), pady=12)
            
            meta_frame = ctk.CTkFrame(f, fg_color="transparent")
            meta_frame.pack(side="left", fill="both", expand=True, padx=12, pady=8)
            
            lbl_title = ctk.CTkLabel(meta_frame, text=p.upper(), font=("Segoe UI Variable Display", 13, "bold"), text_color="#FFFFFF", anchor="w")
            lbl_title.pack(fill="x", anchor="w")
            
            script_lines = self.data[p].get("script", "").split("\n")
            preview_steps = []
            for line in script_lines[:4]:  
                if ":" in line:
                    cmd_type, cmd_val = line.split(":", 1)
                    cmd_type = cmd_type.strip().lower()
                    if cmd_type in preview_translate:
                        if "{" in cmd_val and "}" in cmd_val:
                            try: cmd_val = json.loads(cmd_val).get("text", cmd_val)
                            except: pass
                        preview_steps.append(f"{preview_translate[cmd_type]}: {cmd_val.strip()[:20]}")
            
            preview_string = "  →  ".join(preview_steps) if preview_steps else "Пустой макрос"
            lbl_preview = ctk.CTkLabel(meta_frame, text=preview_string, font=("Segoe UI Variable Text", 11), text_color="gray45", anchor="w")
            lbl_preview.pack(fill="x", anchor="w", pady=(1, 0))

            btn_del = ctk.CTkButton(f, text="✕", width=32, height=28, font=("Segoe UI", 11, "bold"), fg_color="transparent", hover_color="#FF453A", text_color="gray45", corner_radius=8, command=lambda ph=p: self.delete_macro(ph))
            btn_del.pack(side="right", padx=(2, 12))
            
            btn_edit = ctk.CTkButton(f, text="✎", width=32, height=28, font=("Segoe UI", 12), fg_color="#1A1D29", hover_color="#242938", text_color="#E5E7EB", corner_radius=8, command=lambda ph=p: self.open_editor(ph))
            btn_edit.pack(side="right", padx=4)
            
            UIMacroLauncher.attach_launch_button(f, p, self.data, "#17293B")
            
            for target_widget in [f, meta_frame, lbl_title, lbl_preview]:
                target_widget.bind("<Enter>", lambda e, frame=f: frame.configure(border_color=ACCENT, fg_color="#121522"))
                target_widget.bind("<Leave>", lambda e, frame=f: frame.configure(border_color=D_BORDER, fg_color=D_SIDE))

    def open_editor(self, phrase=None):
        self.list_pane.pack_forget()
        if self.action_area and self.action_area.winfo_exists():
            self.action_area.pack_forget()
            self.action_area.destroy()
            
        self.action_area = ctk.CTkScrollableFrame(self.body_editor, fg_color=D_BG, border_width=1, border_color=D_BORDER, corner_radius=14, scrollbar_button_color="#1F2335")
        for w in self.phrase_area.winfo_children(): w.destroy()
            
        self.phrase_inputs_container = ctk.CTkFrame(self.phrase_area, fg_color="transparent")
        self.phrase_inputs_container.pack(fill="x", expand=True)
        
        self.phrase_entries = []
        self.current_actions = []
        self.current_editing_key = phrase
        
        if phrase:
            for p in phrase.split('|'): self.add_phrase_input(p)
            lines_to_render = [line.strip() for line in self.data[phrase]["script"].split('\n') if ':' in line]
            
            current_indent = 0
            for line in lines_to_render:
                t, v = line.split(':', 1)
                t, v = t.strip(), v.strip()
                if t in ["end", "break"]: current_indent = max(0, current_indent - 1)
                block = ActionBlock(self.action_area, t, v, self.remove_block, self.move_block, indent=current_indent)
                self.current_actions.append(block)
                if t in ["if_active", "if_proc", "if_site", "if_var", "loop", "loop_while", "random_block"]: current_indent += 1
            self.recalculate_indents()
        else: self.add_phrase_input("")
            
        ctk.CTkButton(self.phrase_area, text="+ Добавить фразу", font=("Segoe UI Semibold", 11), fg_color="#1A1D29", hover_color=ACCENT, text_color="#E5E7EB", height=32, corner_radius=8, command=lambda: self.add_phrase_input("")).pack(pady=(10, 8), padx=10, fill="x")
        self.action_area.pack(side="right", fill="both", expand=True)
        self.edit_pane.pack(fill="both", expand=True)
        self.update_idletasks()

    def close_editor(self): self.current_editing_key = None; self.edit_pane.pack_forget(); self.list_pane.pack(fill="both", expand=True); self.refresh_list()
    
    def show_view(self, name):
        for v in self.views.values(): v.pack_forget()
        self.views[name].pack(fill="both", expand=True)
        if name == "cmds": self.refresh_list()
        self.btn_cmds.configure(text_color="#FFFFFF" if name == "cmds" else "gray60")
        self.btn_logs.configure(text_color="#FFFFFF" if name == "logs" else "gray60")
        self.btn_settings.configure(text_color="#FFFFFF" if name == "settings" else "gray60")

    # --- 🔥 НОВЫЙ МЕТОД: ДИНАМИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ ТОПИКА АЛИСЫ НА ЛЕТУ ---
    def update_alice_topic(self, new_topic):
        """ Отписывается от старого канала Алисы и мгновенно слушает новый """
        old_topic = getattr(self, 'current_alice_topic', None)
        self.current_alice_topic = new_topic
        
        if hasattr(self, 'mqtt_client') and self.mqtt_client:
            try:
                if old_topic and old_topic != "default_topic":
                    self.mqtt_client.unsubscribe(old_topic)
                self.mqtt_client.subscribe(new_topic)
                self.after(0, lambda: self.v_logs.insert("end", f"🔄 Роутинг Алисы изменен: {old_topic} ➔ {new_topic}\n"))
            except Exception as e:
                print(f"[MQTT] Ошибка динамической смены топика: {e}")

    def start_mqtt(self):
        def on_connect(cl, u, f, rc):
            cl.subscribe(SYSTEM_TOPIC) 
            
            # Подписываемся на актуальный сохранённый топик Алисы
            if getattr(self, 'current_alice_topic', None):
                cl.subscribe(self.current_alice_topic)
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            session_file = os.path.join(current_dir, "dictum_tg_session.json")
            if os.path.exists(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        phone = json.load(f).get("phone", "").strip().replace("+", "").replace(" ", "")
                        if phone: cl.subscribe(f"dictum_tg_{phone}")
                except: pass
                self.after(1000, self.sync_commands_to_bot) # Даем секунду на стабилизацию сессии

        def on_msg(cl, u, m):
            raw = m.payload.decode('utf-8').strip()
            
            if raw.startswith("tg_cmd_"):
                if raw.startswith("tg_cmd_auth_code_ans::"):
                    parts = raw.split("::")
                    phone, code, chat_id = parts[1], parts[2], parts[3]
                    if hasattr(self, 'v_settings') and self.v_settings:
                        input_phone = self.v_settings.entry_phone.get().strip().replace("+", "").replace(" ", "")
                        if input_phone == phone:
                            self.v_settings.cached_code = code
                            self.v_settings.cached_chat_id = chat_id
                            self.after(0, lambda: self.v_settings.lbl_status.configure(text="Статус: Код отправлен в Telegram бота Dictum", text_color="#007AFF"))
                elif raw.startswith("tg_cmd_auth_code_err::"):
                    parts = raw.split("::")
                    phone = parts[1]
                    if hasattr(self, 'v_settings') and self.v_settings:
                        input_phone = self.v_settings.entry_phone.get().strip().replace("+", "").replace(" ", "")
                        if input_phone == phone:
                            self.after(0, lambda: self.v_settings.lbl_status.configure(text="Статус: ❌ Номер не найден! Сначала нажмите 'Шаг 1'.", text_color="#FF453A"))
                return

            if raw.startswith("v_log_trigger::"):
                log_text = raw.split("v_log_trigger::", 1)[1]
                self.after(0, lambda: self.v_logs.insert("end", f"{log_text}\n"))
                return
                
            if m.topic.startswith("dictum_tg_") or raw.startswith("tg_run_secure::"):
                if raw.startswith("tg_run_secure::"):
                    parts = raw.split("::", 2)
                    incoming_chat_id, cmd_raw = parts[1], parts[2].lower().strip()
                else:
                    incoming_chat_id = ""
                    cmd_raw = raw.lower().strip()
                
                try:
                    session_file = os.path.join(current_dir, "dictum_tg_session.json")
                    if os.path.exists(session_file):
                        with open(session_file, "r", encoding="utf-8") as f:
                            auth_id = json.load(f).get("last_chat_id", "")
                    else: auth_id = ""
                except: auth_id = ""
                
                if incoming_chat_id and auth_id and incoming_chat_id != auth_id: return
                log_prefix = "📡 Сигнал (Telegram Защищенный)"
            elif raw.startswith("tg_run::"): return
            else:
                cmd_raw = raw.lower().strip()
                log_prefix = "📡 Сигнал (Алиса)"
                
            self.after(0, lambda: self.v_logs.insert("end", f"{log_prefix}: {cmd_raw}\n"))
            
            for key in self.data:
                if cmd_raw in [p.strip().lower() for p in key.split('|')]:
                    threading.Thread(target=DictumEngine.execute, args=(self.data[key]['script'],), daemon=True).start()
                    
        try: self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError: self.mqtt_client = mqtt.Client()
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_msg
        try: 
            self.mqtt_client.connect(BROKER, 1883, 60)
            self.mqtt_client.loop_forever()
        except Exception as mqtt_err: self.after(0, lambda: self.v_logs.insert("end", f"❌ СБОЙ MQTT: {mqtt_err}\n"))

if __name__ == "__main__":
    try:
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['pid'] != current_pid and proc.info['cmdline']:
                cmd_line = " ".join(proc.info['cmdline']).lower()
                if "main.py" in cmd_line and "python" in proc.info['name'].lower():
                    try: psutil.Process(proc.info['pid']).terminate()
                    except: pass
                if "bridge_tg.py" in cmd_line:
                    try: psutil.Process(proc.info['pid']).terminate()
                    except: pass
        time.sleep(0.2)
    except: pass

    #tg_script = os.path.join(current_dir, "bridge_tg.py")
    #if os.path.exists(tg_script):
    #    subprocess.Popen([sys.executable, tg_script], creationflags=subprocess.CREATE_NO_WINDOW)

    DictumBridge().mainloop()