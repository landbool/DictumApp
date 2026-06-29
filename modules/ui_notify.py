import customtkinter as ctk

class UINotifyCard(ctk.CTkFrame):
    def __init__(self, master, value, sync_callback, add_context_menu_fn):
        super().__init__(master, fg_color="transparent")
        self.sync_callback = sync_callback

        # Разбираем существующее значение (если оно есть)
        title_val, msg_val = "", ""
        raw_string = str(value).strip()
        
        if "|" in raw_string:
            parts = [x.strip() for x in raw_string.split("|", 1)]
            title_val = parts[0]
            msg_val = parts[1] if len(parts) > 1 else ""
        else:
            # Если разделителя нет, считаем всё текстом сообщения
            msg_val = raw_string

        # Поле для Заголовка
        self.entry_title = ctk.CTkEntry(self, placeholder_text="Заголовок уведомления", height=35, font=("Segoe UI", 12))
        self.entry_title.insert(0, title_val)
        self.entry_title.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_title.bind("<KeyRelease>", lambda e: self.sync_callback())
        add_context_menu_fn(self.entry_title)

        # Поле для Текста сообщения
        self.entry_msg = ctk.CTkEntry(self, placeholder_text="Текст сообщения...", height=35, font=("Segoe UI", 12))
        self.entry_msg.insert(0, msg_val)
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_msg.bind("<KeyRelease>", lambda e: self.sync_callback())
        add_context_menu_fn(self.entry_msg)

    def get_values(self):
        """ Возвращает заголовок и текст для сохранения """
        return self.entry_title.get().strip(), self.entry_msg.get().strip()