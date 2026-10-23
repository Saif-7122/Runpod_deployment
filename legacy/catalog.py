import os
import sys
import json
import argparse
import yaml

def load_config(config_path="config.yaml"):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def build_catalog(input_path=None, output_path=None, config_path="config.yaml"):
    config = load_config(config_path)
    dirs = config.get("directories", {})
    catalog_dir = dirs.get("catalog", "/workspace/catalog")
    os.makedirs(catalog_dir, exist_ok=True)

    if not output_path:
        output_path = os.path.join(catalog_dir, "catalog.json")

    # If an input path was not provided, look in catalog directory
    if not input_path:
        candidate = os.path.join(catalog_dir, "drive_raw.json")
        if os.path.exists(candidate):
            input_path = candidate

    raw_items = []
    if input_path and os.path.exists(input_path):
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    raw_items = data
                elif isinstance(data, dict):
                    raw_items = data.get("files", data.get("raw_files", []))
        except Exception as e:
            print(f"[Catalog] Warning: Failed to read input file {input_path}: {e}", file=sys.stderr)

    valid_extensions = (".mp4", ".mov", ".m4v", ".mkv", ".webm")
    catalog_entries = []

    for item in raw_items:
        file_name = item.get("name", "")
        file_id = item.get("id", "")
        mime_type = item.get("mimeType", "")

        is_video = (
            file_name.lower().endswith(valid_extensions) or 
            "video" in mime_type.lower()
        )
        if not is_video:
            continue

        catalog_entries.append({
            "id": file_id,
            "name": file_name,
            "mime_type": mime_type,
            "size": item.get("size", 0)
        })

    # Sort deterministically by filename
    catalog_entries.sort(key=lambda x: x["name"])

    # Build human-readable formatted list for the Director LLM prompt
    inventory_lines = [
        f"- {entry['name']} (ID: {entry['id']})"
        for entry in catalog_entries
    ]
    inventory_text = "\n".join(inventory_lines) if inventory_lines else "No video clips found."

    output_payload = {
        "total_clips": len(catalog_entries),
        "raw_files": catalog_entries,
        "inventory_list": inventory_text
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"[Catalog] Successfully compiled {len(catalog_entries)} video clips to {output_path}", file=sys.stderr)

    # Return clean single line JSON on stdout
    result = {
        "status": "success",
        "total_clips": len(catalog_entries),
        "catalog_path": output_path
    }
    sys.stdout.flush()
    print(json.dumps(result))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build B-Roll Catalog for Video Factory")
    parser.add_argument("--input", default=None, help="Path to raw Drive files JSON")
    parser.add_argument("--output", default=None, help="Path to save processed catalog.json")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    build_catalog(input_path=args.input, output_path=args.output, config_path=args.config)
