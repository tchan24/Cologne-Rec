import base64
import requests
import pandas as pd
from typing import List, Dict
from pathlib import Path

# System and user prompts
SYSTEM_PROMPT = """You are a fragrance recognition system specialized in identifying cologne bottles from images. Your role is to:
1. Identify cologne bottles and their brands
2. Handle partial views and reflective surfaces
3. Report confidence levels
4. Ignore non-cologne objects

Output Format:
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

USER_PROMPT = """Analyze this image and identify all cologne bottles present. For each bottle:
- Identify the brand and exact fragrance name
- Assess your confidence in the identification (0-1)
- Note the bottle's relative position
Only include bottles you can identify with reasonable confidence."""

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
        "model": "gpt-4-vision-preview",
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
    return response.json()["choices"][0]["message"]["content"]

class CologneRecognizer:
    def __init__(self, database_path: str):
        self.cologne_db = pd.read_csv(database_path)
        self.api_key = None

    def analyze_image(self, image_path: str) -> List[Dict]:
        result = analyze_image(image_path, self.api_key)
        return self._match_with_database(result['colognes'])

    def _match_with_database(self, detected_colognes: List[Dict]) -> List[Dict]:
        matched_colognes = []
        
        for cologne in detected_colognes:
            match = self.cologne_db[
                (self.cologne_db['brand'].str.contains(cologne['brand'], case=False)) &
                (self.cologne_db['perfume'].str.contains(cologne['name'], case=False))
            ]
            
            if not match.empty:
                cologne_data = match.iloc[0].to_dict()
                cologne_data['confidence'] = cologne['confidence']
                matched_colognes.append(cologne_data)
        
        return matched_colognes

# Test the system
if __name__ == "__main__":
    api_key = "your-openai-api-key"  # Replace with your actual API key
    recognizer = CologneRecognizer("top_100_mens.csv")
    recognizer.api_key = api_key
    
    image_path = input("Enter path to cologne image: ")
    results = recognizer.analyze_image(image_path)
    
    print("\nRecognized Colognes:")
    for cologne in results:
        print(f"\nBrand: {cologne['brand']}")
        print(f"Name: {cologne['perfume']}")
        print(f"Confidence: {cologne['confidence']:.2%}")
        print(f"Season: {cologne['season']}")
        print(f"Occasion: {cologne['occasion']}")
        print(f"Notes: {cologne['notes']}")