from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Ciao! Questo è il primo test del Betting Agent."}

@app.get("/ev")
def calculate_ev(quota: float, p: float):
    b = quota - 1
    ev = b * p - (1 - p)
    return {"EV": ev, "message": "Conviene" if ev > 0 else "Non conviene"}

@app.get("/kelly")
def calculate_kelly(quota: float, p: float, fraction: float = 0.3):
    b = quota - 1
    f = (b * p - (1 - p)) / b
    stake_fraction = max(0, f) * fraction
    return {"Kelly frazionato": stake_fraction}
import os
import httpx
from fastapi import HTTPException

API_KEY = os.getenv("ODDS_API_KEY")  # Prende la chiave impostata come variabile ambiente

@app.get("/quote-demo")
async def get_demo_quotes():
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Chiave API non configurata")

    url = f"https://api.the-odds-api.com/v4/sports/soccer_uefa_euro_2024/matches?apiKey={API_KEY}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Errore nella chiamata API quote")

        import os
import httpx
from fastapi import HTTPException

API_KEY = os.getenv("ODDS_API_KEY")  # Prende la chiave impostata come variabile ambiente

@app.get("/quote-demo")
async def get_demo_quotes():
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Chiave API non configurata")

    url = f"https://api.the-odds-api.com/v4/sports/soccer_uefa_euro_2024/matches?apiKey={API_KEY}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            # Mostra tutto il messaggio json di risposta per capire l’errore
            detail = response.json()
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
                                result.append({
                                    "match": f"{match['home_team']} vs {match['away_team']}",
                                    "bookmaker": book['title'],
                                    "home_win_odds": odds[0]['price'],
                                    "draw_odds": odds[1]['price'],
                                    "away_win_odds": odds[2]['price'],
                                    "prob_home_win": round(1 / odds[0]['price'], 4),
                                    "prob_draw": round(1 / odds[1]['price'], 4),
                                    "prob_away_win": round(1 / odds[2]['price'], 4),
                                })
        return result
