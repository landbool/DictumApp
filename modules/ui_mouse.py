import os
import ctypes
import pyautogui
import customtkinter as ctk
from tkinter import Toplevel

class UIMouseCard(ctk.CTkFrame):
    def __init__(self, master, value, sync_callback, add_context_menu_fn):
        super().__init__(master, fg_color="transparent")
        self.sync_callback = sync_callback
        self.add_context_menu_fn = add_context_menu_fn
        
        self.click_sub_types = {"Нажать": "click", "Зажать": "down", "Отжать": "up", "Длинный клик": "long"}
        self.mouse_btns = {"Левая кнопка": "left", "Правая кнопка": "right", "Средняя кнопка": "middle", "X1 кнопка": "x1", "X2 кнопка": "x2"}
        self.screen_modes = {"всех экранах": "all_screens", "активном окне": "active_window"}

        parts = [x.strip() for x in value.split('|')] if value and '|' in str(value) else [value]
        self.current_sub_mode = parts[0] if len(parts) > 0 and parts[0] else "mouse_click"
        param1 = parts[1] if len(parts) > 1 else ""
        param2 = parts[2] if len(parts) > 2 else ""

        self.mouse_main_modes = {
            "Кликнуть": "mouse_click", "Навести мышь на картинку": "mouse_image_search", 
            "Передвинуть в точку": "mouse_move", "Подвинуть курсор": "mouse_move_relative", "Каракуля": "mouse_move_curve"
        }
        inv_main_modes = {v: k for k, v in self.mouse_main_modes.items()}

        self.drop_main = ctk.CTkOptionMenu(self, values=list(self.mouse_main_modes.keys()), width=180, height=35, fg_color="#000", button_color="#2C2C2E", command=self._on_main_dropdown_changed)
        self.drop_main.set(inv_main_modes.get(self.current_sub_mode, "Кликнуть"))
        self.drop_main.pack(side="left", padx=2)

        self.sub_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sub_frame.pack(side="left", fill="x", expand=True)

        self.cached_x, self.cached_y = "", ""
        self.cached_scr_mode = "all_screens"
        if param1 and ',' in param1:
            try: self.cached_x, self.cached_y = [c.strip() for c in param1.split(',', 1)]
            except: pass
        if param2: 
            self.cached_scr_mode = param2

        self._build_sub_interface(self.current_sub_mode, param1, param2)

    def get_values(self):
        """ Безопасный сбор данных на основе текущего активного режима """
        mode = self.mouse_main_modes[self.drop_main.get()]
        if mode == "mouse_click":
            c_type = self.click_sub_types.get(self.drop_c_type.get(), "click")
            c_btn = self.mouse_btns.get(self.drop_c_btn.get(), "left")
            return f"mouse_click | {c_type} | {c_btn}"
        elif mode == "mouse_image_search":
            val = self.entry_img_template.get().strip() if hasattr(self, 'entry_img_template') and self.entry_img_template.winfo_exists() else ""
            # Принудительно выпрямляем косые черты, чтобы OneDrive и кириллица не ломали кодировку
            val = val.replace('\\', '/')
            return f"mouse_image_search | {val}"
        elif mode == "mouse_move":
            x = self.entry_x.get().strip() if hasattr(self, 'entry_x') and self.entry_x.winfo_exists() else "0"
            y = self.entry_y.get().strip() if hasattr(self, 'entry_y') and self.entry_y.winfo_exists() else "0"
            scr = self.screen_modes.get(self.drop_scr.get(), "all_screens")
            return f"mouse_move | {x},{y} | {scr}"
        else:
            x = self.entry_x.get().strip() if hasattr(self, 'entry_x') and self.entry_x.winfo_exists() else "0"
            y = self.entry_y.get().strip() if hasattr(self, 'entry_y') and self.entry_y.winfo_exists() else "0"
            return f"{mode} | {x},{y}"

    def _on_main_dropdown_changed(self, choice):
        self.current_sub_mode = self.mouse_main_modes[choice]
        self._build_sub_interface(self.current_sub_mode, "", "")
        self.sync_callback()

    def _build_sub_interface(self, sub_mode, param1, param2):
        for w in self.sub_frame.winfo_children(): w.destroy()

        if sub_mode == "mouse_click":
            inv_click_sub = {v: k for k, v in self.click_sub_types.items()}
            inv_mouse_btns = {v: k for k, v in self.mouse_btns.items()}
            
            c_type = param1 if param1 in self.click_sub_types.values() else "click"
            c_btn = param2 if param2 in self.mouse_btns.values() else "left"

            self.drop_c_type = ctk.CTkOptionMenu(self.sub_frame, values=list(self.click_sub_types.keys()), width=110, height=35, fg_color="#000", button_color="#2C2C2E", command=lambda c: self.sync_callback())
            self.drop_c_type.set(inv_click_sub.get(c_type, "Нажать"))
            self.drop_c_type.pack(side="left", padx=2)

            self.drop_c_btn = ctk.CTkOptionMenu(self.sub_frame, values=list(self.mouse_btns.keys()), width=140, height=35, fg_color="#000", button_color="#2C2C2E", command=lambda c: self.sync_callback())
            self.drop_c_btn.set(inv_mouse_btns.get(c_btn, "Левая кнопка"))
            self.drop_c_btn.pack(side="left", padx=2)

        elif sub_mode == "mouse_image_search":
            self.entry_img_template = ctk.CTkEntry(self.sub_frame, placeholder_text="Выбери скриншот кнопки через обзор...", height=35, font=("Segoe UI", 12))
            if param1: self.entry_img_template.insert(0, param1)
            self.entry_img_template.pack(side="left", fill="x", expand=True, padx=5)
            self.add_context_menu_fn(self.entry_img_template)
            
            btn_browse_img = ctk.CTkButton(self.sub_frame, text="📂 Обзор", width=80, height=35, font=("Segoe UI Bold", 12), fg_color="#2C2C2E", hover_color="#007AFF", command=self._browse_image)
            btn_browse_img.pack(side="left", padx=2)

        else:
            inv_screens = {v: k for k, v in self.screen_modes.items()}

            if sub_mode == "mouse_move":
                self.drop_scr = ctk.CTkOptionMenu(self.sub_frame, values=list(self.screen_modes.keys()), width=130, height=35, fg_color="#000", button_color="#2C2C2E", command=lambda c: self.sync_callback())
                self.drop_scr.set(inv_screens.get(self.cached_scr_mode, "всех экранах"))
                self.drop_scr.pack(side="left", padx=2)

            ctk.CTkLabel(self.sub_frame, text=" X:", font=("Consolas", 12), text_color="gray50").pack(side="left", padx=(5,0))
            self.entry_x = ctk.CTkEntry(self.sub_frame, placeholder_text="0", width=60, height=35, font=("Consolas", 13), justify="center")
            if self.cached_x: self.entry_x.insert(0, self.cached_x)
            self.entry_x.pack(side="left", padx=2)
            self.entry_x.bind("<KeyRelease>", lambda e: self.sync_callback())
            
            ctk.CTkLabel(self.sub_frame, text="Y:", font=("Consolas", 12), text_color="gray50").pack(side="left")
            self.entry_y = ctk.CTkEntry(self.sub_frame, placeholder_text="0", width=60, height=35, font=("Consolas", 13), justify="center")
            if self.cached_y: self.entry_y.insert(0, self.cached_y)
            self.entry_y.pack(side="left", padx=2)
            self.entry_y.bind("<KeyRelease>", lambda e: self.sync_callback())
            
            self.aim_btn = ctk.CTkButton(self.sub_frame, text="▲ Прицел", width=75, height=35, font=("Segoe UI Bold", 12), fg_color="#2C2C2E", hover_color="#007AFF", command=self.capture_coordinates)
            self.aim_btn.pack(side="left", padx=5)

    def _browse_image(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(title="Выберите картинку-шаблон для поиска", filetypes=[("Изображения", "*.png *.jpg *.jpeg"), ("Все файлы", "*.*")])
        if file_path:
            file_path = file_path.replace('\\', '/')
            self.entry_img_template.delete(0, 'end')
            self.entry_img_template.insert(0, file_path)
            self.sync_callback()

    def capture_coordinates(self):
        self.aim_btn.configure(text="...", fg_color="#007AFF")
        v_left = ctypes.windll.user32.GetSystemMetrics(76)
        v_top = ctypes.windll.user32.GetSystemMetrics(77)
        v_width = ctypes.windll.user32.GetSystemMetrics(78)
        v_height = ctypes.windll.user32.GetSystemMetrics(79)
        
        overlay = Toplevel(self.winfo_toplevel())
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.01)
        overlay.config(cursor="cross")
        overlay.geometry(f"{v_width}x{v_height}+{v_left}+{v_top}")
        overlay.overrideredirect(True)

        def _on_overlay_click(event):
            x, y = pyautogui.position()
            overlay.destroy()
            if self.entry_x.winfo_exists():
                self.entry_x.delete(0, 'end')
                self.entry_x.insert(0, str(x))
            if self.entry_y.winfo_exists():
                self.entry_y.delete(0, 'end')
                self.entry_y.insert(0, str(y))
            self.sync_callback()
            self.aim_btn.configure(text="▲ Прицел", fg_color="#2C2C2E")

        overlay.bind("<Button-1>", _on_overlay_click)