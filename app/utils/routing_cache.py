"""
Utilitário para cache de solicitações de rotas para reduzir chamadas à API
"""
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
import hashlib

class RoutingCache:
    """
    Cache para armazenar resultados de roteamento e reduzir chamadas à API
    """
    
    def __init__(self, cache_dir=None, max_age_hours=24):
        """
        Inicializa o cache de rotas
        
        Args:
            cache_dir: Diretório para armazenar os arquivos de cache
            max_age_hours: Tempo máximo em horas para considerar um cache válido
        """
        if cache_dir is None:
            # Usar diretório padrão na pasta do app
            self.cache_dir = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cache'))
        else:
            self.cache_dir = Path(cache_dir)
        
        # Garantir que o diretório de cache existe
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_age_seconds = max_age_hours * 3600
        
        logging.info(f"Cache de rotas inicializado em: {self.cache_dir}")
    
    def get(self, cache_key):
        """
        Recupera dados do cache, se disponíveis e dentro do prazo de validade
        
        Args:
            cache_key: Chave única para identificar a entrada de cache
            
        Returns:
            Dados da rota ou None se não encontrados ou expirados
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            # Verificar idade do cache
            file_age = time.time() - os.path.getmtime(cache_file)
            
            # Se o arquivo é muito antigo, ignorar
            if file_age > self.max_age_seconds:
                logging.info(f"Cache expirado para {cache_key} (idade: {file_age / 3600:.1f}h)")
                return None
            
            # Ler e retornar dados do cache
            with cache_file.open('r') as f:
                data = json.load(f)
                logging.info(f"Cache encontrado para {cache_key} (idade: {file_age / 60:.1f}min)")
                return data
                
        except Exception as e:
            logging.error(f"Erro ao ler cache {cache_key}: {e}")
            return None
    
    def set(self, cache_key, data):
        """
        Armazena dados no cache
        
        Args:
            cache_key: Chave única para identificar a entrada de cache
            data: Dados a serem armazenados
            
        Returns:
            True se conseguiu armazenar, False em caso de erro
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with cache_file.open('w') as f:
                json.dump(data, f)
            logging.info(f"Cache salvo para {cache_key}")
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar cache {cache_key}: {e}")
            return False
    
    def create_key(self, start_point, end_point, waypoints, mode="drive"):
        """
        Cria uma chave de cache baseada nos parâmetros da rota
        
        Args:
            start_point: Ponto de partida {lat, lon}
            end_point: Ponto de chegada {lat, lon}
            waypoints: Lista de waypoints [{lat, lon}, ...]
            mode: Modo de transporte
            
        Returns:
            String única para esta solicitação
        """
        # Simplificar os pontos para a chave de cache (reduzir precisão para 5 casas decimais)
        def simplify_point(point):
            if isinstance(point, dict) and 'lat' in point and 'lon' in point:
                return f"{round(point['lat'], 5)},{round(point['lon'], 5)}"
            return "0,0"
        
        start_str = simplify_point(start_point)
        end_str = simplify_point(end_point)
        
        # Reduzir waypoints para no máximo 10 para a chave (evitar chaves muito longas)
        if len(waypoints) > 10:
            # Selecionar pontos em intervalos regulares
            step = len(waypoints) // 10
            sampled_waypoints = [waypoints[i] for i in range(0, len(waypoints), step)][:10]
        else:
            sampled_waypoints = waypoints
        
        waypoints_str = "|".join(simplify_point(wp) for wp in sampled_waypoints)
        
        # Criar hash como chave de cache
        key_str = f"{start_str}_{waypoints_str}_{end_str}_{mode}"
        hash_key = hashlib.md5(key_str.encode()).hexdigest()
        
        return hash_key
