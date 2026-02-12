import React, { useState, useEffect, useRef } from 'react';

const Dashboard = ({ status, mode, cycleCount, isRunning }) => {
    const [positions, setPositions] = useState([]);
    const [funds, setFunds] = useState({ available: 0, utilized: 0 });
    const [agentMessages, setAgentMessages] = useState([]);
    const [tradeRecords, setTradeRecords] = useState([]);
    const [ranking, setRanking] = useState([]);
    const [llmMetrics, setLlmMetrics] = useState({
        tokensIn: '--',
        tokensOut: '--',
        tokensTotal: '--',
        speed: '--',
        latency: { min: '--', avg: '--', max: '--' }
    });
    const [loading, setLoading] = useState(true);
    const [currentSymbol, setCurrentSymbol] = useState('--');
    const [llmEnabled, setLlmEnabled] = useState(false);
    const [llmProvider, setLlmProvider] = useState('--');
    const [llmModel, setLlmModel] = useState('--');

    // Dropdown states
    const [allSymbols, setAllSymbols] = useState([]);
    const [selectedExchange, setSelectedExchange] = useState('All');
    const [selectedScript, setSelectedScript] = useState('All');

    const wsRef = useRef(null);

    useEffect(() => {
        fetchData();
        fetchSymbols();
        fetchAgentStatus();
        connectWebSocket();

        const interval = setInterval(fetchData, 5000);
        const agentInterval = setInterval(fetchAgentStatus, 10000);
        return () => {
            clearInterval(interval);
            clearInterval(agentInterval);
            if (wsRef.current) wsRef.current.close();
        };
    }, [mode]); // Re-fetch when mode changes

    const fetchAgentStatus = async () => {
        try {
            const res = await fetch('/api/agent/status');
            if (res.ok) {
                const data = await res.json();
                setLlmEnabled(data.llm_enabled || false);
                setLlmProvider(data.llm_provider || '--');
                setLlmModel(data.llm_model || '--');
                if (data.symbols && data.symbols.length > 0) {
                    setCurrentSymbol(data.symbols[0]);
                }
            }
        } catch (err) {
            console.log('Agent status fetch failed');
        }

        // Fetch LLM metrics
        try {
            const mRes = await fetch('/api/llm/metrics');
            if (mRes.ok) {
                const mData = await mRes.json();
                const providers = mData?.metrics?.providers || {};
                // Find first provider with data
                const stats = Object.values(providers)[0];
                if (stats) {
                    setLlmMetrics({
                        tokensIn: stats.total_input_tokens?.toLocaleString() || '0',
                        tokensOut: stats.total_output_tokens?.toLocaleString() || '0',
                        tokensTotal: stats.total_tokens?.toLocaleString() || '0',
                        speed: stats.token_speed_tps || '0',
                        latency: {
                            min: stats.min_latency_ms || '0',
                            avg: stats.avg_latency_ms || '0',
                            max: stats.max_latency_ms || '0'
                        }
                    });
                }
            }
        } catch (err) {
            console.log('LLM metrics fetch failed');
        }
    };

    const fetchSymbols = async () => {
        try {
            const res = await fetch('/api/broker/symbols');
            if (res.ok) {
                const data = await res.json();
                setAllSymbols(data || []);
            }
        } catch (err) {
            console.error('Failed to fetch symbols', err);
        }
    };

    const updateConfig = async (symbols, exchange) => {
        try {
            const body = { symbols };
            if (exchange && exchange !== 'All') body.exchange = exchange;
            if (exchange === 'All') {
                // Determine exchanges map if needed, or backend handles it
            }

            await fetch('/api/config/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            // Refresh status to update current symbol badge
            setTimeout(fetchAgentStatus, 500);
        } catch (err) {
            console.error('Config update failed', err);
        }
    };

    const handleExchangeChange = (e) => {
        const exch = e.target.value;
        setSelectedExchange(exch);
        setSelectedScript('All'); // Reset script

        // If switching exchange, update script list in next render
        // But also update backend configuration if needed?
        // User said: "agar user all select kare to sab exchange may trade ho"
        // If All Exchange selected, we trade on ALL symbols?
        // Let's assume selecting exchange filters the view.
        // And selecting "All" (Script) sends filtered list to backend.

        let symbolsList = [];
        if (exch === 'All') {
            // If Exchange All and Script All -> Send subset of all
            const nse = allSymbols.filter(s => s.exchange === 'NSE').slice(0, 20);
            const bse = allSymbols.filter(s => s.exchange === 'BSE').slice(0, 20);
            symbolsList = [...nse, ...bse].map(s => s.symbol);
            updateConfig(symbolsList, null);
        } else {
            // Specific Exchange, Script All
            symbolsList = allSymbols.filter(s => s.exchange === exch).slice(0, 50).map(s => s.symbol);
            updateConfig(symbolsList, exch);
        }
    };

    const handleScriptChange = (e) => {
        const script = e.target.value;
        setSelectedScript(script);

        if (script === 'All') {
            // Revert to all in current exchange
            handleExchangeChange({ target: { value: selectedExchange } });
        } else {
            // Specific script
            const found = allSymbols.find(s => s.symbol === script);
            const exch = found ? found.exchange : 'NSE';
            updateConfig([script], exch);
        }
    };

    const connectWebSocket = () => {
        try {
            const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'agent_message') {
                    setAgentMessages(prev => [data.data, ...prev].slice(0, 50));
                }

                if (data.type === 'trade') {
                    setTradeRecords(prev => [data.data, ...prev].slice(0, 100));
                }

                if (data.type === 'symbol') {
                    setCurrentSymbol(data.data);
                }
            };

            ws.onerror = () => console.log('WebSocket not available');
            wsRef.current = ws;
        } catch (err) {
            console.log('WebSocket connection failed');
        }
    };

    const fetchData = async () => {
        try {
            const [positionsRes, fundsRes, tradesRes] = await Promise.all([
                fetch('/api/positions').catch(() => null),
                fetch('/api/account/funds').catch(() => null),
                fetch('/api/trades').catch(() => null)
            ]);

            if (positionsRes?.ok) {
                const posData = await positionsRes.json();
                setPositions(posData || []);
            }

            if (fundsRes?.ok) {
                const fundsData = await fundsRes.json();
                setFunds(fundsData || { available: 0, utilized: 0 });
            }

            // Update trade records from broker (live mode)
            if (tradesRes?.ok) {
                const tradesData = await tradesRes.json();
                if (tradesData && tradesData.length > 0) {
                    // Transform broker trades to our format
                    const formattedTrades = tradesData.map(t => ({
                        time: t.updatetime || t.orderUpdateTime || new Date().toLocaleTimeString(),
                        symbol: t.tradingsymbol || t.symbol,
                        side: t.transactiontype || t.side || '--',
                        entry: parseFloat(t.fillprice || t.price || 0),
                        exit: null,
                        pnl: 0
                    }));
                    setTradeRecords(formattedTrades);
                }
            }

            setLoading(false);
        } catch (err) {
            console.error('Error fetching data:', err);
            setLoading(false);
        }
    };

    // Calculate totals from real data
    const totalUnrealizedPnL = positions.reduce((sum, p) => sum + (p.pnl || 0), 0);
    const totalRealizedPnL = tradeRecords.reduce((sum, t) => sum + (t.pnl || 0), 0);

    const [showAgentConfig, setShowAgentConfig] = useState(false);

    const toggleLLM = async () => {
        const newValue = !llmEnabled;
        setLlmEnabled(newValue);
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ llm_enabled: newValue })
            });
        } catch (err) {
            console.log('LLM toggle saved locally');
        }
    };

    if (loading) {
        return (
            <div className="loading">
                <div className="spinner"></div>
            </div>
        );
    }

    return (
        <div className="dashboard-layout hero-layout">
            {/* Left Sidebar: Account & Portfolios */}
            <aside className="sidebar-left">
                <section className="row-charts-account">
                    <div className="glass-panel card live-positions-card">
                        {/* Header */}
                        <div className="card-header-compact">
                            <h2>📊 Live Positions</h2>
                            <span className="badge">{positions.length}</span>
                        </div>

                        {/* Total Unrealized PnL */}
                        <div className="positions-summary">
                            <div className="summary-item">
                                <span className="label">Total Unrealized PnL</span>
                                <span className={`value ${totalUnrealizedPnL > 0 ? 'pos' : totalUnrealizedPnL < 0 ? 'neg' : 'neutral'}`}>
                                    {totalUnrealizedPnL !== 0
                                        ? `${totalUnrealizedPnL >= 0 ? '+' : ''}₹${Math.abs(totalUnrealizedPnL).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                                        : '₹0.00'}
                                </span>
                            </div>
                        </div>

                        {/* Positions List */}
                        <div className="positions-list-container">
                            <div className="position-details-list">
                                {positions.length === 0 ? (
                                    <span className="empty-msg">No active positions</span>
                                ) : (
                                    positions.map((pos, idx) => (
                                        <div key={idx} className={`position-item ${pos.side?.toLowerCase() || 'long'}`}>
                                            <div className="pos-header">
                                                <span className="pos-symbol">{pos.symbol}</span>
                                                <span className={`pos-pnl ${pos.pnl >= 0 ? 'pos' : 'neg'}`}>
                                                    {pos.pnl >= 0 ? '+' : ''}₹{pos.pnl?.toFixed(2) || '0.00'}
                                                </span>
                                            </div>
                                            <div className="pos-details">
                                                <span>{pos.side} × {pos.quantity} @ ₹{pos.average_price?.toFixed(2) || '0.00'}</span>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        <hr className="sidebar-divider" />

                        {/* Account Stats */}
                        <div className="account-stats-compact">
                            <div className="stat-row">
                                <span className="label">Wallet Balance</span>
                                <span className="value">₹{(funds.available || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="stat-row">
                                <span className="label">Realized PnL</span>
                                <span className={`value ${totalRealizedPnL > 0 ? 'pos' : totalRealizedPnL < 0 ? 'neg' : ''}`}>
                                    ₹{totalRealizedPnL.toFixed(2)}
                                </span>
                            </div>
                        </div>

                        <hr className="sidebar-divider" />

                        {/* LLM Metrics */}
                        <div className="account-stats-compact llm-metrics-panel">
                            <div className="stats-section-title">LLM API</div>
                            <div className="stat-row">
                                <span className="label">Tokens (IN/OUT)</span>
                                <span className="value">{llmMetrics.tokensIn}/{llmMetrics.tokensOut}</span>
                            </div>
                            <div className="stat-row">
                                <span className="label">Tokens Total</span>
                                <span className="value">{llmMetrics.tokensTotal}</span>
                            </div>
                            <div className="stat-row">
                                <span className="label">Token Speed</span>
                                <span className="value">{llmMetrics.speed} tps</span>
                            </div>
                            <div className="stat-row">
                                <span className="label">Latency (min/avg/max)</span>
                                <span className="value">{llmMetrics.latency.min}/{llmMetrics.latency.avg}/{llmMetrics.latency.max} ms</span>
                            </div>
                        </div>
                    </div>
                </section>
            </aside>

            {/* Center Hero: Agent Chatroom */}
            <section className="hero-center row-agent-framework">
                <div className="glass-panel card agent-framework-card hero-chatroom-card">
                    {/* Chatroom Header */}
                    <div className="card-header framework-header">
                        <div className="framework-title-block">
                            <h2 className="framework-title">🤖 Agent Chatroom</h2>
                            <p className="framework-subtitle">Agents Report - Decision Agent Concludes</p>
                        </div>
                        <div className="framework-controls">
                            <span className="cycle-badge">Cycle #{cycleCount || status?.cycle_count || 0}</span>
                            <span className="current-symbol-badge">
                                📊 <span>{currentSymbol}</span>
                            </span>

                            {/* Exchange & Script Selectors */}
                            <select
                                className="dashboard-select"
                                value={selectedExchange}
                                onChange={handleExchangeChange}
                            >
                                <option value="All">Exch: All</option>
                                <option value="NSE">NSE</option>
                                <option value="BSE">BSE</option>
                            </select>

                            <select
                                className="dashboard-select"
                                value={selectedScript}
                                onChange={handleScriptChange}
                            >
                                <option value="All">Script: All</option>
                                {allSymbols
                                    .filter(s => selectedExchange === 'All' || s.exchange === selectedExchange)
                                    .slice(0, 100) // Limit dropdown size for performance
                                    .map((s, idx) => (
                                        <option key={idx} value={s.symbol}>{s.symbol}</option>
                                    ))
                                }
                            </select>
                            {llmProvider !== '--' && (
                                <div className="llm-info-badge">
                                    🤖 <span>{llmProvider}</span> (<span>{llmModel}</span>)
                                </div>
                            )}
                            <button className="llm-toggle-btn agent-config-btn" onClick={() => setShowAgentConfig(true)}>Agent Config</button>
                            <button className="llm-toggle-btn" onClick={toggleLLM}>
                                LLM: {llmEnabled ? 'ON' : 'OFF'}
                            </button>
                        </div>
                    </div>

                    {/* Chatroom Messages */}
                    <div className="chatroom-container hero-scroller">
                        <div className="chatroom-messages">
                            {agentMessages.length === 0 ? (
                                <div className="chatroom-empty">
                                    <div className="icon">💬</div>
                                    <p>Initializing neural pathways...</p>
                                </div>
                            ) : (
                                agentMessages.map((msg, idx) => (
                                    <div key={idx} className={`chat-bubble ${msg.agent?.toLowerCase().replace(/\s+/g, '-')}`}>
                                        <div className="chat-header">
                                            <span className="chat-agent">{msg.agent}</span>
                                            <span className="chat-time">{msg.time}</span>
                                        </div>
                                        <div className="chat-content">{msg.message}</div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </section>

            {/* Right Sidebar: Performance & Stats */}
            <aside className="sidebar-right">
                <section className="glass-panel card ranking-card">
                    <h2>🏆 Symbol Performance Ranking</h2>
                    <div className="ranking-compact-container">
                        <table className="compact-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Symbol</th>
                                    <th className="text-right">PnL</th>
                                    <th className="text-right">Wins</th>
                                </tr>
                            </thead>
                            <tbody>
                                {ranking.length === 0 ? (
                                    <tr>
                                        <td colSpan="4" className="text-center empty-msg">
                                            No completed trades in current session
                                        </td>
                                    </tr>
                                ) : (
                                    ranking.map((item, idx) => (
                                        <tr key={idx}>
                                            <td>{item.rank}</td>
                                            <td><strong>{item.symbol}</strong></td>
                                            <td className={`text-right ${item.pnl >= 0 ? 'pos' : 'neg'}`}>
                                                {item.pnl >= 0 ? '+' : ''}₹{item.pnl?.toFixed(2)}
                                            </td>
                                            <td className="text-right">{item.wins}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>
            </aside>

            {/* Bottom: Trade Records */}
            <div className="bottom-detail-panels">
                <section className="row-trades">
                    <div className="glass-panel card trade-table-card">
                        <div className="section-header-compact">
                            <h2>📜 Trade Records</h2>
                        </div>
                        <div className="table-container mini-records">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Symbol</th>
                                        <th>Side</th>
                                        <th>Entry</th>
                                        <th>Exit</th>
                                        <th>PnL</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {tradeRecords.length === 0 ? (
                                        <tr>
                                            <td colSpan="6" className="text-center empty-msg">
                                                No trades yet
                                            </td>
                                        </tr>
                                    ) : (
                                        tradeRecords.map((trade, idx) => (
                                            <tr key={idx}>
                                                <td>{trade.time}</td>
                                                <td><strong>{trade.symbol}</strong></td>
                                                <td>
                                                    <span className={`badge ${trade.side === 'BUY' || trade.side === 'LONG' ? 'buy' : 'sell'}`}>
                                                        {trade.side}
                                                    </span>
                                                </td>
                                                <td>₹{trade.entry?.toFixed(2) || '--'}</td>
                                                <td>₹{trade.exit?.toFixed(2) || '--'}</td>
                                                <td className={trade.pnl >= 0 ? 'pos' : 'neg'}>
                                                    {trade.pnl >= 0 ? '+' : ''}₹{trade.pnl?.toFixed(2) || '0.00'}
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>
            </div>

            {/* Agent Config Modal */}
            {showAgentConfig && (
                <div className="agent-config-modal-overlay" onClick={() => setShowAgentConfig(false)}>
                    <div className="agent-config-modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>🤖 Agent Configuration</h3>
                            <button className="close-btn" onClick={() => setShowAgentConfig(false)}>×</button>
                        </div>
                        <div className="modal-body">
                            <div className="agent-list">
                                <div className="agent-item">
                                    <span className="agent-icon">📊</span>
                                    <div className="agent-info">
                                        <span className="agent-name">Market Data Agent</span>
                                        <span className="agent-desc">Fetches real-time quotes and indicators</span>
                                    </div>
                                    <span className="agent-status active">Active</span>
                                </div>
                                <div className="agent-item">
                                    <span className="agent-icon">🧠</span>
                                    <div className="agent-info">
                                        <span className="agent-name">Strategy Agent</span>
                                        <span className="agent-desc">4-layer filter + LLM analysis</span>
                                    </div>
                                    <span className="agent-status active">Active</span>
                                </div>
                                <div className="agent-item">
                                    <span className="agent-icon">🛡️</span>
                                    <div className="agent-info">
                                        <span className="agent-name">Risk Manager Agent</span>
                                        <span className="agent-desc">Position sizing, veto power, kill switch</span>
                                    </div>
                                    <span className="agent-status active">Active</span>
                                </div>
                                <div className="agent-item">
                                    <span className="agent-icon">⚡</span>
                                    <div className="agent-info">
                                        <span className="agent-name">Execution Agent</span>
                                        <span className="agent-desc">Order placement via broker</span>
                                    </div>
                                    <span className="agent-status active">Active</span>
                                </div>
                                <div className="agent-item">
                                    <span className="agent-icon">👑</span>
                                    <div className="agent-info">
                                        <span className="agent-name">Supervisor Agent</span>
                                        <span className="agent-desc">Orchestrates all agents</span>
                                    </div>
                                    <span className="agent-status active">Active</span>
                                </div>
                            </div>
                            <div className="config-section">
                                <h4>Trading Symbols</h4>
                                <div className="symbols-list">
                                    {['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'].map(s => (
                                        <span key={s} className="symbol-tag">{s}</span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                /* Hero Layout - 3 Columns */
                .hero-layout {
                    display: grid;
                    grid-template-columns: 280px 1fr 320px;
                    grid-template-rows: 1fr auto;
                    gap: 20px;
                    min-height: calc(100vh - 140px);
                }

                .sidebar-left {
                    grid-column: 1;
                    grid-row: 1;
                }

                .hero-center {
                    grid-column: 2;
                    grid-row: 1;
                    display: flex;
                    flex-direction: column;
                }

                .sidebar-right {
                    grid-column: 3;
                    grid-row: 1;
                }

                .bottom-detail-panels {
                    grid-column: 1 / -1;
                    grid-row: 2;
                }

                /* Glass Panel Card */
                .glass-panel.card {
                    background: rgba(14, 18, 23, 0.6);
                    backdrop-filter: blur(16px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                    padding: 0;
                    height: 100%;
                }

                /* Live Positions Card */
                .live-positions-card {
                    display: flex;
                    flex-direction: column;
                    padding: 16px !important;
                    height: 100%;
                }

                .card-header-compact {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 16px;
                }

                .card-header-compact h2 {
                    margin: 0;
                    font-size: 0.95rem;
                    font-weight: 600;
                    color: #EAECEF;
                }

                .card-header-compact .badge {
                    background: rgba(240, 185, 11, 0.2);
                    color: #F0B90B;
                    padding: 2px 10px;
                    border-radius: 10px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }

                /* Positions Summary */
                .positions-summary {
                    background: rgba(0, 0, 0, 0.3);
                    border-radius: 8px;
                    padding: 12px;
                    margin-bottom: 16px;
                }

                .summary-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .summary-item .label {
                    font-size: 0.8rem;
                    color: #848E9C;
                }

                .summary-item .value {
                    font-size: 1.1rem;
                    font-weight: 700;
                    font-family: 'IBM Plex Mono', monospace;
                }

                .summary-item .value.pos { color: #0ECB81; }
                .summary-item .value.neg { color: #F6465D; }
                .summary-item .value.neutral { color: #EAECEF; }

                /* Positions List */
                .positions-list-container {
                    flex: 1;
                    overflow-y: auto;
                    min-height: 100px;
                    margin-bottom: 16px;
                }

                .position-details-list {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }

                .empty-msg {
                    color: #5E6673;
                    font-size: 0.85rem;
                    font-style: italic;
                }

                .position-item {
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 8px;
                    padding: 10px 12px;
                    border-left: 3px solid transparent;
                }

                .position-item.long { border-left-color: #0ECB81; }
                .position-item.short { border-left-color: #F6465D; }

                .pos-header {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 4px;
                }

                .pos-symbol {
                    font-weight: 700;
                    font-size: 0.9rem;
                    color: #EAECEF;
                }

                .pos-pnl { font-weight: 700; font-size: 0.9rem; }
                .pos-pnl.pos { color: #0ECB81; }
                .pos-pnl.neg { color: #F6465D; }

                .pos-details {
                    font-size: 0.75rem;
                    color: #5E6673;
                }

                /* Divider */
                .sidebar-divider {
                    border: none;
                    border-top: 1px solid rgba(255, 255, 255, 0.08);
                    margin: 16px 0;
                }

                /* Account Stats */
                .account-stats-compact {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }

                .stats-section-title {
                    font-size: 0.7rem;
                    font-weight: 600;
                    color: #F0B90B;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 4px;
                }

                .stat-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .stat-row .label {
                    font-size: 0.8rem;
                    color: #848E9C;
                }

                .stat-row .value {
                    font-size: 0.85rem;
                    font-weight: 600;
                    font-family: 'IBM Plex Mono', monospace;
                    color: #EAECEF;
                }

                .stat-row .value.pos { color: #0ECB81; }
                .stat-row .value.neg { color: #F6465D; }

                /* Agent Chatroom */
                .hero-chatroom-card {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                }

                .framework-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    padding: 16px 20px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }

                .framework-title-block {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }

                .framework-title {
                    margin: 0;
                    font-size: 1rem;
                    font-weight: 700;
                    color: #EAECEF;
                }

                .framework-subtitle {
                    margin: 0;
                    font-size: 0.75rem;
                    color: #5E6673;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }

                .framework-controls {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    flex-wrap: wrap;
                }

                .cycle-badge {
                    background: rgba(0, 240, 255, 0.1);
                    border: 1px solid rgba(0, 240, 255, 0.3);
                    color: #00F0FF;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }

                .current-symbol-badge {
                    background: rgba(240, 185, 11, 0.1);
                    border: 1px solid rgba(240, 185, 11, 0.3);
                    color: #F0B90B;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }

                .llm-info-badge {
                    background: rgba(0, 255, 157, 0.1);
                    border: 1px solid rgba(0, 255, 157, 0.3);
                    color: #00FF9D;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }

                .llm-toggle-btn {
                    background: rgba(100, 100, 100, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    color: #EAECEF;
                    padding: 6px 14px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .dashboard-select {
                    background: rgba(100, 100, 100, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    color: #EAECEF;
                    padding: 6px 10px;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    cursor: pointer;
                    outline: none;
                }
                
                .dashboard-select option {
                    background: #1a1a2e;
                    color: #EAECEF;
                    padding: 8px 12px;
                    font-size: 0.8rem;
                }
                
                .dashboard-select:hover, .dashboard-select:focus {
                    background: rgba(240, 185, 11, 0.1);
                    border-color: rgba(240, 185, 11, 0.3);
                }

                .llm-toggle-btn:hover {
                    background: rgba(240, 185, 11, 0.2);
                    border-color: rgba(240, 185, 11, 0.3);
                }

                .agent-config-btn {
                    background: rgba(186, 104, 200, 0.2);
                    border-color: rgba(186, 104, 200, 0.3);
                    color: #ba68c8;
                }

                /* Chatroom Container */
                .chatroom-container {
                    flex: 1;
                    background: rgba(0, 0, 0, 0.3);
                    margin: 16px;
                    border-radius: 8px;
                    overflow: hidden;
                }

                .chatroom-messages {
                    height: 100%;
                    overflow-y: auto;
                    padding: 16px;
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }

                .chatroom-empty {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                    color: #5E6673;
                    text-align: center;
                }

                .chatroom-empty .icon {
                    font-size: 3rem;
                    margin-bottom: 16px;
                    opacity: 0.5;
                }

                .chat-bubble {
                    background: rgba(240, 185, 11, 0.08);
                    border-left: 4px solid #F0B90B;
                    border-radius: 8px;
                    padding: 12px 16px;
                }

                .chat-bubble.system {
                    background: rgba(0, 240, 255, 0.08);
                    border-left-color: #00F0FF;
                }

                .chat-bubble.market-data {
                    background: rgba(0, 255, 157, 0.08);
                    border-left-color: #00FF9D;
                }

                .chat-bubble.risk-manager {
                    background: rgba(246, 70, 93, 0.08);
                    border-left-color: #F6465D;
                }

                .chat-header {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                }

                .chat-agent {
                    font-size: 0.75rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    color: inherit;
                }

                .chat-time {
                    font-size: 0.7rem;
                    color: #5E6673;
                }

                .chat-content {
                    font-size: 0.9rem;
                    line-height: 1.5;
                    color: #EAECEF;
                }

                /* Ranking Card */
                .ranking-card {
                    padding: 16px !important;
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                }

                .ranking-card h2 {
                    margin: 0 0 16px 0;
                    font-size: 0.95rem;
                    font-weight: 600;
                    color: #EAECEF;
                }

                .ranking-compact-container {
                    flex: 1;
                    overflow-y: auto;
                }

                .compact-table {
                    width: 100%;
                    border-collapse: collapse;
                }

                .compact-table th {
                    font-size: 0.7rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    color: #5E6673;
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }

                .compact-table th.text-right { text-align: right; }

                .compact-table td {
                    padding: 10px 8px;
                    font-size: 0.85rem;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                }

                .compact-table td.text-right { text-align: right; }
                .compact-table td.text-center { text-align: center; }
                .compact-table .pos { color: #0ECB81; font-weight: 600; }
                .compact-table .neg { color: #F6465D; font-weight: 600; }

                /* Trade Records */
                .trade-table-card {
                    padding: 16px !important;
                }

                .section-header-compact {
                    margin-bottom: 12px;
                }

                .section-header-compact h2 {
                    margin: 0;
                    font-size: 0.95rem;
                    font-weight: 600;
                    color: #EAECEF;
                }

                .mini-records {
                    max-height: 200px;
                    overflow-y: auto;
                }

                .mini-records table {
                    width: 100%;
                    border-collapse: collapse;
                }

                .mini-records th {
                    font-size: 0.7rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    color: #5E6673;
                    padding: 10px 8px;
                    text-align: left;
                    background: rgba(0, 0, 0, 0.2);
                    position: sticky;
                    top: 0;
                }

                .mini-records td {
                    padding: 10px 8px;
                    font-size: 0.85rem;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                }

                .mini-records .badge {
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.7rem;
                    font-weight: 600;
                }

                .mini-records .badge.buy {
                    background: rgba(14, 203, 129, 0.2);
                    color: #0ECB81;
                }

                .mini-records .badge.sell {
                    background: rgba(246, 70, 93, 0.2);
                    color: #F6465D;
                }

                /* Agent Config Modal */
                .agent-config-modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.85);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                }

                .agent-config-modal {
                    background: linear-gradient(145deg, #1e2330 0%, #141820 100%);
                    border: 1px solid rgba(186, 104, 200, 0.3);
                    border-radius: 16px;
                    width: 500px;
                    max-width: 90vw;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                }

                .agent-config-modal .modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 18px 24px;
                    border-bottom: 1px solid rgba(255,255,255,0.08);
                }

                .agent-config-modal .modal-header h3 {
                    margin: 0;
                    color: #ba68c8;
                    font-size: 1.1rem;
                }

                .agent-config-modal .close-btn {
                    background: none;
                    border: none;
                    color: #848E9C;
                    font-size: 1.5rem;
                    cursor: pointer;
                }

                .agent-config-modal .close-btn:hover {
                    color: #F6465D;
                }

                .agent-config-modal .modal-body {
                    padding: 20px 24px;
                }

                .agent-list {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                    margin-bottom: 20px;
                }

                .agent-item {
                    display: flex;
                    align-items: center;
                    gap: 14px;
                    padding: 12px 16px;
                    background: rgba(186, 104, 200, 0.08);
                    border-radius: 10px;
                    border: 1px solid rgba(186, 104, 200, 0.15);
                }

                .agent-icon {
                    font-size: 1.5rem;
                }

                .agent-info {
                    flex: 1;
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }

                .agent-name {
                    font-weight: 600;
                    color: #EAECEF;
                    font-size: 0.9rem;
                }

                .agent-desc {
                    font-size: 0.75rem;
                    color: #848E9C;
                }

                .agent-status {
                    padding: 4px 10px;
                    border-radius: 12px;
                    font-size: 0.7rem;
                    font-weight: 600;
                }

                .agent-status.active {
                    background: rgba(14, 203, 129, 0.2);
                    color: #0ECB81;
                }

                .config-section h4 {
                    color: #F0B90B;
                    font-size: 0.85rem;
                    margin-bottom: 10px;
                }

                .symbols-list {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }

                .symbol-tag {
                    background: rgba(240, 185, 11, 0.15);
                    color: #F0B90B;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }

                /* Responsive */
                @media (max-width: 1400px) {
                    .hero-layout {
                        grid-template-columns: 260px 1fr 280px;
                    }
                }

                @media (max-width: 1100px) {
                    .hero-layout {
                        grid-template-columns: 1fr;
                        grid-template-rows: auto;
                    }

                    .sidebar-left, .sidebar-right {
                        grid-column: 1;
                    }

                    .hero-center {
                        grid-column: 1;
                        min-height: 400px;
                    }

                    .bottom-detail-panels {
                        grid-column: 1;
                    }
                }
            `}</style>
        </div>
    );
};

export default Dashboard;
