from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
import json
import logging
from typing import List, Dict

class ParfumoSeleniumScraper:
    def __init__(self):
        self.base_url = "https://www.parfumo.com"
        self.setup_logging()
        self.setup_driver()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def setup_driver(self):
        """Configure and start Chrome webdriver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def get_cologne_urls(self) -> List[str]:
        """Scrapes the top 100 men's cologne URLs from the main page."""
        try:
            self.driver.get(f"{self.base_url}/Perfumes/Tops/Men")
            logging.info("Waiting for perfume listings to load...")
            
            # Wait for perfume items to be visible
            perfume_items = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".perfume-listing-item, .perfume-item, [class*='perfume']"))
            )
            
            cologne_links = []
            for item in perfume_items:
                try:
                    link = item.find_element(By.TAG_NAME, "a")
                    href = link.get_attribute("href")
                    if href and '/Perfumes/' in href:
                        cologne_links.append(href)
                        logging.info(f"Found cologne URL: {href}")
                except Exception as e:
                    logging.warning(f"Error extracting link from item: {str(e)}")
            
            return cologne_links[:100]
            
        except Exception as e:
            logging.error(f"Error fetching cologne URLs: {str(e)}")
            return []

    def extract_ratings(self, wait) -> Dict:
        """Extracts various ratings from the cologne page."""
        ratings = {}
        try:
            rating_mapping = {
                'Scent': 'scent_rating',
                'Longevity': 'longevity_rating',
                'Sillage': 'sillage_rating',
                'Bottle': 'bottle_rating',
                'Value for money': 'valueformoney_rating'
            }
            
            for label_text, rating_key in rating_mapping.items():
                try:
                    # Wait for rating elements to be visible
                    rating_element = wait.until(
                        EC.presence_of_element_located((By.XPATH, f"//div[contains(text(), '{label_text}')]/..//div[contains(@class, 'rating-value')]"))
                    )
                    value = float(rating_element.text.strip())
                    ratings[rating_key] = value
                except (TimeoutException, ValueError) as e:
                    logging.warning(f"Could not find or parse rating for {label_text}: {str(e)}")
                    
        except Exception as e:
            logging.error(f"Error extracting ratings: {str(e)}")
            
        return ratings

    def extract_pie_chart_data(self, driver, chart_name: str) -> str:
        """Extracts the highest percentage category from a pie chart."""
        try:
            # Execute JavaScript to get the chart data
            script = f"return window.{chart_name};"
            chart_data = driver.execute_script(script)
            
            if chart_data:
                max_item = max(chart_data, key=lambda x: x.get('percentage', 0))
                return max_item.get('label')
                
            return None
            
        except Exception as e:
            logging.error(f"Error extracting pie chart data for {chart_name}: {str(e)}")
            return None

    def scrape_cologne_details(self, url: str) -> Dict:
        """Scrapes detailed information for a single cologne."""
        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 10)
            
            # Extract basic information
            brand_name = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".brand, [class*='brand']"))
            ).text.strip()
            
            perfume_name = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".name, [class*='name']"))
            ).text.strip()
            
            # Extract accords and notes
            main_accords = []
            try:
                accord_elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".accord, [class*='accord']"))
                )
                main_accords = [elem.text.strip() for elem in accord_elements]
            except TimeoutException:
                logging.warning(f"No accords found for {url}")
            
            fragrance_notes = []
            try:
                note_elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".note, [class*='note']"))
                )
                fragrance_notes = [elem.text.strip() for elem in note_elements]
            except TimeoutException:
                logging.warning(f"No notes found for {url}")
            
            # Extract ratings
            ratings = self.extract_ratings(wait)
            
            # Extract season and occasion
            season = self.extract_pie_chart_data(self.driver, 'seasonData')
            occasion = self.extract_pie_chart_data(self.driver, 'occasionData')
            
            cologne_data = {
                'brand_name': brand_name,
                'perfume_name': perfume_name,
                'main_accords': main_accords,
                'fragrance_notes': fragrance_notes,
                'season': season,
                'occasion': occasion,
                **ratings
            }
            
            logging.info(f"Successfully scraped data for {brand_name} - {perfume_name}")
            return cologne_data
            
        except Exception as e:
            logging.error(f"Error scraping cologne details for {url}: {str(e)}")
            return None

    def scrape_all_colognes(self) -> pd.DataFrame:
        """Scrapes information for all top 100 colognes and returns a DataFrame."""
        try:
            cologne_urls = self.get_cologne_urls()
            
            if not cologne_urls:
                logging.error("No cologne URLs found!")
                return pd.DataFrame()
                
            all_data = []
            
            for i, url in enumerate(cologne_urls, 1):
                try:
                    logging.info(f"Scraping cologne {i}/100: {url}")
                    cologne_data = self.scrape_cologne_details(url)
                    if cologne_data:
                        all_data.append(cologne_data)
                    time.sleep(3)  # Be nice to the server
                except Exception as e:
                    logging.error(f"Error scraping {url}: {str(e)}")
                    continue
                    
            if not all_data:
                logging.error("No cologne data was successfully scraped!")
                return pd.DataFrame()
                
            df = pd.DataFrame(all_data)
            logging.info(f"Successfully created DataFrame with {len(df)} rows")
            return df
            
        finally:
            self.driver.quit()

def main():
    scraper = ParfumoSeleniumScraper()
    
    # Scrape all cologne data
    df = scraper.scrape_all_colognes()
    
    if not df.empty:
        # Save to CSV
        df.to_csv('parfumo/top_100_mens.csv', index=False)
        logging.info("Data saved to 'top_100_mens.csv'")
        logging.info(f"Number of colognes scraped: {len(df)}")
        logging.info(f"Columns in the dataset: {df.columns.tolist()}")
    else:
        logging.error("No data was scraped. Check the logs for details.")

if __name__ == "__main__":
    main()