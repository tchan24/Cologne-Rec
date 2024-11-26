# scraper.py

import aiohttp
import asyncio
import logging
import json
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import urljoin
import backoff  # For exponential backoff on failures
import aiofiles  # For async file operations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class FragranceNote:
    name: str
    category: str  # top, heart, base
    intensity: Optional[float] = None

@dataclass
class FragranceData:
    name: str
    brand: str
    release_year: Optional[int]
    notes: List[FragranceNote]
    seasons: List[str]
    occasions: List[str]
    ratings: Dict[str, float]
    longevity: Optional[float]
    sillage: Optional[float]
    accords: Dict[str, float]
    weather_suitability: Dict[str, float]
    source_urls: List[str]

class ScrapingError(Exception):
    """Custom exception for scraping errors"""
    pass

class FragranceScraper:
    def __init__(self, config_path: str = 'scraper_config.json'):
        """
        Initialize the fragrance scraper.
        
        Args:
            config_path: Path to configuration JSON file
        """
        self.config = self._load_config(config_path)
        self.session = None
        self.data_cache = {}
        self.proxy_list = self.config.get('proxies', [])
        self.current_proxy_index = 0
        self.failed_urls = set()
        
    def _load_config(self, config_path: str) -> dict:
        """Load scraping configuration including API keys and rate limits."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found. Using default settings.")
            return {
                'rate_limits': {
                    'fragrantica': {'calls': 10, 'period': 60},
                    'basenotes': {'calls': 5, 'period': 60}
                },
                'urls': {
                    'fragrantica_base': 'https://www.fragrantica.com',
                    'basenotes_base': 'https://www.basenotes.net'
                },
                'retry_attempts': 3,
                'retry_delay': 5,
                'timeout': 30
            }

    def _get_next_proxy(self) -> Optional[str]:
        """Get the next proxy from the rotation."""
        if not self.proxy_list:
            return None
        
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return self.proxy_list[self.current_proxy_index]

    async def __aenter__(self):
        """Set up async context manager with custom headers and retry logic."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.get('timeout', 30))
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context manager."""
        if self.session:
            await self.session.close()

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3
    )
    async def _fetch_page(self, url: str) -> str:
        """
        Fetch a page with automatic retries and proxy rotation.
        
        Args:
            url: URL to fetch
            
        Returns:
            Page content as string
        
        Raises:
            ScrapingError: If page cannot be fetched after retries
        """
        proxy = self._get_next_proxy()
        
        try:
            async with self.session.get(url, proxy=proxy) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:  # Too Many Requests
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    raise ScrapingError("Rate limited")
                else:
                    raise ScrapingError(f"HTTP {response.status}: {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            self.failed_urls.add(url)
            raise

    async def scrape_fragrance_data(
        self,
        sources: List[str] = ['fragrantica', 'basenotes'],
        max_fragrances: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Main scraping function that coordinates data collection from multiple sources.
        
        Args:
            sources: List of source websites to scrape
            max_fragrances: Optional limit on number of fragrances to scrape
            
        Returns:
            DataFrame containing merged and processed fragrance data
        """
        all_data = []
        
        async with self as scraper:
            for source in sources:
                try:
                    if source == 'fragrantica':
                        data = await self._scrape_fragrantica(max_fragrances)
                    elif source == 'basenotes':
                        data = await self._scrape_basenotes(max_fragrances)
                    else:
                        logger.warning(f"Unknown source: {source}")
                        continue
                        
                    all_data.extend(data)
                except Exception as e:
                    logger.error(f"Error scraping {source}: {str(e)}")
                    continue

        # Process and save data
        df = self._process_scraped_data(all_data)
        await self._save_raw_data(all_data)
        
        # Log scraping summary
        self._log_scraping_summary(df)
        
        return df

    def _process_scraped_data(self, data: List[FragranceData]) -> pd.DataFrame:
        """Process raw scraped data into a structured DataFrame."""
        processed_data = []
        
        for frag in data:
            # Flatten the fragrance data structure
            flat_data = {
                'name': frag.name,
                'brand': frag.brand,
                'release_year': frag.release_year,
                'longevity': frag.longevity,
                'sillage': frag.sillage,
                'seasons': ','.join(frag.seasons),
                'occasions': ','.join(frag.occasions),
                'sources': ','.join(frag.source_urls)
            }
            
            # Process notes by category
            for category in ['top', 'heart', 'base']:
                category_notes = [n for n in frag.notes if n.category == category]
                flat_data[f'{category}_notes'] = ','.join(n.name for n in category_notes)
                flat_data[f'{category}_intensities'] = ','.join(
                    str(n.intensity) for n in category_notes if n.intensity is not None
                )
            
            # Process ratings and accords
            for rating_type, value in frag.ratings.items():
                flat_data[f'rating_{rating_type}'] = value
                
            for accord, strength in frag.accords.items():
                flat_data[f'accord_{accord}'] = strength
                
            # Process weather suitability
            for weather, score in frag.weather_suitability.items():
                flat_data[f'weather_{weather}'] = score
                
            processed_data.append(flat_data)
            
        df = pd.DataFrame(processed_data)
        
        # Add metadata
        df['scrape_date'] = datetime.now().isoformat()
        df['data_version'] = '1.0'
        
        return df

    async def _save_raw_data(self, data: List[FragranceData], path: str = 'raw_data/'):
        """Save raw scraped data for backup and reprocessing."""
        import os
        from datetime import datetime
        
        # Create directory if it doesn't exist
        os.makedirs(path, exist_ok=True)
        
        # Save data with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'fragrance_data_{timestamp}.json'
        filepath = os.path.join(path, filename)
        
        # Convert dataclass objects to dict
        serializable_data = [
            {
                'name': d.name,
                'brand': d.brand,
                'release_year': d.release_year,
                'notes': [{'name': n.name, 'category': n.category, 'intensity': n.intensity} 
                         for n in d.notes],
                'seasons': d.seasons,
                'occasions': d.occasions,
                'ratings': d.ratings,
                'longevity': d.longevity,
                'sillage': d.sillage,
                'accords': d.accords,
                'weather_suitability': d.weather_suitability,
                'source_urls': d.source_urls
            }
            for d in data
        ]
        
        # Async file writing
        async with aiofiles.open(filepath, 'w') as f:
            await f.write(json.dumps(serializable_data, indent=2))
        
        logger.info(f"Raw data saved to {filepath}")

    def _log_scraping_summary(self, df: pd.DataFrame):
        """Log summary statistics of the scraping operation."""
        logger.info(f"Scraping completed:")
        logger.info(f"Total fragrances scraped: {len(df)}")
        logger.info(f"Unique brands: {df['brand'].nunique()}")
        logger.info(f"Date range: {df['release_year'].min()} - {df['release_year'].max()}")
        logger.info(f"Failed URLs: {len(self.failed_urls)}")
        
if __name__ == "__main__":
    async def main():
        scraper = FragranceScraper()
        df = await scraper.scrape_fragrance_data(
            sources=['fragrantica', 'basenotes'],
            max_fragrances=100
        )
        
        # Save processed data
        df.to_csv('fragrance_data.csv', index=False)
        logger.info(f"Scraped data saved to fragrance_data.csv")

    asyncio.run(main())