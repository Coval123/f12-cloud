
import time
import os
import requests
import threading
import urllib.parse
from flask import Flask
import alpaca_trade_api as tradeapi

# --- PARA RENDER ---
app = Flask(__name__)
@app.route('/')
def home():
    return "F12 AJUSTADO ACTIVO - PAPER"
def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_web, daemon=True).start()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "")

def alerta_whatsapp(mensaje):
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        print("⚠️ No hay WHATSAPP_PHONE o APIKEY")
        return
    try:
        msg = urllib.parse.quote(mensaje)
        url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={msg}&apikey={WHATSAPP_APIKEY}"
        r = requests.get(url, timeout=10)
        print(f"📱 WhatsApp enviado: {r.status_code}")
    except Exception as e:
        print(f"⚠️ No se pudo mandar WhatsApp: {e}")

# --- CONFIG F12 AJUSTADO ---
ACTIVO = "SPY"
LOTE_INICIAL = 1
LOTE_MAXIMO = 8  # ANTES 256, AHORA MAS AJUSTADO, NO SE DESBOCA
PHI = 1.6180339
SCORE_COMPRA = 12  # AJUSTADO: ANTES 25, AHORA 12 = ENTRA MAS FACIL
VENTANA_MIN = 5    # AJUSTADO: ANTES 15 MIN, AHORA 5 MIN
FACTOR_STOP = 1.2  # AJUSTADO: ANTES 2.0, AHORA 1.2 = STOP MAS CORTO
FACTOR_TP = 1.5    # AJUSTADO: TP = 1.5x STOP, SALE RAPIDO
lote_actual = LOTE_INICIAL
ultimo_precio_compra = 0.0
racha_perdidas = 0
ultimo_heartbeat = 0

def peso_aureo(n):
    return (100 / (PHI ** (0.4 * n))) / 100

def calcular_score_f12(precio_actual, precio_hace_xmin):
    if not precio_hace_xmin or precio_hace_xmin == 0:
        return 0
    cambio = abs(precio_actual - precio_hace_xmin) / precio_hace_xmin
    return min(100, cambio * 5000)

def calcular_stop_aureo(n, volatilidad):
    wn = peso_aureo(n)
    return max(0.25, wn * volatilidad * FACTOR_STOP)  # MIN 0.25, ANTES 0.50

def ejecutar_orden(simbolo, cantidad, tipo_operacion):
    try:
        orden = api.submit_order(symbol=simbolo, qty=int(cantidad), side=tipo_operacion, type='market', time_in_force='day')
        return orden
    except Exception as e:
        print(f"❌ Error orden: {e}")
        alerta_whatsapp(f"❌ ERROR F12 {simbolo}: {e}")
        return None

print("🚀 Robot F12 AJUSTADO Iniciado - PAPER")
alerta_whatsapp("🚀 F12 AJUSTADO INICIADO - SPY - SCORE 12 - Stop Corto - Te aviso cada 15 min que estoy vivo")

while True:
    try:
        trade = api.get_latest_trade(ACTIVO)
        precio_actual = trade.price

        ahora = time.time()
        if ahora - ultimo_heartbeat > 900:  # 15 min
            ultimo_heartbeat = ahora
            alerta_whatsapp(f"💓 F12 AJUSTADO VIVO - SPY ${precio_actual:.2f} - Esperando SCORE {SCORE_COMPRA} - Lote {lote_actual}")
            print("💓 Heartbeat enviado")

        posicion = None
        try:
            posicion = api.get_position(ACTIVO)
        except Exception:
            pass

        if posicion is None:
            precio_hace_xmin = precio_actual
            volatilidad = 0.30
            try:
                bars = api.get_bars(ACTIVO, tradeapi.TimeFrame.Minute, limit=VENTANA_MIN)
                bars_list = list(bars)
                if len(bars_list) > 0:
                    precio_hace_xmin = bars_list[0].c
                    max_h = max(b.h for b in bars_list)
                    min_l = min(b.l for b in bars_list)
                    volatilidad = max(0.30, (max_h - min_l) / VENTANA_MIN)
            except Exception as e:
                print(f"⚠️ Error historial: {e}")

            score = calcular_score_f12(precio_actual, precio_hace_xmin)
            print(f"📊 Buscando AJUSTADO | Precio: ${precio_actual:.2f} | Hace {VENTANA_MIN}m: ${precio_hace_xmin:.2f} | SCORE: {score:.1f}% | Vol: ${volatilidad:.2f}")

            if score >= SCORE_COMPRA:
                print(f"✅ SEÑAL COMPRA AJUSTADA {lote_actual} acciones")
                alerta_whatsapp(f"🟢 F12 AJUSTADO COMPRA {ACTIVO} {lote_actual} acc a ${precio_actual:.2f} | Score {score:.1f}% | Racha k={racha_perdidas}")
                orden = ejecutar_orden(ACTIVO, lote_actual, 'buy')
                if orden:
                    ultimo_precio_compra = precio_actual
        else:
            try:
                bars = api.get_bars(ACTIVO, tradeapi.TimeFrame.Minute, limit=VENTANA_MIN)
                bars_list = list(bars)
                max_h = max(b.h for b in bars_list)
                min_l = min(b.l for b in bars_list)
                volatilidad = max(0.30, (max_h - min_l) / VENTANA_MIN)
            except:
                volatilidad = 0.30

            stop_aureo = calcular_stop_aureo(racha_perdidas + 1, volatilidad)
            ganancia_objetivo = stop_aureo * FACTOR_TP
            print(f"📈 En Mercado AJUSTADO | Entrada: ${ultimo_precio_compra:.2f} | Actual: ${precio_actual:.2f} | SL: ${stop_aureo:.2f} | TP: ${ganancia_objetivo:.2f}")

            if precio_actual >= (ultimo_precio_compra + ganancia_objetivo):
                alerta_whatsapp(f"💰 F12 VENTA GANANCIA {ACTIVO} a ${precio_actual:.2f} | +${ganancia_objetivo:.2f} | Reset a 8 acc")
                orden = ejecutar_orden(ACTIVO, posicion.qty, 'sell')
                if orden:
                    lote_actual = LOTE_INICIAL
                    racha_perdidas = 0
                    ultimo_precio_compra = 0.0
            elif precio_actual <= (ultimo_precio_compra - stop_aureo):
                alerta_whatsapp(f"🔴 F12 VENTA STOP {ACTIVO} a ${precio_actual:.2f} | -${stop_aureo:.2f}")
                orden = ejecutar_orden(ACTIVO, posicion.qty, 'sell')
                if orden:
                    time.sleep(2)
                    racha_perdidas += 1
                    lote_actual = LOTE_INICIAL * (2 ** racha_perdidas)
                    if lote_actual > LOTE_MAXIMO:
                        alerta_whatsapp(f"🚨 F12 APAGADO - Lote {lote_actual} supera max {LOTE_MAXIMO}")
                        break
                    alerta_whatsapp(f"🔄 F12 Siguiente intento: {lote_actual} acc | Racha k={racha_perdidas}")
    except Exception as e:
        print(f"⚠️ Alerta critica: {e}")
    time.sleep(5)
