import requests
from bs4 import BeautifulSoup
import re
import csv
import time
import math 
import random 
from typing import List, Dict, Any, Tuple
import io # <--- ESSENTIEL : Import pour la création du CSV en mémoire
import streamlit as st 

# --- CONFIGURATION PRINCIPALE ---
# Format: (Nom Lisible du Modèle, URL Complète de sa page Visiodirect)
MODEL_URLS: List[Tuple[str, str]] = [
    # iPhone 15 Series
    ("iPhone 15 Pro Max", "http://www.visiodirect-mobile.com/iphone-15-pro-max-ssf1301-fss2-fcss4.html"),
    ("iPhone 15 Pro", "http://www.visiodirect-mobile.com/iphone-15-pro-ssf1300-fss2-fcss4.html"),
    ("iPhone 15 Plus", "http://www.visiodirect-mobile.com/iphone-15-plus-ssf1299-fss2-fcss4.html"),
    ("iPhone 15", "http://www.visiodirect-mobile.com/iphone-15-ssf1298-fss2-fcss4.html"),
    # iPhone 14 Series
    ("iPhone 14 Pro Max", "http://www.visiodirect-mobile.com/iphone-14-pro-max-ssf1297-fss2-fcss4.html"),
    ("iPhone 14 Pro", "http://www.visiodirect-mobile.com/iphone-14-pro-ssf1296-fss2-fcss4.html"),
    ("iPhone 14 Plus", "http://www.visiodirect-mobile.com/iphone-14-plus-ssf1086-fss2-fcss4.html"),
    ("iPhone 14", "http://www.visiodirect-mobile.com/iphone-14-ssf1085-fss2-fcss4.html"),
    # iPhone 13 Series
    ("iPhone 13 Pro Max", "http://www.visiodirect-mobile.com/iphone-13-pro-max-ssf1295-fss2-fcss4.html"),
    ("iPhone 13 Pro", "http://www.visiodirect-mobile.com/iphone-13-pro-ssf1294-fss2-fcss4.html"),
    ("iPhone 13 mini", "http://www.visiodirect-mobile.com/iphone-13-mini-ssf1052-fss2-fcss4.html"),
    ("iPhone 13", "http://www.visiodirect-mobile.com/iphone-13-ssf1051-fss2-fcss4.html"),
    # iPhone 12 Series
    ("iPhone 12 Pro Max", "http://www.visiodirect-mobile.com/iphone-12-pro-max-ssf981-fss2-fcss4.html"),
    ("iPhone 12 (6.1)", "http://www.visiodirect-mobile.com/iphone-12-taille-61-ssf980-fss2-fcss4.html"),
    ("iPhone 12 mini", "http://www.visiodirect-mobile.com/iphone-12-mini-ssf979-fss2-fcss4.html"),
    # iPhone 11 Series
    ("iPhone 11 Pro Max", "http://www.visiodirect-mobile.com/iphone-11-pro-max-ssf867-fss2-fcss4.html"),
    ("iPhone 11 Pro", "http://www.visiodirect-mobile.com/iphone-11-pro-ssf866-fss2-fcss4.html"),
    ("iPhone 11", "http://www.visiodirect-mobile.com/iphone-11-ssf863-fss2-fcss4.html"),
    # Anciens Modèles
    ("iPhone XS Max", "http://www.visiodirect-mobile.com/iphone-xs-max-ssf691-fss2-fcss4.html"),
    ("iPhone XR", "http://www.visiodirect-mobile.com/iphone-xr-ssf690-fss2-fcss4.html"),
    ("iPhone XS", "http://www.visiodirect-mobile.com/iphone-xs-ssf689-fss2-fcss4.html"),
    ("iPhone X", "http://www.visiodirect-mobile.com/iphone-x-ssf387-fss2-fcss4.html"),
    ("iPhone 8 Plus", "http://www.visiodirect-mobile.com/iphone-8-plus-ssf386-fss2-fcss4.html"),
    ("iPhone 8", "http://www.visiodirect-mobile.com/iphone-8-ssf385-fss2-fcss4.html"),
    ("iPhone 7 Plus", "http://www.visiodirect-mobile.com/iphone-7-plus-ssf289-fss2-fcss4.html"),
    ("iPhone 7", "http://www.visiodirect-mobile.com/iphone-7-ssf288-fss2-fcss4.html"),
    ("iPhone 6S Plus", "http://www.visiodirect-mobile.com/iphone-6s-plus-ssf159-fss2-fcss4.html"),
    ("iPhone 6S", "http://www.visiodirect-mobile.com/iphone-6s-ssf158-fss2-fcss4.html"),
    ("iPhone 6 Plus", "http://www.visiodirect-mobile.com/iphone-6-plus-ssf141-fss2-fcss4.html"),
    ("iPhone 6", "http://www.visiodirect-mobile.com/iphone-6-ssf9-fss2-fcss4.html"),
    ("iPhone SE (2020)", "http://www.visiodirect-mobile.com/iphone-se-2020-ssf194-fss2-fcss4.html"),
    ("iPhone 5C", "http://www.visiodirect-mobile.com/iphone-5c-ssf8-fss2-fcss4.html"),
    ("iPhone SE", "http://www.visiodirect-mobile.com/iphone-5se-ssf724-fss2-fcss4.html"),
    ("iPhone 5S", "http://www.visiodirect-mobile.com/iphone-5s-ssf7-fss2-fcss4.html"),
    ("iPhone 5", "http://www.visiodirect-mobile.com/iphone-5-ssf6-fss2-fcss4.html"),
    ("iPhone 4S", "http://www.visiodirect-mobile.com/iphone-4s-ssf5-fss2-fcss4.html"),
    ("iPhone 4", "http://www.visiodirect-mobile.com/iphone-4-ssf4-fss2-fcss4.html"),
    ("iPhone 3GS", "http://www.visiodirect-mobile.com/iphone-3gs-ssf11-fss2-fcss4.html"),
    ("iPhone 3G", "http://www.visiodirect-mobile.com/iphone-3g-ssf10-fss2-fcss4.html"),
] 

# SÉLECTEUR DE PRODUIT CONFIRMÉ
PRODUCT_CONTAINER_SELECTOR: str = 'div.cadre_prod'

# URL de base du site
BASE_URL: str = "http://www.visiodirect-mobile.com"


# --- PARAMÈTRES DE REPRICING (Calculs) --- 
MARGE_BRUTE = 1.60       
FRAIS_FIXES_MO = 20.0     
TVA_COEFFICIENT = 1.20    


# --- FONCTIONS UTILITAIRES ---
# J'utilise st.cache_data pour que l'opération ne soit pas refaite à chaque fois
@st.cache_data 
def clean_price(price_raw: str) -> float:
    """Nettoie une chaîne de prix pour la convertir en nombre flottant (float)."""
    if price_raw == "N/A": return 0.0
    cleaned_price = price_raw.lower().replace('€', '').replace('ttc', '').replace('.', '').replace(',', '.').strip()
    try: return float(cleaned_price)
    except ValueError: return 0.0

# @st.cache_resource # Utile pour les connexions, mais non nécessaire ici
def get_soup(url: str, max_retries: int = 3, log_func=st.warning) -> BeautifulSoup | None:
    """Télécharge l'URL et retourne l'objet Beautiful Soup, avec des tentatives en cas d'échec."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() 
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            # Utilise le log Streamlit fourni (st.warning)
            log_func(f"    [TENTATIVE {attempt + 1}/{max_retries}] Échec de la requête. Erreur: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    return None

# --- FONCTION PRINCIPALE DE SCRAPING DES COMPOSANTS (MODIFIÉE) ---

# J'ai retiré le placeholder de la fonction pour éviter le conflit
def scrape_model_page_streamlit(model_name: str, model_url: str, log_func) -> List[Dict[str, Any]]:
    """Visite la page du modèle et extrait tous les composants (produits) pour l'interface Streamlit."""
    
    log_func(f"**🔎 Démarrage du scraping des composants pour {model_name}...**")
    
    all_products_for_model: List[Dict[str, Any]] = []
    current_page = 1
    total_pages = 1 
    
    while current_page <= total_pages:
        url = model_url.replace(".html", f"-p{current_page}.html") if current_page > 1 else model_url
        log_func(f"  -> Page {current_page}/{total_pages} : {url}")
        
        # Le log_func (log_status.warning) est passé ici
        soup = get_soup(url, log_func=log_func) 
        if not soup: break
            
        products_on_page = []
        product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)

        if not product_containers and current_page == 1:
            log_func(f"  [AVERTISSEMENT] Aucun composant trouvé pour {model_name} (Page 1).")
            break 
        
        # Extraction des données
        for container in product_containers:
            try:
                name_tag = container.select_one('h3') or container.select_one('h4')
                name = name_tag.text.strip() if name_tag else "N/A"
                
                link_tag = container.find('a', href=True)
                link = BASE_URL + link_tag['href'] if link_tag and link_tag['href'].startswith('/') else link_tag['href'] if link_tag else "N/A"
                
                price_tag = container.select_one('.price_item') or container.select_one('.prix')
                price_raw = price_tag.text.strip() if price_tag else "N/A"
                price_float = clean_price(price_raw)
                
                reference = "N/A"
                ref_text_match = container.find(string=re.compile(r'Réf\. :'))
                if ref_text_match:
                    reference = ref_text_match.split(':', 1)[1].strip()

                products_on_page.append({
                    'marque_modele': model_name, 
                    'nom_composant': name,
                    'reference': reference,
                    'price_float': price_float, 
                    'price_raw': price_raw,     
                    'link': link
                })
            except Exception as e: 
                 log_func(f"    [ERREUR Extraction] Échec sur un produit de la page {current_page}: {e}")
                 continue

        # Gestion de la pagination 
        if current_page == 1:
            pagination_links = soup.select('div.pagination a')
            max_page = 1
            if pagination_links:
                for link in pagination_links:
                    href = link.get('href', '')
                    match = re.search(r'-p(\d+)\.html', href)
                    if match:
                         page_num = int(match.group(1))
                         if page_num > max_page: max_page = page_num
                total_pages = max_page
            
            if total_pages > 1:
                log_func(f"  [INFO] **{total_pages}** pages de composants trouvées pour ce modèle.")
                
        if not products_on_page and current_page > 1: break 
            
        all_products_for_model.extend(products_on_page)
        log_func(f"  [SUCCÈS] **{len(products_on_page)}** composants extraits (Total : {len(all_products_for_model)})")
        
        current_page += 1
        time.sleep(random.uniform(1.5, 3.5)) 
        
    return all_products_for_model

# --- EXPORTATION ET TRI ---

@st.cache_data
def process_and_get_csv_text(data: List[Dict[str, Any]]) -> str | None:
    # ... (fonction inchangée, utilise io.StringIO)
    if not data: return None

    # --- 1. CALCUL ET FORMATAGE DES PRIX ---
    for item in data:
        price_float = item['price_float']
        
        prix_marge = price_float * MARGE_BRUTE
        prix_intermediaire = prix_marge + FRAIS_FIXES_MO
        prix_final_ttc = math.ceil(prix_intermediaire * TVA_COEFFICIENT)
        
        item['Prix Fournisseur HT'] = f"{round(price_float, 2):.2f}".replace('.', ',') + " €"
        item['Marge Brute HT'] = f"{round(prix_marge, 2):.2f}".replace('.', ',') + " €"
        item['Prix Intermédiaire + M.O. HT'] = f"{round(prix_intermediaire, 2):.2f}".replace('.', ',') + " €"
        item['Prix Client TTC'] = f"{prix_final_ttc:.2f}".replace('.', ',') + " €" 
        
        del item['price_float']

    data.sort(key=lambda x: (str(x.get('marque_modele', '')).lower(), str(x.get('nom_composant', '')).lower()))

    # --- 2. CRÉATION DU CSV EN MÉMOIRE ---
    all_keys = set()
    for d in data: all_keys.update(d.keys())
    
    fieldnames = [
        'marque_modele', 
        'nom_composant', 
        'reference', 
        'Prix Fournisseur HT', 
        'Marge Brute HT',      
        'Prix Intermédiaire + M.O. HT', 
        'Prix Client TTC',     
        'price_raw', 
        'link'
    ]
    fieldnames += sorted([k for k in all_keys if k not in fieldnames])
    
    output = io.StringIO()
    # Utilisation du point-virgule (delimiter=';') pour l'export Excel français
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()


# --- INTERFACE ET EXECUTION PRINCIPALE STREAMLIT (MODIFIÉE) ---

def main():
    
    st.set_page_config(
        page_title="Scraper Catalogue iPhone", 
        layout="centered",
        initial_sidebar_state="expanded"
    )

    st.title("🤖 Catalogue iPhone Visiodirect")
    st.caption("Lancez le scraping pour extraire les données, appliquer le calcul de prix et obtenir le fichier CSV.")
    
    # Bouton de lancement
    if st.button("LANCER LE SCRAPING COMPLET", type="primary"):
        toutes_les_donnees: List[Dict[str, Any]] = []
        
        st.info("Démarrage du processus. Cela peut prendre plusieurs minutes (plus de 30 modèles).")
        
        # UTILISATION DU NOUVEAU st.status POUR UN LOG ROBUSTE
        with st.status('Scraping et traitement en cours...', expanded=True) as log_status:
            
            total_models = len(MODEL_URLS)
            
            # La barre de progression est maintenant dans la colonne de droite pour éviter les conflits d'affichage
            col1, col2 = st.columns([4, 1])
            progress_bar = col1.progress(0, text="Progression globale...")
            
            for index, (model_name, model_url) in enumerate(MODEL_URLS):
                
                # Mise à jour de la barre de progression
                progress_bar.progress((index + 1) / total_models, text=f"Modèle {index+1}/{total_models} : {model_name}")
                
                # Attente entre les modèles (conservé pour éthique)
                time.sleep(random.uniform(2.0, 5.0)) 
                
                # Le log_status.info/warning est passé à la fonction
                data_modele = scrape_model_page_streamlit(model_name, model_url, log_status.info)
                toutes_les_donnees.extend(data_modele)

            # Traitement final et obtention du texte CSV
            log_status.update(label="Traitement final des données...", state="running", expanded=True)
            csv_text = process_and_get_csv_text(toutes_les_donnees)
        
        # FIN DU BLOC st.status
        
        st.success(f"🎉 Processus terminé ! **{len(toutes_les_donnees)}** composants extraits.")
        
        if csv_text:
            st.download_button(
                label="📥 Télécharger le Fichier CSV",
                data=csv_text,
                file_name='resultats_catalogue_iphone.csv',
                mime='text/csv'
            )
            st.balloons()
        else:
            st.error("Aucune donnée n'a pu être extraite.")

if __name__ == "__main__":
    main()
