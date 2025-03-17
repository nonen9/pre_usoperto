import folium
from streamlit_folium import folium_static
import streamlit as st
from folium.plugins import MarkerCluster
from branca.element import Figure, MacroElement
from jinja2 import Template
import random
import hashlib
import polyline
import logging
import requests
import os
import json
import time

def get_vehicle_type(vehicle_model):
    """
    Determina o tipo de veículo com base no modelo.
    
    Args:
        vehicle_model: String com o modelo do veículo
        
    Returns:
        String representando o tipo de veículo para a API de rotas
    """
    vehicle_model = vehicle_model.lower() if vehicle_model else ""
    
    # Detectar tipo de veículo com base em palavras-chave no modelo
    if any(keyword in vehicle_model for keyword in ["ônibus", "onibus", "bus"]):
        return "bus"
    elif any(keyword in vehicle_model for keyword in ["van", "sprint", "ducato", "boxer", "kombi"]):
        return "van"
    elif any(keyword in vehicle_model for keyword in ["caminhão", "caminhao", "truck"]):
        return "truck"
    elif any(keyword in vehicle_model for keyword in ["moto", "bike", "motorcycle"]):
        return "motorcycle"
    else:
        return "car"  # Tipo padrão

# Paleta de cores distintas para melhor diferenciação das rotas
DISTINCT_COLORS = [
    '#3366CC', '#DC3912', '#FF9900', '#109618', '#990099', 
    '#0099C6', '#DD4477', '#66AA00', '#B82E2E', '#316395', 
    '#994499', '#22AA99', '#AAAA11', '#6633CC', '#E67300', 
    '#8B0707', '#329262', '#5574A6', '#FF6347', '#4B0082'
]

# Estilos de linha para melhor diferenciação visual
LINE_STYLES = [
    {'weight': 4, 'opacity': 0.8, 'dashArray': None},     # Linha sólida
    {'weight': 4, 'opacity': 0.8, 'dashArray': '10, 10'}, # Linha tracejada
    {'weight': 4, 'opacity': 0.8, 'dashArray': '1, 10'},  # Linha pontilhada
    {'weight': 4, 'opacity': 0.8, 'dashArray': '15, 10, 1, 10'} # Traço-ponto
]

def get_color_for_route(index, route_id=None):
    """
    Obtém uma cor distinta para uma rota baseada no índice ou ID
    
    Args:
        index: Índice da rota na lista
        route_id: ID da rota (opcional, para consistência entre carregamentos)
    
    Returns:
        String com código de cor hex
    """
    # Se temos um route_id, usá-lo para gerar uma cor consistente
    if route_id:
        # Converter route_id para um índice estável na paleta de cores
        hash_val = int(hashlib.md5(str(route_id).encode()).hexdigest(), 16)
        color_idx = hash_val % len(DISTINCT_COLORS)
        return DISTINCT_COLORS[color_idx]
    
    # Caso contrário, usar o índice na lista de cores
    return DISTINCT_COLORS[index % len(DISTINCT_COLORS)]

def get_line_style(index):
    """Obtém um estilo de linha baseado no índice"""
    return LINE_STYLES[index % len(LINE_STYLES)]

def get_route_geometry(start_point, end_point, waypoints, vehicle_type="car"):
    """
    Obtém geometria real de rota da API Geoapify, garantindo que o trajeto siga ruas reais
    
    Args:
        start_point: Ponto de partida {lat, lon}
        end_point: Ponto de chegada {lat, lon}
        waypoints: Lista de waypoints intermediários [{lat, lon}, ...]
        vehicle_type: Tipo de veículo (car, bus, etc.)
        
    Returns:
        Dados da rota com coordenadas ou None se ocorrer um erro
    """
    # Verificar se temos a API key
    API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
    if not API_KEY:
        logging.warning("API key Geoapify não encontrada no ambiente. Trajeto seguirá linha reta.")
        st.warning("API key não configurada. Configure a variável de ambiente GEOAPIFY_API_KEY para obter rotas reais.")
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
    
    # Verificar pontos de entrada
    if not isinstance(start_point, dict) or not isinstance(end_point, dict):
        logging.error("Pontos de início ou fim inválidos")
        return None
        
    if 'lat' not in start_point or 'lon' not in start_point or 'lat' not in end_point or 'lon' not in end_point:
        logging.error("Pontos de início ou fim sem coordenadas lat/lon")
        return None
    
    # Processar waypoints - verificar e filtrar
    valid_waypoints = []
    if waypoints:
        for wp in waypoints:
            if isinstance(wp, dict) and 'lat' in wp and 'lon' in wp and wp['lat'] and wp['lon']:
                valid_waypoints.append(wp)
    
    # Construir a string de waypoints: início, intermediários e fim
    all_points = [start_point] + valid_waypoints + [end_point]
    waypoint_str = "|".join([f"{point['lat']},{point['lon']}" for point in all_points])
    
    # Construir URL e parâmetros para a API
    url = "https://api.geoapify.com/v1/routing"
    params = {
        "waypoints": waypoint_str,
        "mode": travel_mode,
        "details": "instruction_details,route_details",
        "apiKey": API_KEY
    }
    
    try:
        st.info(f"Solicitando rota real da API Geoapify com {len(valid_waypoints)} paradas intermediárias...")
        
        # Fazer a chamada API com retry embutido
        max_retries = 3
        retry_delay = 2  # segundos
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # Verificar se a resposta contém dados úteis
                if 'features' in data and len(data['features']) > 0:
                    feature = data['features'][0]
                    
                    # Verificar se há geometria na resposta
                    if 'geometry' in feature:
                        logging.info(f"Rota com ruas reais obtida com sucesso: {len(feature['geometry'].get('coordinates', [])) if feature['geometry'].get('type') == 'LineString' else 'MultiLineString'} pontos")
                        return data  # Retornar o objeto completo para mais flexibilidade
                    else:
                        logging.error("Resposta da API não contém geometria")
                else:
                    logging.error(f"Resposta da API sem features: {data.get('message', 'Sem mensagem')}")
                
                break  # Se chegou aqui sem exceções, sai do loop
                
            except requests.exceptions.Timeout:
                logging.warning(f"Timeout na tentativa {attempt+1}/{max_retries}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    
            except requests.exceptions.HTTPError as e:
                # Não faz retry para erros HTTP que não são de conexão
                logging.error(f"Erro HTTP na API de routing: {e}")
                break
                
            except Exception as e:
                logging.error(f"Erro inesperado na chamada à API: {e}")
                break
                
        return None  # Se chegou aqui, não conseguiu obter dados válidos
        
    except Exception as e:
        logging.error(f"Erro ao obter geometria da rota: {str(e)}")
        return None

def display_route_on_map(route_data, start_coord, end_coord, waypoints, color='blue'):
    """
    Exibe uma rota calculada em um mapa Folium, priorizando trajetos reais em ruas
    
    Args:
        route_data: Dados da rota retornados pela API
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada  
        waypoints: Lista de waypoints da rota
        color: Cor da linha da rota
    """
    # Create a folium map centered on the route area
    center_lat = (start_coord['lat'] + end_coord['lat']) / 2
    center_lon = (start_coord['lon'] + end_coord['lon']) / 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    # Add start marker com ícone e tooltip melhorados
    folium.Marker(
        location=[start_coord['lat'], start_coord['lon']],
        popup=folium.Popup("<b>Ponto de Partida</b><br>Garagem/Origem", max_width=300),
        icon=folium.Icon(color='green', icon='flag', prefix='fa'),
        tooltip="Ponto de Partida (Origem)"
    ).add_to(m)
    
    # Add end marker com ícone e tooltip melhorados
    folium.Marker(
        location=[end_coord['lat'], end_coord['lon']],
        popup=folium.Popup("<b>Ponto de Chegada</b><br>Empresa/Destino", max_width=300),
        icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa'),
        tooltip="Ponto de Chegada (Destino)"
    ).add_to(m)
    
    # Use MarkerCluster for waypoints if there are many of them
    if len(waypoints) > 10:
        marker_cluster = MarkerCluster(name="Paradas").add_to(m)
        target_group = marker_cluster
    else:
        target_group = m
    
    # Add waypoint markers
    for i, wp in enumerate(waypoints):
        popup_content = f"""
        <div style="font-family: Arial; width: 200px;">
            <h4>Parada {i+1}</h4>
            <b>Passageiro:</b> {wp.get('name', 'Não informado')}<br>
            <b>ID:</b> {wp.get('person_id', 'N/A')}
        </div>
        """
        
        folium.Marker(
            location=[wp['lat'], wp['lon']],
            popup=folium.Popup(popup_content, max_width=300),
            icon=folium.Icon(color=color, icon='user', prefix='fa'),
            tooltip=f"Parada {i+1}: {wp.get('name', 'Passageiro')}"
        ).add_to(target_group)
    
    # MUDANÇA IMPORTANTE: Primeiro buscar rota real da API para garantir trajeto em ruas
    # mesmo que já tenhamos alguns dados no route_data
    line_added = False
    
    # NOVO: Agora chamamos a API primeiro para priorizar rotas reais em ruas
    try:
        # Obter geometria real de rota com a função melhorada
        vehicle_type = route_data.get('vehicle_type', 'car')
        api_route_data = get_route_geometry(start_coord, end_coord, waypoints, vehicle_type)
        
        if api_route_data and 'features' in api_route_data and len(api_route_data['features']) > 0:
            feature = api_route_data['features'][0]
            
            if 'geometry' in feature:
                geom = feature['geometry']
                if geom['type'] == 'LineString':
                    # Get coordinates from LineString (they're in lon, lat order in GeoJSON)
                    line_coords = [(coord[1], coord[0]) for coord in geom['coordinates']]
                    
                    # Obter métricas da rota
                    distance = api_route_data.get('distance', 0)
                    if 'properties' in feature:
                        distance = feature['properties'].get('distance', distance) / 1000
                        
                    duration = api_route_data.get('time', 0)
                    if 'properties' in feature:
                        duration = feature['properties'].get('time', duration) / 60
                    
                    # Add the line to the map with the specified color
                    route_line = folium.PolyLine(
                        line_coords,
                        color=color,
                        weight=5,  # Linha mais grossa
                        opacity=0.8,
                        tooltip=f"Trajeto em ruas reais | Distância: {distance:.1f}km | Tempo: {duration:.0f}min",
                        popup=f"Distância: {distance:.1f}km | Tempo estimado: {duration:.0f}min"
                    ).add_to(m)
                    line_added = True
                    st.success("✅ Trajeto em ruas reais obtido com sucesso!")
                
                elif geom['type'] == 'MultiLineString':
                    # Processar cada segmento do MultiLineString
                    for line_segment in geom['coordinates']:
                        line_coords = [(coord[1], coord[0]) for coord in line_segment]
                        folium.PolyLine(
                            line_coords,
                            color=color,
                            weight=5,
                            opacity=0.8
                        ).add_to(m)
                    line_added = True
                    st.success("✅ Trajeto em ruas reais obtido com sucesso!")
    except Exception as e:
        st.error(f"Erro ao buscar trajeto em ruas reais: {e}")
        logging.exception("Erro ao buscar trajeto em ruas reais")
    
    # Se não conseguiu obter rota real da API, tentar extrair do route_data existente
    if not line_added and 'features' in route_data:
        for feature in route_data['features']:
            if 'geometry' in feature and feature['geometry'].get('type') in ['LineString', 'MultiLineString']:
                try:
                    if feature['geometry']['type'] == 'LineString':
                        # Get coordinates from LineString (they're in lon, lat order in GeoJSON)
                        line_coords = [(coord[1], coord[0]) for coord in feature['geometry']['coordinates']]
                        
                        # Obter métricas da rota
                        distance = route_data.get('total_distance_km', 0)
                        if distance == 0 and 'properties' in feature:
                            distance = feature['properties'].get('distance', 0) / 1000
                            
                        duration = route_data.get('total_duration_minutes', 0)
                        if duration == 0 and 'properties' in feature:
                            duration = feature['properties'].get('time', 0) / 60
                        
                        # Add the line to the map with the specified color
                        route_line = folium.PolyLine(
                            line_coords,
                            color=color,
                            weight=4,
                            opacity=0.7,
                            tooltip=f"Distância: {distance:.1f}km | Tempo: {duration:.0f}min",
                            popup=f"Distância: {distance:.1f}km | Tempo estimado: {duration:.0f}min"
                        ).add_to(m)
                        line_added = True
                    
                    elif feature['geometry']['type'] == 'MultiLineString':
                        # Processar cada segmento do MultiLineString
                        for line_segment in feature['geometry']['coordinates']:
                            line_coords = [(coord[1], coord[0]) for coord in line_segment]
                            folium.PolyLine(
                                line_coords,
                                color=color,
                                weight=4,
                                opacity=0.7
                            ).add_to(m)
                        line_added = True
                except Exception as e:
                    st.error(f"Erro ao processar geometria: {e}")
    
    # Outros métodos de fallback permanecem os mesmos
    # ...existing code...
    
    # 5. Último recurso: desenhar linhas retas apenas como fallback, com aviso claro
    if not line_added:
        try:
            all_points = []
            all_points.append([start_coord['lat'], start_coord['lon']])
            for wp in waypoints:
                all_points.append([wp['lat'], wp['lon']])
            all_points.append([end_coord['lat'], end_coord['lon']])
            
            # Adicionar linha simples conectando os pontos
            folium.PolyLine(
                all_points,
                color=color,
                weight=3,
                opacity=0.5,
                dashArray='5, 5',  # Linha tracejada para indicar que é uma estimativa
                tooltip="ATENÇÃO: Trajeto simplificado (não representa ruas reais)"
            ).add_to(m)
            
            # Adiciona um aviso claro no mapa
            warning_html = """
            <div style="position: fixed; bottom: 10px; left: 10px; z-index: 1000;
                 background-color: #ffcccc; padding: 10px; border-radius: 5px; 
                 border: 2px solid red; font-weight: bold; max-width: 300px;">
                 ⚠️ AVISO: Esta rota é uma aproximação em linha reta 
                 e NÃO representa o trajeto real em ruas!
            </div>
            """
            m.get_root().html.add_child(folium.Element(warning_html))
            
            line_added = True
            st.warning("⚠️ ATENÇÃO: Exibindo trajeto simplificado em linha reta - não representa o caminho real em ruas!")
        except Exception as e:
            st.error(f"Não foi possível renderizar nenhum trajeto: {e}")

    # Add fullscreen button
    folium.plugins.Fullscreen().add_to(m)
    
    # Add locate control
    folium.plugins.LocateControl().add_to(m)
    
    # Add measure tool
    folium.plugins.MeasureControl(position='topright', primary_length_unit='kilometers').add_to(m)
    
    # Display the map
    folium_static(m)

def display_route_map(route_data):
    """Display the route on a Folium map."""
    try:
        # Extrair coordenadas de pontos de partida, chegada e paradas
        if 'waypoints' in route_data:
            # Obter primeiro e último waypoint como pontos de partida e chegada
            waypoints = route_data['waypoints']
            if len(waypoints) >= 2:
                start_coord = {'lat': waypoints[0].get('location', [0, 0])[0], 
                              'lon': waypoints[0].get('location', [0, 0])[1]}
                end_coord = {'lat': waypoints[-1].get('location', [0, 0])[0], 
                            'lon': waypoints[-1].get('location', [0, 0])[1]}
                
                # Waypoints intermediários
                intermediate_waypoints = []
                for wp in waypoints[1:-1]:
                    if 'location' in wp:
                        intermediate_waypoints.append({
                            'lat': wp['location'][0],
                            'lon': wp['location'][1],
                            'name': wp.get('name', 'Parada')
                        })
                
                # Criar mapa
                center_lat = (start_coord['lat'] + end_coord['lat']) / 2
                center_lon = (start_coord['lon'] + end_coord['lon']) / 2
                
                m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
                
                # Adicionar marcadores
                folium.Marker(
                    location=[start_coord['lat'], start_coord['lon']],
                    popup="Ponto de Partida",
                    icon=folium.Icon(color='green', icon='play', prefix='fa')
                ).add_to(m)
                
                folium.Marker(
                    location=[end_coord['lat'], end_coord['lon']],
                    popup="Ponto de Chegada",
                    icon=folium.Icon(color='red', icon='stop', prefix='fa')
                ).add_to(m)
                
                # Adicionar paradas intermediárias
                for i, wp in enumerate(intermediate_waypoints):
                    folium.Marker(
                        location=[wp['lat'], wp['lon']],
                        popup=f"Parada {i+1}: {wp.get('name', 'Passageiro')}",
                        icon=folium.Icon(color='blue', icon='user', prefix='fa')
                    ).add_to(m)
                
                # Adicionar linha da rota
                line_added = False
                
                # 1. Tentar extrair geometria de LineString/MultiLineString
                if 'geometry' in route_data:
                    try:
                        geom = route_data['geometry']
                        if geom['type'] == 'LineString':
                            line_coords = [(coord[1], coord[0]) for coord in geom['coordinates']]
                            folium.PolyLine(
                                line_coords,
                                color='blue',
                                weight=4,
                                opacity=0.8
                            ).add_to(m)
                            line_added = True
                        elif geom['type'] == 'MultiLineString':
                            for line_segment in geom['coordinates']:
                                line_coords = [(coord[1], coord[0]) for coord in line_segment]
                                folium.PolyLine(
                                    line_coords,
                                    color='blue',
                                    weight=4,
                                    opacity=0.8
                                ).add_to(m)
                            line_added = True
                    except Exception as e:
                        st.warning(f"Erro ao processar geometria: {e}")
                
                # 2. Se não conseguiu extrair da geometria, tentar obter rota real da API
                if not line_added:
                    try:
                        # Obter geometria real de rota da API
                        route_geom = get_route_geometry(
                            start_coord,
                            end_coord,
                            intermediate_waypoints,
                            "car"  # Valor padrão
                        )
                        
                        if route_geom:
                            if route_geom['type'] == 'LineString':
                                line_coords = [(coord[1], coord[0]) for coord in route_geom['coordinates']]
                                folium.PolyLine(
                                    line_coords,
                                    color='blue',
                                    weight=4,
                                    opacity=0.8,
                                    tooltip="Rota em ruas reais (obtida da API)"
                                ).add_to(m)
                                line_added = True
                            elif route_geom['type'] == 'MultiLineString':
                                for line_segment in route_geom['coordinates']:
                                    line_coords = [(coord[1], coord[0]) for coord in line_segment]
                                    folium.PolyLine(
                                        line_coords,
                                        color='blue',
                                        weight=4,
                                        opacity=0.8
                                    ).add_to(m)
                                line_added = True
                    except Exception as e:
                        st.warning(f"Erro ao obter rota da API: {e}")
                
                # 3. Último recurso: criar linha reta conectando os pontos (com aviso)
                if not line_added:
                    route_line = []
                    route_line.append([start_coord['lat'], start_coord['lon']])
                    for wp in intermediate_waypoints:
                        route_line.append([wp['lat'], wp['lon']])
                    route_line.append([end_coord['lat'], end_coord['lon']])
                    
                    folium.PolyLine(
                        route_line,
                        color='blue',
                        weight=3,
                        opacity=0.5,
                        dashArray='5, 5',  # Linha tracejada para indicar que é uma rota estimada
                        tooltip="ATENÇÃO: Trajeto estimado (não representa ruas reais)"
                    ).add_to(m)
                    
                    # Adiciona um aviso claro no mapa
                    warning_html = """
                    <div style="position: fixed; bottom: 10px; left: 10px; z-index: 1000;
                         background-color: #ffcccc; padding: 10px; border-radius: 5px; 
                         border: 2px solid red; font-weight: bold; max-width: 300px;">
                         ⚠️ AVISO: Esta rota é uma aproximação em linha reta 
                         e NÃO representa o trajeto real em ruas!
                    </div>
                    """
                    m.get_root().html.add_child(folium.Element(warning_html))
                    
                    st.warning("⚠️ ATENÇÃO: Exibindo trajeto simplificado que não representa o caminho real em ruas!")
                
                # Exibir mapa
                folium_static(m)
            else:
                st.warning("Dados insuficientes para exibir a rota no mapa.")
        else:
            # Tenta extrair informações do formato GeoJSON
            display_route_on_map(route_data, 
                                {'lat': 0, 'lon': 0},  # Serão ignorados se houver features no route_data
                                {'lat': 0, 'lon': 0}, 
                                [])
    except Exception as e:
        st.error(f"Erro ao exibir o mapa da rota: {str(e)}")

def display_multiple_routes_on_map(routes_info, start_coord, end_coord):
    """
    Display multiple routes on the same map with different colors and styles
    for better visual distinction.
    
    Args:
        routes_info: Lista de rotas com veículos, passageiros, etc.
        start_coord: Coordenadas do ponto de partida
        end_coord: Coordenadas do ponto de chegada
    """
    # Create a folium map centered on the route area
    center_lat = (start_coord['lat'] + end_coord['lat']) / 2
    center_lon = (start_coord['lon'] + end_coord['lon']) / 2
    
    # Create a Figure object for custom height
    fig = Figure(width="100%", height=500)  # Altura fixa para visualização adequada
    m = folium.Map(location=[center_lat, center_lon], 
                  zoom_start=13, 
                  control_scale=True)  # Adiciona escala
    fig.add_child(m)
    
    # Adicionar botão de tela cheia
    folium.plugins.Fullscreen().add_to(m)
    
    # Adicionar controle de localização
    folium.plugins.LocateControl().add_to(m)
    
    # Adicionar ferramenta de medição
    folium.plugins.MeasureControl(position='topright', primary_length_unit='kilometers').add_to(m)
    
    # Add start marker with custom icon and tooltip
    folium.Marker(
        location=[start_coord['lat'], start_coord['lon']],
        popup=folium.Popup("<b>Ponto de Partida</b><br>Garagem", max_width=300),
        icon=folium.Icon(color='green', icon='play', prefix='fa'),
        tooltip="Ponto de Partida"
    ).add_to(m)
    
    # Add end marker
    folium.Marker(
        location=[end_coord['lat'], end_coord['lon']],
        popup=folium.Popup("<b>Ponto de Chegada</b><br>Empresa", max_width=300),
        icon=folium.Icon(color='red', icon='stop', prefix='fa'),
        tooltip="Ponto de Chegada"
    ).add_to(m)
    
    # Criar grupos de camadas para cada rota (permitirá mostrar/ocultar rotas)
    feature_groups = {}
    
    # Preparar conteúdo da legenda
    legend_html = """
    <div id="route-map-legend" style="position: fixed; 
                bottom: 50px; left: 10px; max-width: 250px; 
                border: 2px solid rgba(0,0,0,0.2); z-index: 1000; 
                font-size: 14px; background-color: white; 
                padding: 10px; border-radius: 5px; box-shadow: 0 1px 5px rgba(0,0,0,0.4);">
    <div style="text-align: center; font-weight: bold; margin-bottom: 5px;">Legenda de Rotas</div>
    <div style="max-height: 200px; overflow-y: auto; margin-bottom: 10px;">
    """
    
    # Add all routes to the map
    for i, route_info in enumerate(routes_info):
        route_color = get_color_for_route(i, route_info.get('route_id'))
        vehicle = route_info['vehicle']
        route_data = route_info['route_data']
        passengers = route_info['passengers']
        estimated_time = route_info.get('estimated_time', 'N/A')
        
        # Criar um grupo de features para esta rota
        group_name = f"Rota {i+1}: {vehicle['model']}"
        route_group = folium.FeatureGroup(name=group_name, show=True)
        
        # Apply line style based on index for visual distinction
        line_style = get_line_style(i)
        
        # Add route info to legend with checkbox for toggle
        vehicle_seats = vehicle.get('seats', 0)
        utilization = f"{len(passengers)}/{vehicle_seats} ({int(len(passengers)/vehicle_seats*100)}%)" if vehicle_seats else "N/A"
        
        checkbox_id = f"route-toggle-{i}"
        legend_html += f"""
        <div style="margin-bottom: 5px;">
          <input type="checkbox" id="{checkbox_id}" checked
           onchange="toggleRouteVisibility('{checkbox_id}', '{group_name}')" style="margin-right: 5px;">
          <span style="display: inline-block; width: 30px; height: 5px; background-color: {route_color}; 
                 margin-right: 5px; vertical-align: middle;"></span>
          <span><b>Veículo {i+1}:</b> {vehicle["model"]}</span>
          <div style="margin-left: 35px; font-size: 12px;">
            <span>Passageiros: {len(passengers)} | Ocupação: {utilization}</span><br>
            <span>Tempo est.: {estimated_time} min</span>
          </div>
        </div>
        """
        
        # Add waypoint markers for each route with improved popups
        marker_cluster = MarkerCluster(name=f"Paradas Rota {i+1}").add_to(route_group)
        
        for j, wp in enumerate(passengers):
            # Create rich HTML content for marker popup
            popup_content = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin-bottom: 5px;">Parada {j+1} - Rota {i+1}</h4>
                <b>Passageiro:</b> {wp.get('name', 'Não informado')}<br>
                <b>ID:</b> {wp.get('person_id', 'N/A')}<br>
                <hr style="margin: 5px 0;">
                <span style="font-size: 12px;">
                    <b>Veículo:</b> {vehicle['model']} ({vehicle['license_plate']})<br>
                    <b>Motorista:</b> {vehicle.get('driver', 'Não informado')}
                </span>
            </div>
            """
            
            folium.CircleMarker(
                location=[wp['lat'], wp['lon']],
                radius=6,
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=f"Rota {i+1} - {wp.get('name', 'Passageiro')}",
                color=route_color,
                fill=True,
                fill_color=route_color,
                fill_opacity=0.7
            ).add_to(marker_cluster)
        
        # Add route path line if available with improved styling and information
        line_added = False
        
        # Método 1: Verificar features com geometria (GeoJSON)
        if 'features' in route_data:
            for feature in route_data['features']:
                if 'geometry' in feature and feature['geometry'].get('type') in ['LineString', 'MultiLineString']:
                    try:
                        if feature['geometry']['type'] == 'LineString':
                            # Get coordinates from LineString
                            line_coords = [(coord[1], coord[0]) for coord in feature['geometry']['coordinates']]
                            
                            # Extract metrics for popup if available
                            distance = route_data.get('total_distance_km', 0)
                            if distance == 0 and 'properties' in feature:
                                # Tenta extrair dos properties
                                distance = feature['properties'].get('distance', 0) / 1000
                                
                            duration = route_data.get('total_duration_minutes', 0)
                            if duration == 0 and 'properties' in feature:
                                # Tenta extrair dos properties
                                duration = feature['properties'].get('time', 0) / 60
                            
                            # Popup content with rich information
                            route_popup = f"""
                            <div style="font-family: Arial; min-width: 200px;">
                                <h4 style="margin-bottom: 5px;">Rota {i+1}</h4>
                                <b>Veículo:</b> {vehicle['model']} ({vehicle['license_plate']})<br>
                                <b>Motorista:</b> {vehicle.get('driver', 'Não informado')}<br>
                                <b>Passageiros:</b> {len(passengers)}<br>
                                <hr style="margin: 5px 0;">
                                <b>Distância:</b> {distance:.1f} km<br>
                                
                            </div>
                            """
                            
                            # Add the line to the map with the route's color and style
                            folium.PolyLine(
                                line_coords,
                                color=route_color,
                                weight=line_style['weight'],
                                opacity=line_style['opacity'],
                                dashArray=line_style['dashArray'],
                                popup=folium.Popup(route_popup, max_width=300),
                                tooltip=f"Rota {i+1}: {vehicle['model']} - {len(passengers)} passageiros"
                            ).add_to(route_group)
                            line_added = True
                            
                        elif feature['geometry']['type'] == 'MultiLineString':
                            for line_segment in feature['geometry']['coordinates']:
                                line_coords = [(coord[1], coord[0]) for coord in line_segment]
                                folium.PolyLine(
                                    line_coords,
                                    color=route_color,
                                    weight=line_style['weight'],
                                    opacity=line_style['opacity'],
                                    dashArray=line_style['dashArray']
                                ).add_to(route_group)
                            line_added = True
                    except Exception as e:
                        st.warning(f"Erro ao processar geometria para rota {i+1}: {e}")
                            
        # Método 2: Verificar 'path' no route_data
        if not line_added and 'path' in route_data and len(route_data['path']) > 1:
            try:
                path_coords = [(p['lat'], p['lon']) for p in route_data['path']]
                
                # Extract metrics for popup
                distance = route_data.get('total_distance_km', 0)
                duration = route_data.get('total_duration_minutes', 0)
                
                # Popup content
                route_popup = f"""
                <div style="font-family: Arial; min-width: 200px;">
                    <h4 style="margin-bottom: 5px;">Rota {i+1}</h4>
                    <b>Veículo:</b> {vehicle['model']} ({vehicle['license_plate']})<br>
                    <b>Passageiros:</b> {len(passengers)}<br>
                    <hr style="margin: 5px 0;">
                    <b>Distância:</b> {distance:.1f} km<br>
                    <b>Tempo estimado:</b> {duration:.0f} min
                </div>
                """
                
                folium.PolyLine(
                    path_coords,
                    color=route_color,
                    weight=line_style['weight'],
                    opacity=line_style['opacity'],
                    dashArray=line_style['dashArray'],
                    popup=folium.Popup(route_popup, max_width=300),
                    tooltip=f"Rota {i+1}: {vehicle['model']} - {len(passengers)} passageiros"
                ).add_to(route_group)
                line_added = True
            except Exception as e:
                st.warning(f"Erro ao processar path para rota {i+1}: {e}")
        
        # Método 3: Se nenhum dos métodos anteriores funcionou, obter rota real da API
        if not line_added:
            try:
                # Extrair informações do veículo para determinar tipo
                vehicle_type = get_vehicle_type(vehicle['model']) if 'model' in vehicle else "car"
                
                # Obter geometria real da rota
                route_geom = get_route_geometry(
                    start_coord,
                    end_coord,
                    passengers,
                    vehicle_type
                )
                
                if route_geom:
                    if route_geom['type'] == 'LineString':
                        line_coords = [(coord[1], coord[0]) for coord in route_geom['coordinates']]
                        # Extract metrics for popup (usar valores default se necessário)
                        distance = route_data.get('total_distance_km', 0) 
                        duration = route_data.get('total_duration_minutes', 0)
                        
                        # Popup content
                        route_popup = f"""
                        <div style="font-family: Arial; min-width: 200px;">
                            <h4 style="margin-bottom: 5px;">Rota {i+1}</h4>
                            <b>Veículo:</b> {vehicle['model']} ({vehicle['license_plate']})<br>
                            <b>Motorista:</b> {vehicle.get('driver', 'Não informado')}<br>
                            <b>Passageiros:</b> {len(passengers)}<br>
                            <hr style="margin: 5px 0;">
                            <b>Distância:</b> {distance:.1f} km<br>
                            <b>Tempo estimado:</b> {duration:.0f} min
                        </div>
                        """
                        
                        folium.PolyLine(
                            line_coords,
                            color=route_color,
                            weight=line_style['weight'],
                            opacity=line_style['opacity'],
                            dashArray=line_style['dashArray'],
                            popup=folium.Popup(route_popup, max_width=300),
                            tooltip=f"Rota {i+1}: {vehicle['model']} - {len(passengers)} passageiros"
                        ).add_to(route_group)
                        line_added = True
                    elif route_geom['type'] == 'MultiLineString':
                        for line_segment in route_geom['coordinates']:
                            line_coords = [(coord[1], coord[0]) for coord in line_segment]
                            folium.PolyLine(
                                line_coords,
                                color=route_color,
                                weight=line_style['weight'],
                                opacity=line_style['opacity'],
                                dashArray=line_style['dashArray']
                            ).add_to(route_group)
                        line_added = True
            except Exception as e:
                st.warning(f"Erro ao obter rota da API para rota {i+1}: {e}")
        
        # Método 4: Último recurso - linhas retas com aviso
        if not line_added:
            try:
                # Conectar os pontos em ordem: início -> waypoints -> fim
                all_points = []
                all_points.append([start_coord['lat'], start_coord['lon']])
                for wp in passengers:
                    all_points.append([wp['lat'], wp['lon']])
                all_points.append([end_coord['lat'], end_coord['lon']])
                
                # Adicionar linha simples conectando os pontos com estilo tracejado
                folium.PolyLine(
                    all_points,
                    color=route_color,
                    weight=line_style['weight'],
                    opacity=0.5,  # Mais transparente para indicar que é uma estimativa
                    dashArray='5, 5',  # Linha tracejada para indicar que é uma estimativa
                    tooltip=f"ATENÇÃO: Trajeto simplificado da Rota {i+1} (não representa ruas reais)"
                ).add_to(route_group)
                
                st.warning(f"⚠️ Usando trajeto simplificado para rota {i+1} - não representa o caminho real nas ruas!")
            except Exception as e:
                st.error(f"Não foi possível renderizar trajeto para rota {i+1}: {e}")
        
        # Add the feature group to the map
        route_group.add_to(m)
        feature_groups[group_name] = route_group
    
    # Finalize a legenda HTML com JavaScript para alternância de visibilidade
    legend_html += """
    </div>
    <div style="text-align: center; margin-top: 5px;">
      <button onclick="showAllRoutes()" style="margin-right: 5px;">Mostrar Todas</button>
      <button onclick="hideAllRoutes()">Ocultar Todas</button>
    </div>
    </div>

    <script>
    function toggleRouteVisibility(checkboxId, groupName) {
        var checkbox = document.getElementById(checkboxId);
        var map = document.getElementsByClassName('folium-map')[0];
        if (!map) return;
        
        var mapObj = map['_leaflet_map'];
        if (!mapObj) return;
        
        mapObj.eachLayer(function(layer) {
            if (layer.name === groupName) {
                if (checkbox.checked) {
                    layer.addTo(mapObj);
                } else {
                    mapObj.removeLayer(layer);
                }
            }
        });
    }
    
    function showAllRoutes() {
        var checkboxes = document.querySelectorAll('[id^="route-toggle-"]');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = true;
            var groupName = checkbox.id.replace('route-toggle-', 'Rota ') + ': ';
            toggleRouteVisibility(checkbox.id, groupName);
        });
    }
    
    function hideAllRoutes() {
        var checkboxes = document.querySelectorAll('[id^="route-toggle-"]');
        checkboxes.forEach(function(checkbox) {
            checkbox.checked = false;
            var groupName = checkbox.id.replace('route-toggle-', 'Rota ') + ': ';
            toggleRouteVisibility(checkbox.id, groupName);
        });
    }
    </script>
    """
    
    # Add layer control to easily show/hide routes
    folium.LayerControl().add_to(m)
    
    # Add the custom legend
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Display the map
    folium_static(fig)

class InteractiveRouteMap:
    """
    Classe para criar mapas interativos com rotas
    que permitem mostrar/ocultar rotas e visualizar métricas
    """
    def add_route(self, route_info, index):
        """
        Adiciona uma rota ao mapa
        
        Args:
            route_info: Dados da rota
            index: Índice da rota para cores/estilos
        """
        # ...implementação para adicionar rotas...
    
    def display(self):
        """Exibe o mapa finalizado"""
        folium.LayerControl().add_to(self.map)
        folium_static(self.fig)

# Adicionar função auxiliar para extrair coordenadas de rota de diferentes formatos de API
def extract_route_coordinates(route_data):
    """
    Extrai coordenadas do trajeto de diferentes formatos de resposta da API.
    
    Args:
        route_data: Dados da rota retornados pela API
        
    Returns:
        Lista de coordenadas [lat, lon] ou None se não for possível extrair
    """
    try:
        # Método 1: GeoJSON LineString/MultiLineString em features
        if 'features' in route_data:
            for feature in route_data['features']:
                if 'geometry' in feature:
                    geom = feature['geometry']
                    if geom['type'] == 'LineString':
                        # Converter de [lon, lat] para [lat, lon]
                        return [(coord[1], coord[0]) for coord in geom['coordinates']]
                    elif geom['type'] == 'MultiLineString':
                        # Juntar todos os segmentos em uma única lista
                        coords = []
                        for segment in geom['coordinates']:
                            coords.extend([(coord[1], coord[0]) for coord in segment])
                        return coords
        
        # Método 2: 'path' com lista de objetos {lat, lon}
        if 'path' in route_data and len(route_data['path']) > 0:
            return [(p['lat'], p['lon']) for p in route_data['path']]
        
        # Método 3: Polyline codificado
        if 'polyline' in route_data and route_data['polyline']:
            try:
                import polyline
                return polyline.decode(route_data['polyline'])
            except ImportError:
                pass
            
        return None
    except Exception as e:
        logging.error(f"Erro ao extrair coordenadas da rota: {e}")
        return None