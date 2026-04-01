import zipfile, os, json
import geopandas as gpd
import fiona
from lxml import etree
from shapely.ops import unary_union
import numpy as np
import pandas as pd
from datetime import datetime
from rapidfuzz import fuzz
 
# ── ANSI colors for terminal UI ───────────────────────────────────────────────
class C:
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"
 
def banner():
    print(f"""
{C.CYAN}{C.BOLD}
╔══════════════════════════════════════════════════════╗
║        GEO LAYER COMPARISON TOOL  v1.0               ║
║        KML / KMZ / XML Similarity Analyzer           ║
╚══════════════════════════════════════════════════════╝
{C.RESET}""")
 
def divider(label=""):
    width = 54
    if label:
        pad = (width - len(label) - 2) // 2
        print(f"\n{C.DIM}{'─' * pad} {label} {'─' * pad}{C.RESET}\n")
    else:
        print(f"\n{C.DIM}{'─' * width}{C.RESET}\n")
 
# ── File helpers ──────────────────────────────────────────────────────────────
 
def is_geo_file(path):
    return os.path.isfile(path) and os.path.splitext(path)[1].lower() in (".kml", ".kmz", ".xml")
 
def list_geo_files(folder):
    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in (".kml", ".kmz", ".xml")
    ]
 
def prompt_file(label):
    while True:
        path = input(f"{C.YELLOW}  {label}: {C.RESET}").strip().strip('"')
        # Convert Windows path to WSL if needed
        if path.startswith("C:\\") or path.startswith("c:\\"):
            path = "/mnt/c/" + path[3:].replace("\\", "/")
        if is_geo_file(path):
            return path
        print(f"{C.RED}  ✗ File not found or unsupported format. Try again.{C.RESET}")
 
def prompt_folder(label):
    while True:
        folder = input(f"{C.YELLOW}  {label}: {C.RESET}").strip().strip('"')
        if folder.startswith("C:\\") or folder.startswith("c:\\"):
            folder = "/mnt/c/" + folder[3:].replace("\\", "/")
        if os.path.isdir(folder):
            files = list_geo_files(folder)
            if files:
                return folder, files
            print(f"{C.RED}  ✗ No KML/KMZ/XML files found in that folder. Try again.{C.RESET}")
        else:
            print(f"{C.RED}  ✗ Folder not found. Try again.{C.RESET}")
 
def prompt_output_dir():
    default = "/mnt/c/Users/mattm/Documents/Python_Projects/GeospatialDataComparison"
    print(f"\n{C.DIM}  Output folder (press Enter to use project folder):{C.RESET}")
    path = input(f"{C.YELLOW}  [{default}]: {C.RESET}").strip().strip('"')
    if not path:
        return default
    if path.startswith("C:\\") or path.startswith("c:\\"):
        path = "/mnt/c/" + path[3:].replace("\\", "/")
    return path
 
# ── Core geo functions ────────────────────────────────────────────────────────
 
def load_geo_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".kmz":
        with zipfile.ZipFile(filepath, 'r') as z:
            kml_name = [n for n in z.namelist() if n.endswith('.kml')][0]
            z.extract(kml_name, "/tmp/")
            filepath = f"/tmp/{kml_name}"
 
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
 
    layers = {}
    try:
        for layer in fiona.listlayers(filepath):
            gdf = gpd.read_file(filepath, driver='KML', layer=layer)
            if not gdf.empty:
                layers[layer] = gdf
    except Exception as e:
        print(f"{C.RED}  ✗ Could not load {os.path.basename(filepath)}: {e}{C.RESET}")
    return layers
 
def extract_metadata(layers):
    meta = {}
    for name, gdf in layers.items():
        meta[name] = {
            "feature_count": len(gdf),
            "geometry_types": gdf.geom_type.unique().tolist(),
            "columns": gdf.columns.tolist(),
            "bbox": gdf.total_bounds.tolist(),
            "crs": str(gdf.crs),
            "centroid": list(gdf.geometry.unary_union.centroid.coords[0])
        }
    return meta
 
def geometric_similarity(gdf_a, gdf_b):
    union_a = unary_union(gdf_a.geometry)
    union_b = unary_union(gdf_b.geometry)
    intersection = union_a.intersection(union_b).area
    union        = union_a.union(union_b).area
    iou          = intersection / union if union > 0 else 0
    hausdorff    = union_a.hausdorff_distance(union_b)
    centroid_dist= union_a.centroid.distance(union_b.centroid)
    return {"iou": iou, "hausdorff": hausdorff, "centroid_distance": centroid_dist}
 
def metadata_similarity(meta_a, meta_b):
    fc_a, fc_b = meta_a["feature_count"], meta_b["feature_count"]
    cols_a, cols_b = set(meta_a["columns"]), set(meta_b["columns"])
    bbox_dist = np.linalg.norm(np.array(meta_a["bbox"]) - np.array(meta_b["bbox"]))
    return {
        "feature_count_sim": 1 - abs(fc_a - fc_b) / max(fc_a, fc_b, 1),
        "schema_jaccard":    len(cols_a & cols_b) / len(cols_a | cols_b) if cols_a | cols_b else 0,
        "geom_type_match":   float(set(meta_a["geometry_types"]) == set(meta_b["geometry_types"])),
        "bbox_proximity":    1 / (1 + bbox_dist),
    }
 
def composite_score(geo_sim, meta_sim, weights=None):
    if weights is None:
        weights = {
            "iou": 0.30, "hausdorff": 0.15, "centroid_distance": 0.10,
            "feature_count_sim": 0.15, "schema_jaccard": 0.20, "geom_type_match": 0.10
        }
    return round(
        weights["iou"]               * geo_sim["iou"] +
        weights["hausdorff"]         * (1 / (1 + geo_sim["hausdorff"])) +
        weights["centroid_distance"] * (1 / (1 + geo_sim["centroid_distance"])) +
        weights["feature_count_sim"] * meta_sim["feature_count_sim"] +
        weights["schema_jaccard"]    * meta_sim["schema_jaccard"] +
        weights["geom_type_match"]   * meta_sim["geom_type_match"],
        4
    )
 
def compare_two(file_a, file_b):
    layers_a = load_geo_file(file_a)
    layers_b = load_geo_file(file_b)
    meta_a   = extract_metadata(layers_a)
    meta_b   = extract_metadata(layers_b)
    layer_scores = []
    detail = []
    for layer in layers_a:
        if layer in layers_b:
            geo  = geometric_similarity(layers_a[layer], layers_b[layer])
            meta = metadata_similarity(meta_a[layer], meta_b[layer])
            score = composite_score(geo, meta)
            layer_scores.append(score)
            detail.append({"layer": layer, "score": score, **geo, **meta})
    avg = round(float(np.mean(layer_scores)), 4) if layer_scores else 0.0
    return avg, detail
 
def find_best_match(reference_file, candidate_files):
    ref_layers = load_geo_file(reference_file)
    ref_meta   = extract_metadata(ref_layers)
    results = []
    total = len(candidate_files)
    for i, candidate in enumerate(candidate_files, 1):
        name = os.path.basename(candidate)
        print(f"  {C.DIM}[{i}/{total}] Comparing → {name}{C.RESET}")
        cand_layers = load_geo_file(candidate)
        cand_meta   = extract_metadata(cand_layers)
        layer_scores = []
        for layer in ref_layers:
            if layer in cand_layers:
                geo  = geometric_similarity(ref_layers[layer], cand_layers[layer])
                meta = metadata_similarity(ref_meta[layer], cand_meta[layer])
                layer_scores.append(composite_score(geo, meta))
        avg = round(float(np.mean(layer_scores)), 4) if layer_scores else 0.0
        results.append({"file": candidate, "filename": name, "score": avg})
    return sorted(results, key=lambda x: x["score"], reverse=True)
 
# ── Output ────────────────────────────────────────────────────────────────────
 
def save_results(results, output_dir, mode_label):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"geo_comparison_{mode_label}_{timestamp}"
 
    json_path = os.path.join(output_dir, f"{base}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=4)
 
    csv_path = os.path.join(output_dir, f"{base}.csv")
    flat = results if isinstance(results, list) else [results]
    pd.DataFrame(flat).to_csv(csv_path, index=False)
 
    print(f"\n{C.GREEN}  ✓ JSON saved → {json_path}{C.RESET}")
    print(f"{C.GREEN}  ✓ CSV  saved → {csv_path}{C.RESET}")
 
def print_ranked(results):
    divider("RESULTS")
    for i, r in enumerate(results, 1):
        bar_len  = int(r["score"] * 30)
        bar      = "█" * bar_len + "░" * (30 - bar_len)
        pct      = f"{r['score']*100:.1f}%"
        medal    = ["🥇","🥈","🥉"][i-1] if i <= 3 else f" #{i}"
        print(f"  {medal}  {C.BOLD}{pct:>6}{C.RESET}  {C.CYAN}{bar}{C.RESET}  {r['filename']}")
    print()
 
def print_two_file_result(score, detail, file_a, file_b):
    divider("RESULTS")
    pct     = f"{score*100:.1f}%"
    bar_len = int(score * 40)
    bar     = "█" * bar_len + "░" * (40 - bar_len)
    print(f"  {C.BOLD}Overall Similarity: {C.GREEN}{pct}{C.RESET}")
    print(f"  {C.CYAN}{bar}{C.RESET}\n")
    print(f"  {C.DIM}File A: {os.path.basename(file_a)}{C.RESET}")
    print(f"  {C.DIM}File B: {os.path.basename(file_b)}{C.RESET}\n")
    if detail:
        print(f"  {'Layer':<25} {'Score':>7}  {'IoU':>6}  {'FeatSim':>7}  {'Schema':>7}")
        print(f"  {'─'*25} {'─'*7}  {'─'*6}  {'─'*7}  {'─'*7}")
        for d in detail:
            print(f"  {d['layer']:<25} {d['score']:>7.4f}  {d['iou']:>6.4f}  {d['feature_count_sim']:>7.4f}  {d['schema_jaccard']:>7.4f}")
    print()
 
# ── Main menu ─────────────────────────────────────────────────────────────────
 
def main():
    banner()
 
    divider("SELECT MODE")
    print(f"  {C.BOLD}1{C.RESET}  Compare two specific files")
    print(f"  {C.BOLD}2{C.RESET}  Match one file against a folder of files")
    print(f"  {C.BOLD}3{C.RESET}  Compare all files in a folder against each other")
    print(f"  {C.BOLD}q{C.RESET}  Quit\n")
 
    choice = input(f"{C.YELLOW}  Enter choice [1/2/3/q]: {C.RESET}").strip().lower()
 
    # ── Mode 1: Two files ──────────────────────────────────────────────────────
    if choice == "1":
        divider("TWO FILE COMPARISON")
        file_a = prompt_file("File A path")
        file_b = prompt_file("File B path")
        output_dir = prompt_output_dir()
 
        print(f"\n{C.BLUE}  Running comparison...{C.RESET}\n")
        score, detail = compare_two(file_a, file_b)
        print_two_file_result(score, detail, file_a, file_b)
 
        result_obj = {
            "mode": "two_file",
            "file_a": file_a,
            "file_b": file_b,
            "overall_score": score,
            "layer_detail": detail
        }
        save_results(result_obj, output_dir, "two_file")
 
    # ── Mode 2: One vs folder ──────────────────────────────────────────────────
    elif choice == "2":
        divider("ONE FILE vs FOLDER")
        ref_file = prompt_file("Reference file path")
        folder, candidates = prompt_folder("Folder containing candidate files")
 
        # Remove reference from candidates if it's in the same folder
        candidates = [c for c in candidates if os.path.abspath(c) != os.path.abspath(ref_file)]
 
        print(f"\n{C.BLUE}  Found {len(candidates)} candidate file(s). Running comparisons...{C.RESET}\n")
        output_dir = prompt_output_dir()
 
        results = find_best_match(ref_file, candidates)
        print_ranked(results)
        save_results(results, output_dir, "folder_match")
 
        print(f"{C.GREEN}{C.BOLD}  Best match → {results[0]['filename']}  ({results[0]['score']*100:.1f}% similar){C.RESET}\n")
 
    # ── Mode 3: All vs all in folder ───────────────────────────────────────────
    elif choice == "3":
        divider("FOLDER vs FOLDER (ALL PAIRS)")
        folder, files = prompt_folder("Folder path")
        output_dir = prompt_output_dir()
 
        print(f"\n{C.BLUE}  Found {len(files)} files. Running all pairwise comparisons...{C.RESET}\n")
 
        all_results = []
        total_pairs = len(files) * (len(files) - 1) // 2
        pair_num = 0
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                pair_num += 1
                a, b = files[i], files[j]
                print(f"  {C.DIM}[{pair_num}/{total_pairs}] {os.path.basename(a)} ↔ {os.path.basename(b)}{C.RESET}")
                score, detail = compare_two(a, b)
                all_results.append({
                    "file_a": os.path.basename(a),
                    "file_b": os.path.basename(b),
                    "score": score
                })
 
        all_results.sort(key=lambda x: x["score"], reverse=True)
        divider("TOP PAIRS")
        for r in all_results[:10]:
            pct = f"{r['score']*100:.1f}%"
            print(f"  {C.BOLD}{pct:>6}{C.RESET}  {r['file_a']}  ↔  {r['file_b']}")
        print()
        save_results(all_results, output_dir, "all_pairs")
 
    elif choice == "q":
        print(f"\n{C.DIM}  Exiting. Goodbye.{C.RESET}\n")
        return
    else:
        print(f"{C.RED}  Invalid choice. Please re-run the script.{C.RESET}\n")
        return
 
    print(f"{C.CYAN}{C.BOLD}  ✓ Done!{C.RESET}\n")
 
if __name__ == "__main__":
    main()