# =================================================================
# Fichier: App.py (Interface Streamlit et Connexion Sheets)
# =================================================================
import streamlit as st
import gspread 
import gspread_dataframe as gd 
import pandas as pd 
import time
import random
import json # <--- NOUVEL IMPORTATION NÉCESSAIRE POUR DÉCODER LE JSON DU SECRET
from typing import List, Dict, Any, Tuple
# Le fichier scraper_iphone.py doit être dans le même dossier !
from scraper_iphone import scrape_model_page, export_to_csv 

# --- CONFIGURATION GOOGLE SHEETS ---

# ID de votre feuille de calcul (extrait de l'URL)
SPREADSHEET_ID = "1RQCsS2G_N-KQ-TzuEdY7f3X_7shXhm7w2AjPwaESe84" 
# Nom de l'onglet (IMPORTANT : sensible à la casse)
SHEET_NAME = "Configuration_Liens_Scraper" # J'utilise le nom que l'application recherche

# Noms de colonnes cibles
COL_MODEL = 'MODELE'
COL_URL = 'URL'


# --- FONCTION DE LECTURE DES LIENS DEPUIS SHEETS (AVEC gspread-dataframe) ---

@st.cache_data(ttl=600, show_spinner="Chargement et vérification des liens depuis Google Sheets...") 
def load_model_urls_from_sheets():
    """
    Se connecte à Google Sheets et charge la liste des URLs à scraper.
    """
    
    if 'gcp_service_account' not in st.secrets:
        print("DEBUG: Secret 'gcp_service_account' manquant.")
        st.sidebar.error("❌ Secret 'gcp_service_account' manquant. L'application ne peut pas se connecter.")
        return None

    try:
        # --- CORRECTION CRITIQUE DE LA CONNEXION ---
        secret_content = st.secrets['gcp_service_account']
        
        # Votre secret est lu comme une chaîne (str), nous devons le convertir en dictionnaire (dict)
        if isinstance(secret_content, str):
            # Tente de décoder la chaîne JSON
            service_account_info = json.loads(secret_content)
        elif isinstance(secret_content, dict):
            # Cas idéal : le secret est déjà un dict
            service_account_info = secret_content
        else:
            raise TypeError("Secret 'gcp_service_account' n'est ni une chaîne JSON ni un dictionnaire.")
            
        # 1. Connexion et Ouverture de la feuille
        gc = gspread.service_account_from_dict(service_account_info)
        # ----------------------------------------
        
        print("DEBUG: Connexion à Google Sheets réussie.")
        
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME) 
        print(f"DEBUG: Feuille '{SHEET_NAME}' ouverte.")

        # 2. Lecture des données dans un DataFrame
        df_raw = gd.get_as_dataframe(worksheet, header=1)
        
        # --- LOG DE DÉBOGAGE CRITIQUE ---
        print(f"DEBUG: Colonnes brutes lues par gspread-dataframe: {list(df_raw.columns)}")
        # --- FIN LOG DE DÉBOGAGE CRITIQUE ---

        # 3. Nettoyage des noms de colonnes du DataFrame pour la recherche
        found_model_col, found_url_col = None, None
        
        for col in df_raw.columns:
            # Nettoyage des noms de colonnes
            cleaned_col = str(col).strip().upper().replace(' ', '_').replace('-', '_').replace('É', 'E').replace('È', 'E')
            if 'MODEL' in cleaned_col or 'MODELE' in cleaned_col:
                found_model_col = col
            if 'URL' in cleaned_col or 'LINK' in cleaned_col:
                found_url_col = col

        if not found_model_col or not found_url_col:
            st.error(f"❌ Colonnes '{COL_MODEL}' ou '{COL_URL}' introuvables.")
            st.warning(f"Le script a trouvé les colonnes : {list(df_raw.columns)}. Vérifiez que 'MODELE' et 'URL' sont présents.")
            return None
            
        # Créer un DataFrame propre avec les deux colonnes trouvées
        df = df_raw[[found_model_col, found_url_col]].copy()
        df.columns = [COL_MODEL, COL_URL] # Renommer pour un accès facile
        
        # Supprimer les lignes entièrement vides (celles où les deux colonnes sont NaN)
        df.dropna(how='all', inplace=True) 
        
        # 4. Extraction et validation des URLs
        model_urls_list = []
        for index, row in df.iterrows():
            model_name = str(row[COL_MODEL]).strip()
            url = str(row[COL_URL]).strip()
            
            # La validation des liens doit être stricte
            if model_name and url.lower().startswith("http"):
                model_urls_list.append((model_name, url))

        
        if not model_urls_list:
            # Cette erreur se déclenche si toutes les lignes sont invalides ou si le tableau est vide
            print("DEBUG: La liste model_urls_list est vide après traitement.")
            st.error("🛑 Impossible de lancer : La liste de liens chargée est vide. Vérifiez la feuille (Contenu ou URL).")
            return None
            
        st.sidebar.success(f"✅ Chargement réussi : **{len(model_urls_list)}** liens chargés depuis Sheets.")
        
        return model_urls_list

    except Exception as e:
        # Affichage générique pour les erreurs de connexion/permission
        st.sidebar.error(f"❌ Échec de la connexion Sheets. Vérifiez les permissions de partage (compte de service) et le Secret TOML. Erreur : {e}")
        # Affichage de l'erreur dans la console pour un diagnostic précis
        print(f"\n--- ERREUR CRITIQUE DANS load_model_urls_from_sheets ---\n{e}\n----------------------------------------------------")
        return None

# --- INTERFACE STREAMLIT PRINCIPALE ---

st.set_page_config(page_title="Scraper Catalogue iPhone", layout="centered")
st.title("Catalogue iPhone Visiodirect")
st.caption("Synchronisation des liens via Google Sheets")

# --- MENU LATÉRAL : PARAMÈTRES DE CALCUL ---
with st.sidebar:
    st.header("⚙️ Ajuster les Paramètres")
    
    marge_brute = st.slider("Coefficient de Marge Brute", 1.0, 3.0, value=1.60, step=0.01)
    frais_mo = st.number_input("Frais Fixes de Main d'Oeuvre (€)", 0.0, 100.0, value=20.0, step=1.0)
    tva_coeff = st.number_input("Coefficient de TVA (Ex: 1.20 pour 20%)", 1.0, 3.0, value=1.20, step=0.01)
    
    st.markdown("---")
    st.header("Statut de la Connexion")
    # Lance la vérification de la connexion dès le chargement de l'interface
    model_urls_on_load = load_model_urls_from_sheets()

if st.button("LANCER LE SCRAPING COMPLET", type="primary"):
    
    model_urls_to_scrape = model_urls_on_load 

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
            scrape_model_page(model_name, model_url, toutes_les_donnees, log_status) 
        
        log_status.update(label="Traitement final des données...", state="running", expanded=True)
        
        # 3. Exportation et Repricing (utilise les paramètres du sidebar)
        # CORRECTION DE L'APPEL : on passe les variables ajustables en paramètres
        csv_output = export_to_csv(
            toutes_les_donnees, 
            marge_brute, # On passe la valeur du slider
            frais_mo,    # On passe la valeur du number_input
            tva_coeff    # On passe la valeur du number_input
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
            log_status.error("Erreur lors de la génération du fichier CSV (aucune donnée trouvée).")
