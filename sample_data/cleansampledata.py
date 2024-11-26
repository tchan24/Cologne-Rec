import pandas as pd
import numpy as np

def clean_perfume_data(file_path: str) -> pd.DataFrame:
    """
    Clean the perfume database by:
    1. Loading only required columns
    2. Removing null values
    3. Removing duplicates
    4. Cleaning string values
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        pd.DataFrame: Cleaned perfume database
    """
    # Read only the required columns
    df = pd.read_excel(
        file_path, 
        usecols=['brand', 'perfume', 'main_accords', 'notes']
    )
    
    # Convert all string columns to string type and clean them
    string_columns = ['brand', 'perfume', 'main_accords', 'notes']
    for col in string_columns:
        # Convert to string and strip whitespace
        df[col] = df[col].astype(str).str.strip()
        # Replace 'null', 'nan', empty strings with NaN
        df[col] = df[col].replace({'null': np.nan, 'nan': np.nan, '': np.nan})
    
    # Remove rows with any null values
    df = df.dropna()
    
    # Remove duplicates based on brand and perfume name
    df = df.drop_duplicates(subset=['brand', 'perfume'], keep='first')
    
    # Sort by brand and perfume name
    df = df.sort_values(['brand', 'perfume'])
    
    # Reset index
    df = df.reset_index(drop=True)
    
    # Print cleaning summary
    print(f"Total number of perfumes after cleaning: {len(df)}")
    print(f"Number of unique brands: {df['brand'].nunique()}")
    
    return df

def save_cleaned_data(df: pd.DataFrame, output_path: str) -> None:
    """
    Save the cleaned data to Excel and CSV formats
    
    Args:
        df (pd.DataFrame): Cleaned perfume database
        output_path (str): Base path for output files (without extension)
    """
    # Save as Excel
    df.to_excel(f"{output_path}.xlsx", index=False)
    # Save as CSV
    df.to_csv(f"{output_path}.csv", index=False)
    
    print(f"Saved cleaned data to {output_path}.xlsx and {output_path}.csv")

def analyze_data(df: pd.DataFrame) -> None:
    """
    Print basic analysis of the cleaned data
    
    Args:
        df (pd.DataFrame): Cleaned perfume database
    """
    print("\nData Analysis:")
    print("-" * 50)
    print(f"Total number of perfumes: {len(df)}")
    print(f"Number of unique brands: {df['brand'].nunique()}")
    
    # Sample of unique main accords
    unique_accords = set()
    for accords in df['main_accords']:
        if isinstance(accords, str):
            accords_list = [a.strip() for a in accords.split(',')]
            unique_accords.update(accords_list)
    
    print(f"\nNumber of unique main accords: {len(unique_accords)}")
    print("\nSample of main accords:")
    print(list(unique_accords)[:10])

def main():
    input_file = "sample_data/perfume_database.xlsx"
    output_base = "clean_perfume_database"
    
    # Clean the data
    df = clean_perfume_data(input_file)
    
    # Analyze the cleaned data
    analyze_data(df)
    
    # Save the cleaned data
    save_cleaned_data(df, output_base)

if __name__ == "__main__":
    main()