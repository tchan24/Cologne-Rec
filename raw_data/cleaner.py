import pandas as pd

def clean_lists(input_str):
    try:
        # If it's already a string list representation, clean it
        if input_str.startswith('[') and input_str.endswith(']'):
            # Remove nested brackets and split by commas
            cleaned = input_str.replace('[', '').replace(']', '')
            items = [item.strip() for item in cleaned.split(',')]
            # Remove any empty strings
            items = [item for item in items if item]
            return str(items)
        return input_str
    except:
        return input_str

# Read the CSV
df = pd.read_csv('raw_data/top_100_mens.csv')

# Clean the accords and notes columns
df['accords'] = df['accords'].apply(clean_lists)
df['notes'] = df['notes'].apply(clean_lists)

# Save to new CSV
df.to_csv('raw_data/top_100_mens_cleaned.csv', index=False)

print("CSV saved to top_100_mens_cleaned.csv")

# Print first few rows to verify
print("\nFirst few rows of cleaned data:")
print(df[['brand', 'perfume', 'accords', 'notes']].head())