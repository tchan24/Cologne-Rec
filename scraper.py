# scraper.py

import aiohttp
import asyncio
import pandas as pd
import logging
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from ratelimit import limits, sleep_and_retry
from dataclasses import dataclass
from urllib.parse import urljoin

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

class FragranceScraper:
    def __init__(self, config_path: str = 'scraper_config.json'):
        self.config = self._load_config(config_path)
        self.session = None
        self.data_cache = {}
        
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
                }
            }

    async def __aenter__(self):
        """Set up async context manager."""
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'ScentSage Research Bot v1.0'}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context manager."""
        if self.session:
            await self.session.close()

    @sleep_and_retry
    @limits(calls=10, period=60)
    async def _fetch_fragrantica_data(self, fragrance_url: str) -> FragranceData:
        """Fetch and parse data from Fragrantica."""
        if fragrance_url in self.data_cache:
            return self.data_cache[fragrance_url]

        async with self.session.get(fragrance_url) as response:
            if response.status != 200:
                raise Exception(f"Failed to fetch {fragrance_url}: {response.status}")
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract basic information
            name = self._extract_fragrance_name(soup)
            brand = self._extract_brand(soup)
            
            # Extract note pyramid
            notes = self._extract_notes(soup)
            
            # Extract additional data
            data = FragranceData(
                name=name,
                brand=brand,
                release_year=self._extract_release_year(soup),
                notes=notes,
                seasons=self._extract_seasons(soup),
                occasions=self._extract_occasions(soup),
                ratings=self._extract_ratings(soup),
                longevity=self._extract_longevity(soup),
                sillage=self._extract_sillage(soup),
                accords=self._extract_accords(soup),
                weather_suitability=self._extract_weather_suitability(soup),
                source_urls=[fragrance_url]
            )
            
            self.data_cache[fragrance_url] = data
            return data

    def _extract_notes(self, soup: BeautifulSoup) -> List[FragranceNote]:
        """Extract and categorize fragrance notes."""
        notes = []
        note_sections = {
            'top': soup.find('div', {'class': 'top-notes'}),
            'heart': soup.find('div', {'class': 'heart-notes'}),
            'base': soup.find('div', {'class': 'base-notes'})
        }
        
        for category, section in note_sections.items():
            if section:
                note_elements = section.find_all('div', {'class': 'note'})
                for element in note_elements:
                    notes.append(FragranceNote(
                        name=element.get_text().strip(),
                        category=category,
                        intensity=self._extract_note_intensity(element)
                    ))
        
        return notes

    def _extract_weather_suitability(self, soup: BeautifulSoup) -> Dict[str, float]:
        """Extract weather suitability ratings."""
        weather_map = {
            'sunny': ['warm', 'hot', 'summer'],
            'rainy': ['wet', 'rain', 'spring'],
            'cold': ['winter', 'cold', 'cool']
        }
        
        suitability = {}
        weather_div = soup.find('div', {'class': 'weather-ratings'})
        if weather_div:
            for weather, terms in weather_map.items():
                ratings = []
                for term in terms:
                    rating_elem = weather_div.find('div', {'data-weather': term})
                    if rating_elem:
                        try:
                            ratings.append(float(rating_elem.get('data-rating', 0)))
                        except ValueError:
                            continue
                
                if ratings:
                    suitability[weather] = sum(ratings) / len(ratings)
                else:
                    suitability[weather] = 0.0
                    
        return suitability

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

        # Convert to DataFrame and process
        df = self._process_scraped_data(all_data)
        
        # Save raw data for backup
        self._save_raw_data(all_data)
        
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
            
            # Process notes
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

    def _save_raw_data(self, data: List[FragranceData], path: str = 'raw_data/'):
        """Save raw scraped data for backup and reprocessing."""
        import os
        from datetime import datetime
        
        # Create directory if it doesn't exist
        os.makedirs(path, exist_ok=True)
        
        # Save data with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'fragrance_data_{timestamp}.json'
        
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
        
        with open(os.path.join(path, filename), 'w') as f:
            json.dump(serializable_data, f, indent=2)

if __name__ == "__main__":
    async def main():
        scraper = FragranceScraper()
        df = await scraper.scrape_fragrance_data(
            sources=['fragrantica', 'basenotes'],
            max_fragrances=100
        )
        
        # Save processed data
        df.to_csv('fragrance_data.csv', index=False)
        logger.info(f"Scraped data for {len(df)} fragrances")

    asyncio.run(main())