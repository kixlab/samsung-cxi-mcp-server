
from pathlib import Path

# 경로 설정
TARGET_DIR = Path("/home/seooyxx/kixlab/samsung-cxi-mcp-server/dataset/postprocess/modification_gen/without_oracle/task-1")
OLD_STRING = "gpt-4.1-2025-04-14"
NEW_STRING = "gpt-4.1"

# 모든 하위 폴더 대상
for folder in sorted(TARGET_DIR.iterdir()):
    if folder.is_dir() and OLD_STRING in folder.name:
        # 내부 파일 이름 변경
        for file in folder.iterdir():
            if OLD_STRING in file.name:
                new_file = file.parent / file.name.replace(OLD_STRING, NEW_STRING)
                file.rename(new_file)
                print(f"[RENAMED FILE] {file.name} → {new_file.name}")

        # 폴더 이름 변경
        new_folder = folder.parent / folder.name.replace(OLD_STRING, NEW_STRING)
        folder.rename(new_folder)
        print(f"[RENAMED FOLDER] {folder.name} → {new_folder.name}")
