# =================================================================
# Fichier: App.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread 
import gspread_dataframe as gd 
import pandas as pd 
import time
import math # Nécessaire pour math.ceil
from typing import List, Dict, Any

# Importe la logique du scraper
from scraper_iphone import scrape_model_page, apply_repricing 

# --- CONFIGURATION GOOGLE SHEETS ---

# ID de votre feuille de calcul (extrait de l'URL)
SPREADSHEET_ID = "1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84" 
# Nom de l'onglet SOURCE pour les liens (Configuration_Liens_Scraper)
SHEET_NAME_CONFIG = "Configuration_Liens_Scraper" 
# Nom de l'onglet CIBLE pour les résultats (Resultats_Scraping_iPhone_Automatise)
SHEET_NAME_RESULTS = "Resultats_Scraping_iPhone_Automatise" 

# Noms de colonnes cibles dans l'onglet de configuration
COL_MODEL = 'MODELE'
COL_URL = 'URL'

# Délais de scraping (pour être plus doux avec le site)
SCRAPING_DELAY_SECONDS = 2.0


# --- FONCTIONS DE CONNEXION ET DE LECTURE ---

@st.cache_data(ttl=600, show_spinner="Chargement et vérification des liens depuis Google Sheets...") 
def load_model_urls_from_sheets():
    """
    Se connecte à Google Sheets et charge la liste des URLs à scraper.
    """
    try:
        # --- 1. Lecture directe depuis secrets ---
        if 'gcp_service_account' not in st.secrets:
            st.error("🛑 Configuration 'gcp_service_account' manquante dans secrets.toml ou interface Secrets.")
            return []

        creds_dict = dict(st.secrets['gcp_service_account'])
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # Ouvre la feuille de configuration
        ws = sh.worksheet(SHEET_NAME_CONFIG)
        
        # Récupère toutes les données (en tant que DataFrame pour le nettoyage)
        df = gd.get_as_dataframe(ws).dropna(subset=[COL_MODEL, COL_URL]).reset_index(drop=True)
        
        # Vérification des colonnes nécessaires
        if COL_MODEL not in df.columns or COL_URL not in df.columns:
            st.error(f"Colonnes '{COL_MODEL}' ou '{COL_URL}' manquantes dans l'onglet '{SHEET_NAME_CONFIG}'.")
            return []
            
        # Transforme le DataFrame en liste de tuples (modèle, URL)
        urls_to_scrape = list(zip(df[COL_MODEL], df[COL_URL]))
        
        print(f"DEBUG: {len(urls_to_scrape)} liens chargés depuis Sheets.")
        return urls_to_scrape

    except Exception as e:
        # L'erreur Base64 se manifeste souvent ici
        st.error(f"🛑 Échec de la connexion à Google Sheets. Vérifiez la clé secrète et les autorisations. Erreur : {e}")
        return []


# --- FONCTION D'ÉCRITURE DES RÉSULTATS DANS SHEETS ---

def save_results_to_sheets(
    data: List[Dict[str, Any]], 
    marge_brute: float, 
    frais_fixes_mo: float, 
    tva_coefficient: float
) -> bool:
    """
    Effectue le Repricing, formate les données, et écrit le résultat dans l'onglet Google Sheets cible.
    """
    if not data:
        st.warning("Aucune donnée à enregistrer.")
        return False
        
    # --- 1. Repricing et Formatage ---
    # La fonction apply_repricing est maintenant dans scraper_iphone.py
    processed_data = apply_repricing(data, marge_brute, frais_fixes_mo, tva_coefficient)
    if not processed_data:
        st.warning("Aucune donnée formatée après Repricing.")
        return False
        
    df = pd.DataFrame(processed_data)

    # --- 2. Écriture dans Google Sheets ---
    try:
        creds_dict = dict(st.secrets['gcp_service_account'])
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # Ouvre la feuille cible (ou la crée si elle n'existe pas)
        try:
            ws = sh.worksheet(SHEET_NAME_RESULTS)
        except gspread.exceptions.WorksheetNotFound:
            # Crée l'onglet si non trouvé
            ws = sh.add_worksheet(title=SHEET_NAME_RESULTS, rows="1000", cols="20")
            
        # Écrit le DataFrame dans la feuille de calcul (remplace le contenu existant)
        gd.set_with_dataframe(ws, df)
        print(f"DEBUG: Écriture des {len(df)} lignes réussie dans '{SHEET_NAME_RESULTS}'.")
        return True

    except Exception as e:
        st.error(f"🛑 Échec de l'enregistrement dans Google Sheets : {e}")
        print(f"ERROR: Failed to save to Sheets: {e}")
        return False


# --- INTERFACE STREAMLIT PRINCIPALE ---

st.set_page_config(page_title="Scraper Automatique & Repricing", layout="wide")

# Interface par défaut (affichage de l'erreur si la clé manque)
if 'gcp_service_account' not in st.secrets:
    st.title("🤖 Scraper de Catalogue Pièces Détachées (Configuration requise)")
    st.error("Veuillez configurer votre clé de service Google dans l'interface Secrets de Streamlit Cloud.")
    st.markdown("### ⚠️ Clé de service manquante. L'application ne peut pas se connecter à Google Sheets.")
    st.stop()
    
# Si la clé est présente, afficher l'interface principale
st.title("⚙️ Outil d'Automatisation de Repricing")
st.markdown("Scraping en direct de **Visiodirect-Mobile** et écriture automatique dans Google Sheets.")

# --- BARRE LATÉRALE DE PARAMÈTRES ---
with st.sidebar:
    st.header("Paramètres de Repricing")
    st.info("Ces valeurs sont utilisées pour calculer le **Prix Client TTC**.")

    # 1. Marge brute HT (coefficient)
    marge_brute = st.number_input(
        "Coefficient de Marge Brute (Ex: 1.6 pour +60%)",
        min_value=1.0,
        value=1.6,
        step=0.05,
        format="%.2f",
        key="marge_brute_input"
    )

    # 2. Frais fixes de Main d'Œuvre (montant)
    frais_mo = st.number_input(
        "Frais Fixes / Main d'Œuvre HT (€)",
        min_value=0.0,
        value=20.0,
        step=5.0,
        format="%.2f",
        key="frais_mo_input"
    )
    
    # 3. TVA (coefficient)
    tva_coeff = st.number_input(
        "Coefficient de TVA (Ex: 1.2 pour 20%)",
        min_value=1.0,
        value=1.2,
        step=0.01,
        format="%.2f",
        key="tva_coeff_input"
    )

# --- EXECUTION ---

if st.button("🚀 LANCER LE SCRAPING & L'ENREGISTREMENT"):
    
    # 1. Chargement des liens
    urls_to_scrape = load_model_urls_from_sheets()

    if not urls_to_scrape:
        st.error("Le scraping ne peut pas démarrer sans une liste de liens valide.")
        st.stop()
        
    log_status = st.empty()
    log_status.info(f"Démarrage du scraping de **{len(urls_to_scrape)}** modèles...")

    toutes_les_donnees: List[Dict[str, Any]] = []
    
    # 2. Scraping par modèle
    for i, (model_name, url) in enumerate(urls_to_scrape):
        log_status.progress((i + 1) / len(urls_to_scrape), text=f"Scraping en cours... Modèle **{model_name}** ({i + 1}/{len(urls_to_scrape)})")
        
        # Scrape la page et récupère la liste de produits
        products = scrape_model_page(model_name, url)
        toutes_les_donnees.extend(products)
        
        # Pause pour respecter le délai
        if i < len(urls_to_scrape) - 1:
            time.sleep(SCRAPING_DELAY_SECONDS)

    # 3. Enregistrement des résultats dans Google Sheets
    log_status.info(f"✅ Scraping terminé. {len(toutes_les_donnees)} produits bruts collectés. Enregistrement en cours...")

    # Utilisation de la nouvelle fonction save_results_to_sheets
    if save_results_to_sheets(toutes_les_donnees, marge_brute, frais_mo, tva_coeff):
        
        # 4. Affichage du lien final et du succès
        # On pourrait ajouter un bouton pour ouvrir directement la feuille de résultats
        st.balloons()
        log_status.success(f"🎉 Processus terminé ! **{len(toutes_les_donnees)}** composants enregistrés dans l'onglet **'{SHEET_NAME_RESULTS}'** de Google Sheets.")
        
        # Lien vers la feuille
        sheet_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid=" # L'URL ouvre l'ID principal
        st.markdown(f"**[Cliquez ici pour voir les résultats dans Google Sheets]({sheet_url})**")
        
        # Affichage d'un aperçu
        if toutes_les_donnees:
            st.subheader("Aperçu des Données Enregistrées")
            # Le DataFrame est créé et formaté dans save_results_to_sheets.
            # On le recrée ici pour l'affichage uniquement (moins coûteux que l'appel Sheets)
            df_preview = pd.DataFrame(apply_repricing(toutes_les_donnees, marge_brute, frais_mo, tva_coeff))
            st.dataframe(df_preview, use_container_width=True)
            
    else:
        # L'erreur est déjà affichée par la fonction save_results_to_sheets
        log_status.error("❌ Échec de l'enregistrement final dans Google Sheets.")

