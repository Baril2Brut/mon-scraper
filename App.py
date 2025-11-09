# =================================================================
# Fichier: app.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread 
import pandas as pd 
import time
import random
from typing import List, Dict, Any, Tuple
# Assurez-vous que scraper_iphone.py est dans le même dossier !
from scraper_iphone import scrape_model_page, export_to_csv 

# --- CONFIGURATION GOOGLE SHEETS (CORRIGÉE) ---
# URL complète fournie par l'utilisateur
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84/edit" 
# Nom de l'onglet corrigé pour correspondre à votre capture d'écran ('Feuille 1')
SHEET_NAME = "Feuille 1" 

# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS ---

@st.cache_data(ttl=600) 
def load_model_urls_from_sheets():
    """Se connecte à Google Sheets via les secrets et charge la liste des URLs à scraper."""
    
    # Vérification initiale si le secret existe (pour éviter l'erreur initiale)
    if 'gcp_service_account' not in st.secrets:
        st.sidebar.error("❌ Secret 'gcp_service_account' manquant. Configuré ?")
        return None

    try:
        # 1. Connexion à Google Sheets
        gc = gspread.service_account_from_dict(st.secrets['gcp_service_account']) 
        
        # 2. Ouverture de la feuille de calcul
        sh = gc.open_by_url(SPREADSHEET_URL)
        
        # 3. Sélection de l'onglet
        # C'est ici que l'erreur 'Configuration_Liens_Scraper' était causée.
        worksheet = sh.worksheet(SHEET_NAME) 

        # 4. Lecture des données dans un DataFrame
        df = pd.DataFrame(worksheet.get_all_records())
        
        # 5. Vérification et extraction des colonnes
        COL_MODEL = 'Nom du Modèle' 
        COL_URL = 'URL de la Catégorie' 
        
        if COL_MODEL not in df.columns or COL_URL not in df.columns:
            st.error(f"❌ Colonnes '{COL_MODEL}' ou '{COL_URL}' introuvables dans la feuille '{SHEET_NAME}'.")
            return None
            
        # Extraction des paires (Nom du Modèle, URL de la Catégorie)
        model_urls_list = list(df[[COL_MODEL, COL_URL]].dropna().itertuples(index=False, name=None))
        
        st.sidebar.success(f"✅ Chargement réussi : **{len(model_urls_list)}** liens chargés depuis Sheets.")
        
        return model_urls_list

    except Exception as e:
        # Ceci peut être causé par : clé invalide (problème 4), feuille non partagée ou URL incorrecte
        st.sidebar.error(f"❌ Erreur connexion Sheets. Partage ou Clé invalide : {e}")
        return None

# --- INTERFACE STREAMLIT PRINCIPALE ---

st.set_page_config(page_title="Scraper Catalogue iPhone", layout="centered")
st.title(" Каталог iPhone Visiodirect")
st.caption("Synchronisation des liens via Google Sheets")

# --- MENU LATÉRAL : PARAMÈTRES DE CALCUL ---
with st.sidebar:
    st.header("⚙️ Ajuster les Paramètres")
    
    marge_brute = st.slider("Coefficient de Marge Brute", 1.0, 3.0, value=1.60, step=0.01)
    frais_mo = st.number_input("Frais Fixes de Main d'Œuvre (€)", 0.0, 100.0, value=20.0, step=1.0)
    tva_coeff = st.number_input("Coefficient de TVA (Ex: 1.20 pour 20%)", 1.0, 3.0, value=1.20, step=0.01)
    
    st.markdown("---")
    st.header("Statut de la Connexion")

if st.button("LANCER LE SCRAPING COMPLET", type="primary"):
    
    # 1. Tente de charger la liste des URLs (vérifie aussi la connexion Sheets)
    model_urls_to_scrape = load_model_urls_from_sheets()

    if not model_urls_to_scrape:
        st.error("🛑 Impossible de lancer : Aucun lien valide n'a pu être chargé depuis Google Sheets.")
    else:
        st.info(f"🚀 Démarrage du scraping de **{len(model_urls_to_scrape)}** modèles...")
        
        toutes_les_donnees: List[Dict[str, Any]] = []
        log_status = st.status('Scraping et traitement en cours...', expanded=True)
        
        # 2. Boucle et appelle la fonction de scraping
        for model_name, model_url in model_urls_to_scrape:
            # Délai entre les modèles
            time.sleep(random.uniform(2.0, 5.0)) 
            # Note: on passe le conteneur de statut pour afficher les logs dans la boucle
            scrape_model_page(model_name, model_url, toutes_les_donnees, log_status) 
        
        log_status.update(label="Traitement final des données...", state="running", expanded=True)
        
        # 3. Exportation et Repricing (utilise les paramètres du sidebar)
        csv_output = export_to_csv(
            toutes_les_donnees, 
            marge_brute, 
            frais_mo, 
            tva_coeff
        )
        
        if csv_output:
            log_status.success(f"🎉 Processus terminé ! **{len(toutes_les_donnees)}** composants extraits et calculés.")
            
            st.download_button(
                label=" Télécharger le CSV final",
                data=csv_output,
                file_name="resultats_catalogue_iphone.csv",
                mime="text/csv",
            )
            st.balloons()
        else:
            log_status.error("Erreur lors de la génération du fichier CSV.")
