const { useState, useEffect, useRef } = React;

const Dashboard = () => {
    const [messages, setMessages] = useState([]);
    const [inputText, setInputText] = useState("");
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    // Identificador único da sessão ativa de chat
    const [threadId, setThreadId] = useState(() => "sessao_" + Math.random().toString(36).substring(2, 9));

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, loading]);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!inputText.trim() || loading) return;

        const userText = inputText.trim();
        setInputText("");
        
        // Adiciona a mensagem do usuário imediatamente
        setMessages(prev => [...prev, { role: "user", content: userText, tempId: Date.now() }]);
        setLoading(true);

        try {
            const res = await window.apiFetch("/chat", {
                method: "POST",
                body: JSON.stringify({
                    thread_id: threadId,
                    message: userText
                })
            });

            setMessages(prev => [
                ...prev, 
                { 
                    role: "assistant", 
                    content: res.response, 
                    agent: res.agent_used, 
                    tools: res.tools_used || [],
                    tempId: Date.now() + 1 
                }
            ]);
        } catch (err) {
            setMessages(prev => [
                ...prev,
                {
                    role: "assistant error",
                    content: `Erro ao enviar mensagem: ${err.message}`,
                    tempId: Date.now() + 1
                }
            ]);
        } finally {
            setLoading(false);
        }
    };

    const handleNewChat = () => {
        setThreadId("sessao_" + Math.random().toString(36).substring(2, 9));
        setMessages([]);
    };

    return (
        <div className="dashboard">
            <div className="chat-panel">
                <div className="chat-header">
                    <div>
                        <h3 style={{ margin: 0 }}>Atendimento Inteligente — Multi-Agent</h3>
                        <small style={{ color: 'var(--text-muted)' }}>Sessão: {threadId}</small>
                    </div>
                    <button 
                        className="btn-primary" 
                        style={{ width: 'auto', padding: '0.5rem 1rem', fontSize: '0.85rem' }} 
                        onClick={handleNewChat}
                        title="Iniciar nova conversa com novo histórico"
                    >
                        Nova Conversa
                    </button>
                </div>
                
                <div className="chat-messages">
                    {messages.length === 0 ? (
                        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '3rem' }}>
                            <p style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                                👋 Olá! Como posso ajudar hoje?
                            </p>
                            <p style={{ maxWidth: '480px', margin: '0 auto', fontSize: '0.9rem' }}>
                                Pergunte sobre o status de um pedido (ex: <code>PED-001</code>), dúvidas gerais, pesquisas na web ou criação de tarefas.
                            </p>
                        </div>
                    ) : (
                        messages.map((msg) => (
                            <div key={msg.tempId} className={`message ${msg.role}`}>
                                {msg.role.includes('assistant') && (
                                    <div style={{ marginBottom: '0.45rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                        {msg.agent && <span className="agent-tag">Agente: {msg.agent}</span>}
                                        {msg.tools && msg.tools.length > 0 && (
                                            <span className="tool-tag" title="Ferramentas corporativas executadas no turno">
                                                🔧 {msg.tools.join(', ')}
                                            </span>
                                        )}
                                    </div>
                                )}
                                <strong>{msg.role === 'user' ? 'Você' : 'Assistente'}:</strong><br/>
                                <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                            </div>
                        ))
                    )}
                    {loading && (
                        <div className="message assistant">
                            <span className="spinner" style={{ display: 'inline-block', verticalAlign: 'middle', borderColor: 'var(--primary)', borderTopColor: 'transparent', marginRight: '0.5rem' }}></span>
                            <span>Consultando especialistas...</span>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
                
                <form className="chat-input-area" onSubmit={handleSend}>
                    <input 
                        type="text" 
                        placeholder="Digite sua dúvida ou comando..." 
                        value={inputText}
                        onChange={e => setInputText(e.target.value)}
                        disabled={loading}
                        autoFocus
                    />
                    <button type="submit" className="btn-primary" disabled={loading || !inputText.trim()}>
                        Enviar
                    </button>
                </form>
            </div>
        </div>
    );
};

// Expose to window so index.html can use it
window.Dashboard = Dashboard;
