import requests
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Pega a API key do ambiente
API_KEY = os.getenv("GEOAPIFY_API_KEY")

def get_coordinates(address, city=None):
    """
    Obtém coordenadas de latitude e longitude para um endereço usando Geoapify API.
    
    Args:
        address (str): O endereço a ser geocodificado no formato "RUA, NÚMERO, CIDADE"
        city (str, opcional): Nome da cidade para limitar a busca (se não estiver no endereço)
        
    Returns:
        dict: Dicionário contendo latitude e longitude, ou None se não encontrado
    """
    if not API_KEY:
        raise ValueError("API key da Geoapify não configurada. Configure a variável de ambiente GEOAPIFY_API_KEY.")
    
    # Processar o endereço no formato "RUA, NÚMERO, CIDADE"
    parts = [part.strip() for part in address.split(',')]
    
    if len(parts) >= 3:  # Temos todos os componentes
        street = parts[0].strip()
        housenumber = parts[1].strip()
        address_city = parts[2].strip()
        
        # Se a cidade também foi fornecida como parâmetro, priorizamos o que está no endereço
        if not city:
            city = address_city
    elif len(parts) == 2:  # Possivelmente falta a cidade
        street = parts[0].strip()
        housenumber = parts[1].strip()
        # Usamos a cidade fornecida como parâmetro
    else:  # Formato inválido, tentamos usar como texto livre
        street = address
    
    # URL para geocodificação estruturada
    base_url = "https://api.geoapify.com/v1/geocode/search"
    
    params = {
        "apiKey": API_KEY,
        "format": "json"
    }
    
    # Adicionar parâmetros de forma estruturada
    if street:
        params["street"] = street
    
    if 'housenumber' in locals() and housenumber:
        params["housenumber"] = housenumber
    
    if city:
        params["city"] = city
    
    # Adicionar país (opcional, mas melhora a precisão)
    params["country"] = "Brazil"
    
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        
        if results:
            # Pega o primeiro resultado
            first_result = results[0]
            return {
                "lat": first_result.get("lat"),
                "lon": first_result.get("lon")
            }
    
    # Se a busca estruturada falhar, tente com texto completo como fallback
    if street and 'housenumber' in locals() and housenumber and city:
        fallback_text = f"{street} {housenumber}, {city}"
        params = {
            "text": fallback_text,
            "format": "json",
            "apiKey": API_KEY
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results:
                # Pega o primeiro resultado
                first_result = results[0]
                return {
                    "lat": first_result.get("lat"),
                    "lon": first_result.get("lon")
                }
    
    return None