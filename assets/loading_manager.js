/**
 * Loading Manager para Dashboard eShows
 * Gerencia estados de loading e animações
 */

// Frases de loading
const loadingPhrases = [
    "🎸 Afinando os instrumentos...",
    "🎤 Testando o som...",
    "🎵 Organizando o setlist...",
    "🎪 Montando o palco...",
    "✨ Ajustando as luzes...",
    "📊 Calculando as métricas do show...",
    "🎫 Conferindo os ingressos...",
    "🎶 O show já vai começar!",
    "🌟 Preparando uma performance incrível...",
    "🎭 Aquecendo para o grande espetáculo...",
    "📈 Analisando o público...",
    "🎯 Sincronizando os dados do evento...",
    "🔊 Equalizando o áudio...",
    "🎨 Preparando o visual...",
    "📋 Verificando o rider técnico...",
    "🎼 Ensaiando os últimos detalhes...",
    "🚀 Quase tudo pronto para o show!",
    "💫 Criando a magia do espetáculo..."
];

// Gerenciador de loading
class LoadingManager {
    constructor() {
        this.activeLoadings = new Set();
        this.phraseInterval = null;
        this.currentPhraseIndex = 0;
    }

    /**
     * Mostra o loading overlay
     * @param {string} loadingId - ID do loading
     * @param {string} customText - Texto customizado (opcional)
     */
    show(loadingId = 'main-loading', customText = null) {
        const overlay = document.getElementById(loadingId);
        if (!overlay) return;

        this.activeLoadings.add(loadingId);
        overlay.style.display = 'flex';
        
        // Fade in suave
        setTimeout(() => {
            overlay.style.opacity = '1';
        }, 10);

        // Se não houver texto customizado, inicia rotação de frases
        if (!customText) {
            this.startPhraseRotation(loadingId);
        } else {
            const textElement = document.getElementById(`${loadingId}-text`);
            if (textElement) {
                textElement.textContent = customText;
            }
        }
    }

    /**
     * Esconde o loading overlay
     * @param {string} loadingId - ID do loading
     */
    hide(loadingId = 'main-loading') {
        const overlay = document.getElementById(loadingId);
        if (!overlay) return;

        // Fade out suave
        overlay.style.opacity = '0';
        
        setTimeout(() => {
            overlay.style.display = 'none';
            this.activeLoadings.delete(loadingId);
            
            // Para rotação de frases se não houver mais loadings ativos
            if (this.activeLoadings.size === 0) {
                this.stopPhraseRotation();
            }
        }, 300);
    }

    /**
     * Inicia rotação de frases
     * @param {string} loadingId - ID do loading
     */
    startPhraseRotation(loadingId) {
        const textElement = document.getElementById(`${loadingId}-text`);
        if (!textElement) return;

        // Define frase inicial
        textElement.textContent = loadingPhrases[this.currentPhraseIndex];

        // Limpa intervalo anterior se existir
        if (this.phraseInterval) {
            clearInterval(this.phraseInterval);
        }

        // Rotaciona frases a cada 3 segundos
        this.phraseInterval = setInterval(() => {
            this.currentPhraseIndex = (this.currentPhraseIndex + 1) % loadingPhrases.length;
            
            // Fade out
            textElement.style.opacity = '0';
            
            setTimeout(() => {
                textElement.textContent = loadingPhrases[this.currentPhraseIndex];
                // Fade in
                textElement.style.opacity = '1';
            }, 300);
        }, 3000);
    }

    /**
     * Para rotação de frases
     */
    stopPhraseRotation() {
        if (this.phraseInterval) {
            clearInterval(this.phraseInterval);
            this.phraseInterval = null;
        }
    }

    /**
     * Mostra loading inline para elementos específicos
     * @param {string} elementId - ID do elemento
     */
    showInlineLoading(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        element.classList.add('loading');
        
        // Adiciona spinner se for botão
        if (element.tagName === 'BUTTON') {
            element.classList.add('btn-loading');
            element.disabled = true;
        }
    }

    /**
     * Esconde loading inline
     * @param {string} elementId - ID do elemento
     */
    hideInlineLoading(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        element.classList.remove('loading', 'btn-loading');
        
        if (element.tagName === 'BUTTON') {
            element.disabled = false;
        }
    }

    /**
     * Substitui conteúdo por skeleton
     * @param {string} containerId - ID do container
     * @param {string} skeletonType - Tipo de skeleton (kpi, chart, table)
     */
    showSkeleton(containerId, skeletonType = 'kpi') {
        const container = document.getElementById(containerId);
        if (!container) return;

        // Guarda conteúdo original
        container.dataset.originalContent = container.innerHTML;

        // Adiciona skeleton baseado no tipo
        let skeletonHTML = '';
        
        switch(skeletonType) {
            case 'kpi':
                skeletonHTML = this.createKPISkeleton();
                break;
            case 'chart':
                skeletonHTML = this.createChartSkeleton();
                break;
            case 'table':
                skeletonHTML = this.createTableSkeleton();
                break;
        }

        container.innerHTML = skeletonHTML;
    }

    /**
     * Remove skeleton e restaura conteúdo
     * @param {string} containerId - ID do container
     */
    hideSkeleton(containerId) {
        const container = document.getElementById(containerId);
        if (!container || !container.dataset.originalContent) return;

        container.innerHTML = container.dataset.originalContent;
        delete container.dataset.originalContent;
    }

    /**
     * Cria HTML do skeleton de KPI
     */
    createKPISkeleton() {
        return `
            <div class="skeleton-kpi-card">
                <div class="skeleton-content shimmer">
                    <div class="skeleton-line skeleton-title"></div>
                    <div class="skeleton-line skeleton-value"></div>
                    <div class="skeleton-line skeleton-description"></div>
                </div>
            </div>
        `;
    }

    /**
     * Cria HTML do skeleton de gráfico
     */
    createChartSkeleton() {
        return `
            <div class="skeleton-chart">
                <div class="skeleton-line skeleton-chart-title shimmer"></div>
                <div class="skeleton-chart-area shimmer">
                    <div class="skeleton-chart-bars"></div>
                </div>
            </div>
        `;
    }

    /**
     * Cria HTML do skeleton de tabela
     */
    createTableSkeleton() {
        return `
            <div class="skeleton-table">
                <div class="skeleton-content shimmer">
                    <div class="skeleton-line skeleton-header"></div>
                    <div class="skeleton-line skeleton-row"></div>
                    <div class="skeleton-line skeleton-row"></div>
                    <div class="skeleton-line skeleton-row"></div>
                </div>
            </div>
        `;
    }
}

// Instância global do gerenciador
window.loadingManager = new LoadingManager();

// Helpers para facilitar o uso
window.showLoading = (loadingId, customText) => window.loadingManager.show(loadingId, customText);
window.hideLoading = (loadingId) => window.loadingManager.hide(loadingId);
window.showInlineLoading = (elementId) => window.loadingManager.showInlineLoading(elementId);
window.hideInlineLoading = (elementId) => window.loadingManager.hideInlineLoading(elementId);

// Intercepta callbacks do Dash para adicionar loading automático
if (window.dash_clientside) {
    const originalCallback = window.dash_clientside.callback;
    
    window.dash_clientside.callback = function(...args) {
        const result = originalCallback.apply(this, args);
        
        // Adiciona loading automático para callbacks
        return function(...callbackArgs) {
            // Mostra loading
            window.showLoading('main-loading');
            
            // Executa callback original
            const callbackResult = result.apply(this, callbackArgs);
            
            // Se for promise, esconde loading quando completar
            if (callbackResult && typeof callbackResult.then === 'function') {
                callbackResult.then(() => {
                    window.hideLoading('main-loading');
                }).catch(() => {
                    window.hideLoading('main-loading');
                });
            } else {
                // Esconde loading após pequeno delay
                setTimeout(() => {
                    window.hideLoading('main-loading');
                }, 100);
            }
            
            return callbackResult;
        };
    };
}