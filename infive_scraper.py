# infive_scraper.py

"""
This module contains the core logic for scraping the in5 startup directory.
It uses Playwright to handle dynamic content loading (infinite scroll) and
to extract details from each startup's profile page.
"""

import time
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import config

class InFiveScraper:
    """
    A scraper for the in5.ae startup directory.
    """

    def __init__(self):
        """Initializes the scraper, setting up browser and page to None."""
        self.playwright = None
        self.browser = None
        self.page = None

    def _initialize_scraper(self):
        """
        Initializes the Playwright instance and launches a browser.
        This setup is separated to be called once per run.
        """
        print("🚀 Initializing Playwright and launching browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=config.HEADLESS_MODE
        )
        self.page = self.browser.new_page()
        print("✅ Browser initialized.")

    def _scrape_startup_details(self, profile_url):
        """
        Scrapes detailed information from a single startup's profile page.

        Args:
            profile_url (str): The URL of the startup's profile page.

        Returns:
            dict: A dictionary containing the startup's description, website,
                  and social media links.
        """
        details = {
            "description": None,
            "website": None,
            "linkedin": None,
            "twitter": None,
            "facebook": None,
            "instagram": None,
        }
        try:
            print(f"    -> Visiting details page: {profile_url}")
            self.page.goto(profile_url, timeout=config.PAGE_TIMEOUT)
            
            # Extract description
            description_selector = ".startup-description"
            if self.page.is_visible(description_selector):
                details["description"] = self.page.locator(description_selector).inner_text().strip()

            # Extract website and social links
            links_selector = ".startup-links a"
            links = self.page.locator(links_selector).all()
            for link_locator in links:
                href = link_locator.get_attribute("href")
                if not href:
                    continue
                
                if "linkedin.com" in href:
                    details["linkedin"] = href
                elif "twitter.com" in href:
                    details["twitter"] = href
                elif "facebook.com" in href:
                    details["facebook"] = href
                elif "instagram.com" in href:
                    details["instagram"] = href
                else:
                    # Assume the first non-social link is the website
                    if not details["website"]:
                         details["website"] = href
            
        except PlaywrightTimeoutError:
            print(f"      ⚠️ Timeout error while visiting {profile_url}")
        except Exception as e:
            print(f"      ❌ An unexpected error occurred on {profile_url}: {e}")
        
        return details


    def scrape_all_startups(self):
        """
        Orchestrates the entire scraping process. It navigates to the main directory,
        handles infinite scrolling, extracts basic info, and then visits each
        profile to get detailed information.

        Returns:
            pandas.DataFrame: A DataFrame containing all the scraped startup data.
        """
        self._initialize_scraper()
        all_startups_data = []
        try:
            print(f"  -> Navigating to the in5 directory: {config.BASE_URL}")
            self.page.goto(config.BASE_URL, timeout=config.PAGE_TIMEOUT)

            # --- Handle Infinite Scroll ---
            print("  -> Scrolling to load all startups. This may take a moment...")
            last_height = self.page.evaluate("document.body.scrollHeight")
            while True:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(config.SCROLL_DELAY)
                new_height = self.page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("  -> Reached the end of the page.")
                    break
                last_height = new_height

            # --- Extract Initial Startup Info ---
            print("  -> Extracting initial list of startups...")
            startup_elements = self.page.locator(".col-lg-3.col-md-4.col-sm-6.col-xs-12").all()
            initial_info = []
            for element in startup_elements:
                name_element = element.locator("h4")
                link_element = element.locator("a")
                
                name = name_element.inner_text().strip()
                profile_link = link_element.get_attribute("href")
                
                if name and profile_link:
                    initial_info.append({"name": name, "profile_link": profile_link})

            print(f"✅ Found {len(initial_info)} startups. Now scraping details for each...")

            # --- Scrape Detailed Info for Each Startup ---
            for i, info in enumerate(initial_info):
                print(f"\n({i+1}/{len(initial_info)}) Scraping details for: {info['name']}")
                details = self._scrape_startup_details(info['profile_link'])
                
                # Combine initial info with scraped details
                combined_data = {**info, **details}
                all_startups_data.append(combined_data)
                
            return pd.DataFrame(all_startups_data)

        except PlaywrightTimeoutError:
            print(f"❌ Timed out while loading the main directory page: {config.BASE_URL}")
            return pd.DataFrame()
        except Exception as e:
            print(f"❌ An unexpected error occurred during the main scraping process: {e}")
            return pd.DataFrame()
        finally:
            self.close()
    
    def close(self):
        """Closes the browser and the Playwright instance gracefully."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("\n✅ Browser and Playwright instance closed.")

