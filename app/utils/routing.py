import requests
import os
import json
from typing import List, Dict, Any, Tuple
import logging
import math
from datetime import datetime
import numpy as np
from sklearn.cluster import DBSCAN
from collections import defaultdict
import random
import streamlit as st
import time

# Get API key from environment variable or config
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")

def optimize_route(
    start_point: Dict[str, float],
    end_point: Dict[str, float],
    waypoints: List[Dict[str, Any]],
    max_duration_minutes: int = 45
) -> Dict[str, Any]:
    """
    Optimize a route using Geoapify Routing API.
    
    Args:
        start_point: Dict with lat and lon for start point
        end_point: Dict with lat and lon for end point
        waypoints: List of dicts with lat, lon, and person_id for each stop
        max_duration_minutes: Maximum duration of the route in minutes
        
    Returns:
        Dict with optimized route information
    """
    # This is a placeholder function that will be implemented in the future
    # with the actual Geoapify API integration
    
    # Placeholder result to show the structure we'll work with
    result = {
        "success": True,
        "message": "Route optimization not yet implemented",
        "total_distance_km": 0,
        "total_duration_minutes": 0,
        "stops": [
            {
                "stop_order": 0,
                "coordinates": start_point,
                "address": "Start point",
                "persons": [],
                "arrival_time": None
            }
        ],
        "path": []  # List of coordinate pairs for drawing the route
    }
    
    return result

def geocode_address(address: str) -> Dict[str, float]:
    """
    Convert address to coordinates using Geoapify Geocoding API.
    
    Args:
        address: Full address string
        
    Returns:
        Dict with lat and lon if successful, empty dict otherwise
    """
    if not GEOAPIFY_API_KEY:
        logging.warning("GEOAPIFY_API_KEY not set")
        return {}

    url = "https://api.geoapify.com/v1/geocode/search"
    
    params = {
        "text": address,
        "format": "json",
        "apiKey": GEOAPIFY_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["results"] and len(data["results"]) > 0:
            result = data["results"][0]
            return {"lat": result["lat"], "lon": result["lon"]}
    except Exception as e:
        logging.error(f"Error geocoding address: {e}")
    
    return {}

def calculate_route_duration(
    start: Dict[str, float], 
    end: Dict[str, float], 
    waypoints: List[Dict[str, float]] = None
) -> float:
    """
    Calculate the estimated duration of a route in minutes.
    
    Args:
        start: Dict with lat and lon for start point
        end: Dict with lat and lon for end point
        waypoints: Optional list of dicts with lat and lon for waypoints
        
    Returns:
        Estimated duration in minutes
    """
    # This function will be implemented in the future with Geoapify API
    return 0


def optimize_route(start_point, end_point, waypoints, max_duration_minutes=45, vehicle_type="car"):
    """
    Calcula uma rota otimizada utilizando a Geoapify Routing API.
    
    Parâmetros:
      - start_point (dict): Dicionário com as chaves 'lat' e 'lon' representando o ponto de partida.
      - end_point (dict): Dicionário com as chaves 'lat' e 'lon' representando o ponto de chegada.
      - waypoints (list): Lista de dicionários com 'lat' e 'lon' para paradas intermediárias.
      - max_duration_minutes (int): Tempo máximo da rota em minutos.
      - vehicle_type (str): Tipo de veículo para determinar o modo de viagem.
    
    Retorna:
      - dict: Resposta JSON da API com os detalhes da rota.
    """
    API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
    if not API_KEY:
        raise Exception("A variável de ambiente GEOAPIFY_API_KEY não está definida.")

    # Mapeia tipos de veículos para modos de viagem da API
    vehicle_to_mode = {
        "car": "drive",
        "bus": "drive",  # Alterado para 'drive' pois a API não tem modo 'bus'
        "van": "drive",
        "truck": "truck",
        "motorcycle": "motorcycle",
        # Adicione mais mapeamentos conforme necessário
    }
    
    # Define o modo de viagem com base no tipo de veículo (use 'drive' como padrão)
    travel_mode = vehicle_to_mode.get(vehicle_type.lower(), "drive")
    
    # Verifica se há waypoints - se não houver, faz uma rota direta
    if not waypoints:
        logging.warning("Nenhum waypoint fornecido, calculando rota direta.")
        
    # Constrói a string de waypoints: início, paradas intermediárias e fim.
    waypoint_coords = [f"{start_point['lat']},{start_point['lon']}"]
    
    # Adiciona waypoints intermediários (se houver)
    for wp in waypoints:
        waypoint_coords.append(f"{wp['lat']},{wp['lon']}")
        
    waypoint_coords.append(f"{end_point['lat']},{end_point['lon']}")
    waypoints_str = "|".join(waypoint_coords)

    url = "https://api.geoapify.com/v1/routing"
    params = {
        "waypoints": waypoints_str,
        "mode": travel_mode,
        "details": "instruction_details,route_details",
        "units": "metric",
        "apiKey": API_KEY
    }
    
    logging.info(f"Fazendo solicitação para a API de Routing com modo: {travel_mode}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Lança exceção para status codes 4xx/5xx
        
        if response.status_code == 200:
            result = response.json()
            
            # Adiciona informações extras para facilitar o debug
            if 'features' in result:
                logging.info(f"Recebeu {len(result['features'])} features da API")
            else:
                logging.warning("A resposta da API não contém a chave 'features'")
                
            return result
            
    except requests.exceptions.HTTPError as http_err:
        error_msg = f"Erro HTTP: {http_err}"
        if response.text:
            try:
                error_details = response.json()
                error_msg += f" - Detalhes: {error_details}"
            except:
                error_msg += f" - Resposta: {response.text}"
        raise Exception(error_msg)
    except Exception as e:
        raise Exception(f"Erro na requisição da API: {str(e)}")

def plan_route(agents, jobs=None, shipments=None, locations=None, mode="drive", avoid=None, traffic="free_flow", route_type="balanced", max_speed=140, units="metric"):
    """
    Planeja uma rota otimizada para múltiplos veículos e jobs utilizando a Geoapify Route Planner API.
    
    Parâmetros:
      - agents (list): Lista de agentes (por exemplo, veículos), onde cada agente é um dicionário com informações como 'start_location', 'time_windows', etc.
      - jobs (list, opcional): Lista de jobs (tarefas ou paradas) com parâmetros como 'location', 'duration' e 'time_windows'.
      - shipments (list, opcional): Lista de shipments para definir coletas/entregas.
      - locations (list, opcional): Lista de locais que podem ser referenciados nos jobs e shipments.
      - mode (str): Modo de viagem (padrão "drive").
      - avoid (list, opcional): Lista de regras de "avoid" (por exemplo, evitar pedágios, rodovias, etc.).
      - traffic (str): Modelo de tráfego ("free_flow" ou "approximated", padrão "free_flow").
      - route_type (str): Tipo de otimização da rota ("balanced", "short" ou "less_maneuvers", padrão "balanced").
      - max_speed (int): Velocidade máxima permitida (padrão 140).
      - units (str): Unidades ("metric" ou "imperial", padrão "metric").
    
    Retorna:
      - dict: Resposta JSON da API com o planejamento otimizado da rota.
    """
    API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
    if not API_KEY:
        raise Exception("A variável de ambiente GEOAPIFY_API_KEY não está definida.")

    url = f"https://api.geoapify.com/v1/routeplanner?apiKey={API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "mode": mode,
        "agents": agents,
        "avoid": avoid if avoid is not None else [],
        "traffic": traffic,
        "type": route_type,
        "max_speed": max_speed,
        "units": units
    }
    if jobs is not None:
        payload["jobs"] = jobs
    if shipments is not None:
        payload["shipments"] = shipments
    if locations is not None:
        payload["locations"] = locations

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Erro na Route Planner API {response.status_code}: {response.text}")

def optimize_multiple_routes(
    start_point: Dict[str, float],
    end_point: Dict[str, float],
    passenger_groups: List[List[Dict[str, Any]]],
    vehicle_types: List[str],
    max_duration_minutes: int = 45
) -> List[Dict[str, Any]]:
    """
    Otimiza múltiplas rotas, uma para cada grupo de passageiros/veículo.
    
    Parâmetros:
      - start_point: Ponto de partida comum para todas as rotas
      - end_point: Ponto de chegada comum para todas as rotas
      - passenger_groups: Lista de listas de passageiros, uma por veículo
      - vehicle_types: Lista de tipos de veículos, correspondendo aos grupos
      - max_duration_minutes: Tempo máximo de rota em minutos
      
    Retorna:
      - Lista de respostas da API com detalhes das rotas otimizadas
    """
    if not passenger_groups:
        return []
    
    results = []
    
    # Otimizar rota separada para cada grupo de passageiros
    for i, group in enumerate(passenger_groups):
        vehicle_type = vehicle_types[i] if i < len(vehicle_types) else "car"
        
        try:
            route = optimize_route(
                start_point,
                end_point,
                group,
                max_duration_minutes,
                vehicle_type
            )
            results.append({
                "vehicle_index": i,
                "vehicle_type": vehicle_type,
                "passengers": len(group),
                "route_data": route
            })
        except Exception as e:
            logging.error(f"Erro ao otimizar rota para veículo {i}: {e}")
            results.append({
                "vehicle_index": i,
                "vehicle_type": vehicle_type,
                "passengers": len(group),
                "error": str(e),
                "route_data": None
            })
    
    return results

def create_route_planner_payload(
    start_point: Dict[str, float],
    end_point: Dict[str, float],
    waypoints: List[Dict[str, Any]],
    vehicle_type: str = "car",
    max_duration_minutes: int = 45
) -> Dict[str, Any]:
    """
    Cria o payload para a Route Planner API.
    
    Args:
        start_point: Dicionário com lat e lon para o ponto de partida
        end_point: Dicionário com lat e lon para o ponto de chegada
        waypoints: Lista de dicionários com lat, lon e person_id para cada parada
        vehicle_type: Tipo de veículo (car, truck, etc.)
        max_duration_minutes: Tempo máximo da rota em minutos
        
    Returns:
        Dicionário com o payload formatado para a API
    """
    # Mapeia tipos de veículos para configurações da API
    vehicle_profiles = {
        "car": {"type": "car"},
        "van": {"type": "car", "max_speed": 90},
        "bus": {"type": "car", "max_speed": 80},
        "truck": {"type": "truck"},
        "motorcycle": {"type": "motorcycle"}
    }
    
    # Usa car como perfil padrão se o tipo de veículo não for reconhecido
    vehicle_profile = vehicle_profiles.get(vehicle_type.lower(), {"type": "car"})
    
    # Criar agentes (veículos) - Agora sem especificar capacity
    agents = [{
        "id": "vehicle_1",
        "profile": vehicle_profile,
        "start_location": [start_point['lon'], start_point['lat']],
        "end_location": [end_point['lon'], end_point['lat']]
        # Removido o parâmetro capacity que estava causando inconsistência
    }]
    
    # Criar jobs (tarefas/paradas) - Simplificado sem delivery_amount
    jobs = []
    for i, wp in enumerate(waypoints):
        jobs.append({
            "id": f"job_{i}",
            "location": [wp['lon'], wp['lat']],
            "duration": 30  # 30 segundos para parada
            # Removido o parâmetro delivery_amount que estava causando o erro
        })
    
    # Criar o payload completo
    payload = {
        "agents": agents,
        "jobs": jobs,
        "mode": "drive",
        "traffic": "approximated",
        "type": "balanced",
        "units": "metric"
    }
    
    return payload

def process_route_planner_response(response_data: Dict[str, Any], waypoints: List[Dict[str, Any]], start_point: Dict[str, float], end_point: Dict[str, float]) -> Dict[str, Any]:
    """
    Processa a resposta da Route Planner API e formata para uso na aplicação.
    
    Args:
        response_data: Resposta da Route Planner API
        waypoints: Lista original de waypoints com informações de passageiros
        start_point: Dicionário com lat e lon para o ponto de partida
        end_point: Dicionário com lat e lon para o ponto de chegada
        
    Returns:
        Dicionário formatado para compatibilidade com a aplicação
    """
    # Check if the response is in FeatureCollection format
    if response_data.get('type') == 'FeatureCollection' and 'features' in response_data:
        # Extract agent information from features
        feature = response_data['features'][0]  # Take the first feature which contains the route
        
        # Extract agent properties from the feature
        if 'properties' in feature:
            agent_properties = feature['properties']
            
            # Create result structure
            result = {
                "success": True,
                "message": "Rota otimizada com sucesso",
                "total_distance_km": agent_properties.get('distance', 0) / 1000,  # Convert meters to km
                "total_duration_minutes": agent_properties.get('time', 0) / 60,  # Convert seconds to minutes
                "stops": [],
                "path": [],
                "features": [feature]  # Add the feature for map compatibility
            }
            
            # Process waypoints from the feature
            feature_waypoints = agent_properties.get('waypoints', [])
            
            # Mapping job ids to original waypoints
            waypoint_map = {}
            for i, wp in enumerate(waypoints):
                job_id = f"job_{i}"
                waypoint_map[job_id] = wp
            
            # Add start point
            result["stops"].append({
                "stop_order": 0,
                "location_id": "start",
                "coordinates": start_point,
                "address": "Ponto de partida",
                "persons": [],
                "arrival_time": feature_waypoints[0].get('start_time') if feature_waypoints else None
            })
            
            # Process intermediate stops
            for i, feature_wp in enumerate(feature_waypoints[1:-1], 1):  # Skip first (start) and last (end)
                # Get actions at this waypoint
                actions = feature_wp.get('actions', [])
                
                # Find job actions
                job_actions = [action for action in actions if action.get('type') == 'job']
                if job_actions:
                    for action in job_actions:
                        job_id = action.get('job_id')
                        if job_id in waypoint_map:
                            original_wp = waypoint_map[job_id]
                            result["stops"].append({
                                "stop_order": i,
                                "location_id": job_id,
                                "coordinates": {"lat": original_wp['lat'], "lon": original_wp['lon']},
                                "address": original_wp.get('name', f"Parada {i}"),
                                "persons": [original_wp],
                                "arrival_time": action.get('start_time')
                            })
            
            # Add end point
            result["stops"].append({
                "stop_order": len(result["stops"]),
                "location_id": "end",
                "coordinates": end_point,
                "address": "Ponto de chegada",
                "arrival_time": feature_waypoints[-1].get('start_time') if feature_waypoints else None
            })
            
            # Process route geometry for drawing the path
            if 'geometry' in feature:
                if feature['geometry']['type'] == 'MultiLineString':
                    # Flatten the MultiLineString coordinates
                    for line in feature['geometry']['coordinates']:
                        for coord in line:
                            result["path"].append({"lat": coord[1], "lon": coord[0]})
                elif feature['geometry']['type'] == 'LineString':
                    for coord in feature['geometry']['coordinates']:
                        result["path"].append({"lat": coord[1], "lon": coord[0]})
            
            return result
    
    # If not in FeatureCollection format, use the original processing
    if not response_data or 'agents' not in response_data or not response_data['agents']:
        return {"error": "Resposta inválida da API"}
    
    # Rest of the original processing function
    agent = response_data['agents'][0]  # Pegamos o primeiro agente/veículo
    
    # Extrair informações importantes
    result = {
        "success": True,
        "message": "Rota otimizada com sucesso",
        "total_distance_km": agent.get('distance', 0) / 1000,  # Converter metros para km
        "total_duration_minutes": agent.get('duration', 0) / 60,  # Converter segundos para minutos
        "stops": [],
        "path": [],
        "features": []
    }
    
    # Adicionar ponto de partida - agora usando start_location como array [lon, lat]
    if 'start_location' in agent and isinstance(agent['start_location'], list) and len(agent['start_location']) >= 2:
        result["stops"].append({
            "stop_order": 0,
            "location_id": "start",
            "coordinates": {"lat": agent['start_location'][1], "lon": agent['start_location'][0]},
            "address": "Ponto de partida",
            "persons": [],
            "arrival_time": None
        })
    else:
        # Fallback se o formato for inesperado
        result["stops"].append({
            "stop_order": 0,
            "location_id": "start",
            "coordinates": {"lat": start_point['lat'], "lon": start_point['lon']},
            "address": "Ponto de partida",
            "persons": [],
            "arrival_time": None
        })
    
    # Processar cada atividade na rota (paradas)
    stop_index = 1  # Começar em 1, pois 0 é o ponto de partida
    
    # Mapear waypoints para uma estrutura que facilita a busca
    waypoint_map = {f"pickup_{i}": wp for i, wp in enumerate(waypoints)}
    
    # Processar cada atividade na rota (paradas)
    for activity in agent.get('activities', []):
        if activity.get('job_id') and activity.get('location'):
            job_id = activity.get('job_id')
            location = activity.get('location')  # Agora location é um array [lon, lat]
            
            # Encontrar o waypoint correspondente a este job
            if job_id in waypoint_map:
                waypoint = waypoint_map[job_id]
                
                # Adicionar parada
                result["stops"].append({
                    "stop_order": stop_index,
                    "location_id": job_id,
                    "coordinates": {"lat": location[1], "lon": location[0]},
                    "address": waypoint.get('name', f"Parada {stop_index}"),
                    "persons": [waypoint],
                    "arrival_time": activity.get('earliest_start'),
                    "person_id": waypoint.get('person_id')
                })
                stop_index += 1
    
    # Adicionar ponto de chegada - agora usando end_location como array [lon, lat]
    if 'end_location' in agent and isinstance(agent['end_location'], list) and len(agent['end_location']) >= 2:
        result["stops"].append({
            "stop_order": stop_index,
            "location_id": "end",
            "coordinates": {"lat": agent['end_location'][1], "lon": agent['end_location'][0]},
            "address": "Ponto de chegada",
            "persons": [],
            "arrival_time": agent.get('end_time')
        })
    
    # Adicionar geometria da rota completa se disponível
    if 'routes' in response_data and response_data['routes']:
        route = response_data['routes'][0]
        if 'geometry' in route:
            # Adicionamos a geometria como um feature compatível com APIs anteriores
            result["features"].append({
                "type": "Feature",
                "geometry": route['geometry'],
                "properties": {
                    "summary": {
                        "distance": agent.get('distance', 0),
                        "duration": agent.get('duration', 0)
                    },
                    "mode": "drive",
                    "distance": agent.get('distance', 0),
                    "duration": agent.get('duration', 0)
                }
            })
            
            # Extrair path para desenho do mapa
            if route['geometry']['type'] == 'LineString':
                # LineString: lista de [lon, lat]
                coordinates = route['geometry']['coordinates']
                for coord in coordinates:
                    result["path"].append({"lat": coord[1], "lon": coord[0]})
    
    return result

def plan_optimized_route(
    start_point: Dict[str, float], 
    end_point: Dict[str, float], 
    waypoints: List[Dict[str, Any]], 
    max_duration_minutes: int = 45,
    vehicle_type: str = "car",
    is_arrival: bool = True  # Adicionado parâmetro para diferenciar ida/volta
) -> Dict[str, Any]:
    """
    Planeja uma rota otimizada usando a Route Planner API da Geoapify,
    respeitando regras de cálculo de tempo para ida e volta.
    
    Args:
        start_point: Dicionário com lat e lon para o ponto de partida
        end_point: Dicionário com lat e lon para o ponto de chegada
        waypoints: Lista de dicionários com lat, lon e person_id para cada parada
        max_duration_minutes: Tempo máximo da rota em minutos
        vehicle_type: Tipo de veículo para determinar o modo de viagem
        is_arrival: Se True, considera ida para empresa; se False, considera volta
        
    Returns:
        Dicionário com a rota otimizada
    """
    API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
    if not API_KEY:
        raise Exception("A variável de ambiente GEOAPIFY_API_KEY não está definida.")
    
    url = f"https://api.geoapify.com/v1/routeplanner?apiKey={API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    # Criar payload para a API
    payload = create_route_planner_payload(
        start_point,
        end_point,
        waypoints,
        vehicle_type,
        max_duration_minutes
    )
    
    try:
        logging.info(f"Enviando solicitação para Route Planner API com {len(waypoints)} waypoints")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            result_data = response.json()
            
            # Check for both standard agent format and FeatureCollection format
            if ('agents' in result_data and result_data['agents']) or \
               (result_data.get('type') == 'FeatureCollection' and 'features' in result_data):
                logging.info("Rota otimizada calculada com sucesso")
                
                # Processar e formatar a resposta
                result = process_route_planner_response(result_data, waypoints, start_point, end_point)
                
                # Adicionar campos para garantir que o tempo seja calculado corretamente
                estimated_time = estimate_route_time(
                    start_point,
                    end_point,
                    waypoints,
                    vehicle_type,
                    is_arrival
                )
                
                # Adicionar o tempo estimado explicitamente ao resultado
                result['estimated_time'] = estimated_time
                result['is_arrival_route'] = is_arrival
                
                return result
            else:
                logging.error(f"Resposta inválida da API: {result_data}")
                return {"error": "A API não retornou uma rota válida", "api_response": result_data}
                
        else:
            error_msg = f"Erro na API ({response.status_code})"
            try:
                error_details = response.json()
                error_msg += f": {json.dumps(error_details)}"
            except:
                error_msg += f": {response.text}"
            
            logging.error(error_msg)
            return {"error": error_msg}
            
    except Exception as e:
        error_msg = f"Falha na chamada à API de Route Planner: {str(e)}"
        logging.exception(error_msg)
        return {"error": error_msg}

def extract_stops_sequence(route_data, waypoints):
    """
    Process waypoints from the feature
    """
    # Check if the response is in FeatureCollection format
    if route_data.get('type') == 'FeatureCollection' and 'features' in route_data:
        # Extract agent information from features
        feature = route_data['features'][0]  # Take the first feature which contains the route
        
        # Extract agent properties from the feature
        if 'properties' in feature:
            agent_properties = feature['properties']
            
            # Create result structure
            result = {
                "success": True,
                "message": "Rota otimizada com sucesso",
                "total_distance_km": agent_properties.get('distance', 0) / 1000,  # Convert meters to km
                "total_duration_minutes": agent_properties.get('time', 0) / 60,  # Convert seconds to minutes
                "stops": [],
                "path": [],
                "features": [feature]  # Add the feature for map compatibility
            }
            
            # Process waypoints from the feature
            feature_waypoints = agent_properties.get('waypoints', [])
            
            # Mapping job ids to original waypoints
            waypoint_map = {}
            for i, wp in enumerate(waypoints):
                job_id = f"job_{i}"
                waypoint_map[job_id] = wp

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula a distância entre dois pontos na superfície terrestre usando a fórmula de Haversine.
    
    Args:
        lat1, lon1: Coordenadas do primeiro ponto
        lat2, lon2: Coordenadas do segundo ponto
        
    Returns:
        Distância em km
    """
    # Raio da Terra em km
    R = 6371.0
    
    # Converter de graus para radianos
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Diferenças nas coordenadas
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Fórmula de Haversine
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

def get_traffic_factor(hour: int = None, area_type: str = "urban") -> float:
    """
    Retorna um fator de tráfego dinâmico baseado na hora do dia e tipo de área.
    
    Args:
        hour: Hora do dia (0-23), se None usa a hora atual
        area_type: Tipo de área ("urban", "suburban", "rural")
        
    Returns:
        Fator de tráfego (multiplicador)
    """
    if hour is None:
        hour = datetime.now().hour
    
    # Definir perfis de tráfego para diferentes tipos de área
    traffic_profiles = {
        "urban": {
            # Pico da manhã (7-10h): 50% mais tempo
            "morning_peak": (7, 10, 1.5),
            # Pico da tarde (16-20h): 60% mais tempo
            "evening_peak": (16, 20, 1.6),
            # Noite/madrugada (22-5h): 10% mais tempo
            "night": (22, 5, 1.1),
            # Padrão: 30% mais tempo
            "default": 1.3
        },
        "suburban": {
            "morning_peak": (7, 9, 1.4),
            "evening_peak": (16, 19, 1.5),
            "night": (22, 5, 1.05),
            "default": 1.2
        },
        "rural": {
            "morning_peak": (7, 9, 1.2),
            "evening_peak": (16, 19, 1.3),
            "night": (22, 5, 1.0),
            "default": 1.1
        }
    }
    
    # Usar perfil "urban" como padrão se o tipo especificado não existir
    profile = traffic_profiles.get(area_type, traffic_profiles["urban"])
    
    # Verificar em qual período do dia estamos
    if profile["morning_peak"][0] <= hour < profile["morning_peak"][1]:
        return profile["morning_peak"][2]
    elif profile["evening_peak"][0] <= hour < profile["evening_peak"][1]:
        return profile["evening_peak"][2]
    elif profile["night"][0] <= hour or hour < profile["night"][1]:
        return profile["night"][2]
    else:
        return profile["default"]

def estimate_route_time(start_coord, end_coord, passengers, vehicle_type="car", is_arrival=True, area_type="urban"):
    """
    Estima o tempo de uma rota em minutos:
      - Se for ida: do ponto de partida até a empresa, passando por todos os passageiros.
      - Se for volta: da empresa até o último passageiro, sem retorno.
      
    Args:
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada (empresa para rota de ida)
        passengers: Lista de passageiros com suas coordenadas
        vehicle_type: Tipo do veículo (car, bus, etc.)
        is_arrival: Se é rota de ida para empresa (True) ou saída da empresa (False)
        area_type: Tipo de área para ajuste de tráfego ("urban", "suburban", "rural")
        
    Returns:
        Tempo estimado em minutos.
    """
    if not passengers:
        return 0
        
    # Velocidade média estimada em km/h baseada no tipo de veículo
    vehicle_speeds = {
        "car": 40,
        "van": 35,
        "bus": 30,
        "truck": 25,
        "motorcycle": 45
    }
    avg_speed_kmh = vehicle_speeds.get(vehicle_type.lower(), 35)
    
    # Tempo gasto em cada parada em minutos (valores refinados por tipo de veículo)
    stop_times = {
        "car": 1,
        "van": 1.5,
        "bus": 2.5,
        "truck": 2,
        "motorcycle": 0.5
    }
    stop_time_minutes = stop_times.get(vehicle_type.lower(), 1)
    
    # Obter fator de tráfego dinâmico baseado na hora atual e tipo de área
    traffic_factor = get_traffic_factor(area_type=area_type)
    
    # Calcular distância total do trajeto completo
    total_distance = 0
    prev_point = start_coord
    
    # Distância entre pontos consecutivos do trajeto
    for passenger in passengers:
        dist = haversine_distance(
            prev_point['lat'], prev_point['lon'],
            passenger['lat'], passenger['lon']
        )
        total_distance += dist
        prev_point = passenger
    
    # Incluir a distância até o destino final
    if is_arrival:  # Se for rota de ida, adicionar distância até a empresa
        dist_to_end = haversine_distance(
            prev_point['lat'], prev_point['lon'],
            end_coord['lat'], end_coord['lon']
        )
        total_distance += dist_to_end
    # Se for rota de volta, não adicionar distância de retorno após o último passageiro
    
    # Calcular tempo total
    travel_time_minutes = (total_distance / avg_speed_kmh) * 60 * traffic_factor
    stop_time_total = len(passengers) * stop_time_minutes
    total_time_minutes = travel_time_minutes + stop_time_total
    
    # Retornar tempo total arredondado
    return round(total_time_minutes, 1)

def cluster_passengers_by_distance(passengers, epsilon=0.01, min_samples=1):
    """
    Agrupa passageiros geograficamente próximos usando DBSCAN.
    
    Args:
        passengers: Lista de dicionários com lat e lon
        epsilon: Distância máxima entre pontos para serem considerados no mesmo cluster
        min_samples: Número mínimo de pontos para formar um cluster
        
    Returns:
        Lista de clusters, onde cada cluster é uma lista de passageiros
    """
    if not passengers:
        return []
        
    # Converter dados para formato esperado pelo DBSCAN
    points = np.array([[p['lat'], p['lon']] for p in passengers])
    
    # Aplicar DBSCAN
    try:
        db = DBSCAN(eps=epsilon, min_samples=min_samples, metric='euclidean').fit(points)
        labels = db.labels_
        
        # Organizar pontos por cluster
        clusters = defaultdict(list)
        for i, label in enumerate(labels):
            if label != -1:  # -1 são pontos classificados como ruído
                clusters[label].append(passengers[i])
            else:
                # Tratar pontos isolados como clusters de um único passageiro
                clusters[f"noise_{i}"] = [passengers[i]]
                
        return list(clusters.values())
    except Exception as e:
        logging.error(f"Erro ao realizar clustering DBSCAN: {e}")
        # Retornar lista com cada passageiro como seu próprio cluster
        return [[p] for p in passengers]

def optimize_route_order_tsp(start_point, end_point, waypoints):
    """
    Otimiza a ordem dos waypoints usando uma heurística de solução do TSP.
    Utiliza a técnica de "construção + melhoria local" para encontrar uma rota eficiente.
    
    Args:
        start_point: Ponto de partida
        end_point: Ponto de chegada
        waypoints: Lista de pontos intermediários a serem ordenados
        
    Returns:
        Lista ordenada de waypoints
    """
    if not waypoints:
        return []
        
    # Se houver apenas um waypoint, não há nada para ordenar
    if len(waypoints) <= 1:
        return waypoints
        
    # Para rotas pequenas (até 5 pontos), podemos usar força bruta para garantir a melhor solução
    if len(waypoints) <= 5:
        return optimize_route_brute_force(start_point, end_point, waypoints)
    
    # Para rotas maiores, usamos uma heurística mais eficiente
    
    # 1. Construção inicial: Algoritmo do vizinho mais próximo (NN)
    current = start_point
    unvisited = waypoints.copy()
    route = []
    
    while unvisited:
        # Encontrar o ponto mais próximo
        closest_idx = 0
        min_dist = float('inf')
        
        for i, point in enumerate(unvisited):
            dist = haversine_distance(current['lat'], current['lon'], point['lat'], point['lon'])
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        
        # Adicionar o ponto mais próximo à rota
        next_point = unvisited.pop(closest_idx)
        route.append(next_point)
        current = next_point
    
    # 2. Melhoramento: 2-opt para otimização local
    route = two_opt_optimization(route, start_point, end_point)
    
    return route

def optimize_route_brute_force(start_point, end_point, waypoints):
    """
    Encontra a ordem ótima dos waypoints testando todas as permutações possíveis.
    Adequado apenas para conjuntos pequenos (até 8-10 pontos, dependendo da capacidade computacional).
    
    Args:
        start_point: Ponto de partida
        end_point: Ponto de chegada
        waypoints: Lista de waypoints a serem ordenados
        
    Returns:
        Lista ordenada de waypoints com menor distância total
    """
    import itertools
    
    if len(waypoints) <= 1:
        return waypoints
        
    # Gerar todas as permutações possíveis dos waypoints
    permutations = list(itertools.permutations(range(len(waypoints))))
    
    best_distance = float('inf')
    best_order = None
    
    # Calcular distância total para cada permutação
    for perm in permutations:
        # Converter índices para pontos reais
        ordered_points = [waypoints[i] for i in perm]
        
        # Calcular distância total
        total_dist = 0
        
        # Distância do ponto inicial para o primeiro waypoint
        if ordered_points:
            total_dist += haversine_distance(
                start_point['lat'], start_point['lon'],
                ordered_points[0]['lat'], ordered_points[0]['lon']
            )
        
        # Distância entre waypoints
        for i in range(len(ordered_points) - 1):
            total_dist += haversine_distance(
                ordered_points[i]['lat'], ordered_points[i]['lon'],
                ordered_points[i+1]['lat'], ordered_points[i+1]['lon']
            )
        
        # Distância do último waypoint para o ponto final
        if ordered_points:
            total_dist += haversine_distance(
                ordered_points[-1]['lat'], ordered_points[-1]['lon'],
                end_point['lat'], end_point['lon']
            )
        
        # Atualizar a melhor rota se esta for melhor
        if total_dist < best_distance:
            best_distance = total_dist
            best_order = perm
    
    # Converter a melhor ordem em uma lista de waypoints
    if best_order is not None:
        return [waypoints[i] for i in best_order]
    else:
        return waypoints

def two_opt_optimization(route, start_point, end_point, max_iterations=100):
    """
    Aplica a heurística de otimização 2-opt para melhorar a rota.
    
    Args:
        route: Lista atual de waypoints
        start_point: Ponto de partida da rota
        end_point: Ponto de chegada da rota
        max_iterations: Número máximo de iterações
        
    Returns:
        Rota melhorada
    """
    if len(route) <= 2:
        return route
        
    best_route = route.copy()
    improved = True
    iteration = 0
    
    while improved and iteration < max_iterations:
        improved = False
        best_distance = calculate_route_distance(start_point, end_point, best_route)
        
        # Testar trocas de segmentos
        for i in range(len(route) - 2):
            for j in range(i + 2, len(route)):
                # Criar nova rota com segmento invertido
                new_route = best_route.copy()
                new_route[i+1:j+1] = reversed(new_route[i+1:j+1])
                
                # Calcular nova distância
                new_distance = calculate_route_distance(start_point, end_point, new_route)
                
                # Se melhorou, atualizar a rota
                if new_distance < best_distance:
                    best_distance = new_distance
                    best_route = new_route
                    improved = True
        
        iteration += 1
    
    return best_route

def calculate_route_distance(start_point, end_point, waypoints):
    """
    Calcula a distância total de uma rota.
    
    Args:
        start_point: Ponto de partida
        end_point: Ponto de chegada
        waypoints: Lista ordenada de waypoints
        
    Returns:
        Distância total em km
    """
    total_distance = 0
    
    # Adicionar distância do ponto inicial ao primeiro waypoint
    if waypoints:
        total_distance += haversine_distance(
            start_point['lat'], start_point['lon'],
            waypoints[0]['lat'], waypoints[0]['lon']
        )
    
    # Adicionar distâncias entre waypoints
    for i in range(len(waypoints) - 1):
        total_distance += haversine_distance(
            waypoints[i]['lat'], waypoints[i]['lon'],
            waypoints[i+1]['lat'], waypoints[i+1]['lon']
        )
    
    # Adicionar distância do último waypoint ao ponto final
    if waypoints:
        total_distance += haversine_distance(
            waypoints[-1]['lat'], waypoints[-1]['lon'],
            end_point['lat'], end_point['lon']
        )
    
    return total_distance

def plan_routes_by_time_constraint(start_coord, end_coord, passengers, max_duration_minutes, vehicle_types=None, is_arrival=True, area_type="urban"):
    """
    Planeja múltiplas rotas otimizadas respeitando o limite de tempo por rota, utilizando
    clustering geográfico e otimização de rota.
    
    Args:
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada
        passengers: Lista de passageiros com suas coordenadas
        max_duration_minutes: Tempo máximo permitido por rota (em minutos)
        vehicle_types: Lista de tipos de veículos disponíveis
        is_arrival: Se é rota de chegada (True) ou saída (False)
        area_type: Tipo de área para ajuste de tráfego
        
    Returns:
        Lista de rotas, cada uma contendo uma lista de passageiros atendidos
    """
    st.info(f"Planejando rotas com limite de {max_duration_minutes} minutos por rota...")
    
    if not passengers:
        return []
    
    if not vehicle_types:
        vehicle_types = ["car"]
    
    # Etapa 1: Agrupar passageiros por proximidade geográfica
    # Calculamos um valor de epsilon apropriado para a região geográfica
    # Usamos uma fração da distância total da área para determinar o raio dos clusters
    
    # Determinar tamanho da área
    lats = [p['lat'] for p in passengers]
    lons = [p['lon'] for p in passengers]
    lat_range = max(lats) - min(lats)
    lon_range = max(lons) - min(lons)
    
    # Epsilon dinâmico baseado na distribuição geográfica dos pontos
    # Se muitos pontos, clusters menores; se poucos, clusters maiores
    epsilon = max(0.005, min(0.02, (lat_range + lon_range) / 50))
    
    # Ajustar min_samples baseado no número de passageiros
    min_samples = max(1, len(passengers) // 25)
    
    logging.info(f"Aplicando clustering com epsilon={epsilon}, min_samples={min_samples}")
    initial_clusters = cluster_passengers_by_distance(passengers, epsilon, min_samples)
    
    # Etapa 2: Para cada cluster, otimizar a ordem dos pontos e verificar limite de tempo
    final_routes = []
    vehicle_type_index = 0
    
    for cluster in initial_clusters:
        # Se o cluster for muito grande, podemos precisar dividi-lo
        optimized_route = optimize_route_order_tsp(start_coord, end_coord, cluster)
        
        # Verificação iterativa: o cluster cabe em uma única rota?
        estimated_time = estimate_route_time(
            start_coord, 
            end_coord, 
            optimized_route, 
            vehicle_types[vehicle_type_index % len(vehicle_types)],
            is_arrival,
            area_type
        )
        
        # Se o tempo estiver dentro do limite, adicione como uma única rota
        if estimated_time <= max_duration_minutes:
            final_routes.append({
                'passengers': optimized_route,
                'estimated_time': estimated_time,
                'vehicle_type': vehicle_types[vehicle_type_index % len(vehicle_types)]
            })
            vehicle_type_index += 1
        else:
            # Dividir em subrotas que respeitam o limite de tempo
            subroutes = divide_route_by_time_limit(
                start_coord,
                end_coord,
                optimized_route,
                max_duration_minutes,
                vehicle_types[vehicle_type_index % len(vehicle_types)],
                is_arrival,
                area_type
            )
            
            # Adicionar cada subrota à lista final
            for subroute in subroutes:
                final_routes.append({
                    'passengers': subroute['passengers'],
                    'estimated_time': subroute['estimated_time'],
                    'vehicle_type': vehicle_types[vehicle_type_index % len(vehicle_types)]
                })
                vehicle_type_index += 1
    
    # Ordenar rotas por tempo estimado (do maior para o menor)
    final_routes.sort(key=lambda x: x['estimated_time'], reverse=True)
    
    logging.info(f"Planejamento concluído: {len(final_routes)} rotas geradas para {len(passengers)} passageiros")
    return final_routes

def divide_route_by_time_limit(start_coord, end_coord, passengers, max_duration_minutes, vehicle_type="car", is_arrival=True, area_type="urban"):
    """
    Divide uma lista de passageiros em múltiplas rotas, todas respeitando
    o limite de tempo.
    
    Args:
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada
        passengers: Lista ordenada de passageiros
        max_duration_minutes: Tempo máximo por rota
        vehicle_type: Tipo de veículo
        is_arrival: Se é rota de chegada (True) ou saída (False) 
        area_type: Tipo de área para ajuste de tráfego
        
    Returns:
        Lista de subrotas, cada uma com seus passageiros e tempo estimado
    """
    if not passengers:
        return []
    
    # Inicialização
    subroutes = []
    current_route = []
    remaining = passengers.copy()
    
    # Processo iterativo de construção das rotas
    while remaining:
        # Testar se podemos adicionar o próximo passageiro
        test_route = current_route + [remaining[0]]
        
        # Calcular tempo estimado
        test_time = estimate_route_time(
            start_coord, 
            end_coord, 
            test_route, 
            vehicle_type,
            is_arrival,
            area_type
        )
        
        if test_time <= max_duration_minutes and current_route:
            # Podemos adicionar o passageiro à rota atual
            current_route.append(remaining.pop(0))
        else:
            # Se a rota atual não está vazia, finalizá-la
            if current_route:
                current_time = estimate_route_time(
                    start_coord, 
                    end_coord, 
                    current_route, 
                    vehicle_type,
                    is_arrival,
                    area_type
                )
                subroutes.append({
                    'passengers': current_route,
                    'estimated_time': current_time
                })
                
                # Iniciar nova rota
                current_route = []
            
            # Se não pudermos adicionar o passageiro mesmo em uma rota vazia,
            # criar uma rota apenas para ele
            if not current_route and remaining:
                solo_time = estimate_route_time(
                    start_coord, 
                    end_coord, 
                    [remaining[0]], 
                    vehicle_type,
                    is_arrival,
                    area_type
                )
                subroutes.append({
                    'passengers': [remaining.pop(0)],
                    'estimated_time': solo_time
                })
                logging.warning(f"Passageiro com tempo estimado de {solo_time:.1f} min adicionado em rota individual.")
    
    # Adicionar a última rota se não estiver vazia
    if current_route:
        current_time = estimate_route_time(
            start_coord, 
            end_coord, 
            current_route, 
            vehicle_type,
            is_arrival,
            area_type
        )
        subroutes.append({
            'passengers': current_route,
            'estimated_time': current_time
        })
    
    return subroutes

def get_real_route_estimate(
    start_point: Dict[str, float],
    end_point: Dict[str, float],
    waypoints: List[Dict[str, Any]],
    vehicle_type: str = "car",
    is_arrival: bool = True
) -> Dict[str, Any]:
    """
    Obtém estimativas reais de tempo e distância de uma rota usando a API Geoapify.
    
    Args:
        start_point: Coordenadas do ponto de partida
        end_point: Coordenadas do ponto de chegada
        waypoints: Lista de waypoints a visitar
        vehicle_type: Tipo de veículo (car, truck, etc.)
        is_arrival: Se True, considera rota de ida para empresa, senão, de volta
        
    Returns:
        Dicionário com tempo estimado (em minutos) e distância (em km)
    """
    API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
    if not API_KEY:
        logging.warning("GEOAPIFY_API_KEY não está definida, usando estimativa local")
        return None
        
    # Determinar quais pontos incluir na estimativa baseado no tipo de rota
    route_points = []
    
    if is_arrival:
        # Para rotas de ida, apenas consideramos do primeiro passageiro à empresa
        if waypoints:
            # Inicio com o primeiro passageiro (não a garagem)
            route_points.append(waypoints[0])
            # Adiciono demais passageiros
            route_points.extend(waypoints[1:])
            # Termino na empresa
            final_point = {"lat": end_point["lat"], "lon": end_point["lon"]}
            route_points.append(final_point)
    else:
        # Para rotas de volta, consideramos da empresa até o último passageiro
        # Começo na empresa
        first_point = {"lat": start_point["lat"], "lon": start_point["lon"]}
        route_points = [first_point] + waypoints
        # Não considero o retorno para a garagem
    
    # Se não temos pontos suficientes para uma rota, retorne None
    if len(route_points) < 2:
        return None
        
    # Mapeia tipos de veículos para modos de viagem da API
    vehicle_to_mode = {
        "car": "drive",
        "bus": "drive",
        "van": "drive", 
        "truck": "truck",
        "motorcycle": "motorcycle"
    }
    travel_mode = vehicle_to_mode.get(vehicle_type.lower(), "drive")
    
    # Construir a string de waypoints
    waypoint_coords = [f"{p['lat']},{p['lon']}" for p in route_points]
    waypoints_str = "|".join(waypoint_coords)
    
    url = "https://api.geoapify.com/v1/routing"
    params = {
        "waypoints": waypoints_str,
        "mode": travel_mode,
        "traffic": "approximated",
        "details": "route_details",
        "units": "metric",
        "apiKey": API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        if response.status_code == 200:
            data = response.json()
            
            if 'features' in data and len(data['features']) > 0:
                feature = data['features'][0]
                if 'properties' in feature:
                    properties = feature['properties']
                    
                    # Extrair dados da rota
                    distance_meters = properties.get('distance', 0)
                    time_seconds = properties.get('time', 0)
                    
                    return {
                        'time_minutes': round(time_seconds / 60, 1),
                        'distance_km': round(distance_meters / 1000, 2),
                        'success': True,
                        'raw_response': data
                    }
            
            logging.warning("Resposta da API não contém os dados esperados")
            return {
                'success': False,
                'message': "Dados da rota não encontrados na resposta"
            }
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao chamar a API de routing: {str(e)}")
        return {
            'success': False,
            'message': f"Erro de requisição: {str(e)}"
        }
    
    return None

def optimize_route_with_api_feedback(
    start_point: Dict[str, float],
    end_point: Dict[str, float],
    waypoints: List[Dict[str, Any]],
    max_duration_minutes: int = 45,
    vehicle_type: str = "car",
    is_arrival: bool = True,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Otimiza uma rota com feedback da API, ajustando a ordem ou removendo pontos se necessário.
    
    Args:
        start_point: Coordenadas do ponto de partida
        end_point: Coordenadas do ponto de chegada
        waypoints: Lista de waypoints a otimizar
        max_duration_minutes: Tempo máximo da rota em minutos
        vehicle_type: Tipo de veículo 
        is_arrival: Se True, considera rota de ida para empresa
        max_retries: Número máximo de tentativas para ajustar a rota
        
    Returns:
        Rota otimizada com detalhes e status
    """
    if not waypoints:
        return {
            'success': False,
            'message': "Sem waypoints para otimizar"
        }
    
    # Primeiro, otimizar a ordem dos waypoints (TSP)
    logging.info("Otimizando ordem dos waypoints usando TSP")
    ordered_waypoints = optimize_route_order_tsp(start_point, end_point, waypoints)
    
    # Tentar obter estimativa da API com os waypoints ordenados
    api_estimate = get_real_route_estimate(
        start_point,
        end_point,
        ordered_waypoints,
        vehicle_type,
        is_arrival
    )
    
    # Se a API retornou dados válidos, verificar limite de tempo
    if api_estimate and api_estimate.get('success', False):
        time_minutes = api_estimate.get('time_minutes', 0)
        
        # Se estiver dentro do limite, retornar esta rota
        if time_minutes <= max_duration_minutes:
            logging.info(f"Rota otimizada pela API: {time_minutes} min, dentro do limite de {max_duration_minutes} min")
            return {
                'waypoints': ordered_waypoints,
                'api_estimate': api_estimate,
                'success': True,
                'message': f"Rota otimizada com sucesso: {time_minutes} min",
                'estimated_time': time_minutes  # Garantir que o tempo estimado esteja disponível
            }
        else:
            # Excedeu o limite de tempo, tentar ajustar a rota
            logging.warning(f"Rota excede o limite: {time_minutes} min > {max_duration_minutes} min")
            
            # Implementar estratégia de ajuste: remover waypoints até caber no limite
            if max_retries > 0:
                # Calcular quantos pontos podemos tentar remover
                excess_percentage = (time_minutes / max_duration_minutes) - 1
                # Se excesso for muito grande, remover mais pontos de uma vez
                points_to_remove = max(1, int(len(ordered_waypoints) * excess_percentage * 0.5))
                points_to_remove = min(points_to_remove, len(ordered_waypoints) - 1)  # Não remover todos
                
                logging.info(f"Tentando remover {points_to_remove} parada(s) para ficar dentro do limite")
                
                # Priorizar remoção de pontos que aumentam mais o trajeto
                # Para simplificar, vamos remover os últimos pontos (assumindo que já estão ordenados)
                adjusted_waypoints = ordered_waypoints[:-points_to_remove] if points_to_remove < len(ordered_waypoints) else ordered_waypoints[:1]
                
                # Tentar novamente com os waypoints ajustados e um retry a menos
                return optimize_route_with_api_feedback(
                    start_point,
                    end_point,
                    adjusted_waypoints,
                    max_duration_minutes,
                    vehicle_type,
                    is_arrival,
                    max_retries - 1
                )
            else:
                # Sem mais tentativas, retornar falha ou os melhores resultados possíveis
                return {
                    'waypoints': ordered_waypoints,
                    'api_estimate': api_estimate,
                    'success': False,
                    'message': f"Não foi possível ajustar a rota para o limite de {max_duration_minutes} min (atual: {time_minutes} min)",
                    'estimated_time': time_minutes  # Mesmo excedendo, incluímos o tempo para feedback
                }
    else:
        # Fallback: API falhou, usar estimativa local
        logging.warning("Falha ao obter estimativa da API, usando cálculo local")
        local_time = estimate_route_time(
            start_point,
            end_point,
            ordered_waypoints,
            vehicle_type,
            is_arrival
        )
        
        return {
            'waypoints': ordered_waypoints,
            'estimated_time': local_time,
            'success': True,
            'message': f"Rota otimizada com estimativa local: {local_time} min",
            'api_failure': True
        }

def plan_routes_by_time_constraint(start_coord, end_coord, passengers, max_duration_minutes, vehicle_types=None, is_arrival=True, area_type="urban", use_api=True):
    """
    Planeja múltiplas rotas otimizadas respeitando o limite de tempo por rota, utilizando
    clustering geográfico, otimização de rota e dados reais da API quando possível.
    
    Args:
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada
        passengers: Lista de passageiros com suas coordenadas
        max_duration_minutes: Tempo máximo permitido por rota (em minutos)
        vehicle_types: Lista de tipos de veículos disponíveis
        is_arrival: Se é rota de chegada (True) ou saída (False)
        area_type: Tipo de área para ajuste de tráfego
        use_api: Se True, usa a API para estimativas reais quando possível
        
    Returns:
        Lista de rotas, cada uma contendo uma lista de passageiros atendidos
    """
    st.info(f"Planejando rotas com limite de {max_duration_minutes} minutos por rota...")
    
    if not passengers:
        return []
    
    if not vehicle_types:
        vehicle_types = ["car"]
    
    # Etapa 1: Agrupar passageiros por proximidade geográfica
    # Calculamos um valor de epsilon apropriado para a região geográfica
    # Usamos uma fração da distância total da área para determinar o raio dos clusters
    
    # Determinar tamanho da área
    lats = [p['lat'] for p in passengers]
    lons = [p['lon'] for p in passengers]
    lat_range = max(lats) - min(lats)
    lon_range = max(lons) - min(lons)
    
    # Epsilon dinâmico baseado na distribuição geográfica dos pontos
    # Se muitos pontos, clusters menores; se poucos, clusters maiores
    epsilon = max(0.005, min(0.02, (lat_range + lon_range) / 50))
    
    # Ajustar min_samples baseado no número de passageiros
    min_samples = max(1, len(passengers) // 25)
    
    logging.info(f"Aplicando clustering com epsilon={epsilon}, min_samples={min_samples}")
    initial_clusters = cluster_passengers_by_distance(passengers, epsilon, min_samples)
    
    # Etapa 2: Para cada cluster, otimizar a ordem dos pontos e verificar limite de tempo
    final_routes = []
    vehicle_type_index = 0
    
    # Status para o usuário
    total_clusters = len(initial_clusters)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, cluster in enumerate(initial_clusters):
        progress_percentage = (i / total_clusters)
        progress_bar.progress(progress_percentage)
        status_text.text(f"Otimizando rota {i+1}/{total_clusters} com {len(cluster)} passageiros...")
        
        # Atualizar tipo de veículo de forma cíclica
        vehicle_type = vehicle_types[vehicle_type_index % len(vehicle_types)]
        vehicle_type_index += 1
        
        if use_api and len(cluster) > 1:
            # Usar otimização com feedback da API
            try:
                api_result = optimize_route_with_api_feedback(
                    start_coord,
                    end_coord,
                    cluster,
                    max_duration_minutes,
                    vehicle_type,
                    is_arrival
                )
                
                if api_result['success']:
                    # API otimização bem-sucedida
                    optimized_waypoints = api_result['waypoints']
                    
                    # Obter tempo estimado (da API ou local)
                    estimated_time = (
                        api_result['api_estimate']['time_minutes'] 
                        if 'api_estimate' in api_result 
                        else api_result.get('estimated_time', 0)
                    )
                    
                    final_routes.append({
                        'passengers': optimized_waypoints,
                        'estimated_time': estimated_time,
                        'vehicle_type': vehicle_type,
                        'api_optimized': True
                    })
                    
                    # Exibir detalhes do resultado
                    logging.info(f"Cluster {i+1}: Rota otimizada com API, {len(optimized_waypoints)} passageiros, {estimated_time:.1f} min")
                else:
                    # API falhou em otimizar dentro do limite
                    logging.warning(f"Cluster {i+1}: Falha na otimização com API. Mensagem: {api_result['message']}")
                    
                    # Usar método de divisão de rota para garantir que fique dentro do limite
                    subroutes = divide_route_by_time_limit(
                        start_coord,
                        end_coord,
                        cluster,  # Usar cluster original para divisão
                        max_duration_minutes,
                        vehicle_type,
                        is_arrival,
                        area_type
                    )
                    
                    # Adicionar subrotas à lista final
                    for subroute in subroutes:
                        final_routes.append({
                            'passengers': subroute['passengers'],
                            'estimated_time': subroute['estimated_time'],
                            'vehicle_type': vehicle_type,
                            'api_optimized': False
                        })
                        
                    logging.info(f"Cluster {i+1} dividido em {len(subroutes)} sub-rotas")
            
            except Exception as e:
                logging.error(f"Erro ao otimizar rota usando API: {str(e)}")
                # Fallback para o método tradicional em caso de exceção
                fallback_result = fallback_route_optimization(
                    start_coord,
                    end_coord,
                    cluster,
                    max_duration_minutes,
                    vehicle_type,
                    is_arrival,
                    area_type
                )
                final_routes.extend(fallback_result)
        
        else:
            # Usar método tradicional (sem API)
            fallback_result = fallback_route_optimization(
                start_coord,
                end_coord,
                cluster,
                max_duration_minutes,
                vehicle_type,
                is_arrival,
                area_type
            )
            final_routes.extend(fallback_result)
        
        # Evitar muitas requisições API seguidas
        if use_api and i < total_clusters - 1:
            time.sleep(0.5)  # Pequena pausa entre chamadas API
    
    progress_bar.progress(1.0)  # Completar a barra de progresso
    status_text.text(f"Planejamento concluído: {len(final_routes)} rotas geradas para {len(passengers)} passageiros")
    
    # Ordenar rotas por tempo estimado (do maior para o menor)
    final_routes.sort(key=lambda x: x['estimated_time'], reverse=True)
    
    logging.info(f"Planejamento concluído: {len(final_routes)} rotas geradas para {len(passengers)} passageiros")
    return final_routes

def fallback_route_optimization(start_coord, end_coord, waypoints, max_duration_minutes, vehicle_type, is_arrival, area_type):
    """
    Método de fallback para otimização de rota quando API falha ou não é utilizada.
    Usa TSP e verificação de limite de tempo.
    
    Returns:
        Lista de rotas otimizadas
    """
    # Se o cluster for muito grande, podemos precisar dividi-lo
    optimized_route = optimize_route_order_tsp(start_coord, end_coord, waypoints)
    
    # Verificação iterativa: o cluster cabe em uma única rota?
    estimated_time = estimate_route_time(
        start_coord, 
        end_coord, 
        optimized_route, 
        vehicle_type,
        is_arrival,
        area_type
    )
    
    # Se o tempo estiver dentro do limite, adicione como uma única rota
    if estimated_time <= max_duration_minutes:
        return [{
            'passengers': optimized_route,
            'estimated_time': estimated_time,
            'vehicle_type': vehicle_type,
            'api_optimized': False
        }]
    else:
        # Dividir em subrotas que respeitam o limite de tempo
        subroutes = divide_route_by_time_limit(
            start_coord,
            end_coord,
            optimized_route,
            max_duration_minutes,
            vehicle_type,
            is_arrival,
            area_type
        )
        
        # Formatar resultado para compatibilidade
        return [{
            'passengers': subroute['passengers'],
            'estimated_time': subroute['estimated_time'],
            'vehicle_type': vehicle_type,
            'api_optimized': False
        } for subroute in subroutes]