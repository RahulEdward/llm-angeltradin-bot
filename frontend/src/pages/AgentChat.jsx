import React, { useState, useEffect, useRef } from 'react';
import { Bot, Send, RefreshCw, Activity, Zap, Shield, TrendingUp } from 'lucide-react';

const AgentChat = ({ status }) => {
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(true);
    const chatRef = useRef(null);

    useEffect(() => {
        fetchAgentLogs();
        const interval = setInterval(fetchAgentLogs, 5000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (chatRef.current) {
            chatRef.current.scrollTop = chatRef.current.scrollHeight;
        }
    }, [messages]);

    const fetchAgentLogs = async () => {
        try {
            const res = await fetch('/api/logs/agents');
            if (res.ok) {
                const data = await res.json();
                // Transform to chat messages
                const chatMessages = (data.logs || []).map((log, idx) => ({
                    id: idx,
                    agent: log.agent,
                    type: log.type,
                    content: `Status: ${log.is_active ? 'Active' : 'Inactive'} | Processed: ${log.messages_processed} messages`,
                    time: log.last_update,
                    isActive: log.is_active
                }));
                setMessages(chatMessages);
            }
        } catch (err) {
            console.error('Error fetching logs:', err);
        } finally {
            setLoading(false);
        }
    };

    // Demo agent messages
    const demoMessages = [
        { id: 1, agent: 'Market Data Agent', content: 'Fetched quotes for 5 symbols. RELIANCE: ₹2,485.50 (+1.2%)', time: '21:15:32', type: 'market_data' },
        { id: 2, agent: 'Strategy Agent', content: 'Signal generated: BUY RELIANCE @ ₹2,485. Confidence: 78%. 4-layer filter passed.', time: '21:15:33', type: 'strategy' },
        { id: 3, agent: 'Risk Manager', content: 'Signal approved. Position size: 100 shares. Risk level: LOW', time: '21:15:34', type: 'risk_manager' },
        { id: 4, agent: 'Execution Agent', content: 'Order placed: BUY 100 RELIANCE @ MARKET. Order ID: AO123456', time: '21:15:35', type: 'execution' },
        { id: 5, agent: 'Supervisor', content: 'Trade cycle completed. All agents operational.', time: '21:15:36', type: 'supervisor' },
        { id: 6, agent: 'Market Data Agent', content: 'RSI(14) = 42.5, MACD Histogram positive, EMA crossover detected', time: '21:16:32', type: 'market_data' },
        { id: 7, agent: 'Risk Manager', content: 'Daily P&L: +₹8,750. Remaining limit: ₹41,250', time: '21:16:33', type: 'risk_manager' },
    ];

    const displayMessages = messages.length > 0 ? messages : demoMessages;

    const getAgentIcon = (type) => {
        switch (type) {
            case 'market_data': return <TrendingUp size={16} />;
            case 'strategy': return <Zap size={16} />;
            case 'risk_manager': return <Shield size={16} />;
            case 'execution': return <Activity size={16} />;
            default: return <Bot size={16} />;
        }
    };

    const getAgentColor = (type) => {
        switch (type) {
            case 'market_data': return '#3b82f6';
            case 'strategy': return '#8b5cf6';
            case 'risk_manager': return '#f59e0b';
            case 'execution': return '#10b981';
            default: return '#6366f1';
        }
    };

    const agents = status?.agents || {};

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">Agent Chatroom</h1>
                <button className="btn btn-outline" onClick={fetchAgentLogs}>
                    <RefreshCw size={16} />
                    Refresh
                </button>
            </div>

            <div className="grid-2">
                {/* Agent Status Cards */}
                <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}>Agent Status</h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {Object.entries(agents).length > 0 ? (
                            Object.entries(agents).map(([name, agent]) => (
                                <div key={name} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: '0.75rem 1rem',
                                    background: 'var(--bg-tertiary)',
                                    borderRadius: '8px'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                        {getAgentIcon(agent.type)}
                                        <div>
                                            <div style={{ fontWeight: 600 }}>{name.replace('_', ' ').toUpperCase()}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                                {agent.messages_processed} messages
                                            </div>
                                        </div>
                                    </div>
                                    <span className={`badge ${agent.is_active ? 'success' : 'warning'}`}>
                                        {agent.is_active ? 'Active' : 'Idle'}
                                    </span>
                                </div>
                            ))
                        ) : (
                            ['Market Data', 'Strategy', 'Risk Manager', 'Execution', 'Supervisor'].map(name => (
                                <div key={name} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: '0.75rem 1rem',
                                    background: 'var(--bg-tertiary)',
                                    borderRadius: '8px'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                        <Bot size={16} />
                                        <div>
                                            <div style={{ fontWeight: 600 }}>{name}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                                Ready
                                            </div>
                                        </div>
                                    </div>
                                    <span className="badge info">Standby</span>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Chat Messages */}
                <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}>Agent Communication</h3>

                    <div
                        ref={chatRef}
                        className="agent-chat"
                        style={{ maxHeight: '500px', overflowY: 'auto' }}
                    >
                        {loading ? (
                            <div className="loading">
                                <div className="spinner"></div>
                            </div>
                        ) : (
                            displayMessages.map((msg) => (
                                <div
                                    key={msg.id}
                                    className="chat-message"
                                    style={{ borderLeftColor: getAgentColor(msg.type) }}
                                >
                                    <div className="chat-header">
                                        <span className="chat-agent" style={{ color: getAgentColor(msg.type) }}>
                                            {msg.agent}
                                        </span>
                                        <span className="chat-time">{msg.time}</span>
                                    </div>
                                    <div className="chat-content">{msg.content}</div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Agent Architecture Diagram */}
            <div className="card" style={{ marginTop: '1.5rem' }}>
                <h3 className="card-title" style={{ marginBottom: '1rem' }}>Agent Architecture</h3>
                <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: '1rem',
                    padding: '2rem',
                    background: 'var(--bg-tertiary)',
                    borderRadius: '8px',
                    flexWrap: 'wrap'
                }}>
                    {[
                        { name: 'Market Data', icon: TrendingUp, color: '#3b82f6' },
                        { name: 'Strategy', icon: Zap, color: '#8b5cf6' },
                        { name: 'Risk Manager', icon: Shield, color: '#f59e0b' },
                        { name: 'Execution', icon: Activity, color: '#10b981' }
                    ].map((agent, idx) => (
                        <React.Fragment key={agent.name}>
                            <div style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: '0.5rem'
                            }}>
                                <div style={{
                                    width: '60px',
                                    height: '60px',
                                    borderRadius: '12px',
                                    background: `${agent.color}20`,
                                    border: `2px solid ${agent.color}`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center'
                                }}>
                                    <agent.icon size={28} color={agent.color} />
                                </div>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    {agent.name}
                                </span>
                            </div>
                            {idx < 3 && (
                                <div style={{ color: 'var(--text-muted)', fontSize: '1.5rem' }}>→</div>
                            )}
                        </React.Fragment>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default AgentChat;
