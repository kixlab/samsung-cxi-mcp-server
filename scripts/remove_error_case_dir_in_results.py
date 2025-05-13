import os
from pathlib import Path

# === CONFIGURATION ===
ROOT_RESULTS_DIR = Path(f"/home/seooyxx/kixlab/samsung-cxi-mcp-server/dataset/results/modification_gen")
ROOT_POSTPROCESS_DIR = Path(f"/home/seooyxx/kixlab/samsung-cxi-mcp-server/dataset/postprocess/modification_gen/without_oracle")

ERROR_FILE_NAMES = [
    "retry_step_minus_1.txt",
    "node_only_no_assets.txt",
    "missing_both_json_and_assets.txt",
]

# === HELPERS ===
def delete_result_folders(task: str, model: str):
    error_txt_dir = ROOT_POSTPROCESS_DIR / task / "without_oracle" / model
    result_target_dir = ROOT_RESULTS_DIR / task / "without_oracle" / model

    deleted = []

    for error_file in ERROR_FILE_NAMES:
        txt_path = error_txt_dir / error_file
        if not txt_path.exists():
            print(f"[SKIP] {txt_path} does not exist.")
            continue

        with open(txt_path) as f:
            expr_names = [line.strip() for line in f if line.strip()]

        for expr_name in expr_names:
            target_path = result_target_dir / expr_name
            if target_path.exists() and target_path.is_dir():
                try:
                    os.system(f"rm -rf '{target_path}'")
                    deleted.append(target_path)
                except Exception as e:
                    print(f"[ERROR] Failed to delete {target_path}: {e}")
            else:
                print(f"[MISS] {target_path} not found.")

    print(f"[DONE] Deleted {len(deleted)} folders under {result_target_dir}")


# === EXAMPLE USAGE ===
if __name__ == "__main__":
    # 예: task-1 / gpt-4o 만 삭제할 경우
    # delete_result_folders("task-1", "gpt-4o")

    # 여러 모델 일괄 삭제하려면 반복 처리도 가능:
    for task in ["task-1", "task-3"]:
        for model in ["gpt-4o", "gpt-4.1", "gemini", "claude-3.5-sonnet"]:
            delete_result_folders(task, model)
