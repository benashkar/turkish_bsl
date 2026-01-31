"""
=============================================================================
BSL SCRAPER - TURKISH BASKETBALL SUPER LEAGUE
=============================================================================

PURPOSE:
    Scrapes player statistics from TBLStat.net for Turkish BSL.
    Identifies American players and collects their season stats.

DATA SOURCE:
    TBLStat.net: https://bsl.tblstat.net/

COLUMNS (Turkish -> English):
    - Maç = Games
    - Dk = Minutes
    - Sy = Points (Sayı)
    - Rib = Rebounds (Ribaunt)
    - Ast = Assists (Asist)
    - TÇ = Steals (Top Çalma)
    - TK = Turnovers (Top Kaybı)
    - VP = Efficiency Rating (Val Puan)
    - SA = Free Throw % (Serbest Atış)
    - 2Sy = 2-Point FG %
    - 3Sy = 3-Point FG %

OUTPUT:
    - bsl_american_stats_*.json: American player statistics
"""

import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SEASON_CODE = '2526'  # TBLStat uses YYXX format
CURRENT_SEASON = '2025-26'
BASE_URL = 'https://bsl.tblstat.net'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Known American players - expanded list for matching
KNOWN_AMERICANS = [
    'anthony brown', 'bonzie colson', 'briante weber', 'brodric thomas',
    'cj massinburg', 'c.j. massinburg', 'cassius winston', 'daniel hamilton',
    'daniel utomi', 'devon hall', 'emanuel terry', 'evan bruinsma',
    'isaiah mobley', 'jalen lecque', 'javon freeman-liberty', 'jaylon brown',
    'jehyve floyd', 'jonah mathews', 'jordan floyd', 'jordon crawford',
    'lamar peters', 'malik newman', 'maxwell lewis', 'nick weiler-babb',
    'pj dozier', 'p.j. dozier', 'stanley whittaker', 'tyler cook',
    'errick mccollum', 'anthony cowan', 'brandon childress', 'bryant crawford',
    'cameron young', 'charles manning', 'chris chiozza', 'devon dotson',
    'david efianayi', 'armando bacot', 'brandon boston', 'dj stewart',
    'd.j. stewart', 'scottie lindsey', 'jaron blossomgame', 'nigel hayes',
    'sheldon mac', 'chad brown', 'will cummings', 'tony mitchell',
    'vitto brown', 'trey lewis', 'devin williams', 'tyson ward',
]


def normalize_name(name):
    """Normalize player name for matching."""
    if not name:
        return ''
    import unicodedata
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = name.lower().strip()
    name = re.sub(r'\s+(jr\.?|sr\.?|iii|ii|iv)$', '', name, flags=re.IGNORECASE)
    return name


def is_likely_american(player_name):
    """Check if player is likely American based on name matching."""
    norm_name = normalize_name(player_name)

    for american in KNOWN_AMERICANS:
        if american in norm_name or norm_name in american:
            return True
        # Check last name match
        parts = norm_name.split()
        if parts:
            last_name = parts[-1]
            am_parts = american.split()
            if am_parts and last_name == am_parts[-1]:
                return True

    return False


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def get_all_players():
    """Get all players from the players index page."""
    url = f"{BASE_URL}/players/{SEASON_CODE}"
    logger.info(f"Fetching players list from: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        players = []
        links = soup.find_all('a', onclick=True)

        for link in links:
            onclick = str(link.get('onclick', ''))
            match = re.search(r"player/(\d+)", onclick)
            if match:
                player_id = match.group(1)
                name = link.get_text(strip=True)
                players.append({
                    'id': player_id,
                    'name': name,
                    'is_american': is_likely_american(name)
                })

        logger.info(f"Found {len(players)} total players")
        american_count = sum(1 for p in players if p['is_american'])
        logger.info(f"Potential Americans: {american_count}")

        return players

    except requests.RequestException as e:
        logger.error(f"Error fetching players: {e}")
        return []


def get_player_stats(player_id, player_name):
    """Get detailed stats for a specific player."""
    url = f"{BASE_URL}/player/{player_id}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find stats table
        table = soup.find('table')
        if not table:
            return None

        # Find current season row
        rows = table.find_all('tr')
        current_season_data = None

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if len(cells) >= 8 and CURRENT_SEASON in cells[0]:
                # Parse the row: Season, Team, Games, Min, Pts, Reb, Ast, Stl, TO, Eff, FT%, 2P%, 3P%
                try:
                    current_season_data = {
                        'team': cells[1] if len(cells) > 1 else None,
                        'games': int(cells[2]) if len(cells) > 2 and cells[2].isdigit() else 0,
                        'minutes': float(cells[3]) if len(cells) > 3 and cells[3] else 0,
                        'ppg': float(cells[4]) if len(cells) > 4 and cells[4] else 0,
                        'rpg': float(cells[5]) if len(cells) > 5 and cells[5] else 0,
                        'apg': float(cells[6]) if len(cells) > 6 and cells[6] else 0,
                        'spg': float(cells[7]) if len(cells) > 7 and cells[7] else 0,
                        'topg': float(cells[8]) if len(cells) > 8 and cells[8] else 0,
                        'efficiency': float(cells[9]) if len(cells) > 9 and cells[9] else 0,
                        'ft_pct': cells[10].replace('%', '') if len(cells) > 10 else None,
                        'fg2_pct': cells[11].replace('%', '') if len(cells) > 11 else None,
                        'fg3_pct': cells[12].replace('%', '') if len(cells) > 12 else None,
                    }
                    # Convert percentages to floats
                    for key in ['ft_pct', 'fg2_pct', 'fg3_pct']:
                        if current_season_data.get(key):
                            try:
                                current_season_data[key] = float(current_season_data[key])
                            except:
                                current_season_data[key] = 0
                except (ValueError, IndexError) as e:
                    logger.debug(f"Error parsing stats for {player_name}: {e}")
                    continue

        return current_season_data

    except requests.RequestException as e:
        logger.debug(f"Error fetching player {player_id}: {e}")
        return None


def load_existing_players():
    """Load existing American players from our data."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    latest_file = os.path.join(output_dir, 'unified_american_players_latest.json')

    if os.path.exists(latest_file):
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                players = data.get('players', [])
                logger.info(f"Loaded {len(players)} existing American players for matching")
                return {normalize_name(p.get('name', '')): p for p in players}
        except Exception as e:
            logger.warning(f"Error loading existing players: {e}")

    return {}


# Turkish month names to numbers
TURKISH_MONTHS = {
    'ocak': '01', 'şubat': '02', 'mart': '03', 'nisan': '04',
    'mayıs': '05', 'haziran': '06', 'temmuz': '07', 'ağustos': '08',
    'eylül': '09', 'ekim': '10', 'kasım': '11', 'aralık': '12',
    'oca': '01', 'sub': '02', 'şub': '02', 'mar': '03', 'nis': '04',
    'may': '05', 'haz': '06', 'tem': '07', 'agu': '08', 'ağu': '08',
    'eyl': '09', 'eki': '10', 'kas': '11', 'ara': '12',
}


def parse_turkish_date(date_str):
    """Convert Turkish date like '28 Eylül 2025' to '2025-09-28'."""
    if not date_str:
        return None

    # Clean and lowercase
    date_str = date_str.lower().strip()

    # Try to extract parts
    parts = date_str.split()
    if len(parts) >= 3:
        day = parts[0].zfill(2)
        month_name = parts[1]
        year = parts[2]

        # Find month number
        month = None
        for tk_month, num in TURKISH_MONTHS.items():
            if tk_month in month_name:
                month = num
                break

        if month and day.isdigit() and year.isdigit():
            return f"{year}-{month}-{day.zfill(2)}"

    return None


def fetch_schedule():
    """Fetch full schedule from TBLStat.net games page."""
    url = f"{BASE_URL}/games/{SEASON_CODE}"
    logger.info(f"Fetching schedule from: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        games = []

        # Find all game links
        links = soup.find_all('a', onclick=True)
        game_ids = []
        for link in links:
            onclick = str(link.get('onclick', ''))
            match = re.search(r"game/(\d+)", onclick)
            if match:
                game_ids.append(match.group(1))

        game_ids = list(set(game_ids))  # Remove duplicates
        logger.info(f"Found {len(game_ids)} games, fetching details...")

        # Fetch each game's details (all games to capture upcoming)
        for i, game_id in enumerate(game_ids):
            if i > 0 and i % 20 == 0:
                logger.info(f"  Progress: {i}/{len(game_ids)}")

            game_data = fetch_game_details(game_id)
            if game_data:
                games.append(game_data)
            time.sleep(0.3)

        logger.info(f"Fetched details for {len(games)} games")
        return games

    except requests.RequestException as e:
        logger.error(f"Error fetching schedule: {e}")
        return []


def fetch_game_details(game_id):
    """Fetch details for a specific game including box score."""
    url = f"{BASE_URL}/game/{game_id}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        game = {'game_id': game_id}

        # Parse title for teams and date
        # Format: "Team1 vs. Team2 | DD Month YYYY..."
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
            # Extract teams
            if ' vs. ' in title:
                teams_part = title.split('|')[0].strip()
                teams = teams_part.split(' vs. ')
                if len(teams) == 2:
                    game['home_team'] = teams[0].strip()
                    game['away_team'] = teams[1].strip()

            # Extract date
            if '|' in title:
                date_part = title.split('|')[1].strip()
                # Date is usually at the start of this part
                date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', date_part)
                if date_match:
                    game['date'] = parse_turkish_date(date_match.group(1))

        # Get scores from tables (first row sums)
        tables = soup.find_all('table')
        if len(tables) >= 2:
            # Get team totals (last row of each table usually)
            for i, table in enumerate(tables[:2]):
                rows = table.find_all('tr')
                if rows:
                    # Find total row or last data row
                    for row in rows:
                        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        if cells and cells[0].lower() in ['toplam', 'total', '']:
                            # This might be the totals row
                            if len(cells) > 2 and cells[2].isdigit():
                                if i == 0:
                                    game['home_score'] = int(cells[2])
                                else:
                                    game['away_score'] = int(cells[2])

        # Determine if game is played
        game['played'] = bool(game.get('home_score') and game.get('away_score'))

        # Get box score player stats
        game['box_score'] = []
        for table in tables[:2]:
            team_idx = tables.index(table)
            team_name = game.get('home_team') if team_idx == 0 else game.get('away_team')

            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cells) >= 8 and cells[0] and cells[0].lower() not in ['toplam', 'total', '']:
                    player_stat = {
                        'name': cells[0],
                        'team': team_name,
                        'minutes': cells[1] if len(cells) > 1 else None,
                        'points': int(cells[2]) if len(cells) > 2 and cells[2].isdigit() else 0,
                        'rebounds': int(cells[3]) if len(cells) > 3 and cells[3].isdigit() else 0,
                        'assists': int(cells[4]) if len(cells) > 4 and cells[4].isdigit() else 0,
                        'steals': int(cells[5]) if len(cells) > 5 and cells[5].isdigit() else 0,
                        'turnovers': int(cells[6]) if len(cells) > 6 and cells[6].isdigit() else 0,
                        'efficiency': int(cells[7]) if len(cells) > 7 and cells[7].lstrip('-').isdigit() else 0,
                    }
                    game['box_score'].append(player_stat)

        return game

    except requests.RequestException as e:
        logger.debug(f"Error fetching game {game_id}: {e}")
        return None


def build_player_game_logs(games, american_names):
    """Build game-by-game logs for American players from box scores."""
    game_logs = {}  # player_name -> list of game stats

    for game in games:
        if not game.get('box_score'):
            continue

        game_date = game.get('date')
        home_team = game.get('home_team')
        away_team = game.get('away_team')

        for stat in game['box_score']:
            player_name = stat.get('name', '')
            norm_name = normalize_name(player_name)

            # Check if American
            if norm_name not in american_names:
                continue

            # Determine opponent
            player_team = stat.get('team')
            if player_team == home_team:
                opponent = away_team
                home_away = 'Home'
            else:
                opponent = home_team
                home_away = 'Away'

            game_entry = {
                'date': game_date,
                'opponent': opponent,
                'home_away': home_away,
                'minutes': stat.get('minutes'),
                'points': stat.get('points', 0),
                'rebounds': stat.get('rebounds', 0),
                'assists': stat.get('assists', 0),
                'steals': stat.get('steals', 0),
                'turnovers': stat.get('turnovers', 0),
                'efficiency': stat.get('efficiency', 0),
            }

            if norm_name not in game_logs:
                game_logs[norm_name] = []
            game_logs[norm_name].append(game_entry)

    # Sort each player's games by date
    for name in game_logs:
        game_logs[name].sort(key=lambda x: x.get('date') or '', reverse=True)

    return game_logs


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("BSL SCRAPER - TURKISH BASKETBALL SUPER LEAGUE")
    logger.info("=" * 60)
    logger.info(f"Source: TBLStat.net")
    logger.info(f"Season: {CURRENT_SEASON}")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Load existing players for matching
    existing_players = load_existing_players()

    # Get all players
    all_players = get_all_players()
    if not all_players:
        logger.error("Failed to fetch player list")
        return

    # Filter to Americans
    american_players = [p for p in all_players if p['is_american']]
    american_names = {normalize_name(p['name']) for p in american_players}
    logger.info(f"\nFetching stats for {len(american_players)} American players...")

    # Fetch schedule and game logs
    logger.info("\nFetching game schedule and box scores...")
    games = fetch_schedule()

    # Build game logs for Americans
    game_logs = {}
    if games:
        game_logs = build_player_game_logs(games, american_names)
        logger.info(f"Built game logs for {len(game_logs)} American players")

        # Save schedule
        played_games = [g for g in games if g.get('played')]
        upcoming_games = [g for g in games if not g.get('played')]

        schedule_data = {
            'export_date': datetime.now().isoformat(),
            'season': CURRENT_SEASON,
            'league': 'Turkish BSL',
            'source': 'tblstat.net',
            'total_games': len(games),
            'played': len(played_games),
            'upcoming': len(upcoming_games),
            'games': games
        }
        save_json(schedule_data, f'bsl_schedule_{timestamp}.json')
        save_json(schedule_data, 'bsl_schedule_latest.json')

    # Get detailed stats for each American
    american_stats = []
    for i, player in enumerate(american_players):
        logger.info(f"  [{i+1}/{len(american_players)}] {player['name']}...")

        stats = get_player_stats(player['id'], player['name'])

        if stats and stats.get('games', 0) > 0:
            norm_name = normalize_name(player['name'])

            player_data = {
                'tblstat_id': player['id'],
                'name': player['name'],
                **stats,
                'game_log': game_logs.get(norm_name, [])  # Add game-by-game stats
            }

            # Try to match with existing player
            if norm_name in existing_players:
                player_data['player_code'] = existing_players[norm_name].get('code')
                player_data['matched'] = True

            american_stats.append(player_data)
            games_in_log = len(player_data.get('game_log', []))
            logger.info(f"    -> {stats.get('ppg', 0):.1f} PPG, {stats.get('rpg', 0):.1f} RPG, {stats.get('apg', 0):.1f} APG ({games_in_log} games in log)")
        else:
            logger.info(f"    -> No current season stats")

        # Be nice to the server
        time.sleep(0.5)

    logger.info(f"\n{len(american_stats)} Americans with current season stats")

    # Save results
    results = {
        'export_date': datetime.now().isoformat(),
        'season': CURRENT_SEASON,
        'league': 'Turkish BSL',
        'source': 'tblstat.net',
        'player_count': len(american_stats),
        'players': american_stats
    }

    save_json(results, f'bsl_american_stats_{timestamp}.json')
    save_json(results, 'bsl_american_stats_latest.json')

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total players in league: {len(all_players)}")
    logger.info(f"American players found: {len(american_stats)}")

    if american_stats:
        # Sort by PPG
        sorted_stats = sorted(american_stats, key=lambda x: x.get('ppg', 0), reverse=True)
        logger.info("\nTop American Scorers:")
        for p in sorted_stats[:10]:
            logger.info(f"  {p['name']} ({p.get('team', 'N/A')}) - "
                       f"{p.get('ppg', 0):.1f} PPG, {p.get('rpg', 0):.1f} RPG, {p.get('apg', 0):.1f} APG")


if __name__ == '__main__':
    main()
