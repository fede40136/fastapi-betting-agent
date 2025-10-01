from fastapi import FastAPI, HTTPException
import os
import httpx

app = FastAPI()

API_KEY = os.getenv("ODDS_API_KEY")

@app.get("/available-sports")
async def get_sports():
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Chiave API non configurata")
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={API_KEY}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response.json()

@app.get("/quote-demo")
async def get_demo_quotes():
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Chiave API non configurata")

    # Personalizza qui usando uno sport valido ottenuto da /available-sports
    sport = "soccer_epl"  # Cambio automatico consigliato dopo test

    url = f"https://api.the-odds-api.com/v4/sports/{sport}/matches?apiKey={API_KEY}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail)

        data = response.json()
        result = []
        for match in data[:5]:
            for book in match.get('bookmakers', []):
                if book['title'] in ['Bet365', 'Pinnacle']:
                    for market in book.get('markets', []):
                        if market['key'] == 'h2h':
                            odds = market.get('outcomes', [])
                            if len(odds) == 3:
                                # Evita divisione per zero usando controllo
                                try:
                                    prob_home = round(1 / odds[0]['price'], 4) if odds[0]['price'] > 0 else 0
                                    prob_draw = round(1 / odds[1]['price'], 4) if odds[1]['price'] > 0 else 0
                                    prob_away = round(1 / odds[2]['price'], 4) if odds[2]['price'] > 0 else 0
                                except (ZeroDivisionError, KeyError):
                                    prob_home = prob_draw = prob_away = 0

                                result.append({
                                    "match": f"{match.get('home_team', 'Unknown')} vs {match.get('away_team', 'Unknown')}",
                                    "bookmaker": book.get('title', 'Unknown'),
                                    "home_win_odds": odds[0].get('price', 0),
                                    "draw_odds": odds[1].get('price', 0),
                                    "away_win_odds": odds[2].get('price', 0),
                                    "prob_home_win": prob_home,
                                    "prob_draw": prob_draw,
                                    "prob_away_win": prob_away,
                                })
        return result

@app.get("/ev")
def calculate_ev():
    # Placeholder funzione calcolo valore atteso (EV)
    return {"message": "Calcolo EV placeholder"}

@app.get("/kelly")
def calculate_kelly():
    # Placeholder funzione calcolo frazione Kelly
    return {"message": "Calcolo Kelly placeholder"}


