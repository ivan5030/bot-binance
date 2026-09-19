import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime

CESTANDA_CRYPTOS = ["ETH/USDT", "LINK/USDT", "AVAX/USDT", "NEAR/USDT"]
TEMPORALIDAD = "15m"
RATIO_RR = 2.0
CAPITAL_SIMULADO = 100.0  
PORCENTAJE_RIESGO = 0.02
COMISION_BINANCE = 0.001

# Conexión directa y limpia (sin proxy)
exchange = ccxt.binance({'enableRateLimit': True})

posicion_activa = False
crypto_en_operacion = None
precio_entrada = 0
stop_loss = 0
take_profit = 0
cantidad_monedas = 0

def log_operacion(mensaje):
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{fecha_hora}] {mensaje}\n"
    print(linea.strip())

def obtener_datos(simbolo):
    try:
        olas = exchange.fetch_ohlcv(simbolo, timeframe=TEMPORALIDAD, limit=50)
        df = pd.DataFrame(olas, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        df['Media_Movil'] = df['Close'].rolling(window=20).mean()
        df['Desviacion'] = df['Close'].rolling(window=20).std()
        df['Banda_Inferior'] = df['Media_Movil'] - (df['Desviacion'] * 2.0)
        
        high_low = df['High'] - df['Low']
        high_cp = np.abs(df['High'] - df['Close'].shift(1))
        low_cp = np.abs(df['Low'] - df['Close'].shift(1))
        df['ATR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(window=14).mean()
        return df
    except Exception as e:
        print(f"Error en Binance para {simbolo}: {e}")
        return None

log_operacion(f"Bot iniciado en Render. Capital Virtual: {CAPITAL_SIMULADO:.2f} USDT. Escaneando...")

while True:
    try:
        if posicion_activa:
            df = obtener_datos(crypto_en_operacion)
            if df is not None and not df.empty:
                ultima_vela = df.iloc[-1]
                if ultima_vela['Low'] <= stop_loss:
                    CAPITAL_SIMULADO -= ((precio_entrada - stop_loss) * cantidad_monedas)
                    log_operacion(f"❌ SL en {crypto_en_operacion}. Saldo: {CAPITAL_SIMULADO:.2f} USDT")
                    posicion_activa = False
                elif ultima_vela['High'] >= take_profit:
                    CAPITAL_SIMULADO += ((take_profit - precio_entrada) * cantidad_monedas)
                    log_operacion(f"🟢 TP en {crypto_en_operacion}. Saldo: {CAPITAL_SIMULADO:.2f} USDT")
                    posicion_activa = False
        else:
            for crypto in CESTANDA_CRYPTOS:
                df = obtener_datos(crypto)
                if df is None or len(df) < 2:
                    continue
                fila_actual = df.iloc[-1]
                fila_anterior = df.iloc[-2]
                atr = fila_actual['ATR']
                banda_inf = fila_actual['Banda_Inferior']
                
                if np.isnan(atr) or np.isnan(banda_inf):
                    continue
                
                if fila_anterior['Close'] < fila_anterior['Banda_Inferior'] and fila_actual['Close'] > banda_inf:
                    precio_entrada = fila_actual['Close']
                    stop_loss = precio_entrada - (atr * 1.5)
                    take_profit = precio_entrada + ((precio_entrada - stop_loss) * RATIO_RR)
                    distancia_precio_sl = precio_entrada - stop_loss
                    if distancia_precio_sl > 0:
                        cantidad_monedas = (CAPITAL_SIMULADO * PORCENTAJE_RIESGO) / distancia_precio_sl
                        crypto_en_operacion = crypto
                        posicion_activa = True
                        log_operacion(f"🛒 COMPRA VIRTUAL en {crypto} | Entrada: {precio_entrada:.4f}")
                        break 
        time.sleep(30)
    except Exception as e:
        time.sleep(10)
