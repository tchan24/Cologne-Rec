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
        accords = cologne['accords'].lower()
        
        # Temperature scoring
        if weather['temp'] < 60:
            if cologne['season'] in ['fall', 'winter']:
                score += 1.0
            if 'spicy' in accords or 'oriental' in accords:
                score += 0.5
        elif weather['temp'] > 80:
            if cologne['season'] in ['spring', 'summer']:
                score += 1.0
            if 'fresh' in accords or 'citrus' in accords:
                score += 0.5
        else:
            score += 0.5
            
        # Weather condition scoring
        if weather['condition'] == 'rain':
            if 'aquatic' in accords or 'fresh' in accords:
                score += 0.5
        elif weather['condition'] in ['clear', 'clouds']:
            if 'citrus' in accords or 'fresh' in accords:
                score += 0.5
                
        if weather['time_of_day'] == 'night':
            if 'spicy' in accords or 'woody' in accords or 'oriental' in accords:
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

    def _get_collection_profile(self, collection: List[Dict]) -> Dict:
        # Analyze the collection's characteristics
        all_accords = []
        all_notes = []
        seasons = []
        occasions = []
        
        for cologne in collection:
            accords = cologne['accords'].strip('[]').split(',')
            all_accords.extend([a.strip().strip("'") for a in accords])
            
            notes = cologne['notes'].strip('[]').split(',')
            all_notes.extend([n.strip().strip("'") for n in notes])
            
            seasons.append(cologne['season'])
            occasions.append(cologne['occasion'])
            
        return {
            'common_accords': pd.Series(all_accords).value_counts().to_dict(),
            'common_notes': pd.Series(all_notes).value_counts().to_dict(),
            'seasons': pd.Series(seasons).value_counts().to_dict(),
            'occasions': pd.Series(occasions).value_counts().to_dict()
        }

    def recommend_new_purchase(self, collection: List[Dict], want_similar: bool, budget: float = None) -> Dict:
        profile = self._get_collection_profile(collection)
        
        # Filter by budget if specified
        available_colognes = self.cologne_db
        if budget:
            available_colognes = available_colognes[available_colognes['value'] * 100 <= budget]
            
        # Remove colognes already in collection and similar named ones
        collection_names = [c['perfume'].lower() for c in collection]
        collection_brands = [c['brand'].lower() for c in collection]
        available_colognes = available_colognes[~available_colognes['perfume'].str.lower().isin(collection_names)]
        # Remove variants of same fragrance (e.g., if you have Sauvage Elixir, remove all Sauvage versions)
        available_colognes = available_colognes[~available_colognes['perfume'].str.lower().apply(
            lambda x: any(name.split()[0] in x for name in collection_names)
        )]
        
        scores = []
        for _, cologne in available_colognes.iterrows():
            cologne_accords = cologne['accords'].strip('[]').split(',')
            cologne_accords = [a.strip().strip("'").lower() for a in cologne_accords]
            
            cologne_notes = cologne['notes'].strip('[]').split(',')
            cologne_notes = [n.strip().strip("'").lower() for n in cologne_notes]
            
            # Calculate similarity scores
            accord_similarity = len(set(cologne_accords) & set(profile['common_accords'].keys())) / len(cologne_accords)
            note_similarity = len(set(cologne_notes) & set(profile['common_notes'].keys())) / len(cologne_notes)
            season_similarity = 1.0 if cologne['season'] in profile['seasons'] else 0.0
            occasion_similarity = 1.0 if cologne['occasion'] in profile['occasions'] else 0.0
            
            if want_similar:
                total_score = (accord_similarity + note_similarity + season_similarity + occasion_similarity) / 4
            else:
                # For different recommendations, prefer:
                # - Different seasons than most common in collection
                # - Different occasions
                # - Different accords/notes profile
                common_season = max(profile['seasons'].items(), key=lambda x: x[1])[0]
                common_occasion = max(profile['occasions'].items(), key=lambda x: x[1])[0]
                
                season_difference = 0.0 if cologne['season'] == common_season else 1.0
                occasion_difference = 0.0 if cologne['occasion'] == common_occasion else 1.0
                accord_difference = 1 - accord_similarity
                note_difference = 1 - note_similarity
                
                total_score = (accord_difference + note_difference + season_difference + occasion_difference) / 4
            
            scores.append((total_score, cologne))
            
        # Sort by score
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Get top 3 recommendations
        recommendations = []
        reasons = []
        
        for _, cologne in scores[:3]:
            recommendations.append({
                'brand': cologne['brand'],
                'name': cologne['perfume'],
                'season': cologne['season'],
                'occasion': cologne['occasion'],
                'accords': cologne['accords'],
                'notes': cologne['notes']
            })
            
            if want_similar:
                reasons.append(f"Shares similar {cologne['season']}/{cologne['occasion']} profile with {cologne['accords']} accords")
            else:
                reasons.append(f"Offers contrast with {cologne['season']}/{cologne['occasion']} wearing occasions and unique {cologne['accords']} profile")
        
        return {
            'recommendations': recommendations,
            'reasons': reasons
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
    
    # Get mode selection
    print("\nSelect mode:")
    print("1. Current Collection Recommendation")
    print("2. New Purchase Recommendation")
    
    while True:
        mode = input("Enter choice (1 or 2): ").strip()
        if mode in ['1', '2']:
            break
        print("Invalid choice. Please enter 1 or 2.")
    
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
    
    if mode == '1':
        # Current Collection Recommendation
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
    
    else:
        # New Purchase Recommendation
        print("\nPreference for new purchase:")
        print("1. Similar to current collection")
        print("2. Different from current collection")
        
        while True:
            preference = input("Enter choice (1 or 2): ").strip()
            if preference in ['1', '2']:
                break
            print("Invalid choice. Please enter 1 or 2.")
        
        want_similar = preference == '1'
        
        budget = input("\nEnter budget (or press enter to skip): ").strip()
        if budget:
            try:
                budget = float(budget)
            except ValueError:
                budget = None
        
        # Get recommendations
        results = recognizer.recommender.recommend_new_purchase(collection, want_similar, budget)
        
        print("\nRecommended New Purchases:")
        for i, (rec, reason) in enumerate(zip(results['recommendations'], results['reasons']), 1):
            print(f"\n{i}. {rec['brand']} - {rec['name']}")
            print(f"Season: {rec['season']}")
            print(f"Occasion: {rec['occasion']}")
            print(f"Reason: {reason}")
            print(f"Accords: {rec['accords']}")
            print(f"Key Notes: {rec['notes']}")