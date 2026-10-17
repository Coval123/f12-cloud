import time, threading, numpy as np, yfinance as yf, requests, urllib.parse
from flask import Flask
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIG ---
WHATSAPP_PHONE = "526871072532"
WHATSAPP_APIKEY = "8499821"
FINNHUB_TOKEN = "db9ccqhr01qjv8c4fukgdb9ccqhr01qjv8c4ful0"  # <-- NUEVO, EN VIVO

def enviar_whatsapp(mensaje):
    try:
        if "AQUI" in WHATSAPP_APIKEY:
            print(f"[WHATSAPP] {mensaje}")
            return
        texto = urllib.parse.quote(mensaje)
        url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={texto}&apikey={WHATSAPP_APIKEY}"
        requests.get(url, timeout=10)
    except: pass

def precio_en_vivo(ticker):
    """Precio en vivo 0 retraso desde Finnhub"""
    try:
        if "AQUI" in FINNHUB_TOKEN:
            return None
        # Finnhub usa AAPL, para BMV prueba con WALMEX.MX o WALMEX
        symbol = ticker.replace(".MX","")
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_TOKEN}"
        r = requests.get(url, timeout=5).json()
        if r.get('c',0) > 0:
            return float(r['c'])
        # Si falla con .MX, prueba con sufijo MX
        url2 = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_TOKEN}"
        r2 = requests.get(url2, timeout=5).json()
        if r2.get('c',0) > 0:
            return float(r2['c'])
    except: pass
    return None

SL = 1.0; TP = 3.5; N_VENTANA = 8
stats = {"operaciones_totales":0,"ganadas":0,"perdidas":0,"pnl_acumulado_dinero":0.0}
posiciones = {"WALMEX.MX":46.10,"CEMEXCPO.MX":17.44,"GFNORTEO.MX":189.83,"AMXB.MX":19.35,"BIMBOA.MX":55.05,"GMEXICOB.MX":232.40}

TICKERS_30 = [
    "WALMEX.MX","GFNORTEO.MX","AMXB.MX","CEMEXCPO.MX","BIMBOA.MX","GMEXICOB.MX","FEMSAUBD.MX","KOFUBL.MX","LABB.MX","AC.MX",
    "GAPB.MX","ASURB.MX","ALSEA.MX","GENTERA.MX","GRUMAB.MX","KIMBERA.MX","ORBIA.MX","PINFRA.MX","PE&OLES.MX","RA.MX",
    "TLEVISACPO.MX","VESTA.MX","VOLARA.MX","AAPL","NVDA","MSFT","AMZN","TSLA",
    "FUNO11.MX","NAFTRACISHRS.MX","OMAB.MX","FEMSAUB.MX","Q.MX","FMTY14.MX","HERDEZ.MX","FIBRAPL14.MX","CADUA.MX",
    "VITROA.MX","ARA.MX","GFINBURO.MX","AXTELCPO.MX","AUTLANB.MX","CMRB.MX","NEMAKA.MX","FINN13.MX"
]
TICKERS_30 = list(dict.fromkeys(TICKERS_30))

app = Flask(__name__)
lock_general = threading.Lock()

def Wn(n): return ((1+5**0.5)/2)**(-n)
def aplicar_filtro_ifft_dinamico(precios):
    if len(precios) < N_VENTANA: return precios
    sub = precios[-N_VENTANA:]; vol = np.std(np.diff(sub)/sub[:-1])
    fft_vals = np.fft.fft(sub); corte = 3 if vol > 0.012 else 2
    fft_vals[corte:-corte]=0; return np.fft.ifft(fft_vals).real
def calcular_f12_con_ifft(precios_crudos):
    if len(precios_crudos) < N_VENTANA: return None,None
    precios = aplicar_filtro_ifft_dinamico(precios_crudos)
    ret = np.diff(precios)/precios[:-1]
    if len(ret)==0: return None,None
    idx = np.argsort(np.abs(ret))[-len(ret):]
    peso = np.sum([Wn(i) for i in range(len(idx))])
    vol = np.std(ret)*100; fvol = np.log(max(vol,1.01))/10
    baba = (3.26+fvol)*np.mean(ret[idx])*100*(peso/100)
    if baba > 0.010: return "SUBE",True
    elif baba < -0.010: return "BAJA",False
    else: return "LATERAL",None
def ejecutar(tipo,ticker,precio,fuente="VIVO"):
    global stats
    with lock_general:
        ent = posiciones.get(ticker,precio)
        pnl = (precio-ent)/ent*100 if tipo=="VENTA" else 0
        if tipo=="COMPRA":
            print(f"🟢 COMPRA {ticker} ${precio:.2f} [{fuente}]")
            posiciones[ticker]=precio
            enviar_whatsapp(f"🟢 F12 COMPRA {ticker} ${precio:.2f} ({fuente})")
        else:
            stats["operaciones_totales"]+=1; stats["pnl_acumulado_dinero"]+=1000*pnl/100
            if pnl>0: stats["ganadas"]+=1; res="GANADA"
            else: stats["perdidas"]+=1; res="PERDIDA"
            print(f"🔴 VENTA [{res}] {ticker} ${precio:.2f} {pnl:+.2f}% [{fuente}]")
            posiciones.pop(ticker,None)
            enviar_whatsapp(f"🔴 VENTA [{res}] {ticker} ${precio:.2f} PnL {pnl:+.2f}%")

def procesar(t,datos):
    try:
        if t not in datos: return
        precios = datos[t]['Close'].dropna().to_numpy().flatten()
        if len(precios)<N_VENTANA: return
        # Precio histórico para fórmula F12
        pa_hist = round(float(precios[-1]),2)
        # Precio EN VIVO para ejecutar
        pa_vivo = precio_en_vivo(t)
        pa = pa_vivo if pa_vivo else pa_hist
        fuente = "EN VIVO" if pa_vivo else "Yahoo 1m"
        
        pred,comp = calcular_f12_con_ifft(precios)
        if pred is None: return
        with lock_general: en = t in posiciones
        print(f"  > {t.replace('.MX',''):<14}: ${pa:<7.2f} | {pred:<7} | {fuente}")
        if comp is True and not en: ejecutar("COMPRA",t,pa,fuente)
        elif en:
            with lock_general: pe = posiciones.get(t,pa)
            pnl = (pa-pe)/pe*100
            if pnl<=-SL or pnl>=TP or comp is False: ejecutar("VENTA",t,pa,fuente)
    except: pass

def loop_f12():
    print(f"🚀 F12 CLOUD EN VIVO {len(TICKERS_30)} TICKERS")
    enviar_whatsapp(f"🚀 F12 EN VIVO INICIADO {len(TICKERS_30)} tickers - Sin retraso")
    while True:
        try:
            print(f"\n--- Escaneo EN VIVO [{time.strftime('%H:%M:%S')}] ---")
            datos = yf.download(tickers=TICKERS_30, period="1d", interval="1m", group_by='ticker', progress=False, threads=True)
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = [ex.submit(procesar,t,datos) for t in TICKERS_30]
                for f in as_completed(futs): pass
            time.sleep(30)
        except Exception as e:
            print(f"Error loop {e}"); time.sleep(10)

@app.route('/')
def home(): return f"F12 CLOUD EN VIVO - {len(TICKERS_30)} TICKERS - Ops:{stats['operaciones_totales']}"

threading.Thread(target=loop_f12,daemon=True).start()
if __name__=="__main__": app.run(host="0.0.0.0",port=10000)
