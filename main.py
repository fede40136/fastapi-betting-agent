"""
main.py - FastAPI Betting Agent Backend API

Descrizione:
Backend API per un agente di scommesse sportive basato su FastAPI, orientato a scalabilità e
monetizzazione futura. Integra The Odds API per il recupero di quote in tempo reale, espone endpoint
per consultazione quote e include funzioni per calcoli EV e Kelly. Progettato con gestione errori
robusta, sicurezza delle credenziali via variabili d’ambiente e best practice per deployment cloud.

Funzionalità principali:
- /: homepage JSON con stato e link ai docs
- /available-sports: elenca gli sport disponibili per la chiave The Odds API configurata
- /quote-demo: recupera quote H2H (1X2) per uno sport selezionato (default EPL), calcola probabilità implicite e salva snapshot su DB
- /ev, /kelly: calcoli di Valore Atteso e frazione di Kelly
- /quotes/recent, /quotes/{event_id}: consultazione snapshot salvati

Note integrazione The Odds API (v4):
- Per ottenere le quote usare l’endpoint /v4/sports/{sport}/odds con i parametri obbligatori:
  regions, markets, oddsFormat. Il vecchio path /matches non è valido in v4.
- Parametri tipici: regions=uk (o us/eu/au), markets=h2h, oddsFormat=decimal.
- Tenere conto dei costi di quota: costo = n_markets x n_regions per chiamata.

Autore: [Team/Company]
Versione: 1.0
Data: 2025-10-01
"""

import os
from typing import List, Dict, Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Import DB e modelli locali (assicurati che db.py e models.py siano presenti nel progetto)
# db.py deve esportare: Base, engine, get_db
# models.py deve esportare: Event, OddsSnapshot
from db import Base, engine, get_db
from models import Event, OddsSnapshot

app = FastAPI(title="FastAPI Betting Agent", version="1.0.0")

# Crea le tabelle se non esistono (modo semplice per iniziare)
Base.metadata.create_all(bind=engine)

API_KEY = os.getenv("ODDS_API_KEY")


def require_api_key():
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Chiave API non configurata")


@app.get("/")
def root():
    payload = {
        "status": "ok",
        "message": "FastAPI Betting Agent è attivo. Vedi /docs per gli endpoint.",
        "docs": "/docs",
    }
    # Forza UTF-8 per evitare mojibake sugli accenti
    return JSONResponse(content=payload, media_type="application/json; charset=utf-8")


@app.get("/available-sports")
async def available_sports() -> List[Dict[str, Any]]:
    """
    Ritorna l'elenco degli sport disponibili per la chiave The Odds API configurata.
    """
    require_api_key()
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={API_KEY}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)
        return resp.json()


@app.get("/quote-demo")
async def quote_demo(
    sport: str = "soccer_epl",
    regions: str = "uk",
    markets: str = "h2h",
    odds_format: str = "decimal",
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Recupera quote recenti per lo sport specificato (default: EPL) usando The Odds API v4 /odds.
    Parametri query:
    - sport: chiave sport da /available-sports (es. soccer_epl, soccer_italy_serie_a)
    - regions: area bookmaker (uk, us, eu, au). Più regioni separate da virgola aumentano il costo
    - markets: mercati richiesti (default h2h). Più mercati aumentano il costo
    - odds_format: 'decimal' o 'american'
    In più: salva snapshot quote su DB (OddsSnapshot) e crea Event se mancante.
    """
    require_api_key()

    base = "https://api.the-odds-api.com/v4/sports"
    url = (
        f"{base}/{sport}/odds?"
        f"regions={regions}&markets={markets}&oddsFormat={odds_format}&apiKey={API_KEY}"
    )

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise HTTPException(status_code=resp.status_code, detail=detail)

        data = resp.json()
        results: List[Dict[str, Any]] = []

        def prob(x: Any) -> float:
            return round(1 / x, 4) if isinstance(x, (int, float)) and x > 0 else 0.0

        # Salva solo primi 5 eventi per evitare risposte troppo pesanti
        for event in data[:5]:
            event_id = event.get("id") or f"{event.get('home_team')}|{event.get('away_team')}|{event.get('commence_time')}"
            home = event.get("home_team")
            away = event.get("away_team")
            commence_time = event.get("commence_time")

            # Inserisci Event se non presente (upsert semplice)
            if not db.query(Event).filter(Event.id == event_id).first():
                db.add(
                    Event(
                        id=event_id,
                        sport_key=sport,
                        home_team=home,
                        away_team=away,
                        commence_time=commence_time,
                    )
                )

            # Filtra alcuni bookmaker noti; opzionale
            for bm in event.get("bookmakers", []):
                bname = bm.get("title")
                if bname in ["Bet365", "Pinnacle", "William Hill", "Betfair"]:
                    for market in bm.get("markets", []):
                        if market.get("key") == "h2h":
                            outs = market.get("outcomes", [])
                            if len(outs) == 3:
                                home_price = outs[0].get("price")
                                draw_price = outs[1].get("price")
                                away_price = outs[2].get("price")

                                # Salva snapshot su DB
                                db.add(
                                    OddsSnapshot(
                                        event_id=event_id,
                                        sport_key=sport,
                                        bookmaker=bname,
                                        market="h2h",
                                        home_price=home_price,
                                        draw_price=draw_price,
                                        away_price=away_price,
                                        raw=market,  # conserva la porzione di risposta per audit
                                    )
                                )

                                # Riepilogo per risposta client
                                results.append(
                                    {
                                        "match": f"{home} vs {away}",
                                        "bookmaker": bname,
                                        "home_win_odds": home_price,
                                        "draw_odds": draw_price,
                                        "away_win_odds": away_price,
                                        "prob_home_win": prob(home_price),
                                        "prob_draw": prob(draw_price),
                                        "prob_away_win": prob(away_price),
                                    }
                                )

        db.commit()
        return results


# Modelli input per EV/Kelly
class EvInput(BaseModel):
    prob: float = Field(..., ge=0, le=1, description="Probabilità stimata evento (0..1)")
    odds: float = Field(..., gt=1, description="Quota decimale > 1")
    stake: float = Field(..., gt=0, description="Puntata in unità monetarie")


class KellyInput(BaseModel):
    prob: float = Field(..., ge=0, le=1, description="Probabilità stimata evento (0..1)")
    odds: float = Field(..., gt=1, description="Quota decimale > 1")
    safety: float = Field(0.5, gt=0, le=1, description="Fattore prudenziale 0..1")


@app.post("/ev", summary="Calcolo Valore Atteso (EV)")
def calc_ev(body: EvInput):
    b = body.odds - 1
    ev_pct = body.prob * b - (1 - body.prob)
    ev_abs = ev_pct * body.stake
    return {"ev_abs": round(ev_abs, 4), "ev_pct": round(ev_pct, 4)}


@app.post("/kelly", summary="Calcolo frazione di Kelly")
def calc_kelly(body: KellyInput):
    b = body.odds - 1
    k = (body.prob * body.odds - 1) / b if b > 0 else 0.0
    k = max(0.0, k) * body.safety
    return {"kelly_fraction": round(k, 4)}


# Endpoint consultazione snapshot
@app.get("/quotes/recent", summary="Ultimi snapshot quote")
def quotes_recent(
    limit: int = 50,
    sport: Optional[str] = None,
    bookmaker: Optional[str] = None,
    db: Session = Depends(get_db),
):
    limit = min(limit, 200)
    q = db.query(OddsSnapshot).order_by(OddsSnapshot.created_at.desc())
    if sport:
        q = q.filter(OddsSnapshot.sport_key == sport)
    if bookmaker:
        q = q.filter(OddsSnapshot.bookmaker == bookmaker)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "event_id": r.event_id,
            "sport_key": r.sport_key,
            "bookmaker": r.bookmaker,
            "market": r.market,
            "home_price": r.home_price,
            "draw_price": r.draw_price,
            "away_price": r.away_price,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@app.get("/quotes/{event_id}", summary="Storico snapshot per evento")
def quotes_by_event(event_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(OddsSnapshot)
        .filter(OddsSnapshot.event_id == event_id)
        .order_by(OddsSnapshot.created_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "bookmaker": r.bookmaker,
            "home_price": r.home_price,
            "draw_price": r.draw_price,
            "away_price": r.away_price,
            "created_at": r.created_at,
        }
        for r in rows
    ]
