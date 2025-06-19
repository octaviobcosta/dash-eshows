/**
 * Callbacks clientside para gerenciar loading states
 * Integração com Dash para mostrar/esconder loading automaticamente
 */

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    loading: {
        /**
         * Mostra loading quando callback é iniciado
         */
        showLoadingOnStart: function(n_clicks) {
            if (n_clicks > 0) {
                window.showLoading('main-loading');
            }
            return window.dash_clientside.no_update;
        },
        
        /**
         * Esconde loading quando callback termina
         */
        hideLoadingOnComplete: function(data) {
            if (data !== undefined && data !== null) {
                window.hideLoading('main-loading');
            }
            return window.dash_clientside.no_update;
        },
        
        /**
         * Mostra skeleton nos cards de KPI enquanto carrega
         */
        showKpiSkeletons: function(loading) {
            const kpiContainers = document.querySelectorAll('.kpi-card-container');
            
            if (loading) {
                kpiContainers.forEach(container => {
                    container.dataset.originalContent = container.innerHTML;
                    container.innerHTML = window.loadingManager.createKPISkeleton();
                });
            } else {
                kpiContainers.forEach(container => {
                    if (container.dataset.originalContent) {
                        container.innerHTML = container.dataset.originalContent;
                        delete container.dataset.originalContent;
                    }
                });
            }
            
            return window.dash_clientside.no_update;
        }
    }
});