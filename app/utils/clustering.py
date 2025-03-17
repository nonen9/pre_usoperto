import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from typing import List, Dict, Any, Tuple
import logging
from geopy.distance import great_circle
from sklearn.metrics import pairwise_distances

def cluster_by_location(coordinates: List[Dict[str, Any]], num_clusters: int) -> List[int]:
    """
    Agrupa pontos em clusters com base em suas coordenadas geográficas
    usando o algoritmo K-means.
    
    Args:
        coordinates: Lista de dicionários, cada um contendo 'lat', 'lon' e outros dados
        num_clusters: Número de clusters a serem criados
        
    Returns:
        Lista com o índice do cluster para cada ponto na entrada
    """
    if not coordinates:
        return []
    
    if len(coordinates) < num_clusters:
        # Se temos menos pontos que clusters, cada ponto vai para seu próprio cluster
        return list(range(len(coordinates)))
    
    # Extrair coordenadas para o algoritmo
    points = np.array([[point['lat'], point['lon']] for point in coordinates])
    
    # Aplicar K-means para agrupar os pontos
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    cluster_indices = kmeans.fit_predict(points)
    
    return cluster_indices.tolist()

def cluster_by_dbscan(coordinates: List[Dict[str, Any]], eps_km: float = 1.0, min_samples: int = 3) -> List[int]:
    """
    Agrupa pontos em clusters com base em suas coordenadas geográficas usando DBSCAN.
    
    Args:
        coordinates: Lista de dicionários, cada um contendo 'lat', 'lon'
        eps_km: Distância máxima (em km) entre dois pontos para serem considerados vizinhos
        min_samples: Número mínimo de pontos para formar um cluster
        
    Returns:
        Lista com o índice do cluster para cada ponto na entrada (-1 indica ruído)
    """
    if not coordinates:
        return []
    
    # Extrair coordenadas
    points = np.array([[point['lat'], 'lon']] for point in coordinates)
    
    # Calcular matriz de distância usando great_circle (distância em km)
    n = len(points)
    distance_matrix = np.zeros((n, n))
    
    for i in range(n):
        for j in range(i+1, n):
            coord1 = (points[i][0], points[i][1])
            coord2 = (points[j][0], points[j][1])
            distance_km = great_circle(coord1, coord2).kilometers
            distance_matrix[i, j] = distance_matrix[j, i] = distance_km
    
    # Aplicar DBSCAN com a matriz de distância personalizada
    dbscan = DBSCAN(eps=eps_km, min_samples=min_samples, metric='precomputed')
    cluster_indices = dbscan.fit_predict(distance_matrix)
    
    return cluster_indices.tolist()

def cluster_passengers_for_vehicles(passengers: List[Dict[str, Any]], 
                                   vehicles: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Agrupa passageiros por proximidade e atribui a veículos específicos.
    
    Args:
        passengers: Lista de dicionários com informações dos passageiros
        vehicles: Lista de veículos disponíveis com capacidade
        
    Returns:
        Lista de listas, onde cada lista interna contém os passageiros para um veículo
    """
    if not passengers or not vehicles:
        return []
    
    # Determinar o número de clusters com base no número de veículos
    num_clusters = len(vehicles)
    
    # Se temos apenas um veículo, todos os passageiros vão nele
    if num_clusters == 1:
        return [passengers]
    
    # Agrupar passageiros por proximidade
    cluster_labels = cluster_by_location(passengers, num_clusters)
    
    # Criar listas de passageiros por cluster
    clusters = [[] for _ in range(num_clusters)]
    for i, label in enumerate(cluster_labels):
        clusters[label].append(passengers[i])
    
    # Ordenar clusters por tamanho (do maior para o menor)
    clusters.sort(key=len, reverse=True)
    
    # Ordenar veículos por capacidade (do maior para o menor)
    sorted_vehicles = sorted(vehicles, key=lambda v: v['seats'], reverse=True)
    
    # Verificar e ajustar capacidades
    result_clusters = []
    
    for i, (cluster, vehicle) in enumerate(zip(clusters, sorted_vehicles)):
        vehicle_capacity = vehicle['seats']
        
        if len(cluster) <= vehicle_capacity:
            # O veículo comporta todos os passageiros do cluster
            result_clusters.append({
                'vehicle': vehicle,
                'passengers': cluster
            })
        else:
            # Dividir o cluster em vários veículos
            for j in range(0, len(cluster), vehicle_capacity):
                if i + j < len(sorted_vehicles):
                    result_clusters.append({
                        'vehicle': sorted_vehicles[i + j],
                        'passengers': cluster[j:j + vehicle_capacity]
                    })
                else:
                    # Se ficaram passageiros sem veículos, adicionar a um veículo existente
                    logging.warning(f"{len(cluster) - j} passageiros não puderam ser alocados a novos veículos")
                    break
    
    return result_clusters

def optimize_clusters_by_proximity(passengers, vehicles, company_coord, force_include_all=False):
    """
    Optimizes clusters based on proximity and assigns them to vehicles.
    
    Args:
        passengers: List of dictionaries, each with 'lat', 'lon', 'person_id', 'name'
        vehicles: List of dictionaries with vehicle info, including 'seats' (seats capacity)
        company_coord: Dictionary with 'lat' and 'lon' of the company
        force_include_all: If True, ensures all passengers are included in a cluster
    
    Returns:
        Dictionary with cluster assignments and vehicle assignments
    """
    if not passengers or not vehicles:
        return "Não há passageiros ou veículos suficientes para criar clusters"
    
    # Calculate total capacity across all vehicles
    total_capacity = sum(vehicle['seats'] for vehicle in vehicles)
    
    # Check if we have enough capacity for all passengers
    if len(passengers) > total_capacity and not force_include_all:
        return f"Capacidade insuficiente: {len(passengers)} passageiros para {total_capacity} lugares"
    
    # Extract coordinates for clustering
    coords = np.array([[p['lat'], p['lon']] for p in passengers])
    
    # Reference point (company location) for distance calculation
    company_point = np.array([[company_coord['lat'], company_coord['lon']]])
    
    # Calculate distances from company to each passenger
    distances_to_company = pairwise_distances(coords, company_point).flatten()
    
    # Sort passengers by distance from company
    sorted_indices = np.argsort(distances_to_company)
    sorted_passengers = [passengers[i] for i in sorted_indices]
    
    # Determine number of clusters
    num_clusters = min(len(vehicles), len(passengers))
    
    # Initialize clusters
    vehicle_assignments = {}
    for i, vehicle in enumerate(vehicles):
        if i < num_clusters:
            vehicle_assignments[vehicle['id']] = {
                'vehicle': vehicle,
                'passengers': [],
                'current_load': 0
            }
    
    # Assign passengers to vehicles based on capacity and proximity
    for passenger in sorted_passengers:
        # Find best vehicle with available capacity
        best_vehicle_id = None
        min_distance = float('inf')
        
        for vehicle_id, data in vehicle_assignments.items():
            if data['current_load'] < data['vehicle']['seats'] or force_include_all:
                # Calculate distance from this passenger to all others in the vehicle
                if not data['passengers']:
                    # If no passengers yet, use distance to company
                    passenger_point = np.array([[passenger['lat'], passenger['lon']]])
                    company_point = np.array([[company_coord['lat'], company_coord['lon']]])
                    dist = pairwise_distances(passenger_point, company_point).flatten()[0]
                else:
                    # Calculate average distance to other passengers
                    other_points = np.array([[p['lat'], p['lon']] for p in data['passengers']])
                    passenger_point = np.array([[passenger['lat'], passenger['lon']]])
                    dist = np.mean(pairwise_distances(passenger_point, other_points).flatten())
                
                if dist < min_distance:
                    min_distance = dist
                    best_vehicle_id = vehicle_id
        
        if best_vehicle_id:
            vehicle_assignments[best_vehicle_id]['passengers'].append(passenger)
            vehicle_assignments[best_vehicle_id]['current_load'] += 1
    
    # If force_include_all is True and we couldn't fit all passengers,
    # distribute remaining passengers to vehicles regardless of capacity
    if force_include_all:
        unassigned = [p for p in sorted_passengers if all(p not in data['passengers'] for _, data in vehicle_assignments.items())]
        if unassigned:
            for passenger in unassigned:
                # Find vehicle with lowest load
                min_load_vehicle_id = min(vehicle_assignments.keys(), 
                                        key=lambda vid: vehicle_assignments[vid]['current_load'])
                vehicle_assignments[min_load_vehicle_id]['passengers'].append(passenger)
                vehicle_assignments[min_load_vehicle_id]['current_load'] += 1
    
    return {
        'vehicle_assignments': vehicle_assignments,
        'total_passengers': len(passengers)
    }
