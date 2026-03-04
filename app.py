import streamlit as st
import pandas as pd
import os
import math
import requests
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. CONFIGURATION ÉCRAN ---
st.set_page_config(page_title="Cabo Negro Expert v4.0", layout="wide", page_icon="⛳", initial_sidebar_state="collapsed")

# --- 2. PARAMÈTRES & FICHIERS ---
STOCK_FILE = "stocks_magasin.csv"
LOG_FILE = "historique_sorties_2026.csv"
PLANNING_FILE = "Programme de traitement Phyto 2026.xlsx"
CITY_LAT, CITY_LON = 35.78, -5.32
BASE_TEMP = 10.0

# --- 3. FONCTIONS TECHNIQUES ---

def get_weather():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={CITY_LAT}&longitude={CITY_LON}&current=temperature_2m,relative_humidity_2m&timezone=auto"
        res = requests.get(url).json()
        t, h = res['current']['temperature_2m'], res['current']['relative_humidity_2m']
        x = -9.99 + (0.177 * t) + (0.061 * h)
        risk = round((math.exp(x)/(1+math.exp(x)))*100, 1)
        return t, h, risk
    except: return 20.0, 70.0, 10.0

# --- FONCTION GÉNÉRATION PDF OFFICIEL ---
def generate_official_pdf(date, produit, quantite, nature, zone):
    pdf = FPDF()
    pdf.add_page()
    
    # En-tête
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "ROYAL GOLF CABO NEGRO", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, "Objet : PROCEDURE TRAITEMENT PHYTOSANITAIRE", ln=True, align='C')
    pdf.ln(10)
    
    # Contenu
    pdf.set_font("Arial", '', 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(200, 10, f"Date de l'application : {date}", ln=True, fill=True)
    pdf.cell(200, 10, f"Produit : {produit}", ln=True)
    pdf.cell(200, 10, f"Quantite a appliquer : {quantite}", ln=True, fill=True)
    pdf.cell(200, 10, f"Nature du traitement : {nature}", ln=True)
    pdf.cell(200, 10, f"Cible (Objet) : {zone}", ln=True, fill=True)
    
    pdf.ln(20)
    
    # Zone de Visas
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 10, "Visa Representant Prestataire", border=1, align='C')
    pdf.cell(10, 10, "", border=0) # Espace
    pdf.cell(85, 10, "Visa Representant Maitre d'Ouvrage", border=1, align='C', ln=True)
    
    pdf.cell(95, 30, "(ATELIER VERT)", border=1, align='C')
    pdf.cell(10, 30, "", border=0)
    pdf.cell(85, 30, "(ROYAL GOLF CABONEGRO)", border=1, align='C', ln=True)
    
    return pdf.output(dest='S')

# --- FONCTION MISE À JOUR STOCK ---
def update_stock_deduction(produit_nom, quantite_str):
    if os.path.exists(STOCK_FILE):
        df_stock = pd.read_csv(STOCK_FILE)
        # Extraire la valeur numérique de la quantité (ex: "2.5 L/ha" -> 2.5)
        try:
            valeur_num = float(''.join(c for c in quantite_str if c.isdigit() or c == '.'))
        except:
            valeur_num = 0.0
            
        if produit_nom in df_stock['Produit'].values:
            df_stock.loc[df_stock['Produit'] == produit_nom, 'Stock_Reel'] -= valeur_num
            df_stock.to_csv(STOCK_FILE, index=False)
            return True
    return False

# --- 4. LOGIQUE PRINCIPALE ---
st.title("⛳ Cabo Negro Expert v4.0")
temp, hum, sk_risk = get_weather()

tabs = st.tabs(["📊 Dashboard", "🌱 GDD", "💊 Planification Phyto", "📜 Historique & Stocks"])

# --- TAB 1 & 2 (Dashboard & GDD) : Identiques ---
with tabs[0]:
    c1, c2, c3 = st.columns(3)
    c1.metric("Temp.", f"{temp}°C")
    c2.metric("Hum.", f"{hum}%")
    c3.metric("Risque Dollar Spot", f"{sk_risk}%")

with tabs[1]:
    st.subheader("Régulateur de Croissance")
    # ... (Garder votre code GDD ici)

# --- TAB 3 : PLANIFICATION & FORMULAIRE OFFICIEL ---
with tabs[2]:
    st.header("Gestion des Interventions")
    if os.path.exists(PLANNING_FILE):
        xls = pd.ExcelFile(PLANNING_FILE)
        sheets = [s.replace('VERT', 'GREEN') for s in xls.sheet_names]
        choix = st.selectbox("Zone de travail :", range(len(sheets)), format_func=lambda x: sheets[x])
        real_s = xls.sheet_names[choix]
        df_p = pd.read_excel(PLANNING_FILE, sheet_name=real_s, skiprows=3).dropna(how='all', axis=0)
        
        # Détection Alertes J-3
        auj = datetime.now()
        limite = auj + timedelta(days=3)
        col_date = next((c for c in df_p.columns if any(k in c.lower() for k in ["date", "période"])), None)
        
        if col_date:
            df_p[col_date] = pd.to_datetime(df_p[col_date], errors='coerce')
            interventions_proches = df_p[(df_p[col_date] >= auj) & (df_p[col_date] <= limite)]
            
            if not interventions_proches.empty:
                st.error(f"🚨 {len(interventions_proches)} Traitement(s) à préparer !")
                for idx, row in interventions_proches.iterrows():
                    with st.expander(f"📋 ACTION : {row['Produit']} - {row[col_date].strftime('%d/%m')}"):
                        st.write(f"**Quantité:** {row['Quantité à appliquer']}")
                        st.write(f"**Action:** {row['Action']}")
                        
                        # BOUTON PDF
                        pdf_bytes = generate_official_pdf(
                            row[col_date].strftime('%d/%m/%Y'),
                            row['Produit'],
                            row['Quantité à appliquer'],
                            row['Action'],
                            sheets[choix]
                        )
                        st.download_button(
                            label="📥 Générer Formulaire PDF Officiel",
                            data=pdf_bytes,
                            file_name=f"Procedure_Phyto_{sheets[choix]}_{idx}.pdf",
                            mime="application/pdf"
                        )
                        
                        # BOUTON VALIDATION & STOCK
                        if st.button(f"✅ Valider Traitement & Déduire Stock ({idx})"):
                            if update_stock_deduction(row['Produit'], str(row['Quantité à appliquer'])):
                                st.success(f"Stock mis à jour pour {row['Produit']}")
                                # Log de validation
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                                log_entry = pd.DataFrame([{"Date": now_str, "Produit": row['Produit'], "Quantite": row['Quantité à appliquer'], "Type": "SORTIE_VALIDEE"}])
                                log_entry.to_csv(LOG_FILE, mode='a', header=False, index=False)
                            else:
                                st.warning("Produit non trouvé en stock ou fichier manquant.")

        st.divider()
        st.dataframe(df_p, use_container_width=True)

# --- TAB 4 : HISTORIQUE & STOCKS ---
with tabs[3]:
    st.subheader("📦 État des Stocks Magasin")
    if os.path.exists(STOCK_FILE):
        df_st = pd.read_csv(STOCK_FILE)
        st.table(df_st)
    
    st.subheader("📈 Historique des Sorties Validées")
    if os.path.exists(LOG_FILE):
        df_log = pd.read_csv(LOG_FILE)
        st.dataframe(df_log.sort_values(by=df_log.columns[0], ascending=False), use_container_width=True)
