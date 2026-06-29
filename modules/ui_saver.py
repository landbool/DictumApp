import os
import json

class UISaver:
    @staticmethod
    def save_macro_to_json(data_file_path, current_editing_key, ph, extracted_actions, data_cache, pre_generate_voice_fn, delete_voice_by_path_fn):
        if not ph:
            return None, "Нет фраз активации"

        new_paths = set()
        script_lines = []

        # 🔥 Обрабатываем уже пред-извлеченные данные (100% поток-безопасно)
        for act in extracted_actions:
            t = act["type"]
            if t == "key_card":
                script_lines.append(f"{act['mode']}:{act['val']}")
            elif t == "mouse_card":
                script_lines.append(f"mouse_action:{act['val']}")
            elif t == "notify_card":
                script_lines.append(f"notify:{act['title']}|{act['msg']}")
            elif t == "normal":
                cmd_type = act["cmd_type"]
                cmd_val = act["val"]
                if cmd_type == "say":
                    if cmd_val:
                        if "{" in cmd_val and "}" in cmd_val: 
                            script_lines.append(f"say:{cmd_val}")
                        else:
                            file_path = pre_generate_voice_fn(cmd_val)
                            if file_path:
                                new_paths.add(file_path)
                            script_lines.append(f"say:{json.dumps({'text': cmd_val, 'path': file_path}, ensure_ascii=False)}")
                else: 
                    script_lines.append(f"{cmd_type}:{cmd_val}")
        
        script = "\n".join(script_lines)
        new_key = "|".join(ph)
        
        target_key_for_cleanup = current_editing_key if current_editing_key else new_key
        if target_key_for_cleanup in data_cache:
            for line in data_cache[target_key_for_cleanup]["script"].split('\n'):
                if line.startswith("say:"):
                    try:
                        old_data = json.loads(line.split(':', 1)[1].strip())
                        old_path = old_data.get("path", "")
                        if old_path and old_path not in new_paths: 
                            delete_voice_by_path_fn(old_path)
                    except: pass

        if current_editing_key and current_editing_key != new_key:
            if current_editing_key in data_cache: 
                del data_cache[current_editing_key]

        data_cache[new_key] = {"script": script}
        with open(data_file_path, "w", encoding="utf-8") as f: 
            json.dump(data_cache, f, indent=4)
            
        return new_key, "Успешно сохранено"