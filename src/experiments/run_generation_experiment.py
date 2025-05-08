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
    params = {"x": 0, "y": 0, "width": 320, "height": 720, "name": "Frame"}
    async with session.post(f"{API_BASE_URL}/tool/create_root_frame", params=params) as res:
        return await res.json()

async def generate_variant(session, variant, model_name, image_path, meta_json):
    if "image" in variant:
        image_file = image_path.open("rb")
    else:
        image_file = None

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
    else:
        endpoint = "generate/text-image"
        data = aiohttp.FormData()
        data.add_field("message", text_input)
        data.add_field("image", image_file, filename=image_path.name, content_type="image/png")

    async with session.post(f"{API_BASE_URL}/{endpoint}", data=data) as res:
        return await res.json()

def fetch_node_export(json_response, step_count, root_frame_id, result_dir: Path, result_name: str):
    node_id = root_frame_id
    for attempt in range(2):
        node_url = f"https://api.figma.com/v1/files/{FIGMA_FILE_KEY}/nodes?ids={node_id}"
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
                break
            else:
                if attempt == 0:
                    node_id = increment_node_id(node_id)
                else:
                    return

        except Exception as e:
            log(f"[ERROR] Node export failed for {result_name}: {e}")

    with open(result_dir / f"{result_name}_json_response.json", "w", encoding="utf-8") as f:
        json.dump(json_response, f, indent=2, ensure_ascii=False)

    with open(result_dir / f"{result_name}_step_count.json", "w", encoding="utf-8") as f:
        json.dump({"step_count": step_count}, f, indent=2)

async def run_experiment():
    async with aiohttp.ClientSession() as session:
        for model_name in MODELS:
            model_dir = RESULTS_DIR / model_name
            model_dir.mkdir(parents=True, exist_ok=True)

            in_progress_path = model_dir / "in_progress.json"
            failures_path = model_dir / "failures.json"
            in_progress = json.loads(in_progress_path.read_text(encoding='utf-8')) if in_progress_path.exists() else {}
            failures = json.loads(failures_path.read_text(encoding='utf-8')) if failures_path.exists() else {}

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
                        print(f"[SKIP] {result_name}")
                        continue

                    log(f"[RUN] {result_name}")
                    print(f"[RUN] {result_name}")
                    in_progress[result_name] = in_progress.get(result_name, 0) + 1
                    in_progress_path.write_text(json.dumps(in_progress, indent=2, ensure_ascii=False), encoding='utf-8')

                    try:
                        frame_gen_response = await create_root_frame(session)
                        root_frame_id = frame_gen_response.get("root_frame_id")
                        if not root_frame_id:
                            log(f"[ERROR] Root frame creation failed for {result_name}")
                            print(f"[ERROR] Root frame creation failed for {result_name}")
                            continue

                        response = await generate_variant(session, variant, model_name, image_path, meta_json)
                        fetch_node_export(
                            response["json_response"],
                            response["step_count"],
                            root_frame_id,
                            model_dir,
                            result_name
                        )

                        delete_url = f"{API_BASE_URL}/tool/delete_all_top_level_nodes"
                        delete_response = requests.post(delete_url)
                        if delete_response.status_code == 200:
                            log(f"[CLEANUP] Deleted all top-level nodes after {result_name}")
                            print(f"[CLEANUP] Deleted all top-level nodes after {result_name}")
                            if result_name in in_progress:
                                del in_progress[result_name]
                                in_progress_path.write_text(json.dumps(in_progress, indent=2, ensure_ascii=False), encoding='utf-8')
                        else:
                            log(f"[CLEANUP-FAIL] Failed to delete nodes after {result_name}: {delete_response.status_code}")
                            print(f"[CLEANUP-FAIL] Failed to delete nodes after {result_name}: {delete_response.status_code}")


                    except Exception as e:
                        log(f"[ERROR] Failed {result_name}: {e}")
                        print(f"[ERROR] Failed {result_name}: {e}")
                        failures[result_name] = failures.get(result_name, 0) + 1
                        failures_path.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding='utf-8')
                        delete_url = f"{API_BASE_URL}/tool/delete_all_top_level_nodes"
                        requests.post(delete_url)

if __name__ == "__main__":
    asyncio.run(run_experiment())