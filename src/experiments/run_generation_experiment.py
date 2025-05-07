# src/experiments/run_generation_experiment.py
import os
import re
import json
import base64
import asyncio
import aiohttp
import requests
from pathlib import Path
from dotenv import load_dotenv
from config import load_config
from datetime import datetime

load_dotenv()
CONFIG = load_config()

BENCHMARK_DIR = Path(CONFIG["benchmark_dir"])
RESULTS_DIR = Path(CONFIG["results_dir"])
MODELS = CONFIG["models"]
VARIANTS = CONFIG["variants"]
FIGMA_FILE_KEY = CONFIG["figma_file_key"]

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
FIGMA_API_TOKEN = os.getenv("FIGMA_API_TOKEN")
HEADERS = {"X-Figma-Token": FIGMA_API_TOKEN}

LOG_FILE = RESULTS_DIR / "experiment_log.txt"

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    # print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def increment_node_id(node_id):
    match = re.match(r"(\d+)-(\d+)", node_id)
    if not match:
        raise ValueError(f"Invalid node_id format: {node_id}")
    prefix, suffix = match.groups()
    new_suffix = str(int(suffix) + 1).zfill(len(suffix))
    return f"{prefix}-{new_suffix}"

async def create_root_frame(session):
    params = {
        "x": 0, "y": 0, "width": 320, "height": 720, "name": "Frame"
    }
    async with session.post(f"{API_BASE_URL}/tool/create_root_frame", params=params) as res:
        return await res.json()

async def generate_variant(session, variant, model_name, image_path, meta_json):
    if "image" in variant:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        image_file = image_path.open("rb")
    else:
        image_file = None

    text_level = None
    if "text" in variant:
        text_level = "description_one" if "level_1" in variant else "description_two"
        text_input = meta_json[text_level]
    else:
        text_input = ""

    if variant == "image_only":
        endpoint = "generate/image"
        data = aiohttp.FormData()
        data.add_field("image", image_path.open("rb"), filename=image_path.name, content_type="image/png")
    elif variant == "text_level_1" or variant == "text_level_2":
        endpoint = "generate/text"
        data = {"message": text_input}
        # print(data)
    else:
        endpoint = "generate/text-image"
        data = aiohttp.FormData()
        data.add_field("message", text_input)
        data.add_field("image", image_file, filename=image_path.name, content_type="image/png")

    async with session.post(f"{API_BASE_URL}/{endpoint}", data=data) as res:
        return await res.json()

def fetch_node_export(json_response, step_count, root_frame_id, result_dir: Path, result_name: str):
    node_id = root_frame_id
    for attempt in range(2):  # 한 번 실패하면 node_id 증가시도
        node_url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/nodes?ids={node_id}"
        print(f"[INFO] Requesting node: {node_url}")
        try:
            res = requests.get(node_url, headers=HEADERS)

            if res.status_code == 200:
                node_data = res.json()
                with open(result_dir / f"{result_name}.json", "w", encoding="utf-8") as f:
                    json.dump(node_data, f, indent=2, ensure_ascii=False)

                thumbnail_url = node_data.get("thumbnailUrl")
                if thumbnail_url:
                    img_res = requests.get(thumbnail_url)
                    if img_res.status_code == 200:
                        with open(result_dir / f"{result_name}.png", "wb") as f:
                            f.write(img_res.content)
                        print(f"[SUCCESS] Saved thumbnail for {result_name}")
                    else:
                        print(f"[WARN] Failed to fetch thumbnail: {img_res.status_code}")
                else:
                    print(f"[WARN] No thumbnail in response for {result_name}")
                    
            else:
                print(f"[WARN] Failed to fetch node_id={node_id}: {res.status_code} {res.text}")
                if attempt == 0:
                    node_id = increment_node_id(node_id)
                else:
                    print(f"[ERROR] Node fetch completely failed for {result_name}")
                    return
            
            with open(result_dir / f"{result_name}_json_response.json", "w", encoding="utf-8") as f: 
                json.dump(json_response, f, indent=2, ensure_ascii=False)
                print(f"[INFO] Saved json_response to: {f.name}")

            with open(result_dir / f"{result_name}_step_count.json", "w", encoding="utf-8") as f:
                json.dump({"step_count": step_count}, f, indent=2)
                print(f"[INFO] Saved step_count to: {f.name}")
                
        except Exception as e:
            log(f"[ERROR] Node export failed for {result_name}: {e}")


async def run_experiment():
    async with aiohttp.ClientSession() as session:
        for model_name in MODELS:
            model_dir = RESULTS_DIR / model_name
            model_dir.mkdir(parents=True, exist_ok=True)

            for meta_file in BENCHMARK_DIR.glob("*-meta.json"):
                base_id = meta_file.stem.replace("-meta", "")
                image_path = BENCHMARK_DIR / f"{base_id}.png"
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta_json = json.load(f)

                for variant in VARIANTS:
                    result_name = f"{base_id}-{model_name}-{variant}"
                    json_path = model_dir / f"{result_name}.json"
                    png_path = model_dir / f"{result_name}.png"
                    if json_path.exists() and png_path.exists():
                        log(f"[SKIP] {result_name}")
                        continue

                    log(f"[RUN] {result_name}")
                    try:
                        # Step 1. Create Root Frame
                        frame_gen_response = await create_root_frame(session)
                        root_frame_id = frame_gen_response.get("root_frame_id")
                        if not root_frame_id:
                            log(f"[ERROR] Root frame creation failed for {result_name}")
                            continue

                        # Step 2. Generate Variant
                        log(f"[DEBUG] generate_variant: {variant}, {base_id}")
                        response = await generate_variant(session, variant, model_name, image_path, meta_json)
                        log(f"[DEBUG] response: {response}")

                        # Step 3. Save Export Result
                        fetch_node_export(
                            response["json_response"],
                            response["step_count"],
                            root_frame_id,
                            model_dir,
                            result_name
                        )

                        # Step 4. Delete all top-level nodes
                        delete_url = f"{API_BASE_URL}/tool/delete_all_top_level_nodes"
                        delete_response = requests.post(delete_url)
                        if delete_response.status_code == 200:
                            log(f"[CLEANUP] Deleted all top-level nodes after {result_name}")
                        else:
                            log(f"[CLEANUP-FAIL] Failed to delete nodes after {result_name}: {delete_response.status_code} - {delete_response.text}")

                    except Exception as e:
                        log(f"[ERROR] Failed {result_name}: {e}")
                        delete_url = f"{API_BASE_URL}/tool/delete_all_top_level_nodes"
                        delete_response = requests.post(delete_url)

if __name__ == "__main__":
    asyncio.run(run_experiment())
