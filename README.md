# ScentSage: Intelligent Cologne Recommendation System

ScentSage is an AI-powered cologne recommendation system that helps users make informed decisions about their fragrance choices. It combines computer vision for collection recognition with intelligent recommendation algorithms for both daily wear suggestions and new purchase recommendations.

## Features

### 1. Collection Recognition
- Uses GPT-4 Vision API to identify cologne bottles from photos
- Handles multiple bottles in a single image
- Matches recognized fragrances with a comprehensive database
- Provides confidence scores for each identification

### 2. Daily Wear Recommendations
- Weather-based recommendations using real-time weather data
- Occasion-specific suggestions (business, daily, evening, leisure, night out)
- Considers temperature, weather conditions, and time of day
- Analyzes fragrance notes and accords for optimal matching

### 3. New Purchase Recommendations
- Two recommendation modes:
  - Similar to current collection (for consistent taste)
  - Different from current collection (for variety)
- Optional budget consideration
- Analyzes collection patterns in:
  - Fragrance notes
  - Accords
  - Seasons
  - Occasions
- Excludes variants of already-owned fragrances

## Project Structure

```
COLOGNE-REC/
├── final/
│   └── full.py              # Main application file
├── network/
│   └── network.py              # Network analysis
├── parfumo/
│   └── scraper.py           # Fragrance data scraper
├── raw_data/
│   ├── cleaner.py          # Data cleaning utilities
│   ├── top_100_mens.csv    # Original dataset
│   └── top_100_mens_cleaned.csv # Cleaned dataset
├── rec/
│   └── rec.py              # Recommendation algorithms
├── sample_data/            # Sample datasets and utilities
├── scraper/               # Web scraping components
├── vision/
│   ├── vision.py          # Vision recognition system
│   ├── prompt.txt         # GPT-4 Vision prompts
│   └── test.jpg           # Test image
├── README.md
└── requirements.txt        # Required Python packages
```

## Technical Components

### Vision Recognition
- Utilizes GPT-4 Vision API for bottle recognition
- Custom prompts for consistent and accurate identification
- JSON-structured output for reliable parsing

### Weather Integration
- OpenWeatherMap API integration
- Real-time weather data retrieval
- Temperature, conditions, and time-based analysis

### Recommendation Engine
- Sophisticated scoring system for fragrance matching
- Note and accord analysis for scent profile matching
- Season and occasion-appropriate suggestions
- Collection gap analysis for new purchases

## Getting Started

1. Clone the repository:
```bash
git clone https://github.com/yourusername/COLOGNE-REC.git
cd COLOGNE-REC
```

2. Create and activate a virtual environment:
```bash
# On Windows
python -m venv venv
.\venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with your API keys:
```
OPENAI_API_KEY=your_openai_key_here
OPENWEATHER_API_KEY=your_openweather_key_here
```

5. Run the application:
```bash
python final/full.py
```

6. Follow the interactive prompts:
- Choose mode (current/new recommendation)
- Provide collection photo
- Input preferences (occasion/similarity)
- Review recommendations

## API Requirements

- OpenAI API key (GPT-4 Vision access)
- OpenWeatherMap API key

## Database

The system uses a curated database of men's fragrances (`top_100_mens_cleaned.csv`) containing:
- Brand and fragrance names
- Notes and accords
- Seasonal recommendations
- Occasion suitability
- Community ratings
- Value assessments

## Future Enhancements

1. Web Interface
2. Mobile App Integration
3. Personal Collection History
4. Season-Based Rotation Suggestions
5. Price Tracking and Deals
6. Note Learning from User Preferences
7. Extended Fragrance Database

## Contributors

Tarun Chandrasekaran

## Acknowledgments

- Fragrance data sources
  - Parfumo
  - Fragrantica
- API providers
  - OpenAI API
  - OpenWeather API