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
    It scrapes for app info, prepares a flattened data row for CSV export,
    and adds the combined data to the vector store.
    """
    global app_scraper, vector_store
    try:
        company_name = company_data['name']
        print(f"--- Processing {company_name} ---")

        # Scrape for app information
        app_details = app_scraper.scrape_apps(company_name)

        # --- Prepare flattened data for CSV ---
        # Start with the base company info
        output_row = {
            "name": company_name,
            "in5_profile_link": company_data.get('in5_profile_link', ''),
            "website": company_data.get('website', ''),
            "industry": company_data.get('industry', ''),
            "profile_description": company_data.get('profile_description', '')
        }

        # Separate app details by store
        play_store_app = next((app for app in app_details if app['store'] == 'Google Play'), None)
        apple_store_app = next((app for app in app_details if app['store'] == 'Apple App Store'), None)

        # Add Google Play data if it exists
        if play_store_app:
            output_row.update({
                "play_store_app_title": play_store_app.get('title'),
                "play_store_app_description": play_store_app.get('description'),
                "play_store_app_genre": play_store_app.get('genre'),
                "play_store_app_score": play_store_app.get('score'),
                "play_store_app_ratings": play_store_app.get('ratings'),
                "play_store_app_developer": play_store_app.get('developer'),
                "play_store_app_url": play_store_app.get('url')
            })

        # Add Apple App Store data if it exists
        if apple_store_app:
            output_row.update({
                "apple_store_app_title": apple_store_app.get('title'),
                "apple_store_app_description": apple_store_app.get('description'),
                "apple_store_app_genre": apple_store_app.get('genre'),
                "apple_store_app_score": apple_store_app.get('score'),
                "apple_store_app_ratings": apple_store_app.get('ratings'),
                "apple_store_app_developer": apple_store_app.get('developer'),
                "apple_store_app_url": apple_store_app.get('url')
            })

        # --- Vectorize the data ---
        # Prepare data for vectorization (this part remains the same)
        startup_data_for_vector_store = {
            "name": company_name,
            "profile_description": company_data.get('profile_description', ''),
            "website": company_data.get('website', ''),
            "industry": company_data.get('industry', ''),
            "app_details": app_details
        }
        vector_store.add_startup_data(startup_data_for_vector_store)

        return output_row

    except Exception as e:
        print(f"❌ Critical error processing company '{company_data.get('name', 'N/A')}': {e}")
        return None


def process_and_vectorize_data_concurrently():
    """
    Loads scraped data, then uses a thread pool to concurrently enrich it
    with app info, store it in a vector DB, and save the combined results to a CSV.
    """
    global app_scraper, vector_store
    print("\n--- Starting Concurrent Data Processing and Vectorization ---")
    
    csv_files = glob.glob(os.path.join(config.OUTPUT_DIR, "*.csv"))
    if not csv_files:
        print("❌ No CSV files found. Please run with --scrape first.")
        return

    df = pd.concat((pd.read_csv(f) for f in csv_files), ignore_index=True)
    df.drop_duplicates(subset=['in5_profile_link'], inplace=True)
    df.dropna(subset=['name'], inplace=True)
    df.fillna({'profile_description': ''}, inplace=True)
    companies_to_process = df.to_dict('records')
    
    print(f"Found {len(companies_to_process)} total startups to process from {len(csv_files)} files.")

    # Initialize shared instances
    app_scraper = AppScraper()
    vector_store = VectorStore()

    all_processed_data = []
    # Use a ThreadPoolExecutor to process companies in parallel
    with ThreadPoolExecutor(max_workers=config.MAX_PROCESSING_WORKERS, thread_name_prefix='CompanyProcessor') as executor:
        # map will return the results as they are completed
        results = executor.map(process_single_company, companies_to_process)
        
        # Collect all non-None results
        all_processed_data = [res for res in results if res is not None]

    # --- Save the combined data to a single CSV file ---
    if all_processed_data:
        print(f"\n--- Saving {len(all_processed_data)} processed startups to combined.csv ---")
        combined_df = pd.DataFrame(all_processed_data)
        
        # Define the full header to ensure column order
        headers = [
            "name", "in5_profile_link", "website", "industry", "profile_description",
            "play_store_app_title", "play_store_app_description", "play_store_app_genre",
            "play_store_app_score", "play_store_app_ratings", "play_store_app_developer", "play_store_app_url",
            "apple_store_app_title", "apple_store_app_description", "apple_store_app_genre",
            "apple_store_app_score", "apple_store_app_ratings", "apple_store_app_developer", "apple_store_app_url"
        ]
        
        # Reorder DataFrame columns according to the header list
        combined_df = combined_df.reindex(columns=headers)

        output_path = os.path.join(config.OUTPUT_DIR, "combined.csv")
        combined_df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"✅ Successfully saved combined data to '{output_path}'")
    else:
        print("--- No data was processed to save to combined.csv ---")
        
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
