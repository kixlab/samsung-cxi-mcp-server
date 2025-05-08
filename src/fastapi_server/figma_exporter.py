import os
import re
import io
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from config import load_config
from PIL import Image

load_dotenv()
CONFIG = load_config()

FIGMA_API_TOKEN = os.getenv("FIGMA_API_TOKEN")
FIGMA_FILE_KEY = CONFIG["figma_file_key"]
HEADERS = {"X-Figma-Token": FIGMA_API_TOKEN}

EXPORT_BASE_URL = "https://api.figma.com/v1"


def get_node_infos(file_key: str, page_name: str, frame_name: str = None):
    url = f"{EXPORT_BASE_URL}/files/{file_key}"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    document = res.json()["document"]

    page = next((c for c in document["children"] if c["name"] == page_name), None)
    if not page:
        raise ValueError(f"Page '{page_name}' not found")

    targets = []

    def recurse(nodes):
        for node in nodes:
            if "absoluteBoundingBox" in node:
                targets.append({
                    "id": node["id"],
                    "name": re.sub(r"[^\w\-_]", "_", node["name"]),
                    "bbox": node["absoluteBoundingBox"]
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
            file_path = Path(out_dir) / f"{name}.{format}"
            print(file_path)
            with open(file_path, "wb") as f:
                f.write(img_data.content)
            results.append(str(file_path))
    return results


def render_combined_image(node_infos: list, img_urls: dict, out_path="combined_output.png", scale=1):
    if not node_infos:
        raise ValueError("No nodes provided for rendering.")

    min_x = min(int(n["bbox"]["x"] * scale) for n in node_infos)
    min_y = min(int(n["bbox"]["y"] * scale) for n in node_infos)
    max_x = max(int((n["bbox"]["x"] + n["bbox"]["width"]) * scale) for n in node_infos)
    max_y = max(int((n["bbox"]["y"] + n["bbox"]["height"]) * scale) for n in node_infos)

    canvas_width = max_x - min_x
    canvas_height = max_y - min_y
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 0))

    for node in node_infos:
        node_id = node["id"]
        if node_id not in img_urls:
            continue
        img_data = requests.get(img_urls[node_id])
        if img_data.status_code == 200:
            img = Image.open(io.BytesIO(img_data.content)).convert("RGBA")
            x = int((node["bbox"]["x"] * scale) - min_x)
            y = int((node["bbox"]["y"] * scale) - min_y)
            canvas.paste(img, (x, y), img)

    dir_name = os.path.dirname(out_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    canvas.save(out_path)


if __name__ == "__main__":
    page = "Page 1"
    frame = None
    format = "png"
    scale = 1

    node_infos = get_node_infos(FIGMA_FILE_KEY, page_name=page, frame_name=frame)
    saved = export_images(FIGMA_FILE_KEY, node_infos, format=format, scale=scale)

    print("[Exported Files]")
    print("\n".join(saved))

    ids = ",".join([n["id"] for n in node_infos])
    url = f"{EXPORT_BASE_URL}/images/{FIGMA_FILE_KEY}?ids={ids}&format={format}&scale={scale}"
    img_res = requests.get(url, headers=HEADERS)
    img_res.raise_for_status()
    img_urls = img_res.json()["images"]

    combined_path = "combined_output.png"
    render_combined_image(node_infos, img_urls, out_path=combined_path, scale=scale)
    print("✅ Combined image saved to:", combined_path)
