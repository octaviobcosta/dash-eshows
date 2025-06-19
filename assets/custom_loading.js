/**
 * Script para adicionar loading em ações específicas
 * Monitora mudanças e mostra loading automaticamente
 */

// Aguarda um pouco para garantir que tudo está carregado
window.addEventListener('load', function() {
    // Pequeno delay para garantir que o Dash terminou de renderizar
    setTimeout(function() {
    // Monitora cliques em botões específicos
    const loadingButtons = [
        { selector: '#upload-csv-button', message: '📊 Processando arquivo CSV...' },
        { selector: '#validate-button', message: '🔍 Validando dados...' },
        { selector: '#process-button', message: '🎯 Atualizando base de dados...' },
        { selector: '.kpi-dash-icon', message: '📈 Calculando métricas...' },
        { selector: '#export-button', message: '📥 Preparando exportação...' }
    ];
    
    loadingButtons.forEach(({ selector, message }) => {
        document.addEventListener('click', function(e) {
            const target = e.target.closest(selector);
            if (target && window.loadingManager) {
                window.loadingManager.show('main-loading', message);
                
                // Auto-hide após 10 segundos como fallback
                setTimeout(() => {
                    window.loadingManager.hide('main-loading');
                }, 10000);
            }
        });
    });
    
    // Monitora mudanças em dropdowns principais
    const dropdowns = ['dashboard-ano-dropdown', 'dashboard-periodo-dropdown', 'dashboard-mes-dropdown'];
    
    dropdowns.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', function() {
                if (window.loadingManager) {
                    window.loadingManager.show('main-loading');
                }
            });
        }
    });
    
    // Adiciona loading para navegação entre páginas
    const navLinks = document.querySelectorAll('a[href^="/"]');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            const href = link.getAttribute('href');
            if (href && href !== window.location.pathname && window.loadingManager) {
                const messages = {
                    '/dashboard': '🎸 Preparando o Dashboard...',
                    '/indicadores': '📊 Carregando Indicadores...',
                    '/okrs': '🎯 Sincronizando OKRs...',
                    '/': '🏠 Voltando ao início...'
                };
                
                const message = messages[href] || '🎵 Carregando...';
                window.loadingManager.show('main-loading', message);
            }
        });
    });
    }, 1000); // Aguarda 1 segundo
});

// Intercepta respostas do Dash para esconder loading
if (window.dash_clientside) {
    const originalSetProps = window.dash_clientside.set_props;
    
    window.dash_clientside.set_props = function(id, props) {
        // Chama função original
        const result = originalSetProps.apply(this, arguments);
        
        // Esconde loading quando componentes são atualizados
        if (window.loadingManager) {
            // Pequeno delay para garantir que a UI foi atualizada
            setTimeout(() => {
                window.loadingManager.hide('main-loading');
            }, 300);
        }
        
        return result;
    };
}