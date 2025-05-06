import json
import pandas as pd
import numpy as np
import os
from collections import defaultdict
import argparse

class Dream11Predictor:
    def __init__(self, batter_data_path, bowler_data_path, teams_folder_path):
        # Load data from JSON files
        with open(batter_data_path, 'r') as f:
            self.batter_data = json.load(f)
        
        with open(bowler_data_path, 'r') as f:
            self.bowler_data = json.load(f)
        
        # Load team data from CSV files
        self.teams_data = {}
        self.load_teams_data(teams_folder_path)
        
        self.player_scores = {}
        self.selected_team = []
        self.player_roles = {}
        self.player_credits = {}
        self.player_is_foreign = {}
    
    def load_teams_data(self, teams_folder_path):
        """Load all team data from CSV files in the Teams folder"""
        for filename in os.listdir(teams_folder_path):
            if filename.endswith('_squad.csv'):
                team_name = filename.replace('_squad.csv', '').replace('-', ' ').title()
                file_path = os.path.join(teams_folder_path, filename)
                try:
                    team_df = pd.read_csv(file_path)
                    self.teams_data[team_name] = team_df
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
    
    def get_player_info_from_csv(self, player_name):
        """Find player information in the CSV data"""
        for team_name, team_df in self.teams_data.items():
            # Try exact match first
            player_row = team_df[team_df['Name'] == player_name]
            
            # If not found, try partial match
            if player_row.empty:
                player_row = team_df[team_df['Name'].str.contains(player_name, case=False, na=False)]
            
            if not player_row.empty:
                # Return the first match
                player_info = player_row.iloc[0]
                
                # Check different possible credit column names
                credit_value = 7.0  # Default value
                for credit_col in ['Credits', 'credits', 'Credit']:
                    if credit_col in player_info and not pd.isna(player_info[credit_col]):
                        credit_value = float(player_info[credit_col])
                        break
                
                return {
                    'role': player_info['Role'],
                    'credits': credit_value,
                    'foreign': player_info.get('Foreign Player', False) == True,
                    'team': team_name
                }
        
        # If player not found in any team
        return None
    
    def set_player_roles(self, players_with_roles):
        """Set player roles from the provided list and update with CSV data"""
        for player_info in players_with_roles:
            parts = player_info.strip().split('(', 1)
            if len(parts) >= 2:
                player_name = parts[0].strip()
                role_part = parts[1].strip()
                if role_part.endswith(')'):
                    role = role_part[:-1].strip()
                    self.player_roles[player_name] = role
            else:
                # If no role is specified, default to "Unknown"
                player_name = player_info.strip()
                self.player_roles[player_name] = "Unknown"
            
            # Try to get additional info from CSV
            csv_info = self.get_player_info_from_csv(player_name)
            if csv_info:
                # Update role if it was unknown
                if self.player_roles[player_name] == "Unknown":
                    self.player_roles[player_name] = csv_info['role']
                
                # Set credits and foreign status
                self.player_credits[player_name] = csv_info['credits']
                self.player_is_foreign[player_name] = csv_info['foreign']
            else:
                # Default values if not found in CSV
                self.player_credits[player_name] = 7.0  # Default credit value
                self.player_is_foreign[player_name] = False  # Default to Indian player
    
    def analyze_head_to_head(self, team1_players, team2_players):
        """Analyze head-to-head performance between players of two teams"""
        for batter in team1_players:
            if batter not in self.player_scores:
                self.player_scores[batter] = 0
                
            if batter in self.batter_data:
                # Analyze batter's performance against team2 bowlers
                for bowler in team2_players:
                    if bowler in self.batter_data[batter].get('head_to_head', {}):
                        h2h_data = self.batter_data[batter]['head_to_head'][bowler]
                        
                        # If there's a list of encounters, take the first one
                        if isinstance(h2h_data, list) and len(h2h_data) > 0:
                            h2h_data = h2h_data[0]
                        
                        # Skip if no data or message indicates no data
                        if isinstance(h2h_data, dict) and 'Message' not in h2h_data:
                            # Calculate batting score based on strike rate, average, and boundary %
                            try:
                                strike_rate = h2h_data.get('Strike Rate', 0)
                                avg = h2h_data.get('Average', 0)
                                boundary_pct = h2h_data.get('Boundary %', 0)
                                dismissals = h2h_data.get('Dismissals', 0)
                                
                                # Higher score for better performance against this bowler
                                batting_score = (strike_rate / 100) * 2 + (avg / 10) + (boundary_pct / 10) - (dismissals * 2)
                                self.player_scores[batter] += batting_score
                            except (TypeError, ValueError):
                                pass
        
        for bowler in team2_players:
            if bowler not in self.player_scores:
                self.player_scores[bowler] = 0
                
            if bowler in self.bowler_data:
                # Analyze bowler's performance against team1 batters
                for batter in team1_players:
                    if batter in self.bowler_data[bowler].get('head_to_head', {}):
                        h2h_data = self.bowler_data[bowler]['head_to_head'][batter]
                        
                        # Skip if no data
                        if isinstance(h2h_data, dict):
                            # Calculate bowling score based on economy and wickets
                            try:
                                dismissals = float(h2h_data.get('Dismissals', 0))
                                economy = float(h2h_data.get('Econ', 15))  # Default high economy if not available
                                
                                # Higher score for more wickets and lower economy
                                bowling_score = (dismissals * 5) + (10 - min(economy, 10))
                                self.player_scores[bowler] += bowling_score
                            except (TypeError, ValueError):
                                pass
    
    def analyze_venue_performance(self, venue, players):
        """Analyze players' performance at the given venue"""
        for player in players:
            if player not in self.player_scores:
                self.player_scores[player] = 0
            
            # Check batter venue stats
            if player in self.batter_data:
                venue_data = self.batter_data[player].get('venue', {})
                if venue_data and 'Batting' in venue_data:
                    # Parse the venue data (it's in string format in your JSON)
                    try:
                        venue_df = pd.read_csv(pd.StringIO(venue_data['Batting']), sep=r'\s{2,}', engine='python')
                        
                        # Find this venue's data
                        venue_row = venue_df[venue_df['venue'].str.contains(venue, case=False, na=False)]                        
                        if not venue_row.empty:
                            # Add venue-specific batting score
                            strike_rate = venue_row['Strike_Rate'].values[0] if 'Strike_Rate' in venue_row else 0
                            avg = venue_row['Average'].values[0] if 'Average' in venue_row else 0
                            
                            venue_score = (strike_rate / 100) + (avg / 20)
                            self.player_scores[player] += venue_score
                    except Exception:
                        pass
            
            # Check bowler venue stats
            if player in self.bowler_data:
                venue_data = self.bowler_data[player].get('venue', {})
                if venue_data and 'Bowling' in venue_data:
                    try:
                        venue_df = pd.read_csv(pd.StringIO(venue_data['Bowling']), sep=r'\s{2,}', engine='python')
                        
                        # Find this venue's data
                        venue_row = venue_df[venue_df['venue'].str.contains(venue, case=False, na=False)]
                        if not venue_row.empty:
                            # Add venue-specific bowling score
                            wickets = venue_row['Wickets'].values[0] if 'Wickets' in venue_row else 0
                            economy = venue_row['Economy'].values[0] if 'Economy' in venue_row else 15
                            
                            venue_score = (wickets * 3) + (10 - min(economy, 10))
                            self.player_scores[player] += venue_score
                    except Exception:
                        pass
    
    def analyze_recent_form(self, players):
        """Analyze players' recent form based on last 5 matches"""
        for player in players:
            if player not in self.player_scores:
                self.player_scores[player] = 0
            
            # Check batter recent form
            if player in self.batter_data and 'recent_form' in self.batter_data[player]:
                recent_form = self.batter_data[player]['recent_form']
                
                for form_data in recent_form:
                    if len(form_data) >= 2 and form_data[0] == 'Batting Match-wise':
                        try:
                            form_df = pd.read_csv(pd.StringIO(form_data[1]), sep=r'\s{2,}', engine='python')
                            
                            # Calculate average runs and strike rate from last 5 matches
                            if 'Runs' in form_df.columns:
                                avg_runs = form_df['Runs'].mean()
                                self.player_scores[player] += avg_runs / 10
                            
                            if 'Strike Rate' in form_df.columns:
                                avg_sr = form_df['Strike Rate'].mean()
                                self.player_scores[player] += avg_sr / 100
                        except Exception:
                            pass
            
            # Check bowler recent form
            if player in self.bowler_data and 'recent_form' in self.bowler_data[player]:
                recent_form = self.bowler_data[player]['recent_form']
                
                for form_data in recent_form:
                    if len(form_data) >= 2 and form_data[0] == 'Bowling Match-wise':
                        try:
                            form_df = pd.read_csv(pd.StringIO(form_data[1]), sep=r'\s{2,}', engine='python')
                            
                            # Calculate average wickets and economy from last 5 matches
                            if 'Wickets' in form_df.columns:
                                avg_wickets = form_df['Wickets'].mean()
                                self.player_scores[player] += avg_wickets * 5
                            
                            if 'Economy' in form_df.columns:
                                avg_economy = form_df['Economy'].mean()
                                self.player_scores[player] += (10 - min(avg_economy, 10))
                        except Exception:
                            pass
    
    def categorize_players(self, sorted_players):
        """Categorize players based on their roles"""
        batsmen = []
        bowlers = []
        all_rounders = []
        wicket_keepers = []
        
        for player, score in sorted_players:
            role = self.player_roles.get(player, "Unknown")
            
            if "WK" in role:
                wicket_keepers.append((player, score))
            elif "Bowler" in role:
                bowlers.append((player, score))
            elif "All-Rounder" in role or "Allrounder" in role or "All-rounder" in role or "All Rounder" in role:
                all_rounders.append((player, score))
            elif "Batter" in role or "Batsman" in role:
                batsmen.append((player, score))
            else:
                # Fallback to the original logic if role is unknown
                if player in self.batter_data and player not in self.bowler_data:
                    # Pure batsman
                    if player in ['MS Dhoni', 'Rishabh Pant', 'KL Rahul', 'Sanju Samson', 'Ishan Kishan', 'Nicholas Pooran', 'Josh Inglis', 'Prabhsimran Singh']:
                        wicket_keepers.append((player, score))
                    else:
                        batsmen.append((player, score))
                elif player in self.bowler_data and player not in self.batter_data:
                    # Pure bowler
                    bowlers.append((player, score))
                else:
                    # All-rounder (has both batting and bowling data)
                    all_rounders.append((player, score))
        
        return {
            'batsmen': batsmen,
            'bowlers': bowlers,
            'all_rounders': all_rounders,
            'wicket_keepers': wicket_keepers
        }
    
    def ensure_minimum_requirements(self, categorized_players, total_credits, foreign_count):
        """Ensure minimum requirements for each category (1 player from each)"""
        selected_players = []
        
        # New constraints
        min_per_category = 1
        max_per_category = 5
        max_credits = 100
        max_foreign = 4
        
        # Select at least one player from each category
        for category_name in ['wicket_keepers', 'batsmen', 'all_rounders', 'bowlers']:
            category = categorized_players[category_name if category_name != 'wicket_keepers' else 'wicket_keepers']
            
            for player, score in category:
                if len([p for p in selected_players if p[0] == player]) > 0:
                    continue  # Skip if player already selected
                    
                credits = self.player_credits.get(player, 7.0)
                is_foreign = self.player_is_foreign.get(player, False)
                
                if total_credits + credits <= max_credits and (not is_foreign or foreign_count < max_foreign):
                    selected_players.append((player, score))
                    total_credits += credits
                    if is_foreign:
                        foreign_count += 1
                    break  # We only need one player from each category for minimum requirements
        
        return selected_players, total_credits, foreign_count
    
    def select_dream11_team(self):
        """Select the best Dream11 team based on player scores with flexible constraints"""
        # Sort players by score
        sorted_players = sorted(self.player_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Categorize players
        categorized_players = self.categorize_players(sorted_players)
        
        # Initialize selection variables
        total_credits = 0
        foreign_count = 0
        max_credits = 100  # Maximum credits allowed
        max_foreign = 4    # Maximum foreign players allowed
        
        # New constraints
        min_per_category = 1
        max_per_category = 8
        
        # Ensure minimum requirements (1 from each category)
        selected_players, total_credits, foreign_count = self.ensure_minimum_requirements(
            categorized_players, total_credits, foreign_count
        )
        
        # Count players by category in the current selection
        def count_by_category(players):
            counts = {'wicket_keepers': 0, 'batsmen': 0, 'all_rounders': 0, 'bowlers': 0}
            for player, _ in players:
                role = self.player_roles.get(player, "Unknown")
                if "WK" in role:
                    counts['wicket_keepers'] += 1
                elif "Bowler" in role:
                    counts['bowlers'] += 1
                elif "All-Rounder" in role or "Allrounder" in role or "All-rounder" in role or "All Rounder" in role:
                    counts['all_rounders'] += 1
                elif "Batter" in role or "Batsman" in role:
                    counts['batsmen'] += 1
                else:
                    # Fallback logic
                    if player in self.batter_data and player not in self.bowler_data:
                        if player in ['MS Dhoni', 'Rishabh Pant', 'KL Rahul', 'Sanju Samson', 'Ishan Kishan', 'Nicholas Pooran', 'Josh Inglis', 'Prabhsimran Singh']:
                            counts['wicket_keepers'] += 1
                        else:
                            counts['batsmen'] += 1
                    elif player in self.bowler_data and player not in self.batter_data:
                        counts['bowlers'] += 1
                    else:
                        counts['all_rounders'] += 1
            return counts
        
        # Fill remaining slots with best performers while respecting constraints
        remaining_slots = 11 - len(selected_players)
        
        # First, prioritize top performers regardless of role
        for player, score in sorted_players:
            if len(selected_players) >= 11:
                break
                
            if player in [p[0] for p in selected_players]:
                continue  # Skip if already selected
                
            credits = self.player_credits.get(player, 7.0)
            is_foreign = self.player_is_foreign.get(player, False)
            
            # Check if adding this player would violate category constraints
            current_counts = count_by_category(selected_players)
            role = self.player_roles.get(player, "Unknown")
            
            category = None
            if "WK" in role:
                category = 'wicket_keepers'
            elif "Bowler" in role:
                category = 'bowlers'
            elif "All-Rounder" in role or "Allrounder" in role or "All-rounder" in role or "All Rounder" in role:
                category = 'all_rounders'
            elif "Batter" in role or "Batsman" in role:
                category = 'batsmen'
            else:
                # Fallback logic
                if player in self.batter_data and player not in self.bowler_data:
                    if player in ['MS Dhoni', 'Rishabh Pant', 'KL Rahul', 'Sanju Samson', 'Ishan Kishan', 'Nicholas Pooran', 'Josh Inglis', 'Prabhsimran Singh']:
                        category = 'wicket_keepers'
                    else:
                        category = 'batsmen'
                elif player in self.bowler_data and player not in self.batter_data:
                    category = 'bowlers'
                else:
                    category = 'all_rounders'
            
            # Check if adding this player would exceed category limit
            if current_counts[category] >= max_per_category:
                continue
            
            # Check credit and foreign player constraints
            if total_credits + credits <= max_credits and (not is_foreign or foreign_count < max_foreign):
                selected_players.append((player, score))
                total_credits += credits
                if is_foreign:
                    foreign_count += 1
        
        # Store the selected team
        self.selected_team = selected_players
        
        # Select captain and vice-captain (highest and second-highest scores)
        if len(self.selected_team) >= 2:
            captain = self.selected_team[0][0]
            vice_captain = self.selected_team[1][0]
            return self.selected_team, captain, vice_captain, total_credits, foreign_count
        else:
            return self.selected_team, None, None, total_credits, foreign_count
    
    def predict_dream11(self, team1, team2, venue, team1_playing11, team2_playing11):
        """Main function to predict Dream11 team for a match with specific playing XI"""
        # Combine playing 11 from both teams
        playing11 = team1_playing11 + team2_playing11
        
        # Set player roles from the provided playing 11
        self.set_player_roles(playing11)
        
        # Extract player names without roles
        all_players = [p.split('(')[0].strip() for p in playing11]
        
        # Determine which players belong to which team
        team1_players = [p.split('(')[0].strip() for p in team1_playing11]
        team2_players = [p.split('(')[0].strip() for p in team2_playing11]
        
        # Reset player scores
        self.player_scores = {}
        
        # Analyze different aspects
        self.analyze_head_to_head(team1_players, team2_players)
        self.analyze_head_to_head(team2_players, team1_players)  # Analyze in reverse too
        self.analyze_venue_performance(venue, all_players)
        self.analyze_recent_form(all_players)
        
        # Select the best team
        team, captain, vice_captain, total_credits, foreign_count = self.select_dream11_team()
        
        return team, captain, vice_captain, team1, team2, venue, total_credits, foreign_count

    def display_team(self, team, captain, vice_captain, team1, team2, venue, total_credits, foreign_count):
        """Display the selected Dream11 team"""
        print(f"\n===== DREAM 11 TEAM =====\n")
        print(f"Match: {team1} vs {team2}")
        print(f"Venue: {venue}\n")
        print(f"Total Credits: {total_credits:.1f}/100.0")
        print(f"Foreign Players: {foreign_count}/4\n")
        
        # Categorize selected players
        wk = []
        bat = []
        ar = []
        bowl = []
        
        for player, score in team:
            role = self.player_roles.get(player, "Unknown")
            credits = self.player_credits.get(player, 7.0)
            is_foreign = self.player_is_foreign.get(player, False)
            
            if "WK" in role:
                wk.append((player, score, "WK", credits, is_foreign))
            elif "Bowler" in role:
                bowl.append((player, score, "BOWL", credits, is_foreign))
            elif "All-Rounder" in role or "Allrounder" in role or "All-rounder" in role or "All Rounder" in role:
                ar.append((player, score, "ALL", credits, is_foreign))
            elif "Batter" in role or "Batsman" in role:
                bat.append((player, score, "BAT", credits, is_foreign))
            else:
                # Fallback to the original logic if role is unknown
                if player in self.batter_data and player not in self.bowler_data:
                    if player in ['MS Dhoni', 'Rishabh Pant', 'KL Rahul', 'Sanju Samson', 'Ishan Kishan', 'Nicholas Pooran', 'Josh Inglis', 'Prabhsimran Singh']:
                        wk.append((player, score, "WK", credits, is_foreign))
                    else:
                        bat.append((player, score, "BAT", credits, is_foreign))
                elif player in self.bowler_data and player not in self.batter_data:
                    bowl.append((player, score, "BOWL", credits, is_foreign))
                else:
                    ar.append((player, score, "ALL", credits, is_foreign))
        
        # Display by category
        print("WICKET-KEEPERS:")
        for player, score, _, credits, is_foreign in wk:
            captain_mark = " (C)" if player == captain else " (VC)" if player == vice_captain else ""
            foreign_mark = " [FOREIGN]" if is_foreign else ""
            print(f"  {player}{captain_mark} - {score:.2f} points - {credits} credits{foreign_mark}")
        
        print("\nBATSMEN:")
        for player, score, _, credits, is_foreign in bat:
            captain_mark = " (C)" if player == captain else " (VC)" if player == vice_captain else ""
            foreign_mark = " [FOREIGN]" if is_foreign else ""
            print(f"  {player}{captain_mark} - {score:.2f} points - {credits} credits{foreign_mark}")
        
        print("\nALL-ROUNDERS:")
        for player, score, _, credits, is_foreign in ar:
            captain_mark = " (C)" if player == captain else " (VC)" if player == vice_captain else ""
            foreign_mark = " [FOREIGN]" if is_foreign else ""
            print(f"  {player}{captain_mark} - {score:.2f} points - {credits} credits{foreign_mark}")
        
        print("\nBOWLERS:")
        for player, score, _, credits, is_foreign in bowl:
            captain_mark = " (C)" if player == captain else " (VC)" if player == vice_captain else ""
            foreign_mark = " [FOREIGN]" if is_foreign else ""
            print(f"  {player}{captain_mark} - {score:.2f} points - {credits} credits{foreign_mark}")
        
        print("\nCAPTAIN: " + (captain if captain else "None"))
        print("VICE-CAPTAIN: " + (vice_captain if vice_captain else "None"))

def main():
    # Define paths to data files
    batter_data = 'batter_data_cache.json'
    bowler_data = 'bowler_data_cache.json'
    teams_folder = 'Teams'
    
    # Create predictor instance
   # Define paths to data files
    batter_data = 'batter_data_cache.json'
    bowler_data = 'bowler_data_cache.json'
    teams_folder = 'Teams'
    
    # Create predictor instance
    predictor = Dream11Predictor(batter_data, bowler_data, teams_folder)
    
    # CONFIGURATION: Set these variables to your desired teams and venue
    team1 = "Mumbai Indians"
    team2 = "Gujarat Titans"
    venue = "Wankhade Stadium,Mumbai"
    
    # Define playing XI for each team with their roles
    # Format: "Player Name (Role)"
    team1_playing11 =  [
    "Ryan Rickelton(WK-Batter)",
    "Rohit Sharma(Batter)",
    "Will Jacks(All-Rounder)",
    "Suryakumar Yadav(Batter)",
    "Tilak Varma(Batter)",
    "Hardik Pandya(All-Rounder)",
    "Naman Dhir(All-Rounder)",
    "Corbin Bosch(All-Rounder)",
    "Deepak Chahar(Bowler)",
    "Trent Boult(Bowler)",
    "Jasprit Bumrah(Bowler)",
    "Karn Sharma(Bowler)"
]


    
    team2_playing11 = [
    "Sai Sudharsan(All-Rounder)",
    "Shubman Gill(Batter)",
    "Jos Buttler(WK-Batter)",
    "Rahul Tewatia(Bowler)",
    "Shahrukh Khan(All-Rounder)",
    "Rashid Khan(Bowler)",
    "Sai Kishore(All-Rounder)",
    "Arshad Khan(All-Rounder)",
    "Gerald Coetzee(Bowler)",
    "Mohammed Siraj(Bowler)",
    "Prasidh Krishna(Bowler)",
    "Washington Sundar(All-Rounder)",
    "Mahipal Lomror(All-Rounder)",
    "Anuj Rawat(WK-Batter)"
]


    # Predict Dream11 team
    team, captain, vice_captain, team1, team2, venue, total_credits, foreign_count = predictor.predict_dream11(
        team1, team2, venue, team1_playing11, team2_playing11
    )
    
    # Display the team
    predictor.display_team(team, captain, vice_captain, team1, team2, venue, total_credits, foreign_count)
    
    # Save the team data to a JSON file
    team_data = []
    for player, score in team:
        role = predictor.player_roles.get(player, "Unknown")
        credits = predictor.player_credits.get(player, 7.0)
        is_foreign = predictor.player_is_foreign.get(player, False)
        
        # Determine player's team
        player_team = "Unknown"
        if player in [p.split('(')[0].strip() for p in team1_playing11]:
            player_team = team1
        elif player in [p.split('(')[0].strip() for p in team2_playing11]:
            player_team = team2
            
        # Convert team name to abbreviation
        team_abbr = ""
        if "Sunrisers" in player_team:
            team_abbr = "SRH"
        elif "Delhi" in player_team:
            team_abbr = "DC"
        elif "Chennai" in player_team:
            team_abbr = "CSK"
        elif "Mumbai" in player_team:
            team_abbr = "MI"
        elif "Kolkata" in player_team:
            team_abbr = "KKR"
        elif "Punjab" in player_team:
            team_abbr = "PBKS"
        elif "Rajasthan" in player_team:
            team_abbr = "RR"
        elif "Bangalore" in player_team or "Bengaluru" in player_team:
            team_abbr = "RCB"
        elif "Gujarat" in player_team:
            team_abbr = "GT"
        elif "Lucknow" in player_team:
            team_abbr = "LSG"
        else:
            team_abbr = player_team[:2]
        
        # Simplify role for web display
        display_role = "Batsman"
        if "WK" in role:
            display_role = "Wicketkeeper"
        elif "Bowler" in role:
            display_role = "Bowler"
        elif "All-Rounder" in role or "Allrounder" in role:
            display_role = "All-Rounder"
        
        team_data.append({
            "name": player,
            "team": team_abbr,
            "role": display_role,
            "credit": credits,
        })
    
    # Save to JSON file
    with open('fantasy_team.json', 'w') as f:
        json.dump({
            "players": team_data,
            "total_credits": total_credits,
            "match": f"{team1} vs {team2}",
            "venue": venue,
            "captain": captain,
            "vice_captain": vice_captain
        }, f, indent=2)
    
    print("\nTeam data saved to fantasy_team.json")

if __name__ == "__main__":
    main()