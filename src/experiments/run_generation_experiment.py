import os
import re
import json
import base64
import asyncio
import aiohttp
import requests
import io
from pathlib import Path
from dotenv import load_dotenv
from config import load_experiment_config
from datetime import datetime
from PIL import Image
import time
import argparse
import yaml

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="Worker Model name (e.g. gemini, gpt-4o)")
    parser.add_argument("--variants", type=str, required=True, help="Comma-separated variants (e.g. image_only,text_level_1)")
    parser.add_argument("--channel", type=str, required=True, help="Channel name from config.yaml (e.g. channel_1)")
    parser.add_argument("--config_name", type=str, default="base", help="Path to config.yaml (optional)")
    parser.add_argument("--batch_name", type=str, help="Optional: batch name to run (e.g., batch_1)")
    parser.add_argument("--batches_config_path", type=str, help="Optional: path to batches.yaml")
    parser.add_argument("--multi_agent", action="store_true", help="Use multi-agent (supervisor-worker) mode")
    return parser.parse_args()

args = parse_args()
load_dotenv()
CONFIG = load_experiment_config(args.config_name)

channel_cfg = CONFIG["channels"].get(args.channel)
if channel_cfg is None:
    raise ValueError(f"[ERROR] Channel '{args.channel}' not found in config.yaml")

BENCHMARK_DIR = Path(CONFIG["benchmark_dir"])
RESULTS_DIR = Path(CONFIG["results_dir"]) / Path(f"{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS = [args.model]
VARIANTS = args.variants.split(",")
API_BASE_URL = channel_cfg["api_base_url"]
FIGMA_FILE_KEY = channel_cfg["figma_file_key"]
FIGMA_API_TOKEN = os.getenv("FIGMA_API_TOKEN")

HEADERS = {"X-Figma-Token": FIGMA_API_TOKEN}
EXPORT_BASE_URL = "https://api.figma.com/v1"

LOG_FILE = RESULTS_DIR / f"experiment_log_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.txt"

page = "Page 1"
frame = None
format = "png"
scale = 1

allowed_ids = None
if args.batch_name and args.batches_config_path:
    try:
        with open(args.batches_config_path, "r") as f:
            batch_yaml = yaml.safe_load(f)
        BATCH_FILE_PATH = batch_yaml["batches"].get(args.batch_name)
        if BATCH_FILE_PATH is None:
            raise ValueError(f"[ERROR] batch_name '{args.batch_name}' not found in {args.batches_config_path}")
        with open(BATCH_FILE_PATH, "r") as f:
            allowed_ids = set(line.strip() for line in f)
    except Exception as e:
        raise RuntimeError(f"[ERROR] Failed to load batch from YAML: {e}")

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def ensure_canvas_empty():
    for _ in range(3):
        try:
            res = requests.post(f"{API_BASE_URL}/tool/get_document_info")
            results = res.json().get("status", "{}")
            log(f"{results}")
            if not results == "success":
                del_res = requests.post(f"{API_BASE_URL}/tool/delete_all_top_level_nodes")
                if del_res.status_code == 200:
                    log("[CLEANUP] Deleted top-level nodes")
                    return
                else:
                    log(f"[CLEANUP-RETRY] Failed with status {del_res.status_code}")
            else:
                return  # Already empty
        except Exception as e:
            log(f"[CLEANUP-ERROR] Exception during cleanup: {e}")
        time.sleep(1)
    raise RuntimeError("Canvas cleanup failed after retries")

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

async def get_document_info():
    response = requests.post(f"{API_BASE_URL}/tool/get_document_info")
    try:
        return json.loads(response.json()["message"])
    except:
        return {}

async def generate_variant(session, variant, model_name, image_path, meta_json):
    # ---------- Common ----------
    text_input = ""
    if "text" in variant:
        text_level = "description_one" if "level_1" in variant else "description_two"
        text_input = meta_json.get(text_level, "")

    image_file = image_path.open("rb") if "image" in variant else None

    # ---------- Multi-Agent ----------
    if args.multi_agent:
        endpoint = "generate/multi"
        data = aiohttp.FormData()
        data.add_field("message", text_input or "Replicate this UI.")
        if image_file:
            data.add_field("image", image_file, filename=image_path.name, content_type="image/png")

        async with session.post(f"{API_BASE_URL}/{endpoint}?worker_model={model_name}",
                                data=data) as res:
            return await res.json()

    # ---------- Single-Agent ----------
    if variant == "image_only":
        endpoint = "generate/image"
        data = aiohttp.FormData()
        data.add_field("image", image_file, filename=image_path.name, content_type="image/png")

    elif variant.startswith("text_level"):
        endpoint = "generate/text"
        data = {"message": text_input}

    else:
        endpoint = "generate/text-image"
        data = aiohttp.FormData()
        data.add_field("message", text_input)
        data.add_field("image", image_file, filename=image_path.name, content_type="image/png")

    async with session.post(f"{API_BASE_URL}/{endpoint}", data=data) as res:
        return await res.json()



def get_node_infos(file_key: str, page_name: str, frame_name: str = None, result_dir: Path = None, result_name: str = None):
    url = f"{EXPORT_BASE_URL}/files/{file_key}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        node_data = res.json()
        with open(result_dir / f"{result_name}.json", "w", encoding="utf-8") as f:
            json.dump(node_data, f, indent=2, ensure_ascii=False)

    res.raise_for_status()
    document = res.json()["document"]

    page = next((c for c in document["children"] if c["name"] == page_name), None)
    if not page:
        raise ValueError(f"Page '{page_name}' not found")

    targets = []

    def recurse(nodes):
        for node in nodes:
            if "absoluteRenderBounds" in node:
                targets.append({
                    "id": node["id"],
                    "name": re.sub(r"[^\w\-_]", "_", node["name"]),
                    "bbox": node["absoluteRenderBounds"]
                })
            if "children" in node:
                recurse(node["children"])

    if frame_name:
        frame = next((f for f in page["children"] if f["name"] == frame_name), None)
        if not frame:
            raise ValueError(f"Frame '{frame_name}' not found")
        recurse(frame["children"])
    else:
        recurse(page["children"])

    return targets  # List of dicts: id, name, bbox


def export_images(file_key: str, node_infos: list, format: str = "png", out_dir: str = "exported_assets", scale: int = 1):
    os.makedirs(out_dir, exist_ok=True)
    ids = ",".join([n["id"] for n in node_infos])
    url = f"{EXPORT_BASE_URL}/images/{file_key}?ids={ids}&format={format}&scale={scale}"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    images = res.json()["images"]

    results = []
    for node in node_infos:
        node_id = node["id"]
        name = node["name"]
        if node_id not in images:
            continue
        img_url = images[node_id]
        img_data = requests.get(img_url)
        if img_data.status_code == 200:
            file_path = Path(out_dir) / "assets" / f"{node_id}.{format}"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            print(file_path)
            with open(file_path, "wb") as f:
                f.write(img_data.content)
            results.append(str(file_path))
    return results

def fetch_node_export(json_response, step_count, model_dir: Path, result_name: str):
    output_dir = model_dir / result_name
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / f"{result_name}_json_response.json", "w", encoding="utf-8") as f:
        json.dump(json_response, f, indent=2, ensure_ascii=False)

    with open(output_dir / f"{result_name}_step_count.json", "w", encoding="utf-8") as f:
        json.dump({"step_count": step_count}, f, indent=2)

async def run_experiment():
    async with aiohttp.ClientSession() as session:
        for model_name in MODELS:
            log(f"[Figma File key]: {FIGMA_FILE_KEY}")
            log(f"[MODELS]: {MODELS}")
            log(f"[API_BASE_URL]: {API_BASE_URL}")
            log(f"[VARIANTS]: {VARIANTS}")
            print(f"[DEBUG] Loaded allowed_ids: {allowed_ids}")

            model_dir = RESULTS_DIR / model_name
            model_dir.mkdir(parents=True, exist_ok=True)

            in_progress_path = model_dir / "in_progress.json"
            failures_path = model_dir / "failures.json"
            in_progress = json.loads(in_progress_path.read_text(encoding='utf-8')) if in_progress_path.exists() else {}
            failures = json.loads(failures_path.read_text(encoding='utf-8')) if failures_path.exists() else {}

            for meta_file in BENCHMARK_DIR.glob("*-meta.json"):
                base_id = meta_file.stem.replace("-meta", "")
                
                if allowed_ids is not None and base_id not in allowed_ids:
                    continue
                
                image_path = BENCHMARK_DIR / f"{base_id}.png"
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta_json = json.load(f)

                for variant in VARIANTS:
                    result_name = f"{base_id}-{model_name}-{variant}"
                    json_path = model_dir / f"{result_name}.json"
                    png_path = model_dir / result_name / f"{result_name}.png"
                    print(json_path)
                    print(png_path)
                    if json_path.exists() and png_path.exists():
                        log(f"[SKIP] {result_name}")
                        print(f"[SKIP] {result_name}")
                        continue

                    log(f"[RUN] {result_name}")
                    print(f"[RUN] {result_name}")
                    in_progress[result_name] = in_progress.get(result_name, 0) + 1
                    in_progress_path.write_text(json.dumps(in_progress, indent=2, ensure_ascii=False), encoding='utf-8')

                    try:
                        ensure_canvas_empty()
                        response = await generate_variant(session, variant, model_name, image_path, meta_json)
                        log(f"response: {response}")

                        fetch_node_export(
                            response["json_response"],
                            response["step_count"],
                            model_dir,
                            result_name
                        )
                        node_infos = get_node_infos(FIGMA_FILE_KEY, page_name=page, frame_name=frame, result_dir=model_dir, result_name=result_name)
                        saved = export_images(FIGMA_FILE_KEY, node_infos, format=format, scale=scale, out_dir=model_dir / result_name)

                        print("[Exported Files]")
                        print("\n".join(saved))

                        ids = ",".join([n["id"] for n in node_infos])
                        url = f"{EXPORT_BASE_URL}/images/{FIGMA_FILE_KEY}?ids={ids}&format={format}&scale={scale}"
                        img_res = requests.get(url, headers=HEADERS)
                        img_res.raise_for_status()
                        img_urls = img_res.json()["images"]

                        with open(model_dir / result_name / f"{result_name}_step_count.json", "w", encoding="utf-8") as f:
                            json.dump({"step_count": response["step_count"]}, f, indent=2)

                    except Exception as e:
                        log(f"[ERROR] Failed {result_name}: {e}")
                        print(f"[ERROR] Failed {result_name}: {e}")
                        failures[result_name] = failures.get(result_name, 0) + 1
                        failures_path.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding='utf-8')

                        if 'response' in locals() and isinstance(response, dict):
                            try:
                                fetch_node_export(
                                    response.get("json_response", {}),
                                    response.get("step_count", -1),
                                    model_dir,
                                    result_name
                                )
                            except Exception as e_inner:
                                log(f"[ERROR][SAVE-FAIL] Couldn't save partial response for {result_name}: {e_inner}")

                    finally:
                        try:
                            ensure_canvas_empty()
                            log(f"[CLEANUP] Deleted all top-level nodes after {result_name}")
                            print(f"[CLEANUP] Deleted all top-level nodes after {result_name}")
                        except Exception as e:
                            log(f"[CLEANUP-FAIL] Failed to cleanup after {result_name}: {e}")

                        if result_name in in_progress:
                            del in_progress[result_name]
                            in_progress_path.write_text(json.dumps(in_progress, indent=2, ensure_ascii=False), encoding='utf-8')

if __name__ == "__main__":
    asyncio.run(run_experiment())