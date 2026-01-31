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
    logger.info(f"\nFetching stats for {len(american_players)} American players...")

    # Get detailed stats for each American
    american_stats = []
    for i, player in enumerate(american_players):
        logger.info(f"  [{i+1}/{len(american_players)}] {player['name']}...")

        stats = get_player_stats(player['id'], player['name'])

        if stats and stats.get('games', 0) > 0:
            player_data = {
                'tblstat_id': player['id'],
                'name': player['name'],
                **stats
            }

            # Try to match with existing player
            norm_name = normalize_name(player['name'])
            if norm_name in existing_players:
                player_data['player_code'] = existing_players[norm_name].get('code')
                player_data['matched'] = True

            american_stats.append(player_data)
            logger.info(f"    -> {stats.get('ppg', 0):.1f} PPG, {stats.get('rpg', 0):.1f} RPG, {stats.get('apg', 0):.1f} APG")
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
