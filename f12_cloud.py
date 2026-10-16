import os
import time
import numpy as np
import yfinance as yf
from flask import Flask
import threading
import requests

TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD"]
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "")

app = Flask(__name__)

def calcular_f12(precios):
    try:
        arr = np.array(precios).reshape(-1)
        arr = arr[~np.isnan(arr)]
        if len(arr) < 20:
            return "LATERAL", 0.0
        sma = np.mean(arr[-20:])
        last = float(arr[-1])
        diff = (last - sma) / sma if sma != 0 else 0
        if abs(diff) < 0.005:
            return "LATERAL", diff
        elif diff > 0:
            return "ALCISTA", diff
        else:
            return "BAJISTA", diff
    except Exception as e:
        print(f"Error calcular_f12: {e}")
        return "LATERAL", 0.0

def enviar_whatsapp(mensaje):
    print(f"WHATSAPP: {mensaje}")
    try:
        if WHATSAPP_PHONE and WHATSAPP_APIKEY:
            url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={requests.utils.quote(mensaje)}&apikey={WHATSAPP_APIKEY}"
            requests.get(url, timeout=10)
    except Exception as e:
        print(f"Error whatsapp: {e}")

def loop_principal():
    print("Iniciando loop F12...")
    while True:
        try:
            for t in TICKERS:
                try:
                    print(f"Descargando {t}...")
                    df = yf.download(t, period="1d", interval="1m", progress=False, auto_adjust=True)
                    if df.empty or 'Close' not in df.columns:
                        print(f"{t} sin datos")
                        continue
                    precios = df['Close'].dropna().values
                    precio = float(np.array(precios).reshape(-1)[-1])
                    prod, val = calcular_f12(precios)
                    print(f"{t} -> {precio} -> {prod} {val}")
                    if prod == "LATERAL":
                        enviar_whatsapp(f"{t} ${precio:.2f} F12:{val:.4f}")
                except Exception as e:
                    print(f"Error en ticker {t}: {e}")
                    continue
        except Exception as e:
            print(f"Error general loop: {e}")
        print("Esperando 60s...")
        time.sleep(60)

@app.route("/")
def home():
    return "F12 CLOUD LIVE - OK", 200

@app.route("/health")
def health():
    return "OK", 200

threading.Thread(target=loop_principal, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
