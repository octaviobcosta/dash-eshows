# Correção para o arquivo custom_components.py
# Removido o atributo scrolling que não é suportado

from dash import html

def create_gauge_component(value=50, title="Meta Geral", min_value=0, max_value=100, id="custom-gauge"):
    """
    Cria um componente de medidor semicircular com gradiente de cores e ponteiro dinâmico.
    
    Args:
        value (float): Valor atual do medidor (0-100)
        title (str): Título do medidor
        min_value (int): Valor mínimo da escala (padrão: 0)
        max_value (int): Valor máximo da escala (padrão: 100)
        id (str): ID do componente para referência no DOM
        
    Returns:
        dash.html.Iframe: Componente Iframe contendo o medidor SVG
    """
    # Certifica-se de que o valor está entre 0 e 100 para cálculos
    value_percent = min(max(value, min_value), max_value)
    value_percent = ((value_percent - min_value) / (max_value - min_value)) * 100
    
    # Cálculo do ângulo de rotação para o ponteiro (-90 para iniciar na esquerda, +180 para o arco completo)
    angle = -90 + (value_percent * 1.8)
    
    # Cálculo do comprimento do arco para o stroke-dasharray
    # O arco completo tem um perímetro de aproximadamente 377 (π * diâmetro / 2)
    arc_length = value_percent * 3.77
    
    # Espessura do arco: 24 pixels
    stroke_width = 24
    
    # Define a cor do ponteiro baseada no valor
    needle_color = "#FF3366"  # Cor padrão (vermelho)
    if value_percent > 70:
        needle_color = "#009933"  # Verde
    elif value_percent > 40:
        needle_color = "#FFCC33"  # Amarelo
    
    # Definição de cores para o gradiente
    gauge_script = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
                background-color: transparent;
            }}
            svg {{
                width: 100%;
                height: 100%;
                display: block;
            }}
        </style>
    </head>
    <body>
        <svg id="{id}" width="100%" height="100%" viewBox="0 0 400 300">
            <!-- Definição do gradiente de cores -->
            <defs>
                <linearGradient id="gauge-gradient" x1="0%" y1="0%" x2="100%" y1="0%">
                    <stop offset="0%" stop-color="#FF3366" />
                    <stop offset="20%" stop-color="#FF6633" />
                    <stop offset="40%" stop-color="#FFCC33" />
                    <stop offset="60%" stop-color="#66CC33" />
                    <stop offset="100%" stop-color="#009933" />
                </linearGradient>
                <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="1" dy="1" stdDeviation="2" flood-color="rgba(0,0,0,0.3)" />
                </filter>
            </defs>
            
            <!-- Arco de fundo (trilho neutro) -->
            <path d="M40,250 A 160,160 0 0,1 360,250" 
                  fill="none" 
                  stroke="#F3F4F6" 
                  stroke-width="{stroke_width}" 
                  stroke-linecap="round"/>

            <!-- Arco de progresso colorido -->
            <path d="M40,250 A 160,160 0 0,1 360,250" 
                  fill="none" 
                  stroke="url(#gauge-gradient)" 
                  stroke-width="{stroke_width}" 
                  stroke-linecap="round" 
                  stroke-dasharray="{arc_length} 377"/>

            <!-- Valores percentuais (rótulos) -->
            <text x="35" y="280" 
                  font-family="Inter, sans-serif" 
                  font-size="14" 
                  fill="#6B7280" 
                  text-anchor="start">{min_value}</text>
                  
            <text x="365" y="280" 
                  font-family="Inter, sans-serif" 
                  font-size="14" 
                  fill="#6B7280" 
                  text-anchor="end">{max_value}</text>

            <!-- Grupo do ponteiro com rotação -->
            <g transform="translate(200, 250) rotate({angle})">
                <!-- Sombra do ponteiro -->
                <path d="M-4,0 L0,-90 L4,0 Z" 
                      fill="rgba(0,0,0,0.2)" 
                      transform="translate(1.5,1.5)"
                      filter="url(#shadow)"/>
                      
                <!-- Ponteiro principal -->
                <path d="M-6,0 L0,-90 L6,0 Z" 
                      fill="{needle_color}"/>
                      
                <!-- Base do ponteiro -->
                <circle cx="0" cy="0" r="10" 
                        fill="{needle_color}" />
                        
                <!-- Reflexo na base -->
                <circle cx="-3" cy="-3" r="5" 
                        fill="rgba(255,255,255,0.6)" />
            </g>

            <!-- Borda branca ao redor do medidor -->
            <path d="M40,250 A 160,160 0 0,1 360,250" 
                  fill="none" 
                  stroke="white" 
                  stroke-width="1" 
                  stroke-linecap="round"/>

            <!-- Texto do valor -->
            <text x="200" y="220" 
                  text-anchor="middle" 
                  font-family="Inter, sans-serif" 
                  font-size="28" 
                  font-weight="bold" 
                  fill="#1F2937">{value:.1f}%</text>
                  
            <!-- Título -->
            <text x="200" y="180" 
                  text-anchor="middle" 
                  font-family="Inter, sans-serif" 
                  font-size="20" 
                  fill="#4B5563">{title}</text>
        </svg>
    </body>
    </html>
    """
    
    # Retorna o iframe sem o atributo scrolling (conforme pedido)
    from dash import html
    return html.Iframe(
        srcDoc=gauge_script,
        style={
            "width": "400px",
            "height": "300px",
            "border": "none",
            "overflow": "hidden",
            "background": "transparent"
        },
        id=id + "-wrapper"
    )
    """
    Cria um componente de medidor semicircular com gradiente de cores e ponteiro dinâmico.
    
    Args:
        value (int): Valor atual do medidor (0-100)
        title (str): Título do medidor
        min_value (int): Valor mínimo da escala (padrão: 0)
        max_value (int): Valor máximo da escala (padrão: 100)
        id (str): ID do componente para referência no DOM
        
    Returns:
        dash.html.Iframe: Componente Iframe contendo o medidor SVG
    """
    # Certifica-se de que o valor está entre 0 e 100 para cálculos
    value_percent = min(max(value, min_value), max_value)
    value_percent = ((value_percent - min_value) / (max_value - min_value)) * 100
    
    # Cálculo do ângulo de rotação para o ponteiro (-90 para iniciar na esquerda, +180 para o arco completo)
    angle = -90 + (value_percent * 1.8)
    
    # Cálculo do comprimento do arco para o stroke-dasharray
    # O arco completo tem um perímetro de aproximadamente 377 (π * diâmetro / 2)
    arc_length = value_percent * 3.77
    
    # AUMENTO DA ESPESSURA DO ARCO: alterado de 16 para 24 pixels
    stroke_width = 24
    
    # Definição de cores para o gradiente
    gauge_script = f"""
    <div id="{id}-container" style="width: 100%; height: 100%; position: relative;">
        <svg id="{id}" width="100%" height="100%" viewBox="0 0 400 300">
            <!-- Definição do gradiente de cores -->
            <defs>
                <linearGradient id="gauge-gradient" x1="0%" y1="0%" x2="100%" y1="0%">
                    <stop offset="0%" stop-color="#FF3366" />
                    <stop offset="20%" stop-color="#FF6633" />
                    <stop offset="40%" stop-color="#FFCC33" />
                    <stop offset="60%" stop-color="#66CC33" />
                    <stop offset="100%" stop-color="#009933" />
                </linearGradient>
            </defs>
            
            <!-- Arco de fundo (trilho neutro) - ESPESSURA AUMENTADA -->
            <path d="M40,250 A 160,160 0 0,1 360,250" 
                  fill="none" 
                  stroke="#F3F4F6" 
                  stroke-width="{stroke_width}" 
                  stroke-linecap="round"/>

            <!-- Arco de progresso colorido - mesma espessura do fundo -->
            <path id="{id}-progress" 
                  d="M40,250 A 160,160 0 0,1 360,250" 
                  fill="none" 
                  stroke="url(#gauge-gradient)" 
                  stroke-width="{stroke_width}" 
                  stroke-linecap="round" 
                  stroke-dasharray="{arc_length} 377"/>

            <!-- Valores percentuais (rótulos) -->
            <text x="35" y="280" 
                  font-family="Inter, sans-serif" 
                  font-size="14" 
                  fill="#6B7280" 
                  text-anchor="start">{min_value}</text>
                  
            <text x="365" y="280" 
                  font-family="Inter, sans-serif" 
                  font-size="14" 
                  fill="#6B7280" 
                  text-anchor="end">{max_value}</text>

            <!-- Ponteiro -->
            <g id="{id}-needle" transform="translate(200, 250) rotate({angle})">
                <!-- Sombra do ponteiro - efeito 3D -->
                <path d="M-4,0 L0,-90 L4,0 Z" 
                      fill="rgba(0,0,0,0.2)" 
                      transform="translate(1.5,1.5)"/>
                      
                <!-- Ponteiro principal - aproximadamente 4% do raio na base -->
                <path d="M-6,0 L0,-90 L6,0 Z" 
                      fill="#FF3366"/>
                      
                <!-- Base do ponteiro - 6-8% do raio -->
                <circle cx="0" cy="0" r="10" 
                        fill="#FF3366" />
                        
                <!-- Reflexo na base - efeito 3D -->
                <circle cx="-3" cy="-3" r="5" 
                        fill="rgba(255,255,255,0.6)" />
            </g>

            <!-- Borda branca ao redor do medidor - efeito 3D -->
            <path d="M40,250 A 160,160 0 0,1 360,250" 
                  fill="none" 
                  stroke="white" 
                  stroke-width="1" 
                  stroke-linecap="round"
                  filter="drop-shadow(0px 1px 2px rgba(0,0,0,0.2))"/>

            <!-- Texto do valor e título -->
            <text x="200" y="220" 
                  text-anchor="middle" 
                  font-family="Inter, sans-serif" 
                  font-size="28" 
                  font-weight="bold" 
                  fill="#1F2937">{value}%</text>
                  
            <text x="200" y="180" 
                  text-anchor="middle" 
                  font-family="Inter, sans-serif" 
                  font-size="20" 
                  fill="#4B5563">{title}</text>
        </svg>
    </div>
    """
    
    # REMOÇÃO DA BARRA DE ROLAGEM: sem o atributo scrolling, apenas estilos CSS
    return html.Iframe(
        srcDoc=gauge_script,
        style={
            "width": "400px",
            "height": "300px",
            "border": "none",
            "overflow": "hidden",
            "background": "transparent"
        },
        id=id + "-wrapper"
    )