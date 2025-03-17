"""
Utilitários para trabalhar com cores em rotas e mapas
"""

import hashlib
import colorsys

# Paleta de cores distintas para melhor diferenciação de elementos visuais
DISTINCT_COLORS = [
    '#3366CC', '#DC3912', '#FF9900', '#109618', '#990099', 
    '#0099C6', '#DD4477', '#66AA00', '#B82E2E', '#316395', 
    '#994499', '#22AA99', '#AAAA11', '#6633CC', '#E67300', 
    '#8B0707', '#329262', '#5574A6', '#3B3EAC', '#B77322'
]

def get_distinct_color(index=None, identifier=None):
    """
    Obtém uma cor distinta usando índice ou identificador
    
    Args:
        index: Índice para usar com a paleta fixa (opcional)
        identifier: String ou número para gerar cor consistente (opcional)
    
    Returns:
        String no formato "#RRGGBB" com código de cor
    """
    # Se temos um identificador, usamos para gerar uma cor consistente
    if identifier is not None:
        # Gerar um hash do identificador
        hash_val = int(hashlib.md5(str(identifier).encode()).hexdigest(), 16)
        # Usar o hash para escolher uma cor da paleta
        return DISTINCT_COLORS[hash_val % len(DISTINCT_COLORS)]
    
    # Se temos um índice, usar a paleta fixa
    if index is not None:
        return DISTINCT_COLORS[index % len(DISTINCT_COLORS)]
    
    # Se não temos nem índice nem identificador, retorna uma cor padrão
    return "#3366CC"

def generate_color_palette(num_colors):
    """
    Gera uma paleta de cores visualmente distintas
    
    Args:
        num_colors: Número de cores a gerar
        
    Returns:
        Lista de cores em formato hex (#RRGGBB)
    """
    palette = []
    
    for i in range(num_colors):
        # Usar HSV para gerar cores distribuídas uniformemente pelo espectro
        h = i / num_colors
        s = 0.7 + 0.3 * ((i % 3) / 3)  # Variação de saturação (0.7-1.0)
        v = 0.7 + 0.3 * ((i % 2) / 2)  # Variação de brilho (0.7-1.0)
        
        # Converter HSV para RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        
        # Converter RGB para hex
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )
        
        palette.append(hex_color)
    
    return palette
