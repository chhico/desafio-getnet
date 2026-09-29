// Base da API relativa (agnóstica de porta, host ou protocolo)
// Permite override opcional via window.__API_BASE__ se necessário
const API_BASE = window.__API_BASE__ || "/api/v1";

/**
 * Wrapper centralizado para fetch API.
 * Lida com respostas JSON e erros amigáveis.
 */
const apiFetch = async (endpoint, options = {}) => {
    // Default headers
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    const config = {
        ...options,
        headers
    };

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = errData.detail || errData.message || `Erro do Servidor (${response.status})`;
            throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg));
        }

        return await response.json();
    } catch (error) {
        console.error("API Error:", error);
        throw error;
    }
};

// Expose globally
window.apiFetch = apiFetch;
