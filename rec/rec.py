import base64
import requests
import pandas as pd
from typing import List, Dict
from pathlib import Path
import json
import ast
from datetime import datetime

SYSTEM_PROMPT = """You are a fragrance recognition system. Analyze cologne bottles and output a JSON response with:
1. Brand name
2. Fragrance name
3. Confidence level (0-1)
4. Location in image"""

USER_PROMPT = """Analyze this image and return a JSON object with cologne bottles identified. Format:
{
    "colognes": [
        {
            "brand": "Brand name",
            "name": "Fragrance name",
            "confidence": 0.95,
            "bottle_location": "left/center/right"
        }
    ]
}"""

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(image_path: str, api_key: str) -> dict:
    base64_image = encode_image(image_path)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "response_format": { "type": "json_object" }
    }
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload
    )
    json_response = response.json()
    
    if 'error' in json_response:
        raise Exception(f"API Error: {json_response['error']['message']}")
        
    return json.loads(json_response["choices"][0]["message"]["content"])

def get_weather(api_key: str, city: str = "Austin") -> Dict:
    """Get current weather data from OpenWeatherMap"""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=imperial"
    response = requests.get(url)
    data = response.json()
    
    return {
        'temp': data['main']['temp'],
        'humidity': data['main']['humidity'],
        'condition': data['weather'][0]['main'].lower(),
        'time_of_day': 'day' if 6 <= datetime.now().hour < 18 else 'night'
    }

class CologneRecommender:
    def __init__(self, cologne_db: pd.DataFrame):
        self.cologne_db = cologne_db
        
    def _calculate_weather_score(self, cologne: pd.Series, weather: Dict) -> float:
        score = 0.0
        
        # Convert string representation of lists to actual lists
        accords = ast.literal_eval(cologne['accords'])
        
        # Temperature scoring
        if weather['temp'] < 60:
            if cologne['season'] in ['fall', 'winter']:
                score += 1.0
            if 'warm spicy' in accords or 'oriental' in accords:
                score += 0.5
        elif weather['temp'] > 80:
            if cologne['season'] in ['spring', 'summer']:
                score += 1.0
            if 'fresh' in accords or 'citrus' in accords:
                score += 0.5
        else:
            score += 0.5  # Moderate temperature suits most fragrances
            
        # Weather condition scoring
        if weather['condition'] == 'rain':
            if 'aquatic' in accords or 'fresh' in accords:
                score += 0.5
        elif weather['condition'] == 'clear':
            if 'citrus' in accords or 'fresh' in accords:
                score += 0.5
            
        return score
        
    def _calculate_occasion_score(self, cologne: pd.Series, occasion: str) -> float:
        return 1.0 if cologne['occasion'] == occasion else 0.0
        
    def recommend(self, collection: List[Dict], weather: Dict, occasion: str) -> Dict:
        best_score = -1
        recommendation = None
        
        for cologne in collection:
            cologne_series = pd.Series(cologne)
            weather_score = self._calculate_weather_score(cologne_series, weather)
            occasion_score = self._calculate_occasion_score(cologne_series, occasion)
            
            total_score = weather_score + occasion_score
            
            if total_score > best_score:
                best_score = total_score
                recommendation = cologne
                
        return {
            'recommendation': recommendation,
            'reasoning': f"Selected based on {weather['temp']}°F temperature, {weather['condition']} conditions, and {occasion} occasion."
        }

class CologneRecognizer:
    def __init__(self, database_path: str):
        self.cologne_db = pd.read_csv(database_path)
        self.api_key = None
        self.recommender = CologneRecommender(self.cologne_db)

    def analyze_image(self, image_path: str) -> List[Dict]:
        result = analyze_image(image_path, self.api_key)
        return self._match_with_database(result['colognes'])

    def _match_with_database(self, detected_colognes: List[Dict]) -> List[Dict]:
        matched_colognes = []
        
        for cologne in detected_colognes:
            brand_terms = cologne['brand'].lower().split()
            brand_match = self.cologne_db['brand'].str.lower().apply(
                lambda x: any(term in x for term in brand_terms)
            )
            
            name_match = self.cologne_db['perfume'].str.contains(
                cologne['name'], case=False, regex=False
            )
            
            match = self.cologne_db[brand_match & name_match]
            
            if not match.empty:
                cologne_data = match.iloc[0].to_dict()
                cologne_data['confidence'] = cologne['confidence']
                cologne_data['bottle_location'] = cologne.get('bottle_location', '')
                matched_colognes.append(cologne_data)
        
        return matched_colognes

    def get_recommendation(self, collection: List[Dict], weather: Dict, occasion: str) -> Dict:
        return self.recommender.recommend(collection, weather, occasion)

if __name__ == "__main__":
    openai_key = "api"
    weather_key = "api"
    
    # Initialize recognizer
    recognizer = CologneRecognizer("raw_data/top_100_mens_cleaned.csv")
    recognizer.api_key = openai_key
    
    # Get collection from image
    image_path = input("Enter path to cologne image: ")
    collection = recognizer.analyze_image(image_path)
    
    print("\nRecognized Collection:")
    for cologne in collection:
        print(f"\nBrand: {cologne['brand']}")
        print(f"Name: {cologne['perfume']}")
        print(f"Confidence: {cologne['confidence']:.2%}")
        print(f"Season: {cologne['season']}")
        print(f"Occasion: {cologne['occasion']}")
        
    # Get user input
    print("\nOccasions: business, daily, evening, leisure, night out")
    occasion = input("Enter occasion: ").lower()
    
    # Get weather
    weather = get_weather(weather_key)
    print(f"\nCurrent Weather: {weather['temp']}°F, {weather['condition']}")
    
    # Get recommendation
    recommendation = recognizer.get_recommendation(collection, weather, occasion)
    
    print("\nRecommended Fragrance:")
    print(f"Brand: {recommendation['recommendation']['brand']}")
    print(f"Name: {recommendation['recommendation']['perfume']}")
    print(f"Reasoning: {recommendation['reasoning']}")