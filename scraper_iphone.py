# =================================================================
# Fichier: scraper_iphone.py (Contient la logique pure du scraping)
# =================================================================

import requests
from bs4 import BeautifulSoup
import re
import csv
import time
import math 
import random 
from typing import List, Dict, Any, Tuple
import io # Ajout pour l'export CSV en mémoire

# SÉLECTEUR DE PRODUIT CONFIRMÉ
PRODUCT_CONTAINER_SELECTOR: str = 'div.cadre_prod'

# URL de base du site
BASE_URL: str = "http://www.visiodirect-mobile.com"


# --- PARAMÈTRES DE REPRICING (Valeurs par défaut) --- 
# Ces valeurs sont conservées comme défauts mais seront écrasées par App.py
MARGE_BRUTE_DEFAULT = 1.60       # Multiplicateur pour une marge de 60%
FRAIS_FIXES_MO_DEFAULT = 20.0     # Frais de main d'œuvre fixes de 20.0 €
TVA_COEFFICIENT_DEFAULT = 1.20    # Multiplicateur pour une TVA de 20%


# --- FONCTIONS UTILITAIRES ---

def clean_price(price_raw: str) -> float:
    """Nettoie une chaîne de prix pour la convertir en nombre flottant (float)."""
    if price_raw == "N/A": return 0.0
    # Suppression du point (séparateur de milliers) avant de remplacer la virgule par un point (séparateur décimal)
    cleaned_price = price_raw.lower().replace('€', '').replace('ttc', '').replace('.', '').replace(',', '.').strip()
    try: return float(cleaned_price)
    except ValueError: return 0.0

def get_soup(url: str, max_retries: int = 3) -> BeautifulSoup | None:
    """Télécharge l'URL et retourne l'objet Beautiful Soup, avec des tentatives en cas d'échec."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() 
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            # Affiche l'erreur pour le débogage et réessaye si possible
            print(f"    [TENTATIVE {attempt + 1}/{max_retries}] Échec de la requête pour {url}. Erreur: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue # Passe à la tentative suivante
            # Si toutes les tentatives ont échoué, sort de la boucle
    return None

# --- FONCTION PRINCIPALE DE SCRAPING DES COMPOSANTS ---

def scrape_model_page(model_name: str, model_url: str, all_products: List[Dict[str, Any]], st_container: Any):
    """Visite la page du modèle et extrait tous les composants (produits)."""
    st_container.info(f"🔎 Démarrage du scraping des composants pour **{model_name}**")
    print(f"\n🔎 Démarrage du scraping des composants pour **{model_name}**") # Reste pour le log Streamlit Cloud
    
    current_page = 1
    total_pages = 1 
    
    products_count = 0

    while current_page <= total_pages:
        # Construction de l'URL pour la pagination
        url = model_url.replace(".html", f"-p{current_page}.html") if current_page > 1 else model_url
        st_container.text(f"  -> Page {current_page}/{total_pages} : {url}")
        
        soup = get_soup(url)
        if not soup: break
            
        products_on_page = []
        product_containers = soup.select(PRODUCT_CONTAINER_SELECTOR)

        if not product_containers and current_page == 1:
            st_container.warning(f"  [AVERTISSEMENT] Aucun composant trouvé pour {model_name} (Page 1).")
            break 
        
        # Extraction des données
        for container in product_containers:
            try:
                name_tag = container.select_one('h3') or container.select_one('h4')
                name = name_tag.text.strip() if name_tag else "N/A"
                
                link_tag = container.find('a', href=True)
                # Correction pour gérer les liens relatifs/absolus
                link = BASE_URL + link_tag['href'] if link_tag and link_tag['href'].startswith('/') else link_tag['href'] if link_tag else "N/A"
                
                price_tag = container.select_one('.price_item') or container.select_one('.prix')
                price_raw = price_tag.text.strip() if price_tag else "N/A"
                price_float = clean_price(price_raw)
                
                reference = "N/A"
                # Le motif de référence est souvent dans un noeud texte sans balise spécifique.
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
                 st_container.error(f"    [ERREUR Extraction] Échec sur un produit de la page {current_page}: {e}")
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
                st_container.text(f"  [INFO] **{total_pages}** pages de composants trouvées pour ce modèle.")
                
        if not products_on_page and current_page > 1: break # Arrête si une page non-première est vide
            
        all_products.extend(products_on_page)
        products_count += len(products_on_page)
        st_container.success(f"  [SUCCÈS] **{len(products_on_page)}** composants extraits (Total : {products_count})")
        
        current_page += 1
        # Délai aléatoire entre 1.5 et 3.5 secondes entre les pages
        time.sleep(random.uniform(1.5, 3.5)) 

# --- EXPORTATION ET TRI ---

def export_to_csv(data: List[Dict[str, Any]], 
                  marge_brute: float = MARGE_BRUTE_DEFAULT,      # <--- ACCEPTE LA MARGE BRUTE
                  frais_fixes_mo: float = FRAIS_FIXES_MO_DEFAULT, # <--- ACCEPTE LES FRAIS FIXES
                  tva_coefficient: float = TVA_COEFFICIENT_DEFAULT, # <--- ACCEPTE LE COEFFICIENT TVA
                  filename: str = "resultats_catalogue_iphone.csv"):
    """Effectue le Repricing, formate les prix en euros, trie les données, puis les écrit dans un fichier CSV."""
    if not data:
        print("\n[EXPORT] Aucune donnée à exporter.")
        return

    # --- 1. CALCUL ET FORMATAGE DES PRIX ---
    for item in data:
        price_float = item['price_float']
        
        # 1. Appliquer la marge brute (x1.60)
        prix_marge = price_float * marge_brute # <--- UTILISE LA VALEUR PASSÉE
        
        # 2. Ajouter les frais fixes de main d'œuvre (+ 20.0 €)
        prix_intermediaire = prix_marge + frais_fixes_mo # <--- UTILISE LA VALEUR PASSÉE
        
        # 3. Ajouter la TVA et arrondir au supérieur (math.ceil)
        prix_final_ttc = math.ceil(prix_intermediaire * tva_coefficient) # <--- UTILISE LA VALEUR PASSÉE
        
        # FORMATAGE EN CHAÎNE DE CARACTÈRES AVEC LE SYMBOLE € ET LA VIRGULE POUR LE DÉCIMAL
        
        # --- CORRECTION DE LA VIRGULE APPLIQUÉE ICI AVEC .replace('.', ',') ---
        item['Prix Fournisseur HT'] = f"{round(price_float, 2):.2f}".replace('.', ',') + " €"
        item['Marge Brute HT'] = f"{round(prix_marge, 2):.2f}".replace('.', ',') + " €"
        item['Prix Intermédiaire + M.O. HT'] = f"{round(prix_intermediaire, 2):.2f}".replace('.', ',') + " €"
        # Le prix TTC est arrondi au supérieur (entier), mais formaté avec deux décimales pour l'affichage (ex: 100,00 €)
        item['Prix Client TTC'] = f"{prix_final_ttc:.2f}".replace('.', ',') + " €" 
        
        # On retire la colonne temporaire
        del item['price_float']


    print("\n[TRI] Tri des données par nom de modèle et composant...")
    data.sort(key=lambda x: (str(x.get('marque_modele', '')).lower(), str(x.get('nom_composant', '')).lower()))

    all_keys = set()
    for d in data: all_keys.update(d.keys())
    
    # Ordre des colonnes ajusté pour la lisibilité
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
    # Ajoute les clés restantes
    fieldnames += sorted([k for k in all_keys if k not in fieldnames])
    
    print(f"\n[EXPORT] Écriture de **{len(data)}** lignes dans le fichier **'{filename}'**...")

    # Utilisation de 'utf-8-sig' et du point-virgule (delimiter=';') pour la compatibilité Excel/Sheets en français
    # Retourne le contenu en mémoire (BytesIO) pour Streamlit, au lieu de l'écrire sur disque.
    csv_buffer = io.StringIO()
    try:
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(data)
        csv_buffer.seek(0)
        return csv_buffer.getvalue()
    except Exception as e:
        print(f"[ERREUR EXPORT] Impossible d'écrire le fichier CSV : {e}")
        return None
