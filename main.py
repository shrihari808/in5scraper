# main.py

"""
Main orchestrator for the in5 startup scraper.

This script handles command-line arguments to allow for scraping all startups
or just those for a specific letter. It manages the browser lifecycle and
delegates the scraping task for each letter to the InFiveScraper class.

Usage:
  - Scrape all startups from '#' to 'Z':
    python main.py --all

  - Scrape only startups for a specific letter (e.g., 'C'):
    python main.py --letter C
"""

import os
import argparse
import pandas as pd
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import config
from infive_scraper import InFiveScraper

def main():
    """
    Main function to parse arguments and run the selected scraping process.
    """
    parser = argparse.ArgumentParser(description="Scrape the in5 startup directory.")
    parser.add_argument(
        "--letter",
        type=str,
        help="Scrape startups for a single specific letter (e.g., 'A', 'B', '#')."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape all startups, iterating from '#' through 'Z'."
    )
    args = parser.parse_args()

    if not args.letter and not args.all:
        parser.print_help()
        print("\nError: Please provide an argument, either --letter or --all.")
        return

    # --- Create output directory if it doesn't exist ---
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)
        print(f"Created output directory: {config.OUTPUT_DIR}")

    # --- Determine which letters to scrape ---
    letters_to_process = []
    if args.letter:
        letters_to_process.append(args.letter.upper())
    elif args.all:
        letters_to_process = config.SCRAPE_CHARACTERS

    # --- Initialize Browser ---
    print("🚀 Initializing Playwright and launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.HEADLESS_MODE)
        page = browser.new_page()
        
        try:
            # Instantiate the scraper with the page object
            scraper = InFiveScraper(page)

            # --- Loop through and process each letter ---
            for letter in letters_to_process:
                try:
                    # **FIX**: Navigate to the page before scraping each letter.
                    # This ensures a clean state and prevents errors from carried-over page content.
                    print(f"\n---\n🔄 Navigating to the main directory for letter: '{letter}'...")
                    page.goto(config.BASE_URL, timeout=config.PAGE_TIMEOUT, wait_until='domcontentloaded')
                    
                    df = scraper.scrape_by_letter(letter)

                    if not df.empty:
                        # Sanitize letter for filename
                        filename_letter = "numeric" if letter == "#" else letter
                        output_path = os.path.join(
                            config.OUTPUT_DIR,
                            f"{config.OUTPUT_FILENAME_BASE}_{filename_letter}.csv"
                        )
                        df.to_csv(output_path, index=False, encoding='utf-8')
                        print(f"✅ Successfully saved {len(df)} startups to '{output_path}'")
                    else:
                        print(f"⚠️ No startups found or saved for letter '{letter}'.")
                
                except PlaywrightError as e:
                    print(f"❌ A Playwright error occurred for letter '{letter}': {e}")
                    print("   -> Moving to the next letter.")
                    continue # Continue to the next letter in the loop

        except Exception as e:
            print(f"❌ A critical error occurred in the main process: {e}")
        finally:
            print("\nClosing browser...")
            browser.close()
            print("✅ Browser closed.")

if __name__ == "__main__":
    main()
