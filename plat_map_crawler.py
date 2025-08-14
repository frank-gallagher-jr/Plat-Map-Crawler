#!/usr/bin/env python3
"""
Esmeralda County Plat Map Retrieval Utility

This script systematically downloads plat map PDFs from the Esmeralda County website
by following cross-references between maps to discover the complete set of available maps.
"""

import os
import re
import time
import logging
from collections import deque
from pathlib import Path
from typing import Set, List
import requests
import fitz  # PyMuPDF

# Configuration
BASE_URL = "https://esmeraldanv.devnetwedge.com/PropertyImages/Platmaps/{}.pdf"
OUTPUT_DIR = "plat_maps"
DELAY_SECONDS = 1

# Community prefixes known in Esmeralda County
COMMUNITY_PREFIXES = [
    #"000", # Mining Claims
    "001",  # Goldfield, NV
    "002",  # Silverpeak, NV
    "003",  # Gold Point, NV
    "004",  # Lida, NV 
    "006",  # Lida, NV
    "007",  # Dyer, NV
    #"101",  # Unknown (Additional Goldfield Plats?)
]

# Starting maps for each community
STARTING_MAPS = [
    "001-01",  # Goldfield
    "002-01",  # Silverpeak
    "003-01",  # Gold Point
    "004-01",  # Lida
    "006-01",  # Lida
    "007-01",  # Dyer (changed from 007-65 to 007-01 since we have that example)
]

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed output
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('plat_map_crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_output_directory(output_dir: str) -> Path:
    """Create output directory if it doesn't exist."""
    path = Path(output_dir)
    path.mkdir(exist_ok=True)
    logger.info(f"Output directory: {path.absolute()}")
    return path


def download_pdf(map_id: str, output_path: Path) -> bool:
    """
    Download a single PDF file.
    
    Args:
        map_id: The map ID (e.g., '001-01')
        output_path: Path object for the output directory
    
    Returns:
        True if successful, False otherwise
    """
    url = BASE_URL.format(map_id)
    file_path = output_path / f"{map_id}.pdf"
    
    # Skip if file already exists
    if file_path.exists():
        logger.info(f"Skipping {map_id} - already exists")
        return True
    
    try:
        logger.info(f"Downloading {map_id} from {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Successfully downloaded {map_id}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {map_id}: {e}")
        return False


def extract_map_references(pdf_path: Path) -> List[str]:
    """
    Extract circled map reference numbers from a PDF.
    Uses multiple extraction methods to find references.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        List of map IDs found in the PDF
    """
    references = []
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Method 1: Extract all text (including text in different layers)
            text_dict = page.get_text("dict")
            all_text_content = []
            
            def extract_text_from_dict(obj):
                """Recursively extract text from PDF dictionary structure."""
                if isinstance(obj, dict):
                    if "spans" in obj:
                        for span in obj["spans"]:
                            if "text" in span:
                                all_text_content.append(span["text"])
                    for key, value in obj.items():
                        if key in ["blocks", "lines", "spans"]:
                            if isinstance(value, list):
                                for item in value:
                                    extract_text_from_dict(item)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_text_from_dict(item)
            
            extract_text_from_dict(text_dict)
            combined_text = " ".join(all_text_content)
            
            # Method 2: Also get regular text extraction
            regular_text = page.get_text()
            full_text = combined_text + " " + regular_text
            
            logger.debug(f"Extracted text from {pdf_path.name}, page {page_num}: {repr(full_text[:500])}")
            
            # Also log all unique short text pieces for debugging
            short_texts = re.findall(r'\b\w{1,4}\b', full_text)
            unique_short = sorted(set(short_texts))
            logger.debug(f"All short text pieces (1-4 chars): {unique_short}")
            
            # Look for potential map reference patterns
            # Based on visual inspection, we expect 2-digit numbers like 02, 03, 04
            
            # First, look for full format references
            full_format_matches = re.findall(r'\b(0\d{2}-\d{2})\b', full_text)
            for match in full_format_matches:
                references.append(match)
            
            # Then look for 2-digit numbers that could be map references
            # We need to be careful to distinguish between map references and lot numbers
            two_digit_matches = re.findall(r'\b(\d{2})\b', full_text)
            
            found_numbers = set()
            for match in two_digit_matches:
                num = int(match)
                # Map references are typically small numbers (1-50 range for adjacent maps)
                # Lot numbers are typically larger (100+) or have 3+ digits
                if 1 <= num <= 50:  # Narrower range for likely map references
                    found_numbers.add(num)
                    logger.debug(f"Found potential map reference: {match}")
            
            # Convert found numbers to proper format
            for num in found_numbers:
                formatted_id = f"001-{num:02d}"
                references.append(formatted_id)
                
            logger.debug(f"Two-digit numbers found: {sorted([int(x) for x in two_digit_matches])}")
            logger.debug(f"Filtered map references: {sorted(found_numbers)}")
        
        doc.close()
        
        # Remove duplicates, exclude the current map, and sort
        current_map = pdf_path.stem  # Get filename without extension
        references = list(set(references))
        references = [ref for ref in references if ref != current_map]
        references.sort()
        
        logger.info(f"Found {len(references)} potential references in {pdf_path.name}: {references}")
        
        # If we found very few or no references, let's try some adjacent numbers as fallback
        if len(references) < 3:
            logger.warning(f"Found fewer than 3 references in {pdf_path.name}, using adjacent number fallback")
            # Extract the number from current map (e.g., "001-01" -> 1)
            if current_map.startswith("001-"):
                try:
                    current_num = int(current_map.split("-")[1])
                    # Add likely adjacent maps
                    fallback_refs = []
                    for offset in [-1, 1, 10, -10]:  # Try adjacent and nearby maps
                        adjacent_num = current_num + offset
                        if 1 <= adjacent_num <= 99:
                            fallback_refs.append(f"001-{adjacent_num:02d}")
                    
                    references.extend(fallback_refs)
                    references = list(set(references))  # Remove duplicates
                    references.sort()
                    logger.info(f"Added fallback references: {fallback_refs}")
                except ValueError:
                    pass
        
    except Exception as e:
        logger.error(f"Failed to extract references from {pdf_path}: {e}")
    
    return references


def crawl_all_communities(output_dir: Path) -> None:
    """
    Crawl all known communities in Esmeralda County.
    
    Args:
        output_dir: Directory to save PDFs
    """
    logger.info("Starting multi-community crawl for Esmeralda County")
    
    total_processed = 0
    total_failed = 0
    
    for starting_map in STARTING_MAPS:
        community_prefix = starting_map.split("-")[0]
        logger.info(f"Starting crawl for community {community_prefix} from map: {starting_map}")
        
        processed, failed = hybrid_crawl_community(starting_map, output_dir)
        total_processed += processed
        total_failed += failed
        
        logger.info(f"Completed community {community_prefix}: {processed} maps downloaded, {failed} failed")
    
    logger.info(f"All communities complete! Total: {total_processed} maps downloaded, {total_failed} failed")
    return total_processed, total_failed


def crawl_plat_maps(starting_map: str, output_dir: Path) -> tuple[int, int]:
    """
    Main crawling function that downloads maps and follows references for a single community.
    
    Args:
        starting_map: The map ID to start with
        output_dir: Directory to save PDFs
    
    Returns:
        Tuple of (processed_count, failed_count)
    """
    queue = deque([starting_map])
    processed: Set[str] = set()
    failed: Set[str] = set()
    
    community_prefix = starting_map.split("-")[0]
    logger.info(f"Starting crawl for community {community_prefix} from map: {starting_map}")
    
    while queue:
        current_map = queue.popleft()
        
        # Skip if already processed
        if current_map in processed:
            continue
            
        # Skip if previously failed
        if current_map in failed:
            continue
        
        logger.info(f"Processing map: {current_map} ({len(processed)} completed, {len(queue)} in queue)")
        
        # Download the PDF
        success = download_pdf(current_map, output_dir)
        
        if not success:
            failed.add(current_map)
            continue
            
        processed.add(current_map)
        
        # Wait to be respectful to the server
        time.sleep(DELAY_SECONDS)
        
        # Extract references from the downloaded PDF
        pdf_path = output_dir / f"{current_map}.pdf"
        references = extract_map_references(pdf_path)
        
        # Add new references to the queue (only for the same community)
        for ref in references:
            if ref.startswith(community_prefix + "-") and ref not in processed and ref not in failed and ref not in queue:
                queue.append(ref)
                logger.info(f"Added {ref} to download queue")
        
        logger.info(f"Queue size: {len(queue)}, Processed: {len(processed)}, Failed: {len(failed)}")
    
    logger.info(f"Community {community_prefix} crawl complete! Downloaded {len(processed)} maps, {len(failed)} failed")
    
    if failed:
        logger.warning(f"Failed to download from community {community_prefix}: {sorted(failed)}")
    
    return len(processed), len(failed)


def systematic_discovery(community_prefix: str, output_dir: Path, max_attempts: int = 100) -> Set[str]:
    """
    Systematically try sequential map numbers for a community to discover all available maps.
    
    Args:
        community_prefix: The community prefix (e.g., "001", "002", etc.)
        output_dir: Directory to save PDFs
        max_attempts: Maximum number of sequential attempts to try
    
    Returns:
        Set of successfully discovered map IDs
    """
    discovered = set()
    consecutive_failures = 0
    max_consecutive_failures = 10  # Stop after 10 consecutive failures
    
    logger.info(f"Starting systematic discovery for community {community_prefix}")
    
    for i in range(1, max_attempts + 1):
        map_id = f"{community_prefix}-{i:02d}"
        
        # Skip if already processed
        if (output_dir / f"{map_id}.pdf").exists():
            logger.debug(f"Skipping {map_id} - already exists")
            discovered.add(map_id)
            consecutive_failures = 0
            continue
        
        logger.info(f"Trying systematic discovery: {map_id}")
        success = download_pdf(map_id, output_dir)
        
        if success:
            discovered.add(map_id)
            consecutive_failures = 0
            logger.info(f"✓ Discovered {map_id} via systematic search")
        else:
            consecutive_failures += 1
            logger.debug(f"✗ {map_id} not found ({consecutive_failures} consecutive failures)")
            
            # Stop if we've had too many consecutive failures
            if consecutive_failures >= max_consecutive_failures:
                logger.info(f"Stopping systematic discovery for {community_prefix} after {consecutive_failures} consecutive failures")
                break
        
        # Be respectful to the server
        time.sleep(DELAY_SECONDS)
    
    logger.info(f"Systematic discovery for {community_prefix} complete: found {len(discovered)} maps")
    return discovered


def hybrid_crawl_community(starting_map: str, output_dir: Path) -> tuple[int, int]:
    """
    Hybrid approach: First try PDF-based crawling, then systematic discovery.
    
    Args:
        starting_map: The map ID to start with
        output_dir: Directory to save PDFs
    
    Returns:
        Tuple of (processed_count, failed_count)
    """
    community_prefix = starting_map.split("-")[0]
    logger.info(f"Starting hybrid crawl for community {community_prefix}")
    
    # Phase 1: PDF-based crawling (existing method)
    logger.info(f"Phase 1: PDF-based crawling for {community_prefix}")
    processed_pdf, failed_pdf = crawl_plat_maps(starting_map, output_dir)
    
    # Phase 2: Systematic discovery
    logger.info(f"Phase 2: Systematic discovery for {community_prefix}")
    discovered_systematic = systematic_discovery(community_prefix, output_dir)
    
    # Phase 3: Try to extract references from newly discovered maps
    logger.info(f"Phase 3: Processing newly discovered maps for {community_prefix}")
    newly_discovered = []
    for map_id in discovered_systematic:
        pdf_path = output_dir / f"{map_id}.pdf"
        if pdf_path.exists():
            references = extract_map_references(pdf_path)
            for ref in references:
                if ref.startswith(community_prefix + "-") and not (output_dir / f"{ref}.pdf").exists():
                    newly_discovered.append(ref)
    
    # Phase 4: Download any additional references found
    logger.info(f"Phase 4: Downloading additional references for {community_prefix}")
    additional_processed = 0
    additional_failed = 0
    
    for ref in newly_discovered:
        logger.info(f"Downloading additional reference: {ref}")
        success = download_pdf(ref, output_dir)
        if success:
            additional_processed += 1
        else:
            additional_failed += 1
        time.sleep(DELAY_SECONDS)
    
    total_processed = processed_pdf + len(discovered_systematic) + additional_processed
    total_failed = failed_pdf + additional_failed
    
    logger.info(f"Hybrid crawl complete for {community_prefix}:")
    logger.info(f"  PDF-based: {processed_pdf} found")
    logger.info(f"  Systematic: {len(discovered_systematic)} found")
    logger.info(f"  Additional: {additional_processed} found")
    logger.info(f"  Total: {total_processed} maps, {total_failed} failed")
    
    return total_processed, total_failed
    """
    Main crawling function that downloads maps and follows references for a single community.
    
    Args:
        starting_map: The map ID to start with
        output_dir: Directory to save PDFs
    
    Returns:
        Tuple of (processed_count, failed_count)
    """
    queue = deque([starting_map])
    processed: Set[str] = set()
    failed: Set[str] = set()
    
    community_prefix = starting_map.split("-")[0]
    logger.info(f"Starting crawl for community {community_prefix} from map: {starting_map}")
    
    while queue:
        current_map = queue.popleft()
        
        # Skip if already processed
        if current_map in processed:
            continue
            
        # Skip if previously failed
        if current_map in failed:
            continue
        
        logger.info(f"Processing map: {current_map} ({len(processed)} completed, {len(queue)} in queue)")
        
        # Download the PDF
        success = download_pdf(current_map, output_dir)
        
        if not success:
            failed.add(current_map)
            continue
            
        processed.add(current_map)
        
        # Wait to be respectful to the server
        time.sleep(DELAY_SECONDS)
        
        # Extract references from the downloaded PDF
        pdf_path = output_dir / f"{current_map}.pdf"
        references = extract_map_references(pdf_path)
        
        # Add new references to the queue (only for the same community)
        for ref in references:
            if ref.startswith(community_prefix + "-") and ref not in processed and ref not in failed and ref not in queue:
                queue.append(ref)
                logger.info(f"Added {ref} to download queue")
        
        logger.info(f"Queue size: {len(queue)}, Processed: {len(processed)}, Failed: {len(failed)}")
    
    logger.info(f"Community {community_prefix} crawl complete! Downloaded {len(processed)} maps, {len(failed)} failed")
    
    if failed:
        logger.warning(f"Failed to download from community {community_prefix}: {sorted(failed)}")
    
    return len(processed), len(failed)


def main():
    """Main entry point."""
    logger.info("Starting Esmeralda County Multi-Community Plat Map Retrieval")
    
    # Setup
    output_dir = setup_output_directory(OUTPUT_DIR)
    
    # Start crawling all communities
    total_processed, total_failed = crawl_all_communities(output_dir)
    
    # Summary
    pdf_files = list(output_dir.glob("*.pdf"))
    logger.info(f"Total PDF files in output directory: {len(pdf_files)}")
    
    # Group by community for summary
    communities = {}
    for pdf_file in pdf_files:
        prefix = pdf_file.stem.split("-")[0]
        if prefix not in communities:
            communities[prefix] = []
        communities[prefix].append(pdf_file.stem)
    
    print(f"\nCrawl completed!")
    print(f"Total maps downloaded: {total_processed}")
    print(f"Total failures: {total_failed}")
    print(f"\nBy community:")
    for prefix, maps in sorted(communities.items()):
        print(f"  {prefix}-XX: {len(maps)} maps")
    
    print(f"\nCheck the '{OUTPUT_DIR}' directory for downloaded plat maps.")
    print(f"See 'plat_map_crawler.log' for detailed logs.")


if __name__ == "__main__":
    main()
