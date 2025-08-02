# main.py

"""
Main orchestrator for the in5 startup scraper and processor.
Uses concurrency for both scraping and data processing to maximize speed.
"""

import os
import argparse
import pandas as pd
import numpy as np
from playwright.async_api import async_playwright
import asyncio
import glob
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# Project modules
import config
from infive_scraper import InFiveScraper
from app_scraper import AppScraper
from vector_store import VectorStore
from website_scraper import WebsiteScraper

# --- Global instances for processing ---
# These are initialized in the processing function to be shared across threads.
app_scraper = None
website_scraper = None
vector_store = None

# --- Define the canonical order and headers for the final CSV ---
CSV_HEADERS = [
    "name", "in5_profile_link", "website", "industry", "profile_description", "has_login_or_signup",
    "play_store_app_title", "play_store_app_description", "play_store_app_genre",
    "play_store_app_score", "play_store_app_ratings", "play_store_app_developer", "play_store_app_url",
    "apple_store_app_title", "apple_store_app_description", "apple_store_app_genre",
    "apple_store_app_score", "apple_store_app_ratings", "apple_store_app_developer", "apple_store_app_url"
]

def process_single_company(company_data, do_app_processing: bool, do_website_processing: bool):
    """
    The core logic for processing one company. This function is executed by worker threads.
    It scrapes for app info and website data, prepares a flattened data row with all
    headers, and adds the data to the vector store.
    """
    global app_scraper, vector_store, website_scraper

    # --- Initialize a full row with NA (Not Available) values ---
    output_row = {header: np.nan for header in CSV_HEADERS}

    try:
        company_name = company_data.get('name')
        if not company_name:
            print("⚠️ Skipping row with no company name.")
            return output_row # Return an empty row with NA values

        print(f"--- Processing {company_name} ---")

        # --- Populate basic info from the initial scrape ---
        output_row.update({
            "name": company_name,
            "in5_profile_link": company_data.get('in5_profile_link'),
            "website": company_data.get('website'),
            "industry": company_data.get('industry'),
            "profile_description": company_data.get('profile_description'),
        })
        website_url = company_data.get('website', '')

        # --- Conditionally perform enrichment scraping ---
        app_details = []
        if do_app_processing:
            if not app_scraper:
                raise RuntimeError("AppScraper not initialized.")
            app_details = app_scraper.scrape_apps(company_name)

        has_login_or_signup = False
        if do_website_processing:
            if not website_scraper:
                raise RuntimeError("WebsiteScraper not initialized.")
            has_login_or_signup = website_scraper.check_for_login_or_signup(website_url)

        output_row['has_login_or_signup'] = has_login_or_signup

        # --- Add app data to the row if it was found ---
        if do_app_processing and app_details:
            play_store_app = next((app for app in app_details if app['store'] == 'Google Play'), None)
            apple_store_app = next((app for app in app_details if app['store'] == 'Apple App Store'), None)

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

        # --- Vectorize the data (if vector store is enabled) ---
        if vector_store:
            startup_data_for_vector_store = {
                "name": company_name,
                "profile_description": output_row.get('profile_description', ''),
                "website": website_url,
                "industry": output_row.get('industry', ''),
                "app_details": app_details,
                "has_login_signup": has_login_or_signup
            }
            vector_store.add_startup_data(startup_data_for_vector_store)

        return output_row

    except Exception as e:
        print(f"❌ Critical error processing company '{company_data.get('name', 'N/A')}': {e}")
        # Return the row with as much data as was gathered before the error
        return output_row

def process_data_concurrently(do_app_processing: bool, do_website_processing: bool):
    """
    Loads scraped data, then uses a thread pool to concurrently enrich it
    with app info and/or website data, store it in a vector DB, and save
    the combined results to a CSV.
    """
    global app_scraper, vector_store, website_scraper
    print("\n--- Starting Concurrent Data Processing and Vectorization ---")
    
    csv_files = glob.glob(os.path.join(config.OUTPUT_DIR, f"{config.OUTPUT_FILENAME_BASE}_*.csv"))
    if not csv_files:
        print(f"❌ No CSV files found in '{config.OUTPUT_DIR}'. Please run with --scrape first.")
        return

    df = pd.concat((pd.read_csv(f) for f in csv_files), ignore_index=True)
    df.drop_duplicates(subset=['in5_profile_link'], inplace=True)
    df.dropna(subset=['name'], inplace=True)
    df.fillna({'profile_description': ''}, inplace=True)
    companies_to_process = df.to_dict('records')
    
    print(f"Found {len(companies_to_process)} total startups to process from {len(csv_files)} files.")

    # Initialize shared instances based on flags
    vector_store = VectorStore()
    if do_app_processing:
        print("-> App processing is enabled.")
        app_scraper = AppScraper()
    if do_website_processing:
        print("-> Website processing is enabled.")
        website_scraper = WebsiteScraper()

    all_processed_data = []
    # Use functools.partial to pass the processing flags to the worker function
    worker_function = partial(process_single_company, 
                              do_app_processing=do_app_processing, 
                              do_website_processing=do_website_processing)

    with ThreadPoolExecutor(max_workers=config.MAX_PROCESSING_WORKERS, thread_name_prefix='CompanyProcessor') as executor:
        # Execute the processing for all companies and store the results
        results = list(executor.map(worker_function, companies_to_process))
        all_processed_data = results

    # --- Save the combined data to a single CSV file ---
    if all_processed_data:
        print(f"\n--- Saving {len(all_processed_data)} processed startups to combined.csv ---")
        # Create DataFrame from the list of dictionaries
        combined_df = pd.DataFrame(all_processed_data)
        
        # Ensure the DataFrame uses the canonical header order
        combined_df = combined_df.reindex(columns=CSV_HEADERS)

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
            # Use a new context for each task for better isolation
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
    parser.add_argument("--scrape", action="store_true", help="Enable the initial scraping workflow to gather company data.")
    parser.add_argument("--letter", type=str, help="Scrape a single letter. Requires --scrape.")
    parser.add_argument("--all", action="store_true", help="Scrape all letters. Requires --scrape.")
    parser.add_argument("--process-apps", action="store_true", help="Process data to find app store information.")
    parser.add_argument("--process-websites", action="store_true", help="Process data to check websites for login/signup features.")
    
    args = parser.parse_args()

    if args.scrape:
        asyncio.run(main_async(args))
    elif args.process_apps or args.process_websites:
        # Combine processing into one function call
        process_data_concurrently(
            do_app_processing=args.process_apps, 
            do_website_processing=args.process_websites
        )
    else:
        parser.print_help()
        print("\nError: Please specify a workflow: --scrape, --process-apps, or --process-websites.")
