import time
import threading
import numpy as np
import yfinance as yf
import requests
from flask import Flask
from concurrent.futures import ThreadPoolExecutor, as_completed

SL = 1.0
TP = 3.5
CAPITAL = 1000
N_VENTANA = 8
MAX_WORKERS = 8

lock_general = threading.Lock()
stats = {"operaciones_totales": 0, "ganadas": 0, "perdidas": 0, "pnl_acumulado_dinero": 0.0}

POSICIONES_INICIALES = {
    "WALMEX.MX": 46.10, "CEMEXCPO.MX": 17.44, "GFNORTEO.MX": 189.83,
    "AMXB.MX": 19.35, "BIMBOA.MX": 55.05, "GMEXICOB.MX": 232.40,
}
posiciones = POSICIONES_INICIALES.copy()

TICKERS_30 = [
    "WALMEX.MX", "GFNORTEO.MX", "AMXB.MX", "CEMEXCPO.MX", "BIMBOA.MX",
    "GMEXICOB.MX", "FEMSAUBD.MX", "KOFUBL.MX", "LABB.MX", "AC.MX",
    "GAPB.MX", "ASURB.MX", "ALSEA.MX", "ELEKTRA.MX", "GENTERA.MX",
    "GRUMAB.MX", "KIMBERA.MX", "LIVEPOLC1.MX", "ORBIA.MX", "PINFRA.MX",
    "PE&OLES.MX", "RA.MX", "TLEVISACPO.MX", "VESTA.MX", "VOLARA.MX",
    "AAPL.MX", "NVDA.MX", "MSFT.MX", "AMZN.MX", "TSLA.MX"
]

app = Flask(__name__)

def enviar_whatsapp(mensaje):
    # Si no pones PHONE y APIKEY, solo imprime en consola
    try:
        PHONE = "526871072532"
        APIKEY = "8499821"
        if PHONE and APIKEY:
            url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={requests.utils.quote(mensaje)}&apikey={APIKEY}"
            requests.get(url, timeout=15)
        print(f"ALERTA: {mensaje}")
    except Exception as e:
        print(f"Error: {e}")

def Wn(n):
    phi = (1 + 5**0.5) / 2
    return phi**(-n)

def aplicar_filtro_ifft_dinamico(precios):
    if len(precios) < N_VENTANA: return precios
    sub_precios = precios[-N_VENTANA:]
    retornos_locales = np.diff(sub_precios) / sub_precios[:-1]
    volatilidad_local = np.std(retornos_locales)
    fft_vals = np.fft.fft(sub_precios)
    corte = 3 if volatilidad_local > 0.012 else 2
    fft_vals[corte:-corte] = 0
    return np.fft.ifft(fft_vals).real

def calcular_f12_con_ifft(precios_crudos):
    if len(precios_crudos) < N_VENTANA: return None, None
    precios = aplicar_filtro_ifft_dinamico(precios_crudos)
    retornos = np.diff(precios) / precios[:-1]
    retornos_abs = np.abs(retornos)
    indices_top = np.argsort(retornos_abs)[-min(len(retornos), len(retornos)):]
    peso_top20 = np.sum([Wn(i) for i in range(len(indices_top))])
    volatilidad = np.std(retornos) * 100
    factor_vol = np.log(max(volatilidad, 1.01)) / 10
    momento_top = np.mean(retornos[indices_top])
    baba = (3.26 + factor_vol) * momento_top * 100 * (peso_top20 / 100)
    if baba > 0.010: return "SUBE", True
    elif baba < -0.010: return "BAJA", False
    else: return "LATERAL", None

def ejecutar(tipo, ticker, precio):
    global stats
    with lock_general:
        entrada = posiciones.get(ticker, precio)
        pnl_pct = (precio - entrada) / entrada * 100 if tipo == "VENTA" else 0
        pnl_dinero = CAPITAL * pnl_pct / 100
        if tipo == "COMPRA":
            msg = f"🟢 F12 COMPRA: {ticker} ${precio:.2f} SL 1% TP 3.5%"
            print(msg); enviar_whatsapp(msg)
            posiciones[ticker] = precio
        else:
            stats["operaciones_totales"] += 1
            stats["pnl_acumulado_dinero"] += pnl_dinero
            if pnl_pct > 0: stats["ganadas"] += 1; res="GANADA"
            else: stats["perdidas"] += 1; res="PERDIDA"
            tasa = (stats["ganadas"] / stats["operaciones_totales"]) * 100
            msg = f"🔴 F12 VENTA [{res}] {ticker} ${precio:.2f} PnL {pnl_pct:+.2f}% Acierto {tasa:.1f}%"
            print(msg); enviar_whatsapp(msg)
            posiciones.pop(ticker, None)

def procesar_activo(t, datos_ticker):
    try:
        precios = datos_ticker['Close'].dropna().to_numpy().flatten()
        if len(precios) < N_VENTANA: return
        precio_actual = round(float(precios[-1]), 2)
        prediccion, es_compra = calcular_f12_con_ifft(precios)
        if prediccion is None: return
        with lock_general: en_portafolio = t in posiciones
        etiqueta = " [EN PORTAFOLIO]" if en_portafolio else ""
        print(f"  > {t.replace('.MX',''):<12}: ${precio_actual:<7.2f} | F12+IFFT: {prediccion:<7}{etiqueta}")
        if es_compra is True and not en_portafolio:
            ejecutar("COMPRA", t, precio_actual)
        elif en_portafolio:
            with lock_general: precio_entrada = posiciones.get(t, precio_actual)
            pnl = (precio_actual - precio_entrada) / precio_entrada * 100
            if pnl <= -SL or pnl >= TP or es_compra is False:
                ejecutar("VENTA", t, precio_actual)
    except Exception as e:
        print(f"Error {t}: {e}")

def loop_f12():
    print("🚀 F12 GBM CLOUD SL 1.0 TP 3.5 Iniciado - SIN WHATSAPP, SOLO CONSOLA")
    while True:
        try:
            print(f"\n--- Escaneo [{time.strftime('%H:%M:%S')}] ---")
            datos_masivos = yf.download(tickers=TICKERS_30, period="5d", interval="15m", group_by='ticker', progress=False, threads=True)
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futuros = [executor.submit(procesar_activo, t, datos_masivos[t] if len(TICKERS_30)>1 else datos_masivos) for t in TICKERS_30]
                for f in as_completed(futuros): pass
            print(f"📈 Resumen: Ops {stats['operaciones_totales']} | PnL ${stats['pnl_acumulado_dinero']:+.2f}")
            time.sleep(60)
        except Exception as e:
            print(f"Error loop: {e}"); time.sleep(10)

@app.route('/')
def home():
    return f"F12 CLOUD LIVE - OK - SL 1.0 TP 3.5 | Ops: {stats['operaciones_totales']} | PnL: ${stats['pnl_acumulado_dinero']:.2f} | Portafolio: {list(posiciones.keys())}"

threading.Thread(target=loop_f12, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
