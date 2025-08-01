# main.py

"""
Main orchestrator for the in5 startup scraper.

This script initializes the scraper, runs the scraping process,
and saves the collected data to a CSV file as defined in the config.
"""

from infive_scraper import InFiveScraper
import config

def main():
    """
    The main function to execute the scraper.
    """
    print("--- Starting in5 Startup Scraper ---")
    
    # Create an instance of the scraper
    scraper = InFiveScraper()
    
    # Run the scraping process
    startup_df = scraper.scrape_all_startups()

    # Save the results if data was successfully scraped
    if not startup_df.empty:
        try:
            startup_df.to_csv(config.OUTPUT_CSV_FILE, index=False, encoding='utf-8')
            print(f"\n🎉 --- Scraping Finished --- 🎉")
            print(f"Successfully saved {len(startup_df)} startups to '{config.OUTPUT_CSV_FILE}'")
        except Exception as e:
            print(f"\n❌ Error saving data to CSV: {e}")
    else:
        print("\n⚠️ No data was scraped. The output file was not created.")

if __name__ == "__main__":
    main()
