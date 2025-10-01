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
