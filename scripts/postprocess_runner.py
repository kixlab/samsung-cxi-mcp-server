import json
import requests
from pathlib import Path
from PIL import Image, ImageDraw
from tqdm import tqdm

# === CONFIG ===
# TASK_IDS = ["task-1", "task-3"]
# MODEL_DIRS = ["gpt-4o", "gpt-4.1", "claude-3.5-sonnet", "gemini"]

# TASK_IDS = ["task-1", "task-3"]
# MODEL_DIRS = ["gpt-4.1", "claude-3.5-sonnet", "gemini"]

TASK_IDS = ["task-3"]
MODEL_DIRS = ["gpt-4o"]


# === TRACKING ===
RETRY_LIST = []
NODE_ONLY_LIST = []
MISSING_ALL_LIST = []
RENDERED_OUTPUTS = []
THUMBNAIL_EXIST_LIST = []

# === UTILS ===
def get_step_count(path: Path) -> int:
    try:
        with open(path) as f:
            return json.load(f).get("step_count", -1)
    except:
        return -1

def render_canvas_with_assets(node_json_path: Path, asset_dir: Path, output_img_path: Path):
    """Figma node hierarchy 기반으로 assets를 붙여 정확히 캔버스 복원"""
    with open(node_json_path) as f:
        node_data = json.load(f)

    elements = []

    def collect_elements(node):
        if isinstance(node, dict):
            bounds = node.get("absoluteRenderBounds")
            node_id = node.get("id")
            if bounds and node_id:
                elements.append({
                    "id": node_id,
                    "bbox": bounds
                })
            for child in node.get("children", []):
                collect_elements(child)

    collect_elements(node_data.get("document", {}))

    if not elements:
        print(f"[WARNING] No renderable elements in {node_json_path}")
        return

    # 캔버스 영역 계산
    min_x = min(e["bbox"]["x"] for e in elements)
    min_y = min(e["bbox"]["y"] for e in elements)
    max_x = max(e["bbox"]["x"] + e["bbox"]["width"] for e in elements)
    max_y = max(e["bbox"]["y"] + e["bbox"]["height"] for e in elements)
    canvas_width = int(max_x - min_x)
    canvas_height = int(max_y - min_y)

    # 투명 배경 위에 PNG layer 붙이기
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 0))

    for el in elements:
        node_id = el["id"]
        img_path = asset_dir / f"{node_id}.png"
        if img_path.exists():
            try:
                img = Image.open(img_path).convert("RGBA")
                x = int(el["bbox"]["x"] - min_x)
                y = int(el["bbox"]["y"] - min_y)
                canvas.paste(img, (x, y), mask=img)
            except Exception as e:
                print(f"[ERROR] Cannot paste {img_path}: {e}")
        else:
            print(f"[MISSING] No asset image for node {node_id}")

    # 흰 배경으로 최종 저장
    final = Image.new("RGB", canvas.size, (255, 255, 255))
    final.paste(canvas, mask=canvas.split()[3])
    final.save(output_img_path)


# === MAIN PROCESSING ===
def process_postprocess_dir(task_id, model_dir):
    POSTPROCESS_DIR = Path(f"/home/seooyxx/kixlab/samsung-cxi-mcp-server/dataset/postprocess/modification_gen/without_oracle/{task_id}/without_oracle/{model_dir}").expanduser()
    RETRY_LIST = []
    NODE_ONLY_LIST = []
    MISSING_ALL_LIST = []
    RENDERED_OUTPUTS = []

    expr_dirs = [d for d in POSTPROCESS_DIR.iterdir() if d.is_dir()]
    total = len(expr_dirs)

    for expr_dir in tqdm(expr_dirs, desc=f"Processing Experiments [{task_id}/{model_dir}]"):
        expr_name = expr_dir.name
        step_path = expr_dir / f"{expr_name}-step-count.json"
        step_count = get_step_count(step_path)

        if step_count == -1:
            RETRY_LIST.append(expr_name)
            continue

        node_json = expr_dir / f"{expr_name}.json"
        asset_dir = expr_dir / "assets"
        output_img_path = expr_dir / f"{expr_name}.png"

        if node_json.exists() and asset_dir.exists():
            render_canvas_with_assets(node_json, asset_dir, output_img_path)
            RENDERED_OUTPUTS.append(expr_name)

        elif node_json.exists():
            NODE_ONLY_LIST.append(expr_name)
            with open(node_json) as f:
                data = json.load(f)
            url = data.get("thumbnailUrl")
            if url:
                try:
                    response = requests.get(url)
                    with open(output_img_path, "wb") as out:
                        out.write(response.content)
                    THUMBNAIL_EXIST_LIST.append(expr_name)
                except Exception as e:
                    print(f"[ERROR] Thumbnail download failed for {expr_name}: {e}")
            else:
                print(f"[WARNING] No thumbnailUrl for {expr_name}")

        else:
            MISSING_ALL_LIST.append(expr_name)
            resp_path = expr_dir / f"{expr_name}-json-response.json"
            if resp_path.exists():
                with open(resp_path) as f:
                    print(f"[INFO] {expr_name} json-response exists")
            else:
                print(f"[MISSING] No response.json for {expr_name}")

    print(f"\n=== SUMMARY for {task_id}/{model_dir} ===")
    print(f"Total experiments: {total}")
    print(f"- StepCount == -1: {len(RETRY_LIST)}")
    # print(f"- Node JSON only (no assets): {len(NODE_ONLY_LIST)}")
    print(f"- Missing both node json & assets: {len(MISSING_ALL_LIST)}")
    print(f"- Thumbnail export list: {len(THUMBNAIL_EXIST_LIST)}")
    print(f"- Rendered: {len(RENDERED_OUTPUTS)}")
    print(f"- Sum: {len(RETRY_LIST) + len(THUMBNAIL_EXIST_LIST) + len(MISSING_ALL_LIST) + len(RENDERED_OUTPUTS)}")

    assert total == (len(RETRY_LIST) + len(THUMBNAIL_EXIST_LIST) + len(MISSING_ALL_LIST) + len(RENDERED_OUTPUTS)), "Mismatch in total count!"

    with open(POSTPROCESS_DIR / "retry_step_minus_1.txt", "w") as f:
        for name in RETRY_LIST:
            f.write(name + "\n")
    with open(POSTPROCESS_DIR / "node_only_no_assets.txt", "w") as f:
        for name in NODE_ONLY_LIST:
            f.write(name + "\n")
    with open(POSTPROCESS_DIR /"missing_both_json_and_assets.txt", "w") as f:
        for name in MISSING_ALL_LIST:
            f.write(name + "\n")

# === ENTRY POINT ===
if __name__ == "__main__":
    for task_id in TASK_IDS:
        for model_dir in MODEL_DIRS:
            process_postprocess_dir(task_id, model_dir)