import customtkinter as ctk
import ctypes
from ctypes import wintypes

# Описываем структуру данных WinAPI для низкоуровневого перехвата клавиш
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

# Сигнатура функции обратного вызова хука Windows
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# 🔥 СТРОГАЯ НАСТРОЙКА ТИПОВ (Предотвращает усечение 64-битных указателей)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p

user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = ctypes.c_void_p


class UIKeyboardCard(ctk.CTkFrame):
    def __init__(self, master, value, fix_layout_callback, fix_layout_string_fn, add_context_menu_fn):
        super().__init__(master, fg_color="transparent")
        self.fix_layout_callback = fix_layout_callback
        self.fix_layout_string_fn = fix_layout_string_fn
        self.recorded_sequence = []
        
        # Переменные для WinAPI хука
        self.windows_hook = None
        self._hook_proc_ref = None

        self.LAYOUT_MAP = {
            'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
            'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
            'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.', '.': '/'
        }

        parts = [x.strip() for x in str(value).split('|')] if value and '|' in str(value) else [str(value).strip()]
        self.current_sub_mode = parts[0] if len(parts) > 0 and parts[0] else "key"
        k_val = parts[1] if len(parts) > 1 else ""

        self.key_dropdown_modes = {
            "Нажать комбинацию": "key", "Зажать клавишу": "key_down", 
            "Отпустить клавишу": "key_up", "Длинный клик (1.5с)": "key_long"
        }
        inv_key_modes = {v: k for k, v in self.key_dropdown_modes.items()}

        self.drop_k = ctk.CTkOptionMenu(self, values=list(self.key_dropdown_modes.keys()), width=180, height=35, fg_color="#000", button_color="#2C2C2E", command=lambda c: self.fix_layout_callback())
        self.drop_k.set(inv_key_modes.get(self.current_sub_mode, "Нажать комбинацию"))
        self.drop_k.pack(side="left", padx=2)

        self.entry_key_str = ctk.CTkEntry(self, placeholder_text="Впиши клавиши (например: ctrl+v) или нажми Запись...", height=35, font=("Segoe UI", 12))
        if k_val: self.entry_key_str.insert(0, k_val.lower().strip())
        self.entry_key_str.pack(side="left", padx=5, fill="x", expand=True)
        add_context_menu_fn(self.entry_key_str)

        self.entry_key_str.bind("<KeyRelease>", self._clean_input_layout)

        self.rec_switch = ctk.CTkCheckBox(self, text="🔴 Запись", width=80, height=28, command=self.toggle_key_recording)
        self.rec_switch.pack(side="right", padx=5)

        self.bind("<Destroy>", lambda e: self.stop_hardware_hook())

    def _clean_input_layout(self, event=None):
        txt = self.entry_key_str.get()
        if txt and txt != "[Запись запущена...]":
            fixed = "".join([self.LAYOUT_MAP.get(c, c) for c in txt.lower()])
            if txt != fixed:
                pos = self.entry_key_str.index('insert')
                self.entry_key_str.delete(0, 'end')
                self.entry_key_str.insert(0, fixed)
                self.entry_key_str.icursor(pos)
        self.fix_layout_callback()

    def get_values(self):
        mode = self.key_dropdown_modes[self.drop_k.get()]
        val = self.entry_key_str.get().strip().lower()
        if val == "[запись запущена...]": 
            val = ""
        fixed_val = "".join([self.LAYOUT_MAP.get(c, c) for c in val])
        return mode, fixed_val

    def toggle_key_recording(self):
        if self.rec_switch.get() == 1:
            self.entry_key_str.delete(0, 'end')
            self.entry_key_str.insert(0, "[Запись запущена...]")
            self.recorded_sequence.clear()
            self.start_hardware_hook()
        else:
            self.stop_hardware_hook()
            if self.entry_key_str.get() == "[Запись запущена...]": 
                self.entry_key_str.delete(0, 'end')

    def _hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0:
            try:
                kbd = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kbd.vkCode
                
                VK_TO_NAME = {
                    0x10: 'shift', 0x11: 'ctrl', 0x12: 'alt',
                    0x5B: 'win', 0x5C: 'win',
                    0x0D: 'enter', 0x08: 'backspace', 0x09: 'tab',
                    0x20: 'space', 0x2E: 'delete', 0x1B: 'escape',
                    0x25: 'left', 0x26: 'up', 0x27: 'right', 0x28: 'down',
                    0x70: 'f1', 0x71: 'f2', 0x72: 'f3', 0x73: 'f4',
                    0x74: 'f5', 0x75: 'f6', 0x76: 'f7', 0x77: 'f8',
                    0x78: 'f9', 0x79: 'f10', 0x7A: 'f11', 0x7B: 'f12'
                }
                
                k = ""
                if vk in VK_TO_NAME:
                    k = VK_TO_NAME[vk]
                elif 0x41 <= vk <= 0x5A:
                    k = chr(vk).lower()
                elif 0x30 <= vk <= 0x39:
                    k = chr(vk)
                
                if k:
                    is_down = wParam in [0x0100, 0x0104]
                    is_up = wParam in [0x0101, 0x0105]
                    
                    if is_down:
                        if k not in self.recorded_sequence:
                            self.recorded_sequence.append(k)
                            combination = "+".join(self.recorded_sequence)
                            fixed_combo = "".join([self.LAYOUT_MAP.get(c, c) for c in combination.lower()])
                            
                            if self.entry_key_str.winfo_exists():
                                self.entry_key_str.delete(0, 'end')
                                self.entry_key_str.insert(0, fixed_combo)
                                self.fix_layout_callback()
                    elif is_up:
                        if k in self.recorded_sequence: 
                            self.recorded_sequence.remove(k)
            except Exception as e:
                print(f"Ошибка чтения кодов WinAPI: {e}")
                
            return 1  # Блокируем клавишу для Windows
            
        return user32.CallNextHookEx(self.windows_hook, nCode, wParam, lParam)

    def start_hardware_hook(self):
        self.stop_hardware_hook()
        self._hook_proc_ref = HOOKPROC(self._hook_callback)
        
        # 13 означает WH_KEYBOARD_LL
        self.windows_hook = user32.SetWindowsHookExW(
            13, 
            self._hook_proc_ref, 
            kernel32.GetModuleHandleW(None), 
            0
        )

    def stop_hardware_hook(self):
        if self.windows_hook is not None:
            try:
                user32.UnhookWindowsHookEx(self.windows_hook)
            except:
                pass
            self.windows_hook = None
            self._hook_proc_ref = None
        self.recorded_sequence.clear()