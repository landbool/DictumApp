import customtkinter as ctk

class UISoundCard(ctk.CTkFrame):
    def __init__(self, master, value, fix_layout_callback, fix_layout_string_fn, add_context_menu_fn):
        super().__init__(master, fg_color="transparent")
        self.fix_layout_callback = fix_layout_callback

        # СЕКРЕТНЫЙ ТРЮК: Делаем скрытый виджет, из которого оригинальный main.py без крашей заберёт данные!
        self.val_entry = ctk.CTkEntry(self)

        # Вытаскиваем чистую строку параметров, отсекая двоеточия и префиксы, если они есть
        raw_string = str(value).strip()
        if ":" in raw_string:
            raw_string = raw_string.split(":", 1)[1].strip()
        if raw_string.startswith("sound_control"):
            raw_string = raw_string.replace("sound_control", "", 1).strip().lstrip('|').strip()

        # Разбираем подрежим и значение по вертикальной палочке
        parts = [x.strip() for x in raw_string.split('|')] if '|' in raw_string else [raw_string]
        s_mode = parts[0] if len(parts) > 0 and parts[0] else "volume_set"
        s_val = parts[1] if len(parts) > 1 else ""

        # Карта соответствий графических подрежимов под ядро движка
        self.sound_dropdown_modes = {
            "Установить громкость": "volume_set",
            "Прибавить громкость": "volume_add", 
            "Сменить устройство": "audio_switch"
        }
        inv_sound_modes = {v: k for k, v in self.sound_dropdown_modes.items()}

        # 1. Выпадающий список подрежимов
        self.drop_s = ctk.CTkOptionMenu(
            self, 
            values=list(self.sound_dropdown_modes.keys()), 
            width=180, 
            height=35, 
            fg_color="#000", 
            button_color="#2C2C2E", 
            command=lambda c: self._sync_to_hidden_entry()
        )
        self.drop_s.set(inv_sound_modes.get(s_mode, "Установить громкость"))
        self.drop_s.pack(side="left", padx=2)

        # 2. Поле ввода значения
        self.visible_entry = ctk.CTkEntry(
            self, 
            placeholder_text="Введи значение (н-р: 50 для громкости или 2 для шага)...", 
            height=35, 
            font=("Segoe UI", 12)
        )
        if s_val: 
            self.visible_entry.insert(0, str(s_val))
        self.visible_entry.pack(side="left", padx=5, fill="x", expand=True)
        add_context_menu_fn(self.visible_entry)
        
        # Привязываем триггеры мгновенного обновления скрытого поля
        self.visible_entry.bind("<KeyRelease>", lambda e: self._sync_to_hidden_entry())
        
        # Первичная синхронизация при создании карточки
        self._sync_to_hidden_entry()

    def _sync_to_hidden_entry(self):
        """ Упаковывает данные в скрытый entry для оригинального сохранения main.py """
        mode = self.sound_dropdown_modes[self.drop_s.get()]
        val = self.visible_entry.get().strip()
        combined_string = f"{mode} | {val}"
        
        self.val_entry.delete(0, 'end')
        self.val_entry.insert(0, combined_string)
        self.fix_layout_callback()

    def get_values(self):
        """ Нативный кортеж на случай прямых вызовов """
        mode = self.sound_dropdown_modes[self.drop_s.get()]
        val = self.visible_entry.get().strip()
        return mode, val