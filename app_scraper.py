# app_scraper.py

"""
This module contains the logic for scraping app stores to find out
if a company has a mobile application, focusing on specific data points.
"""

import requests
from google_play_scraper import search as search_play_store, app as app_play_store
from concurrent.futures import ThreadPoolExecutor, as_completed
import config

class AppScraper:
    """
    Searches for and scrapes detailed data from the Google Play Store and Apple App Store
    for a given company.
    """

    def _format_google_play_details(self, details):
        """Formats Google Play app details into a structured dictionary."""
        return {
            "store": "Google Play",
            "title": details.get('title'),
            "description": details.get('description'),
            "genre": details.get('genre'),
            "installs": details.get('installs'),
            "score": details.get('score'),
            "ratings": details.get('ratings'),
            "free": details.get('free'),
            "developer": details.get('developer'),
            "developerEmail": details.get('developerEmail'),
            "url": details.get('url')
        }

    def _format_apple_store_details(self, details):
        """Formats Apple App Store details into a structured dictionary."""
        return {
            "store": "Apple App Store",
            "title": details.get('trackName'),
            "description": details.get('description'),
            "genre": details.get('primaryGenreName'),
            "installs": None,  # Not available via this API
            "score": details.get('averageUserRating'),
            "ratings": details.get('userRatingCount'),
            "free": details.get('price', -1) == 0.0,
            "developer": details.get('artistName'),
            "developerEmail": None, # Not available via this API
            "url": details.get('trackViewUrl')
        }

    def _search_apple_app_store(self, term, country, limit):
        """Searches the Apple App Store using the official iTunes Search API."""
        url = "https://itunes.apple.com/search"
        params = {"term": term, "country": country, "media": "software", "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json().get('results', [])
        except requests.RequestException as e:
            print(f"    ⚠️ An error occurred during Apple App Store API call: {e}")
            return []

    def _scrape_google_play(self, company_name):
        """Scrapes the Google Play Store for a company's app."""
        try:
            search_results = search_play_store(query=company_name, n_hits=config.NO_OF_APPS_TO_SCRAPE, country="ae")
            if search_results:
                app_id = search_results[0]['appId']
                print(f"    -> Found Google Play app: {app_id}")
                details = app_play_store(app_id, lang='en', country='ae')
                return self._format_google_play_details(details)
        except Exception as e:
            print(f"    ⚠️ An error occurred during Google Play scraping for '{company_name}': {e}")
        return None

    def _scrape_apple_store(self, company_name):
        """Scrapes the Apple App Store for a company's app."""
        try:
            search_results = self._search_apple_app_store(term=company_name, country="ae", limit=config.NO_OF_APPS_TO_SCRAPE)
            if search_results:
                app_details = search_results[0]
                app_name = app_details.get('trackName')
                print(f"    -> Found Apple App Store app: {app_name}")
                return self._format_apple_store_details(app_details)
        except Exception as e:
            print(f"    ⚠️ An error occurred during Apple Store scraping for '{company_name}': {e}")
        return None

    def scrape_apps(self, company_name):
        """
        Searches both app stores concurrently for a company's app.
        
        Returns:
            list: A list of dictionaries, where each dictionary contains detailed app info.
        """
        app_details_list = []
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='AppStoreScraper') as executor:
            future_google = executor.submit(self._scrape_google_play, company_name)
            future_apple = executor.submit(self._scrape_apple_store, company_name)

            for future in as_completed([future_google, future_apple]):
                try:
                    result = future.result()
                    if result:
                        app_details_list.append(result)
                except Exception as e:
                    print(f"    ⚠️ An error occurred in an app scraping thread: {e}")
        
        if not app_details_list:
            print(f"  -> No mobile apps found for '{company_name}' in either store.")
            
        return app_details_list
