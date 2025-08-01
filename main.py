# main.py

"""
Main orchestrator for the in5 startup scraper.

This script handles command-line arguments to allow for scraping all startups
or just those for a specific letter. It uses asyncio and Playwright's async API
to run scraping tasks concurrently, significantly speeding up the process.

Usage:
  - Scrape all startups from '#' to 'Z' concurrently:
    python main.py --all

  - Scrape only startups for a specific letter (e.g., 'C'):
    python main.py --letter C
"""

import os
import argparse
import pandas as pd
from playwright.async_api import async_playwright, Error as PlaywrightError
import config
from infive_scraper import InFiveScraper
import asyncio

async def scrape_letter_task(browser, letter, semaphore):
    """
    A self-contained, async task to scrape all startups for a single letter.
    It uses a semaphore to limit the number of concurrently active tasks.
    It creates its own browser context and page to ensure isolation.

    Args:
        browser: The shared async Playwright browser instance.
        letter (str): The letter to scrape (e.g., 'A').
        semaphore (asyncio.Semaphore): Semaphore to control concurrency.
    """
    async with semaphore:
        print(f"🚀 Starting task for letter: '{letter}'")
        context = None
        try:
            # Create an isolated browser context and page for this task
            context = await browser.new_context()
            page = await context.new_page()

            scraper = InFiveScraper(browser, page)

            print(f"🔄 Navigating to the main directory for letter: '{letter}'...")
            await page.goto(config.BASE_URL, timeout=config.PAGE_TIMEOUT, wait_until='domcontentloaded')

            df = await scraper.scrape_by_letter(letter)

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
        except Exception as e:
            print(f"❌ An unexpected critical error occurred for letter '{letter}': {e}")
        finally:
            if context:
                await context.close()
                print(f"Context for letter '{letter}' closed.")
            print(f"✅ Finished task for letter: '{letter}'")

async def main():
    """
    Main async function to parse arguments and run the scraping process.
    """
    parser = argparse.ArgumentParser(description="Scrape the in5 startup directory concurrently.")
    parser.add_argument(
        "--letter",
        type=str,
        help="Scrape startups for a single specific letter (e.g., 'A', 'B', '#')."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape all startups concurrently, iterating from '#' through 'Z'."
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

    # --- Initialize Browser and run tasks ---
    print("🚀 Initializing Playwright and launching a shared browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS_MODE)
        
        print(f"Scraping {len(letters_to_process)} letters using up to {config.MAX_CONCURRENT_TASKS} concurrent tasks...")
        
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_TASKS)
        
        # Create a list of async tasks to run
        tasks = [scrape_letter_task(browser, letter, semaphore) for letter in letters_to_process]
        
        # Run all tasks concurrently and wait for them to complete
        await asyncio.gather(*tasks)

        print("\nAll scraping tasks have completed.")
        await browser.close()
        print("✅ Shared browser closed.")

if __name__ == "__main__":
    asyncio.run(main())
