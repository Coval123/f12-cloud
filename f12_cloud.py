import time, threading, numpy as np, yfinance as yf, requests, urllib.parse
from flask import Flask
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- WHATSAPP CONFIG ---
WHATSAPP_PHONE = "526871072532"
WHATSAPP_APIKEY = "8499821"

def enviar_whatsapp(mensaje):
    try:
        if "AQUI" in WHATSAPP_APIKEY:
            print(f"[WHATSAPP] {mensaje}")
            return
        texto = urllib.parse.quote(mensaje)
        url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={texto}&apikey={WHATSAPP_APIKEY}"
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"Error WhatsApp: {e}")

SL = 1.0; TP = 3.5; N_VENTANA = 8
stats = {"operaciones_totales":0,"ganadas":0,"perdidas":0,"pnl_acumulado_dinero":0.0}
posiciones = {"WALMEX.MX":46.10,"CEMEXCPO.MX":17.44,"GFNORTEO.MX":189.83,"AMXB.MX":19.35,"BIMBOA.MX":55.05,"GMEXICOB.MX":232.40}

TICKERS_30 = [
    "WALMEX.MX","GFNORTEO.MX","AMXB.MX","CEMEXCPO.MX","BIMBOA.MX","GMEXICOB.MX","FEMSAUBD.MX","KOFUBL.MX","LABB.MX","AC.MX",
    "GAPB.MX","ASURB.MX","ALSEA.MX","GENTERA.MX","GRUMAB.MX","KIMBERA.MX","ORBIA.MX","PINFRA.MX","PE&OLES.MX","RA.MX",
    "TLEVISACPO.MX","VESTA.MX","VOLARA.MX","AAPL.MX","NVDA.MX","MSFT.MX","AMZN.MX","TSLA.MX",
    "FUNO11.MX","NAFTRACISHRS.MX","OMAB.MX","FEMSAUB.MX","Q.MX","AEROMEX.MX","FMTY14.MX","HERDEZ.MX","FIBRAPL14.MX","CADUA.MX",
    "VITROA.MX","ARA.MX","GFINBURO.MX","AXTELCPO.MX","AUTLANB.MX","CMRB.MX","NEMAKA.MX","FINN13.MX"
]
TICKERS_30 = list(dict.fromkeys(TICKERS_30))

app = Flask(__name__)
lock_general = threading.Lock()

def Wn(n): return ((1+5**0.5)/2)**(-n)
def aplicar_filtro_ifft_dinamico(precios):
    if len(precios) < N_VENTANA: return precios
    sub = precios[-N_VENTANA:]
    vol = np.std(np.diff(sub)/sub[:-1])
    fft_vals = np.fft.fft(sub)
    corte = 3 if vol > 0.012 else 2
    fft_vals[corte:-corte]=0
    return np.fft.ifft(fft_vals).real

def calcular_f12_con_ifft(precios_crudos):
    if len(precios_crudos) < N_VENTANA: return None,None
    precios = aplicar_filtro_ifft_dinamico(precios_crudos)
    ret = np.diff(precios)/precios[:-1]
    idx = np.argsort(np.abs(ret))[-len(ret):]
    peso = np.sum([Wn(i) for i in range(len(idx))])
    vol = np.std(ret)*100
    fvol = np.log(max(vol,1.01))/10
    baba = (3.26+fvol)*np.mean(ret[idx])*100*(peso/100)
    if baba > 0.010: return "SUBE",True
    elif baba < -0.010: return "BAJA",False
    else: return "LATERAL",None

def ejecutar(tipo,ticker,precio):
    global stats
    with lock_general:
        ent = posiciones.get(ticker,precio)
        pnl = (precio-ent)/ent*100 if tipo=="VENTA" else 0
        if tipo=="COMPRA":
            print(f"🟢 COMPRA {ticker} ${precio:.2f}")
            posiciones[ticker]=precio
            enviar_whatsapp(f"🟢 F12 COMPRA {ticker} ${precio:.2f}")
        else:
            stats["operaciones_totales"]+=1
            stats["pnl_acumulado_dinero"]+=1000*pnl/100
            if pnl>0: stats["ganadas"]+=1; res="GANADA"
            else: stats["perdidas"]+=1; res="PERDIDA"
            print(f"🔴 VENTA [{res}] {ticker} ${precio:.2f} {pnl:+.2f}%")
            posiciones.pop(ticker,None)
            enviar_whatsapp(f"🔴 F12 VENTA [{res}] {ticker} ${precio:.2f} PnL {pnl:+.2f}%")

def procesar(t,datos):
    try:
        precios = datos['Close'].dropna().to_numpy().flatten()
        if len(precios)<N_VENTANA: return
        pa = round(float(precios[-1]),2)
        pred,comp = calcular_f12_con_ifft(precios)
        if pred is None: return
        with lock_general: en = t in posiciones
        print(f"  > {t.replace('.MX',''):<14}: ${pa:<7.2f} | {pred:<7}{' [EN PORT]' if en else ''}")
        if comp is True and not en:
            ejecutar("COMPRA",t,pa)
        elif en:
            with lock_general: pe = posiciones.get(t,pa)
            pnl = (pa-pe)/pe*100
            if pnl<=-SL or pnl>=TP or comp is False:
                ejecutar("VENTA",t,pa)
    except Exception as e:
        print(f"Error {t}: {e}")

def loop_f12():
    print(f"🚀 F12 CLOUD FINAL {len(TICKERS_30)} TICKERS - SL 1.0 TP 3.5 - WHATSAPP")
    enviar_whatsapp(f"🚀 F12 CLOUD INICIADO {len(TICKERS_30)} tickers")
    while True:
        try:
            print(f"\n--- Escaneo [{time.strftime('%H:%M:%S')}] ---")
            datos = yf.download(tickers=TICKERS_30, period="5d", interval="15m", group_by='ticker', progress=False, threads=True)
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = [ex.submit(procesar,t,datos[t] if len(TICKERS_30)>1 else datos) for t in TICKERS_30]
                for f in as_completed(futs): pass
            time.sleep(60)
        except Exception as e:
            print(f"Error loop {e}")
            time.sleep(10)

@app.route('/')
def home():
    return f"F12 CLOUD LIVE WHATSAPP - {len(TICKERS_30)} TICKERS OK - Ops:{stats['operaciones_totales']}"

threading.Thread(target=loop_f12,daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
