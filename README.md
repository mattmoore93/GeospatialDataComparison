# Geospatial Data Comparison Tool

An interactive Python CLI tool for comparing and analyzing KML, KMZ, 
and XML geo layer files using spatial and metadata similarity scoring.

## Features
- Compare two specific geo files with full layer-by-layer breakdown
- Match one reference file against an entire folder of candidates
- Pairwise comparison across all files in a folder
- Composite similarity scoring using:
  - IoU (Intersection over Union) — spatial overlap
  - Hausdorff distance — shape boundary similarity
  - Centroid distance — geographic proximity
  - Schema/column Jaccard similarity — metadata structure
  - Feature count similarity — data density comparison
  - Geometry type matching
- Results exported as both JSON and CSV
- Supports Windows paths automatically converted for WSL

## Requirements
- Python 3.10+
- WSL (Windows Subsystem for Linux) if running on Windows

## Installation

Clone the repository:
\```bash
git clone https://github.com/mattmoore93/GeospatialDataComparison.git
cd GeospatialDataComparison
\```

Create and activate a virtual environment:
\```bash
python3 -m venv geo_env
source geo_env/bin/activate
\```

Install dependencies:
\```bash
pip install -r requirements.txt
\```

## Usage

Run the script:
\```bash
python3 GeospatialDataComparison.py
\```

You will be prompted to choose a mode:
\```
1  Compare two specific files
2  Match one file against a folder of files
3  Compare all files in a folder against each other
q  Quit
\```

Then enter file or folder paths when prompted. Windows paths 
(C:\Users\...) are accepted and auto-converted.

## Output

Each run saves two files to your project directory:
| File | Description |
|------|-------------|
| `geo_comparison_TIMESTAMP.json` | Full results, nested detail per layer |
| `geo_comparison_TIMESTAMP.csv`  | Flat table, easy to open in Excel     |

## Tech Stack
- **GeoPandas** — geo layer loading and spatial DataFrames
- **Shapely** — geometric operations and similarity metrics
- **Fiona** — KML/KMZ file reading
- **Scikit-learn / NumPy / SciPy** — numerical scoring and distance metrics
- **RapidFuzz** — metadata fuzzy string matching
- **Pandas** — tabular output and CSV export

## Author
Matt Moore — [github.com/mattmoore93](https://github.com/mattmoore93)
