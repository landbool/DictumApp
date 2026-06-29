import os
import sys
import winreg
import json
import webbrowser
import customtkinter as ctk
from engine import DictumEngine

class UISettingsView(ctk.CTkFrame):
    def __init__(self, master, bg_color, border_color, side_color, accent_color):
        super().__init__(master, fg_color="transparent")
        self.bg_color = bg_color
        self.border_color = border_color
        self.side_color = side_color
        self.accent_color = accent_color
        
        self.REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
        self.APP_NAME = "Dictum"
        
        self.cached_code = None
        self.cached_chat_id = None
        
        self.setup_ui()
        self.refresh_status()
        self.load_mqtt_topic()

    def setup_ui(self):
        frame = ctk.CTkFrame(self, fg_color=self.side_color, border_width=1, border_color=self.border_color, corner_radius=14)
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        lbl_title = ctk.CTkLabel(frame, text="НАСТРОЙКИ СИСТЕМЫ", font=("Segoe UI Variable Display", 16, "bold"), text_color="#FFFFFF")
        lbl_title.pack(anchor="w", padx=25, pady=(25, 15))
        
        divider = ctk.CTkFrame(frame, height=1, fg_color=self.border_color)
        divider.pack(fill="x", padx=25, pady=(0, 25))
        
        # --- КОМПОНЕНТ 1: АВТОЗАПУСК ---
        row_startup = ctk.CTkFrame(frame, fg_color="transparent")
        row_startup.pack(fill="x", padx=25, pady=(0, 20))
        
        text_container = ctk.CTkFrame(row_startup, fg_color="transparent")
        text_container.pack(side="left", fill="y")
        
        lbl_startup = ctk.CTkLabel(text_container, text="Запуск при старте Windows", font=("Segoe UI Semibold", 14), text_color="#E5E7EB")
        lbl_startup.pack(anchor="w")
        
        lbl_hint = ctk.CTkLabel(text_container, text="Автоматически запускать Dictum в свернутом режиме при включении ПК", font=("Segoe UI", 11), text_color="gray45")
        lbl_hint.pack(anchor="w", pady=(2, 0))
        
        self.switch_startup = ctk.CTkSwitch(row_startup, text="", width=45, progress_color=self.accent_color, command=self.toggle_startup)
        self.switch_startup.pack(side="right", anchor="center")
        
        if self.check_startup_status(): self.switch_startup.select()
        else: self.switch_startup.deselect()
        
        divider2 = ctk.CTkFrame(frame, height=1, fg_color=self.border_color)
        divider2.pack(fill="x", padx=25, pady=15)
        
        # --- КОМПОНЕНТ 2: АВТОРИЗАЦИЯ ТЕЛЕГРАМ ---
        lbl_tg_section = ctk.CTkLabel(frame, text="СВЯЗЬ С TELEGRAM", font=("Segoe UI Variable Display", 14, "bold"), text_color=self.accent_color)
        lbl_tg_section.pack(anchor="w", padx=25, pady=(10, 15))
        
        self.lbl_status = ctk.CTkLabel(frame, text="Статус: Проверка данных...", font=("Segoe UI Semibold", 13), text_color="gray60")
        self.lbl_status.pack(anchor="w", padx=25, pady=(0, 15))
        
        self.btn_unlink = ctk.CTkButton(frame, text="🛑 Разорвать текущую связь (Сброс)", font=("Segoe UI Semibold", 11), fg_color="#2A1717", hover_color="#FF453A", text_color="#FCE8E8", height=30, corner_radius=8, command=self.unlink_account)
        
        btn_open_bot = ctk.CTkButton(frame, text="🔗 Шаг 1. Перейти к MyDictumBot", font=("Segoe UI Semibold", 12), fg_color="#1F2438", hover_color=self.accent_color, height=35, corner_radius=8, command=lambda: webbrowser.open("https://t.me/MyDictumBot"))
        btn_open_bot.pack(anchor="w", padx=25, pady=(0, 15))
        
        row_phone = ctk.CTkFrame(frame, fg_color="transparent")
        row_phone.pack(fill="x", padx=25, pady=(0, 15))
        
        self.entry_phone = ctk.CTkEntry(row_phone, placeholder_text="Введи свой телефон, привязанный в ТГ (н-р: 79991112233)", height=35, corner_radius=8, fg_color="#090A0F", border_color=self.border_color)
        self.entry_phone.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_get_code = ctk.CTkButton(row_phone, text="📩 Шаг 2. Запросить код", font=("Segoe UI Bold", 12), fg_color="#1A1D29", hover_color=self.accent_color, height=35, width=160, corner_radius=8, command=self.request_auth_code)
        self.btn_get_code.pack(side="right")
        
        row_code = ctk.CTkFrame(frame, fg_color="transparent")
        row_code.pack(fill="x", padx=25, pady=(0, 15))
        
        self.entry_code = ctk.CTkEntry(row_code, placeholder_text="Введи цифровой код безопасности из чата бота", height=35, corner_radius=8, fg_color="#090A0F", border_color=self.border_color, justify="center")
        self.entry_code.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_verify = ctk.CTkButton(row_code, text="✅ Шаг 3. Верифицировать", font=("Segoe UI Bold", 12), fg_color="#248A3D", hover_color="#1E7A31", height=35, width=160, corner_radius=8, command=self.verify_auth_code)
        self.btn_verify.pack(side="right")

        # --- КОМПОНЕНТ 3: НАСТРОЙКА MQTT (АЛИСА / КУЗЯ) ---
        divider3 = ctk.CTkFrame(frame, height=1, fg_color=self.border_color)
        divider3.pack(fill="x", padx=25, pady=15)
        
        lbl_mqtt_section = ctk.CTkLabel(frame, text="ИНТЕГРАЦИЯ С АЛИСОЙ (MQTT топик)", font=("Segoe UI Variable Display", 14, "bold"), text_color=self.accent_color)
        lbl_mqtt_section.pack(anchor="w", padx=25, pady=(10, 15))
        
        row_mqtt = ctk.CTkFrame(frame, fg_color="transparent")
        row_mqtt.pack(fill="x", padx=25, pady=(0, 15))
        
        self.entry_topic = ctk.CTkEntry(row_mqtt, placeholder_text="Введи личный секретный топик для Домовёнка Кузи", height=35, corner_radius=8, fg_color="#090A0F", border_color=self.border_color)
        self.entry_topic.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_save_topic = ctk.CTkButton(row_mqtt, text="💾 Сохранить топик", font=("Segoe UI Bold", 12), fg_color="#248A3D", hover_color="#1E7A31", height=35, width=160, corner_radius=8, command=self.save_mqtt_topic)
        self.btn_save_topic.pack(side="right")
        
    def check_startup_status(self) -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, self.APP_NAME)
            winreg.CloseKey(key)
            return True
        except WindowsError: return False
        
    def toggle_startup(self):
        if self.switch_startup.get() == 1:
            try:
                main_script_path = os.path.abspath(sys.argv[0])
                cmd = f'"{sys.executable}" "{main_script_path}"' if main_script_path.lower().endswith('.py') else f'"{main_script_path}"'
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_WRITE)
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
            except Exception as e: print(f"[Dictum Registry] Автозапуск сбой: {e}")
        else:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_WRITE)
                winreg.DeleteValue(key, self.APP_NAME)
                winreg.CloseKey(key)
            except WindowsError: pass
            
    def refresh_status(self):
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        session_file = os.path.join(current_dir, "dictum_tg_session.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    phone = data.get("phone", "Зарегистрирован")
                    self.lbl_status.configure(text=f"Статус: ✅ Синхронизировано с Telegram: +{phone}", text_color="#34C759")
                    self.btn_unlink.pack(anchor="w", padx=25, pady=(0, 15))
                    if phone != "Зарегистрирован":
                        self.entry_phone.delete(0, 'end')
                        self.entry_phone.insert(0, phone)
                    return
            except: pass
        self.lbl_status.configure(text="Статус: ❌ Синхронизация отсутствует", text_color="#FF453A")
        self.btn_unlink.pack_forget()

    def unlink_account(self):
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        session_file = os.path.join(current_dir, "dictum_tg_session.json")
        
        chat_id = None
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    chat_id = json.load(f).get("last_chat_id")
            except: pass
            
        if chat_id:
            main_app = DictumEngine.main_gui_ref
            if main_app and hasattr(main_app, 'mqtt_client') and main_app.mqtt_client:
                from main import SYSTEM_TOPIC
                main_app.mqtt_client.publish(SYSTEM_TOPIC, f"tg_cmd_unlink::{chat_id}")
        
        if os.path.exists(session_file):
            try: os.remove(session_file)
            except: pass
            
        self.entry_code.delete(0, 'end')
        self.refresh_status()
        
    def request_auth_code(self):
        phone = self.entry_phone.get().strip().replace("+", "").replace(" ", "")
        if not phone:
            self.lbl_status.configure(text="Статус: ⚠️ Укажите номер телефона", text_color="#FF9500")
            return
        
        main_app = DictumEngine.main_gui_ref
        if main_app and hasattr(main_app, 'mqtt_client') and main_app.mqtt_client:
            self.lbl_status.configure(text="Статус: ⏳ Запрашиваем секретный код у бота...", text_color="#007AFF")
            from main import SYSTEM_TOPIC
            main_app.mqtt_client.publish(SYSTEM_TOPIC, f"tg_cmd_auth_code_req::{phone}")
        else:
            self.lbl_status.configure(text="Статус: ❌ Отсутствует подключение к брокеру!", text_color="#FF453A")
            
    def verify_auth_code(self):
        entered = self.entry_code.get().strip()
        if not entered: return
        
        if self.cached_code and entered == self.cached_code:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            session_file = os.path.join(current_dir, "dictum_tg_session.json")
            try:
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump({"last_chat_id": str(self.cached_chat_id), "phone": self.entry_phone.get().strip().replace("+", "")}, f, indent=4)
                
                main_app = DictumEngine.main_gui_ref
                if main_app and hasattr(main_app, 'mqtt_client') and main_app.mqtt_client:
                    from main import SYSTEM_TOPIC
                    main_app.mqtt_client.publish(SYSTEM_TOPIC, f"tg_cmd_auth_success::{self.cached_chat_id}")
                
                self.refresh_status()
                self.entry_code.delete(0, 'end')
            except Exception as ex:
                print(f"Ошибка сохранения сессии: {ex}")
        else:
            self.lbl_status.configure(text="Статус: ❌ Неверный одноразовый код!", text_color="#FF453A")

    def load_mqtt_topic(self):
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mqtt_file = os.path.join(current_dir, "dictum_mqtt_config.json")
        if os.path.exists(mqtt_file):
            try:
                with open(mqtt_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    topic = data.get("mqtt_topic", "")
                    self.entry_topic.delete(0, 'end')
                    self.entry_topic.insert(0, topic)
            except Exception as e:
                print(f"Ошибка чтения MQTT конфига: {e}")

    def save_mqtt_topic(self):
        topic = self.entry_topic.get().strip()
        if not topic:
            return
        
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mqtt_file = os.path.join(current_dir, "dictum_mqtt_config.json")
        try:
            with open(mqtt_file, "w", encoding="utf-8") as f:
                json.dump({"mqtt_topic": topic}, f, indent=4)
            
            # 🔥 НАТИВНЫЙ ПЕРЕХВАТ: Дергаем метод главного ядра для мгновенного переподключения топика
            main_app = DictumEngine.main_gui_ref
            if main_app and hasattr(main_app, 'update_alice_topic'):
                main_app.update_alice_topic(topic)
            
            self.btn_save_topic.configure(fg_color="#34C759", text="✅ Успешно сохранено")
            self.after(2000, lambda: self.btn_save_topic.configure(fg_color="#248A3D", text="💾 Сохранить топик"))
        except Exception as e:
            print(f"Ошибка сохранения MQTT конфига: {e}")