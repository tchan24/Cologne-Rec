import base64
import requests
import pandas as pd
from typing import List, Dict
from pathlib import Path
import json

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
    print("API Response:", json_response)
    
    if 'error' in json_response:
        raise Exception(f"API Error: {json_response['error']['message']}")
        
    return json.loads(json_response["choices"][0]["message"]["content"])

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
            # Handle brand variations
            brand_terms = cologne['brand'].lower().split()
            brand_match = self.cologne_db['brand'].str.lower().apply(
                lambda x: any(term in x for term in brand_terms)
            )
            
            # Match fragrance name
            name_match = self.cologne_db['perfume'].str.contains(
                cologne['name'], case=False, regex=False
            )
            
            match = self.cologne_db[brand_match & name_match]
            
            if not match.empty:
                cologne_data = match.iloc[0].to_dict()
                cologne_data['confidence'] = cologne['confidence']
                matched_colognes.append(cologne_data)
        
        return matched_colognes

if __name__ == "__main__":
    api_key = "api"
    recognizer = CologneRecognizer("raw_data/top_100_mens.csv")
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