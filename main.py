# main.py

"""
Main orchestrator for the in5 startup scraper and processor.
Uses concurrency for both scraping and data processing to maximize speed.
"""

import os
import argparse
import pandas as pd
from playwright.async_api import async_playwright
import asyncio
import glob
from concurrent.futures import ThreadPoolExecutor

# Project modules
import config
from infive_scraper import InFiveScraper
from app_scraper import AppScraper
from vector_store import VectorStore

# --- Global instances for processing ---
# Initialized once to be shared across threads.
app_scraper = None
vector_store = None

def process_single_company(company_data):
    """
    The core logic for processing one company. This function is executed by worker threads.
    It scrapes for app info and adds the combined data to the vector store.
    """
    global app_scraper, vector_store
    try:
        company_name = company_data['name']
        print(f"--- Processing {company_name} ---")

        # Scrape for app information
        app_details = app_scraper.scrape_apps(company_name)

        # Prepare data for vectorization
        startup_data = {
            "name": company_name,
            "profile_description": company_data.get('profile_description', ''),
            "website": company_data.get('website', ''),
            "industry": company_data.get('industry', ''),
            "app_details": app_details
        }

        # Add to vector store
        vector_store.add_startup_data(startup_data)
    except Exception as e:
        print(f"❌ Critical error processing company '{company_data.get('name', 'N/A')}': {e}")


def process_and_vectorize_data_concurrently():
    """
    Loads scraped data, then uses a thread pool to concurrently enrich it
    with app info and store it in a vector DB.
    """
    global app_scraper, vector_store
    print("\n--- Starting Concurrent Data Processing and Vectorization ---")
    
    csv_files = glob.glob(os.path.join(config.OUTPUT_DIR, "*.csv"))
    if not csv_files:
        print("❌ No CSV files found. Please run with --scrape first.")
        return

    df = pd.concat((pd.read_csv(f) for f in csv_files), ignore_index=True)
    df.dropna(subset=['name'], inplace=True)
    df.fillna({'profile_description': ''}, inplace=True) # Ensure description is not NaN
    companies_to_process = df.to_dict('records')
    
    print(f"Found {len(companies_to_process)} total startups to process from {len(csv_files)} files.")

    # Initialize shared instances
    app_scraper = AppScraper()
    vector_store = VectorStore()

    # Use a ThreadPoolExecutor to process companies in parallel
    with ThreadPoolExecutor(max_workers=config.MAX_PROCESSING_WORKERS, thread_name_prefix='CompanyProcessor') as executor:
        # Submit all companies to the executor
        executor.map(process_single_company, companies_to_process)
        
    print("\n--- ✅ All startups have been processed and vectorized. ---")


async def scrape_letter_task(browser, letter, semaphore):
    """An async task to scrape all startups for a single letter."""
    async with semaphore:
        print(f"🚀 Starting scraping task for letter: '{letter}'")
        context = None
        try:
            context = await browser.new_context()
            page = await context.new_page()
            scraper = InFiveScraper(browser, page)
            await page.goto(config.BASE_URL, timeout=config.PAGE_TIMEOUT, wait_until='domcontentloaded')
            df = await scraper.scrape_by_letter(letter)
            if not df.empty:
                output_path = os.path.join(config.OUTPUT_DIR, f"{config.OUTPUT_FILENAME_BASE}_{letter}.csv")
                df.to_csv(output_path, index=False, encoding='utf-8')
                print(f"✅ Saved {len(df)} startups to '{output_path}'")
        except Exception as e:
            print(f"❌ An unexpected error occurred for letter '{letter}': {e}")
        finally:
            if context: await context.close()
            print(f"✅ Finished scraping task for letter: '{letter}'")


async def main_async(args):
    """The main async entry point for scraping."""
    if not args.letter and not args.all:
        print("\nError: --scrape requires either --letter or --all.")
        return
        
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)

    letters_to_process = [args.letter.upper()] if args.letter else config.SCRAPE_CHARACTERS

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS_MODE)
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_TASKS)
        tasks = [scrape_letter_task(browser, letter, semaphore) for letter in letters_to_process]
        await asyncio.gather(*tasks)
        await browser.close()
    print("\n--- ✅ Scraping workflow completed. ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape and process the in5 startup directory.")
    parser.add_argument("--scrape", action="store_true", help="Enable the scraping workflow.")
    parser.add_argument("--letter", type=str, help="Scrape a single letter. Requires --scrape.")
    parser.add_argument("--all", action="store_true", help="Scrape all letters. Requires --scrape.")
    parser.add_argument("--process", action="store_true", help="Process CSVs to find app data and vectorize.")
    args = parser.parse_args()

    if args.scrape:
        asyncio.run(main_async(args))
    elif args.process:
        process_and_vectorize_data_concurrently()
    else:
        parser.print_help()
        print("\nError: Please specify a workflow: --scrape or --process.")
