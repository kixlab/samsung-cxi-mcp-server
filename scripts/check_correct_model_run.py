import json
from pathlib import Path
import shutil

# === 설정 ===
BASE_DIR = Path("/home/seooyxx/kixlab/samsung-cxi-mcp-server/dataset/postprocess/modification_gen/without_oracle/task-3/without_oracle/gpt-4o")
DEST_DIR = Path("/home/seooyxx/kixlab/samsung-cxi-mcp-server/dataset/final_results/modification_gen/without_oracle/task-3")

INVALID_FOLDER_INFO = []  # (folder_path, correct_model_name)

# === Step 1: 잘못된 model_name 탐색 ===
for json_path in BASE_DIR.rglob("*-json-response.json"):
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        model_name = data.get("messages", [])[1]["content"]["data"]["response_metadata"].get("model_name", "")
        if not model_name.startswith("gpt-4o"):
            print(f"[INVALID] {model_name} in {json_path}")
            INVALID_FOLDER_INFO.append((json_path.parent, model_name))
    except Exception as e:
        print(f"[ERROR] Failed to process {json_path}: {e}")

# === Step 2: 폴더 및 파일 이름만 변경, 내용은 유지 ===
for folder, correct_model_name in INVALID_FOLDER_INFO:
    try:
        parent = folder.parent
        new_folder_name = folder.name.replace("gpt-4o", correct_model_name)
        new_folder_path = parent / new_folder_name

        # 폴더 이름 변경
        folder.rename(new_folder_path)
        print(f"[RENAMED] Folder: {folder.name} → {new_folder_name}")

        # 내부 파일 이름들도 변경
        for file in new_folder_path.glob("*gpt-4o*.json"):
            new_file_name = file.name.replace("gpt-4o", correct_model_name)
            new_file_path = file.parent / new_file_name
            file.rename(new_file_path)
            print(f"[RENAMED] File: {file.name} → {new_file_name}")

        # 최종 위치로 이동
        final_dest = DEST_DIR / new_folder_path.name
        if final_dest.exists():
            print(f"[SKIPPED] {final_dest} already exists")
            continue

        shutil.move(str(new_folder_path), str(final_dest))
        print(f"[MOVED] {new_folder_path} → {final_dest}")

    except Exception as e:
        print(f"[ERROR] Failed to process {folder}: {e}")
