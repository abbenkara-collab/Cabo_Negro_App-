import streamlit as st
import pandas as pd
import os
import math
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ÉCRAN & MOBILE ---
st.set_page_config(
    page_title="Cabo Negro Expert v3.9",
    layout="wide",
    page_icon="⛳",
    initial_sidebar_state="collapsed" 
)

# --- 2. STYLE CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAlert { border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. PARAMÈTRES & FICHIERS ---
STOCK_FILE = "stocks_magasin.csv"
LOG_FILE = "historique_sorties_2026.csv"
PLANNING_FILE = "Programme de traitement Phyto 2026.xlsx"
CITY_LAT, CITY_LON = 35.78, -5.32
GDD_THRESHOLD = 200.0
BASE_TEMP = 10.0

# --- 4. FONCTIONS ---
def get_weather():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={CITY_LAT}&longitude={CITY_LON}&current=temperature_2m,relative_humidity_2m&timezone=auto"
        res = requests.get(url).json()
        t, h = res['current']['temperature_2m'], res['current']['relative_humidity_2m']
        x = -9.99 + (0.177 * t) + (0.061 * h)
        risk = round((math.exp(x)/(1+math.exp(x)))*100, 1)
        return t, h, risk
    except: return 20.0, 70.0, 10.0

def verifier_alertes_j3(df):
    alertes = []
    auj = datetime.now()
    limite = auj + timedelta(days=3)
    col_date = next((c for c in df.columns if any(k in c.lower() for k in ["date", "période"])), None)
    if col_date:
        df[col_date] = pd.to_datetime(df[col_date], errors='coerce')
        echeances = df[(df[col_date] >= auj) & (df[col_date] <= limite)]
        for _, row in echeances.iterrows():
            prod = row.get('Produit', 'Traitement')
            alertes.append(f"⚠️ **{prod}** prévu le {row[col_date].strftime('%d/%m')}")
    return alertes

# --- 5. LOGIQUE PRINCIPALE ---
st.title("⛳ Cabo Negro Digital v3.9")
temp, hum, sk_risk = get_weather()

tabs = st.tabs(["📊 Dashboard", "🌱 GDD", "💊 Planification", "📜 Historique & Diagrammes"])

# --- TAB 1 : DASHBOARD ---
with tabs[0]:
    c1, c2, c3 = st.columns(3)
    c1.metric("Temp.", f"{temp}°C")
    c2.metric("Humidité", f"{hum}%")
    c3.metric("Risque Dollar Spot", f"{sk_risk}%", delta="ALERTE" if sk_risk > 20 else "OK", delta_color="inverse")

# --- TAB 2 : GDD ---
with tabs[1]:
    st.subheader("Suivi Régulateur (GDD)")
    if os.path.exists(STOCK_FILE):
        df_s = pd.read_csv(STOCK_FILE)
        cumul = df_s.loc[df_s["Produit"] == "GDD_CUMUL", "Stock_Reel"].values[0] if not df_s.empty else 0.0
        nouveau = round(cumul + max(0, temp - BASE_TEMP), 1)
        st.write(f"Cumul actuel : **{nouveau}** / {GDD_THRESHOLD}")
        st.progress(min(nouveau/GDD_THRESHOLD, 1.0))
        if st.button("💾 Enregistrer GDD & Risque"):
            df_s.loc[df_s["Produit"] == "GDD_CUMUL", "Stock_Reel"] = nouveau
            df_s.to_csv(STOCK_FILE, index=False)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            log_entry = pd.DataFrame([
                {"Date": now_str, "Produit": "GDD_TRACE", "Quantite": nouveau, "Type": "SYNC"},
                {"Date": now_str, "Produit": "SK_TRACE", "Quantite": sk_risk, "Type": "SYNC"}
            ])
            log_entry.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)
            st.success("Données synchronisées !")
            st.rerun()

# --- TAB 3 : PLANIFICATION ---
with tabs[2]:
    st.subheader("Planning Phyto 2026")
    if os.path.exists(PLANNING_FILE):
        try:
            xls = pd.ExcelFile(PLANNING_FILE)
            noms_feuilles = [s.replace('VERT', 'GREEN') for s in xls.sheet_names]
            choix = st.selectbox("Zone :", range(len(noms_feuilles)), format_func=lambda x: noms_feuilles[x])
            df_p = pd.read_excel(PLANNING_FILE, sheet_name=xls.sheet_names[choix], skiprows=3).dropna(how='all', axis=0)
            alertes = verifier_alertes_j3(df_p.copy())
            if alertes:
                for a in alertes: st.error(a)
            else: st.success("✅ RAS sous 3 jours")
            st.dataframe(df_p, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Erreur Excel : {e}")

# --- TAB 4 : HISTORIQUE & DIAGRAMMES (FIXED SYNTAX) ---
with tabs[3]:
    st.subheader("📈 Évolution & Archives")
    if os.path.exists(LOG_FILE):
        try:
            df_l = pd.read_csv(LOG_FILE)
            if not df_l.empty and 'Date' in df_l.columns:
                df_l['Date'] = pd.to_datetime(df_l['Date'], errors='coerce')
                df_l = df_l.dropna(subset=['Date'])
                df_l['Quantite'] = pd.to_numeric(df_l['Quantite'], errors='coerce')
                
                df_pivot = df_l.groupby(['Date', 'Produit'])['Quantite'].mean().unstack()
                
                col_g, col_s = st.columns(2)
                with col_g:
                    st.caption("Évolution GDD (Vert)")
                    if 'GDD_TRACE' in df_pivot.columns:
                        st.line_chart(df_pivot['GDD_TRACE'], color="#2e7d32")
                with col_s:
                    st.caption("Risque Dollar Spot % (Bleu)")
                    if 'SK_TRACE' in df_pivot.columns:
                        st.line_chart(df_pivot['SK_TRACE'], color="#0000FF")
                
                st.divider()
                st.write("📋 Archives des mesures")
                st.dataframe(df_l.sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Erreur d'analyse : {e}")
    else:
        st.info("L'historique est vide.")