import json
import sys
import os
from pathlib import Path

from extract_bugteam_metrics import extract_text
from config.constants import ALL_SESSION_MARKERS, JSON_INDENT_WIDTH


def scan_file(file_path: str) -> dict:
    each_scanned = {
        "path": file_path,
        "size_bytes": os.path.getsize(file_path),
        "matched_markers": [],
        "total_lines": 0,
        "marker_lines": 0,
        "error": None,
    }
    marker_found_in_file = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file_handle:
            for each_line in file_handle:
                each_line = each_line.strip()
                if not each_line:
                    continue
                each_scanned["total_lines"] += 1
                try:
                    parsed_entry = json.loads(each_line)
                except json.JSONDecodeError:
                    continue
                text = extract_text(parsed_entry)
                if not text:
                    continue
                for each_marker in ALL_SESSION_MARKERS:
                    if each_marker.lower() in text.lower():
                        marker_found_in_file.add(each_marker)
            if marker_found_in_file:
                each_scanned["matched_markers"] = sorted(marker_found_in_file)
                each_scanned["marker_lines"] = each_scanned["total_lines"]
    except Exception as each_exception:
        each_scanned["error"] = str(each_exception)
    return each_scanned


def main() -> None:
    all_paths = sys.argv[1:]
    if not all_paths:
        print(
            "Usage: python scan_session_markers.py <session.jsonl> [...] [--output <path>]"
        )
        sys.exit(1)

    output_path = None
    if "--output" in all_paths:
        output_index = all_paths.index("--output")
        if output_index + 1 < len(all_paths):
            output_path = all_paths[output_index + 1]
            all_paths = all_paths[:output_index] + all_paths[output_index + 2 :]

    all_scanned = []
    for each_path in all_paths:
        each_scanned = scan_file(each_path)
        all_scanned.append(each_scanned)
        name = Path(each_path).stem
        size_mb = each_scanned["size_bytes"] / (1024 * 1024)
        markers = each_scanned["matched_markers"]
        if markers:
            print(f"  {name}: {size_mb:.1f}MB, markers={markers}")
        elif each_scanned["error"]:
            print(f"  {name}: ERROR - {each_scanned['error']}")
        else:
            print(f"  {name}: {size_mb:.1f}MB, no markers")

    scan_result = {
        "files_scanned": len(all_scanned),
        "matched_count": sum(1 for each in all_scanned if each["matched_markers"]),
        "files": all_scanned,
    }

    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file_handle:
            json.dump(scan_result, file_handle, indent=JSON_INDENT_WIDTH)
        print(f"\nResults written to {output_path}")
    else:
        print(json.dumps(scan_result, indent=JSON_INDENT_WIDTH))


if __name__ == "__main__":
    main()
