# =================================================================
# Fichier: scraper_iphone.py (Contient la logique pure du scraping)
# =================================================================

import requests
from bs4 import BeautifulSoup
import re
import math
import random 
import time
from typing import List, Dict, Any, Tuple

# SÉLECTEUR DE PRODUIT CONFIRMÉ
PRODUCT_CONTAINER_SELECTOR: str = 'div.cadre_prod'

# URL de base du site
BASE_URL: str = "http://www.visiodirect-mobile.com"


# --- FONCTIONS UTILITAIRES ---

def clean_price(price_raw: str) -> float:
    """Nettoie une chaîne de prix pour la convertir en nombre flottant (float)."""
    if price_raw == "N/A": return 0.0
    # Suppression du point (séparateur de milliers) avant de remplacer la virgule par un point (séparateur décimal)
    cleaned_price = price_raw.lower().replace('€', '').replace('ttc', '').replace('.', '').replace(',', '.').strip()
    try: 
        return float(cleaned_price)
    except ValueError: 
        print(f"ATTENTION: Prix non convertible ('{price_price}')")
        return 0.0

def get_soup(url: str, max_retries: int = 3) -> BeautifulSoup | None:
    """Tente de récupérer et parser une URL avec gestion d'erreurs."""
    # Simuler un navigateur pour éviter le blocage
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)
            return BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            print(f"Erreur de requête pour {url} (Tentative {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 + random.uniform(0, 1)) # Attente aléatoire avant de réessayer
    return None

def scrape_model_page(model_name: str, url: str) -> List[Dict[str, Any]]:
    """Scrape tous les composants sur une page donnée et retourne les données brutes."""
    
    soup = get_soup(url)
    if soup is None:
        print(f"🛑 Échec du scraping de la page pour le modèle {model_name}.")
        return []

    data = []
    
    # Trouver tous les conteneurs de produits
    product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)
    
    for container in product_containers:
        # 1. Nom du composant et référence
        # Le nom est souvent dans un <a> ou un <h3>/<h4>, on prend le plus lisible
        name_tag = container.select_one('h3 a, h4 a, .nom_prod a')
        name_text = name_tag.text.strip() if name_tag else "N/A"
        
        # Référence (souvent difficile à extraire proprement)
        ref_match = re.search(r'\(Ref: (.*?)\)', name_text)
        reference = ref_match.group(1).strip() if ref_match else "N/A"
        
        # Nettoyer le nom du composant
        nom_composant = re.sub(r'\(Ref: .*?\)', '', name_text).strip()
        
        # 2. Prix
        price_tag = container.select_one('.prix_prod')
        price_raw = price_tag.text.strip() if price_tag else "N/A"
        
        # 3. Lien (URL absolue)
        link_tag = container.select_one('.nom_prod a')
        relative_link = link_tag.get('href') if link_tag else None
        
        full_link = BASE_URL + relative_link if relative_link and not relative_link.startswith(BASE_URL) else relative_link
        
        # Conversion du prix brut en float pour les calculs futurs
        price_float = clean_price(price_raw)
        
        # Assemblage des données brutes
        item = {
            'marque_modele': model_name,
            'nom_composant': nom_composant,
            'reference': reference,
            'price_raw': price_raw,      # Prix brut (pour l'historique)
            'price_float': price_float,  # Prix nettoyé (pour le calcul)
            'link': full_link if full_link else url
        }
        data.append(item)
        
    print(f"✅ Modèle '{model_name}': {len(data)} produits trouvés.")
    return data

def apply_repricing(data: List[Dict[str, Any]], marge_brute: float, frais_fixes_mo: float, tva_coefficient: float) -> List[Dict[str, Any]]:
    """Applique la logique de Repricing et formate les colonnes finales."""
    if not data:
        return []

    # 1. Conversion en DataFrame pour les calculs massifs
    import pandas as pd
    df = pd.DataFrame(data)

    # 2. Calculs de Repricing
    df['Prix Fournisseur HT'] = df['price_float'].round(2)
    df['Marge Brute HT'] = (df['Prix Fournisseur HT'] * marge_brute).round(2)
    df['Prix Intermédiaire + M.O. HT'] = (df['Marge Brute HT'] + frais_fixes_mo).round(2)
    
    # Arrondi au supérieur (ceiling) pour le prix Client TTC
    df['Prix Client TTC'] = (df['Prix Intermédiaire + M.O. HT'] * tva_coefficient).apply(math.ceil)
    
    # 3. Nettoyage et Renommage
    df = df.drop(columns=['price_float', 'price_raw'])
    df = df.rename(columns={'marque_modele': 'MODELE', 'nom_composant': 'NOM_COMPOSANT', 'link': 'URL_SOURCE'})
    
    # 4. Réorganisation des colonnes
    fieldnames = [
        'MODELE', 
        'NOM_COMPOSANT', 
        'reference', 
        'Prix Fournisseur HT', 
        'Marge Brute HT', 
        'Prix Intermédiaire + M.O. HT', 
        'Prix Client TTC', 
        'URL_SOURCE'
    ]
    df = df.reindex(columns=fieldnames)
    
    # 5. Conversion finale en liste de dictionnaires
    return df.to_dict('records')

