from flask import Flask, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

API_URL = 'https://livescoreapi.thehindu.com/api/cricket/grouped/fixtures/3634'

@app.route('/api/live-matches')
def live_matches():
    try:
        # First try to fetch from external API
        try:
            resp = requests.get(API_URL, timeout=5)  # Add timeout
            if resp.status_code == 200:
                return jsonify(resp.json())
            else:
                raise Exception(f"API returned status code {resp.status_code}")
        except Exception as e:
            print(f"External API error: {str(e)}")
            
        # Fallback to local JSON file if external API fails
        with open('ipl_matches_2025.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)
        
    except Exception as e:
        return jsonify({'error': str(e), 'message': 'Unable to load match data'}), 500


@app.route('/points_table')
def points_table():
    api_url = 'https://cf-gotham.sportskeeda.com/cricket/ipl/points-table'
    # Use a CORS proxy
    proxy_url = f'https://corsproxy.io/?{api_url}'
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.sportskeeda.com/'
        }
        response = requests.get(proxy_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Flatten the group if needed
        points = []
        if 'table' in data and data['table'] and 'table' in data['table'][0]:
            for team in data['table'][0]['table']:
                if 'group' in team:
                    points.extend(team['group'])
                else:
                    points.append(team)
        print("API data fetched successfully:", len(points), "teams")
    except Exception as e:
        points = []
        print(f"Error fetching points table: {e}")

    return jsonify({'points': points})
import pandas as pd
import numpy as np
import json
import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Create a directory to store JSON results if it doesn't exist
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    if not batter_name or not bowler_name:
        return jsonify({'error': 'Both batsman and bowler names are required'}), 400
    
    try:
        result = analyze_batter_vs_bowler("deliveries.csv", batter_name, bowler_name)
        if result is None:
            return jsonify({'error': f'No head-to-head data found between {batter_name} and {bowler_name}.'}), 404
        
        # Save the result to a JSON file
        filename = f"{batter_name.replace(' ', '')}_vs_{bowler_name.replace(' ', '')}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(result, f)
        
        # Return the filename so the frontend knows which file to request
        return jsonify({'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results/<filename>', methods=['GET'])
def get_result(filename):
    filepath = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='application/json')
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/head_to_head', methods=['GET', 'POST'])
def head_to_head():
    h2h = None
    if request.method == 'POST':
        player1 = request.form.get('player1')
        player2 = request.form.get('player2')
        # TODO: Fetch head-to-head data for player1 and player2 and assign to h2h
        # Example: h2h = fetch_h2h(player1, player2)
    return jsonify({'h2h': h2h})

def analyze_batter_vs_bowler(file, batter_name, bowler_name):
    df = pd.read_csv(file)
    # Filter only the relevant head-to-head deliveries
    head_to_head = df[(df['batter'] == batter_name) & (df['bowler'] == bowler_name)].copy()
    
    # Exclude extras that don't count as legal deliveries faced
    head_to_head = head_to_head[~head_to_head['extras_type'].isin(['wides', 'legbyes', 'byes']) | head_to_head['extras_type'].isna()]

    if head_to_head.empty:
        return None

    total_balls = len(head_to_head)
    dot_balls = len(head_to_head[head_to_head['batsman_runs'] == 0])
    runs = head_to_head['batsman_runs'].sum()
    run_breakdown = head_to_head['batsman_runs'].value_counts().to_dict()
    dismissals = head_to_head['player_dismissed'].eq(batter_name).sum()
    
    strike_rate = (runs / total_balls) * 100 if total_balls else 0
    average = (runs / dismissals) if dismissals else runs
    boundary_pct = (run_breakdown.get(4, 0) + run_breakdown.get(6, 0)) / total_balls * 100 if total_balls else 0

    summary = {
        'Batter': batter_name,
        'Bowler': bowler_name,
        'Balls Faced': total_balls,
        'Dot Balls': dot_balls,
        'Total Runs': runs,
        '1s': run_breakdown.get(1, 0),
        '2s': run_breakdown.get(2, 0),
        '3s': run_breakdown.get(3, 0),
        '4s': run_breakdown.get(4, 0),
        '6s': run_breakdown.get(6, 0),
        'Dismissals': dismissals,
        'Strike Rate': round(strike_rate, 2),
        'Average': round(average, 2),
        'Boundary %': round(boundary_pct, 2)
    }
    # Convert all values to native Python types
    summary = {k: (int(v) if isinstance(v, (np.integer, int)) else float(v) if isinstance(v, (np.floating, float)) else v) for k, v in summary.items()}
    return summary
if __name__ == '__main__':
    app.run(debug=True)