import threading
from engine import DictumEngine

class UIMacroLauncher:
    @staticmethod
    def attach_launch_button(master_frame, phrase_key, data_cache, accent_color):
        """ 
        Добавляет красивую кнопку запуска макроса прямо на плашку в главном списке
        """
        import customtkinter as ctk
        
        def _run_local_macro():
            if phrase_key in data_cache and "script" in data_cache[phrase_key]:
                script_code = data_cache[phrase_key]["script"]
                # Запускаем выполнение макроса в фоновом потоке, чтобы GUI Студии не зависал!
                threading.Thread(target=DictumEngine.execute, args=(script_code,), daemon=True).start()

        # Создаем зелёную кнопку "▶" на плашке макроса
        btn_run = ctk.CTkButton(
            master_frame, 
            text="▶", 
            width=40, 
            height=32, 
            fg_color="#28A745", 
            hover_color="#218838",
            font=("Segoe UI Bold", 14),
            command=_run_local_macro
        )
        # Упаковываем её справа, сразу перед кнопкой редактирования "✎"
        btn_run.pack(side="right", padx=5)