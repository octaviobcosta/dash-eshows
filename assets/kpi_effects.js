// assets/kpi_effects.js

// Função principal que será executada quando o DOM estiver pronto
function setupKpiGraphEffects() {
    console.log("KPI Graph Effects initialized");
    
    // Aplicar efeito de pulse nos pontos do gráfico
    function applyPulseEffect() {
        // Usar MutationObserver para detectar quando o gráfico é renderizado
        const graphContainer = document.getElementById('kpi-dash-modal-graph');
        
        if (!graphContainer) return;
        
        const observer = new MutationObserver(function(mutations) {
            const dataPoints = document.querySelectorAll('#kpi-dash-modal-graph .plotly .scatter .point');
            
            if (dataPoints.length > 0) {
                console.log("Data points found:", dataPoints.length);
                
                dataPoints.forEach(point => {
                    point.addEventListener('mouseenter', function() {
                        this.style.animation = 'pulse 0.4s';
                    });
                    
                    point.addEventListener('mouseleave', function() {
                        this.style.animation = 'none';
                    });
                });
                
                // Desconecta o observer depois de encontrar os pontos
                observer.disconnect();
            }
        });
        
        // Configuração do observer
        observer.observe(graphContainer, {
            childList: true,
            subtree: true
        });
    }
    
    // Adicionar estado de loading ao abrir o modal
    function setupLoadingEffect() {
        const kpiIcons = document.querySelectorAll('[id*="kpi-dash-icon"]');
        const graphContainer = document.getElementById('kpi-dash-modal-graph');
        
        if (!graphContainer || kpiIcons.length === 0) return;
        
        console.log("Setting up loading effects for", kpiIcons.length, "KPI icons");
        
        kpiIcons.forEach(icon => {
            icon.addEventListener('click', function() {
                console.log("KPI icon clicked, applying loading effect");
                
                // Função executada quando o modal é aberto
                setTimeout(() => {
                    const graphDiv = document.getElementById('kpi-dash-modal-graph');
                    if (graphDiv) {
                        graphDiv.classList.add('loading-graph');
                        
                        // Remove a classe após o carregamento
                        setTimeout(() => {
                            graphDiv.classList.remove('loading-graph');
                            applyPulseEffect(); // Tenta aplicar o efeito de pulse após carregar
                        }, 800);
                    }
                }, 100);
            });
        });
    }
    
    // Executar as funções de setup quando o modal for aberto
    function setupModalOpenHandler() {
        // Observar mudanças no DOM para detectar quando o modal é aberto
        const bodyElement = document.body;
        
        const observer = new MutationObserver(function(mutations) {
            const modalElement = document.getElementById('kpi-dash-modal');
            
            if (modalElement && modalElement.classList.contains('show')) {
                console.log("KPI Modal detected as open");
                setupLoadingEffect();
                applyPulseEffect();
            }
        });
        
        // Iniciar a observação
        observer.observe(bodyElement, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class']
        });
    }
    
    // Iniciar tudo
    setupModalOpenHandler();
}

// Garantir que o script seja executado após o carregamento do DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupKpiGraphEffects);
} else {
    setupKpiGraphEffects();
}