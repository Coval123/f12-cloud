import yfinance as yf
import numpy as np
import requests
import os
TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_ID = os.getenv("PHONE_ID")
MI_NUM = os.getenv("MI_NUM")
def enviar_whatsapp(msg):
    url = f"https://graph.facebook.com/v22.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product":"whatsapp","to":MI_NUM,"type":"text","text":{"body":msg}}
    requests.post(url, headers=headers, json=data)
def calcular_f12(precios):
    if len(precios) < 8: return "ESPERA",0
    sub = precios[-8:]
    fft_vals = np.fft.fft(sub)
    fft_vals[3:-3]=0
    precios_f = np.fft.ifft(fft_vals).real
    ret = np.diff(precios_f)/precios_f[:-1]
    baba = np.mean(ret)*100
    if baba>0.01: return "SUBE",baba
    if baba<-0.01: return "BAJA",baba
    return "LATERAL",baba
TICKERS = ["WALMEX.MX","GFNORTEO.MX","CEMEXCPO.MX"]
for t in TICKERS:
    df = yf.download(t, period="1d", interval="1m", progress=False, auto_adjust=True)
    precios = df['Close'].dropna().values
    precio = float(precios[-1])
    pred,val = calcular_f12(precios)
    if pred!="LATERAL":
        enviar_whatsapp(f"{pred} {t} ${precio:.2f} F12:{val:.4f}")