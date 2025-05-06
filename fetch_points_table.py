import json
import requests
import os
from datetime import datetime

# API URL for IPL points table
API_URL = 'https://cf-gotham.sportskeeda.com/cricket/ipl/points-table'
OUTPUT_FILE = 'points_table.json'

def fetch_points_table():
    print(f"Fetching points table data from {API_URL}")
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.sportskeeda.com/'
        }
        
        # Try direct API access first
        try:
            response = requests.get(API_URL, headers=headers, timeout=10)
            response.raise_for_status()
        except:
            print("Direct API access failed, trying with CORS proxy...")
            proxy_url = f'https://corsproxy.io/?{API_URL}'
            response = requests.get(proxy_url, headers=headers, timeout=10)
            response.raise_for_status()
            
        data = response.json()
        
        # Transform data to match expected format if needed
        formatted_data = format_data(data)
        
        # Save to JSON file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, ensure_ascii=False, indent=2)
            
        print(f"Points table data saved to {OUTPUT_FILE}")
        return True
        
    except Exception as e:
        print(f"Error fetching points table data: {e}")
        print("Unable to update points table data. The table may show outdated information.")
        return False

def format_data(data):
    # Check if data is already in the expected format
    if 'table' in data and isinstance(data['table'], list):
        return data
    
    # If data is in a different format, transform it to match expected structure
    # This depends on the actual API response format
    formatted_data = {
        "table": [
            {
                "table": [
                    {
                        "group": []
                    }
                ]
            }
        ]
    }
    
    # Extract teams from the API response and add to the formatted structure
    # This is a placeholder - adjust based on actual API response structure
    if 'teams' in data:
        for team in data['teams']:
            formatted_data['table'][0]['table'][0]['group'].append(team)
    elif 'standings' in data:
        for team in data['standings']:
            formatted_data['table'][0]['table'][0]['group'].append(team)
    
    return formatted_data

if __name__ == "__main__":
    fetch_points_table()
    print(f"Points table data processing complete.")