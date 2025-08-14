# plat_map_crawler.py
Retrieves Plat Map PDF files dynamically by parsing adjacent map numbers (thereby finding additional associated file names) from Esmerelda County, NV's Property Tax Query public website.  This code was developed to help make submitting corrections for roadway mislabeling to major mapping providers more convenient and repeatable.

---

# Esmeralda County Plat Map Retrieval Utility

A Python utility to systematically download plat map PDFs from the Esmeralda County, Nevada website for mapping accuracy improvements.

## Purpose

This tool helps improve the accuracy of online mapping services (Google Maps, OpenStreetMap, Apple Maps) for Esmeralda County residents by:

- Retrieving official plat map data from the county website
- Providing reference material to identify incorrect road names, directions, and designations
- Supporting efforts to fix delivery and navigation issues caused by inaccurate mapping data

## Background

Esmeralda County is a uniquely rural and sparsely populated area where mapping inaccuracies significantly impact daily life:
- 3-hour trips for groceries and supplies through mountain passes
- Package delivery failures due to mislabeled roads and missing street signs
- Years of accumulated mapping errors need systematic correction

## How It Works

The utility uses a web crawling approach:

1. **Starts** with a seed plat map (001-01)
2. **Downloads** the PDF from the county website
3. **Parses** the PDF to extract circled reference numbers pointing to adjacent maps
4. **Follows** these references to discover and download all connected plat maps
5. **Continues** until all discoverable maps are retrieved

## URL Pattern

Esmeralda County plat maps follow this URL structure:
```
https://esmeraldanv.devnetwedge.com/PropertyImages/Platmaps/{MAP_ID}.pdf
```

Example: `https://esmeraldanv.devnetwedge.com/PropertyImages/Platmaps/001-24.pdf`

## Features

- **Automatic discovery** of all plat maps by following cross-references
- **Respectful crawling** with 1-second delays between requests
- **Skip existing files** to avoid re-downloading
- **Comprehensive logging** of all activities and errors
- **Error handling** continues processing even if individual maps fail
- **Smart PDF parsing** to distinguish map references from lot numbers

## Requirements

```bash
pip install requests PyMuPDF
```

## Usage

```bash
python plat_map_crawler.py
```

The script will:
- Create a `plat_maps/` directory for downloaded PDFs
- Start crawling from map 001-01
- Log all activity to `plat_map_crawler.log` and console
- Continue until all discoverable maps are downloaded

## Output

- **PDFs**: Downloaded to `plat_maps/` directory with original naming (e.g., `001-24.pdf`)
- **Logs**: Detailed activity log in `plat_map_crawler.log`
- **Console output**: Real-time progress updates

## Configuration

Key settings in the script:
- `STARTING_MAP = "001-01"` - Initial map to begin crawling
- `DELAY_SECONDS = 1` - Delay between requests (be respectful to server)
- `OUTPUT_DIR = "plat_maps"` - Directory for downloaded PDFs

## Map Reference Detection

The script identifies adjacent map references by:
- Extracting text from PDFs using multiple methods
- Looking for 2-digit numbers in the 1-50 range (likely map references)
- Filtering out 3-digit lot numbers (252, 253, etc.)
- Converting found numbers to full format (02 → 001-02)

## Files

- `plat_map_crawler.py` - Main crawling script
- `plat_map_crawler.log` - Generated activity log (created when script runs)
- `plat_maps/` - Downloaded PDF files (created when script runs)

## Next Steps

Once plat maps are downloaded, they can be:
- Analyzed to extract street names and directional information
- Cross-referenced with online mapping services
- Used to identify and report mapping inaccuracies
- Processed to generate correction requests for mapping providers

## Rural Impact

This project directly supports residents of one of Nevada's most remote counties, helping solve real-world problems with navigation, deliveries, and emergency services that result from mapping inaccuracies.
