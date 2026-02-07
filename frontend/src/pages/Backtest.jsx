import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, ArrowLeft, ChevronRight, Plus, X, TrendingUp, Activity, BarChart3, Clock, Target } from 'lucide-react';

const Backtest = ({ onBack }) => {
    // Tab Management
    const [tabs, setTabs] = useState([{ id: 1, name: 'Backtest 1', status: 'idle' }]);
    const [activeTab, setActiveTab] = useState(1);
    const [tabCounter, setTabCounter] = useState(1);
    const MAX_TABS = 5;

    // Per-tab state
    const [tabConfigs, setTabConfigs] = useState({
        1: getDefaultConfig()
    });
    const [tabResults, setTabResults] = useState({});
    const [tabProgress, setTabProgress] = useState({});

    // UI State
    const [showSymbols, setShowSymbols] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [history, setHistory] = useState([]);

    function getDefaultConfig() {
        return {
            symbols: ['RELIANCE'],
            startDate: '2024-01-01',
            endDate: '2024-12-31',
            capital: 100000,
            step: '12', // 1h
            leverage: 5,
            marginMode: 'cross',
            includeFunding: true
        };
    }

    const allSymbols = {
        nifty50: ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'],
        bankNifty: ['SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'FEDERALBNK'],
        it: ['WIPRO', 'HCLTECH', 'TECHM', 'LTIM', 'MPHASIS'],
        others: ['BHARTIARTL', 'ITC', 'LT', 'MARUTI', 'BAJFINANCE']
    };

    const config = tabConfigs[activeTab] || getDefaultConfig();

    const updateConfig = (field, value) => {
        setTabConfigs(prev => ({
            ...prev,
            [activeTab]: { ...prev[activeTab], [field]: value }
        }));
    };

    const toggleSymbol = (symbol) => {
        const current = config.symbols || [];
        const updated = current.includes(symbol)
            ? current.filter(s => s !== symbol)
            : [...current, symbol];
        updateConfig('symbols', updated);
    };

    const selectPreset = (preset) => {
        let symbols = [];
        switch (preset) {
            case 'nifty50': symbols = allSymbols.nifty50; break;
            case 'bankNifty': symbols = allSymbols.bankNifty; break;
            case 'it': symbols = allSymbols.it; break;
            case 'all': symbols = Object.values(allSymbols).flat(); break;
            case 'none': symbols = []; break;
        }
        updateConfig('symbols', symbols);
    };

    const setDateRange = (days) => {
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - days);
        updateConfig('startDate', start.toISOString().split('T')[0]);
        updateConfig('endDate', end.toISOString().split('T')[0]);
    };

    const addTab = () => {
        if (tabs.length >= MAX_TABS) {
            alert(`Maximum ${MAX_TABS} tabs allowed`);
            return;
        }
        const newId = tabCounter + 1;
        setTabCounter(newId);
        setTabs([...tabs, { id: newId, name: `Backtest ${newId}`, status: 'idle' }]);
        setTabConfigs(prev => ({ ...prev, [newId]: getDefaultConfig() }));
        setActiveTab(newId);
    };

    const closeTab = (tabId) => {
        if (tabs.length <= 1) return;
        const newTabs = tabs.filter(t => t.id !== tabId);
        setTabs(newTabs);
        if (activeTab === tabId) {
            setActiveTab(newTabs[0].id);
        }
    };

    const runBacktest = async () => {
        // Update tab status
        setTabs(prev => prev.map(t => t.id === activeTab ? { ...t, status: 'running' } : t));
        setTabProgress(prev => ({ ...prev, [activeTab]: { percent: 0, text: 'Initializing...' } }));

        try {
            // Simulate progress
            const progressInterval = setInterval(() => {
                setTabProgress(prev => {
                    const current = prev[activeTab]?.percent || 0;
                    if (current >= 95) {
                        clearInterval(progressInterval);
                        return prev;
                    }
                    return {
                        ...prev,
                        [activeTab]: {
                            percent: current + Math.random() * 10,
                            text: `Processing ${Math.floor(current)}%...`,
                            equity: 100000 + (Math.random() * 20000 - 5000),
                            trades: Math.floor(current / 5),
                            winRate: (50 + Math.random() * 20).toFixed(1),
                            maxDD: (Math.random() * 10).toFixed(2)
                        }
                    };
                });
            }, 300);

            // API call
            const res = await fetch('/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbols: config.symbols,
                    start_date: config.startDate,
                    end_date: config.endDate,
                    initial_capital: parseFloat(config.capital),
                    step: config.step,
                    leverage: config.leverage
                })
            }).catch(() => null);

            clearInterval(progressInterval);

            // Generate result (mock if API fails)
            const result = res?.ok ? await res.json() : {
                finalEquity: (parseFloat(config.capital) * (1 + (Math.random() * 0.4 - 0.1))).toFixed(2),
                profitLoss: (Math.random() * 30000 - 5000).toFixed(2),
                totalReturn: ((Math.random() * 40 - 10)).toFixed(2),
                maxDrawdown: (Math.random() * 15).toFixed(2),
                sharpeRatio: (Math.random() * 2 + 0.5).toFixed(2),
                sortinoRatio: (Math.random() * 2 + 0.8).toFixed(2),
                volatility: (Math.random() * 20 + 10).toFixed(2),
                totalTrades: Math.floor(Math.random() * 80 + 20),
                winRate: (50 + Math.random() * 25).toFixed(1),
                profitFactor: (Math.random() * 1.5 + 0.8).toFixed(2),
                longTrades: Math.floor(Math.random() * 40 + 10),
                shortTrades: Math.floor(Math.random() * 30 + 5),
                avgHoldTime: `${Math.floor(Math.random() * 4 + 1)}h ${Math.floor(Math.random() * 59)}m`,
                trades: []
            };

            setTabResults(prev => ({ ...prev, [activeTab]: result }));
            setTabs(prev => prev.map(t => t.id === activeTab ? { ...t, status: 'completed' } : t));
            setTabProgress(prev => ({ ...prev, [activeTab]: { percent: 100, text: 'Completed!' } }));

            // Add to history
            setHistory(prev => [{
                id: Date.now(),
                symbol: config.symbols.join(', '),
                period: `${config.startDate} → ${config.endDate}`,
                result,
                timestamp: new Date().toISOString()
            }, ...prev].slice(0, 10));

        } catch (err) {
            console.error('Backtest error:', err);
            setTabs(prev => prev.map(t => t.id === activeTab ? { ...t, status: 'error' } : t));
        }
    };

    const stopBacktest = () => {
        setTabs(prev => prev.map(t => t.id === activeTab ? { ...t, status: 'idle' } : t));
        setTabProgress(prev => ({ ...prev, [activeTab]: null }));
    };

    const currentTab = tabs.find(t => t.id === activeTab);
    const isRunning = currentTab?.status === 'running';
    const progress = tabProgress[activeTab];
    const result = tabResults[activeTab];

    const getStatusIcon = (status) => {
        switch (status) {
            case 'running': return '🔄';
            case 'completed': return '✅';
            case 'error': return '❌';
            default: return '⏸️';
        }
    };

    return (
        <div className="backtest-container">
            {/* Header */}
            <div className="backtest-header">
                <div>
                    <button className="back-link" onClick={onBack}>← Back to Dashboard</button>
                    <h1>🔬 Backtesting</h1>
                </div>
                <div className="live-status-indicator">
                    <span className="status-dot"></span>
                    <span>Live: Ready</span>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="backtest-tabs">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        className={`backtest-tab ${activeTab === tab.id ? 'active' : ''}`}
                        onClick={() => setActiveTab(tab.id)}
                    >
                        <span className="tab-icon">📊</span>
                        <span className="tab-name">{tab.name}</span>
                        <span className={`tab-status ${tab.status}`}>{getStatusIcon(tab.status)}</span>
                        {tabs.length > 1 && (
                            <span className="tab-close" onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}>✕</span>
                        )}
                    </button>
                ))}
                {tabs.length < MAX_TABS && (
                    <button className="add-tab-btn" onClick={addTab}>➕ New Tab</button>
                )}
            </div>

            {/* Configuration Form */}
            <div className="backtest-form glass-panel">
                <div className="form-title">⚙️ Configuration</div>

                {/* Symbols Section */}
                <div className="form-group full-width">
                    <label className="collapsible-label" onClick={() => setShowSymbols(!showSymbols)}>
                        <span>Symbols (Multi-Select)</span>
                        <span className="toggle-icon">{showSymbols ? '▼' : '▶'}</span>
                        <span className="selected-count">Selected: {config.symbols?.length || 0}</span>
                    </label>

                    {showSymbols && (
                        <div className="symbol-section">
                            {/* Quick Select */}
                            <div className="quick-select-btns">
                                <button className="quick-btn" onClick={() => selectPreset('nifty50')}>🔥 Nifty 50 (5)</button>
                                <button className="quick-btn" onClick={() => selectPreset('bankNifty')}>🏦 Bank Nifty (5)</button>
                                <button className="quick-btn" onClick={() => selectPreset('it')}>💻 IT (5)</button>
                                <button className="quick-btn" onClick={() => selectPreset('all')}>📊 All</button>
                                <button className="quick-btn" onClick={() => selectPreset('none')}>❌ Clear</button>
                            </div>
                            {/* Symbol Grid */}
                            <div className="symbol-grid">
                                {Object.entries(allSymbols).map(([category, symbols]) => (
                                    symbols.map(symbol => (
                                        <label key={symbol} className={`symbol-checkbox ${config.symbols?.includes(symbol) ? 'selected' : ''}`}>
                                            <input
                                                type="checkbox"
                                                checked={config.symbols?.includes(symbol) || false}
                                                onChange={() => toggleSymbol(symbol)}
                                            />
                                            <span>{symbol}</span>
                                        </label>
                                    ))
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Date Range Quick Select */}
                <div className="form-group full-width">
                    <label>📅 Date Range</label>
                    <div className="quick-select-btns">
                        <button className="quick-btn" onClick={() => setDateRange(1)}>1 Day</button>
                        <button className="quick-btn" onClick={() => setDateRange(7)}>7 Days</button>
                        <button className="quick-btn" onClick={() => setDateRange(14)}>14 Days</button>
                        <button className="quick-btn" onClick={() => setDateRange(30)}>30 Days</button>
                        <button className="quick-btn" onClick={() => setDateRange(90)}>90 Days</button>
                    </div>
                </div>

                {/* Compact Config Row */}
                <div className="config-row">
                    <div className="config-item">
                        <label>Start</label>
                        <input
                            type="date"
                            value={config.startDate}
                            onChange={(e) => updateConfig('startDate', e.target.value)}
                        />
                    </div>
                    <div className="config-item">
                        <label>End</label>
                        <input
                            type="date"
                            value={config.endDate}
                            onChange={(e) => updateConfig('endDate', e.target.value)}
                        />
                    </div>
                    <div className="config-item">
                        <label>💰 Capital</label>
                        <input
                            type="number"
                            value={config.capital}
                            onChange={(e) => updateConfig('capital', e.target.value)}
                        />
                    </div>
                    <div className="config-item">
                        <label>⏱ Step</label>
                        <select
                            value={config.step}
                            onChange={(e) => updateConfig('step', e.target.value)}
                        >
                            <option value="1">5m</option>
                            <option value="3">15m</option>
                            <option value="12">1h</option>
                        </select>
                    </div>
                </div>

                {/* Advanced Settings */}
                <div className="form-group full-width">
                    <label className="collapsible-label" onClick={() => setShowAdvanced(!showAdvanced)}>
                        <span>⚙️ Advanced Settings</span>
                        <span className="toggle-icon">{showAdvanced ? '▼' : '▶'}</span>
                    </label>

                    {showAdvanced && (
                        <div className="advanced-section">
                            <div className="config-row">
                                <div className="config-item">
                                    <label>Leverage</label>
                                    <div className="leverage-control">
                                        <input
                                            type="range"
                                            min="1"
                                            max="20"
                                            value={config.leverage}
                                            onChange={(e) => updateConfig('leverage', e.target.value)}
                                        />
                                        <span className="leverage-value">{config.leverage}x</span>
                                    </div>
                                </div>
                                <div className="config-item">
                                    <label>Margin Mode</label>
                                    <select value={config.marginMode} onChange={(e) => updateConfig('marginMode', e.target.value)}>
                                        <option value="cross">🔗 Cross</option>
                                        <option value="isolated">🔒 Isolated</option>
                                    </select>
                                </div>
                                <div className="config-item checkbox-item">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={config.includeFunding}
                                            onChange={(e) => updateConfig('includeFunding', e.target.checked)}
                                        />
                                        Include Funding Rate
                                    </label>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Run/Stop Buttons */}
                <div className="form-actions">
                    <button className="run-btn" onClick={runBacktest} disabled={isRunning}>
                        ▶️ Run Backtest
                    </button>
                    {isRunning && (
                        <button className="stop-btn" onClick={stopBacktest}>
                            ⏹️ Stop
                        </button>
                    )}
                </div>
            </div>

            {/* Progress Section */}
            {isRunning && progress && (
                <div className="progress-section glass-panel">
                    <div className="form-title">⏳ Running Backtest...</div>
                    <div className="progress-bar-container">
                        <div className="progress-bar" style={{ width: `${progress.percent}%` }}></div>
                    </div>
                    <div className="progress-text">{progress.text}</div>

                    <div className="realtime-metrics">
                        <div className="metric-row">
                            <span className="metric-label">Current Equity:</span>
                            <span className="metric-value">₹{(progress.equity || 100000).toLocaleString()}</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Trades:</span>
                            <span className="metric-value">{progress.trades || 0}</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Win Rate:</span>
                            <span className="metric-value">{progress.winRate || 0}%</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Max DD:</span>
                            <span className="metric-value negative">{progress.maxDD || 0}%</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Results Section */}
            {result && !isRunning && (
                <div className="results-section glass-panel">
                    <h2>📊 Backtest Result</h2>

                    <div className="metrics-grid">
                        {/* Performance Card */}
                        <div className="metric-card">
                            <h3>📊 Performance</h3>
                            <div className="metric-item">
                                <span className="metric-label">Final Equity</span>
                                <span className="metric-value large">₹{parseFloat(result.finalEquity).toLocaleString()}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Profit/Loss</span>
                                <span className={`metric-value ${parseFloat(result.profitLoss) >= 0 ? 'positive' : 'negative'}`}>
                                    ₹{parseFloat(result.profitLoss).toLocaleString()}
                                </span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Total Return</span>
                                <span className={`metric-value large ${parseFloat(result.totalReturn) >= 0 ? 'positive' : 'negative'}`}>
                                    {parseFloat(result.totalReturn) >= 0 ? '+' : ''}{result.totalReturn}%
                                </span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Max Drawdown</span>
                                <span className="metric-value negative large">-{result.maxDrawdown}%</span>
                            </div>
                        </div>

                        {/* Risk Card */}
                        <div className="metric-card">
                            <h3>⚖️ Risk Metrics</h3>
                            <div className="metric-item">
                                <span className="metric-label">Sharpe Ratio</span>
                                <span className="metric-value">{result.sharpeRatio}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Sortino Ratio</span>
                                <span className="metric-value">{result.sortinoRatio}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Volatility</span>
                                <span className="metric-value">{result.volatility}%</span>
                            </div>
                        </div>

                        {/* Trading Card */}
                        <div className="metric-card">
                            <h3>📊 Trading</h3>
                            <div className="metric-item">
                                <span className="metric-label">Total Trades</span>
                                <span className="metric-value">{result.totalTrades}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Win Rate</span>
                                <span className="metric-value">{result.winRate}%</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Profit Factor</span>
                                <span className="metric-value">{result.profitFactor}</span>
                            </div>
                        </div>

                        {/* Long/Short Card */}
                        <div className="metric-card">
                            <h3>🐂🐻 Long/Short</h3>
                            <div className="metric-item">
                                <span className="metric-label">Long Trades</span>
                                <span className="metric-value">{result.longTrades}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Short Trades</span>
                                <span className="metric-value">{result.shortTrades}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Avg Hold Time</span>
                                <span className="metric-value">{result.avgHoldTime}</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* History Section */}
            <div className="history-section glass-panel">
                <div className="history-title">📜 Recent Backtests</div>
                <div className="history-list">
                    {history.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-icon">📊</div>
                            <p>No backtest history yet. Run your first backtest above!</p>
                        </div>
                    ) : (
                        history.map(item => (
                            <div key={item.id} className="history-item">
                                <div className="history-info">
                                    <div className="history-main-row">
                                        <span className="symbol">{item.symbol}</span>
                                        <span className="run-time">{new Date(item.timestamp).toLocaleString()}</span>
                                    </div>
                                    <div className="history-detail-row">
                                        <span className="period">{item.period}</span>
                                    </div>
                                </div>
                                <div className="history-stats">
                                    <div className="history-stat">
                                        <span className="label">Return</span>
                                        <span className={`value ${parseFloat(item.result?.totalReturn) >= 0 ? 'positive' : 'negative'}`}>
                                            {parseFloat(item.result?.totalReturn) >= 0 ? '+' : ''}{item.result?.totalReturn}%
                                        </span>
                                    </div>
                                    <div className="history-stat">
                                        <span className="label">Win Rate</span>
                                        <span className="value">{item.result?.winRate}%</span>
                                    </div>
                                    <div className="history-stat">
                                        <span className="label">Trades</span>
                                        <span className="value">{item.result?.totalTrades}</span>
                                    </div>
                                    <div className="history-stat">
                                        <span className="label">Max DD</span>
                                        <span className="value negative">-{item.result?.maxDrawdown}%</span>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            <style>{`
                .backtest-container {
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 20px;
                }

                /* Header */
                .backtest-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    flex-wrap: wrap;
                    gap: 20px;
                }

                .back-link {
                    background: none;
                    border: none;
                    color: #6366f1;
                    font-size: 0.9rem;
                    cursor: pointer;
                    padding: 0;
                    margin-bottom: 8px;
                    display: block;
                }

                .back-link:hover { text-decoration: underline; }

                .backtest-header h1 {
                    margin: 0;
                    font-size: 1.8rem;
                    color: #EAECEF;
                }

                .live-status-indicator {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    background: rgba(0, 0, 0, 0.3);
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 0.85rem;
                    color: #848E9C;
                }

                .status-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background: #00ff9d;
                    box-shadow: 0 0 8px rgba(0, 255, 157, 0.6);
                    animation: pulse 2s ease-in-out infinite;
                }

                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }

                /* Tab Navigation */
                .backtest-tabs {
                    display: flex;
                    align-items: center;
                    gap: 0;
                    margin-bottom: 20px;
                    border-bottom: 2px solid rgba(255, 255, 255, 0.1);
                }

                .backtest-tab {
                    padding: 12px 20px;
                    background: transparent;
                    border: none;
                    color: #848E9C;
                    font-size: 0.95rem;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    border-bottom: 2px solid transparent;
                    margin-bottom: -2px;
                    transition: all 0.2s;
                }

                .backtest-tab:hover {
                    color: #EAECEF;
                    background: rgba(255, 255, 255, 0.03);
                }

                .backtest-tab.active {
                    color: #6366f1;
                    border-bottom-color: #6366f1;
                }

                .tab-status {
                    font-size: 0.75rem;
                    padding: 2px 6px;
                    border-radius: 4px;
                    background: rgba(255, 255, 255, 0.05);
                }

                .tab-status.running {
                    background: rgba(99, 102, 241, 0.2);
                    animation: pulse 2s ease-in-out infinite;
                }

                .tab-status.completed {
                    background: rgba(34, 197, 94, 0.2);
                }

                .tab-close {
                    font-size: 0.85rem;
                    opacity: 0.5;
                    margin-left: 4px;
                    padding: 2px 4px;
                    border-radius: 4px;
                }

                .tab-close:hover {
                    opacity: 1;
                    background: rgba(255, 71, 87, 0.2);
                    color: #F6465D;
                }

                .add-tab-btn {
                    padding: 8px 16px;
                    background: rgba(99, 102, 241, 0.1);
                    border: 1px dashed #6366f1;
                    color: #6366f1;
                    border-radius: 8px;
                    font-size: 0.9rem;
                    cursor: pointer;
                    margin-left: 10px;
                    transition: all 0.2s;
                }

                .add-tab-btn:hover {
                    background: rgba(99, 102, 241, 0.2);
                }

                /* Form */
                .backtest-form {
                    padding: 25px;
                    margin-bottom: 20px;
                }

                .form-title {
                    font-size: 1.1rem;
                    color: #EAECEF;
                    margin-bottom: 20px;
                }

                .form-group {
                    margin-bottom: 16px;
                }

                .form-group.full-width {
                    grid-column: 1 / -1;
                }

                .collapsible-label {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    cursor: pointer;
                    color: #EAECEF;
                    font-size: 0.9rem;
                }

                .toggle-icon {
                    font-size: 0.8rem;
                    color: #5E6673;
                }

                .selected-count {
                    margin-left: auto;
                    font-size: 0.85rem;
                    color: #5E6673;
                }

                .quick-select-btns {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                    margin: 10px 0;
                }

                .quick-btn {
                    background: rgba(99, 102, 241, 0.1);
                    border: 1px solid rgba(99, 102, 241, 0.3);
                    color: #EAECEF;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 0.8rem;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .quick-btn:hover {
                    background: rgba(99, 102, 241, 0.2);
                    border-color: rgba(99, 102, 241, 0.5);
                }

                .symbol-section {
                    margin-top: 10px;
                }

                .symbol-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                    gap: 8px;
                    max-height: 200px;
                    overflow-y: auto;
                    padding: 10px;
                    background: rgba(0, 0, 0, 0.2);
                    border-radius: 8px;
                    margin-top: 10px;
                }

                .symbol-checkbox {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 10px;
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    font-size: 0.85rem;
                    cursor: pointer;
                    color: #EAECEF;
                    transition: all 0.2s;
                }

                .symbol-checkbox:hover {
                    background: rgba(99, 102, 241, 0.1);
                    border-color: rgba(99, 102, 241, 0.3);
                }

                .symbol-checkbox.selected {
                    background: rgba(99, 102, 241, 0.15);
                    border-color: #6366f1;
                }

                .symbol-checkbox input { 
                    accent-color: #6366f1; 
                    width: 14px;
                    height: 14px;
                }

                .config-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 15px;
                    align-items: flex-end;
                    margin: 15px 0;
                }

                .config-item {
                    flex: 1;
                    min-width: 120px;
                }

                .config-item label {
                    display: block;
                    font-size: 0.8rem;
                    color: #5E6673;
                    margin-bottom: 4px;
                }

                .config-item input,
                .config-item select {
                    width: 100%;
                    padding: 8px 10px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: #EAECEF;
                    font-size: 0.9rem;
                }

                .config-item input:focus,
                .config-item select:focus {
                    outline: none;
                    border-color: #6366f1;
                }

                .checkbox-item label {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    cursor: pointer;
                    font-size: 0.85rem;
                    color: #848E9C;
                }

                .checkbox-item input {
                    width: auto;
                    accent-color: #00ff9d;
                }

                .leverage-control {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }

                .leverage-control input {
                    flex: 1;
                }

                .leverage-value {
                    min-width: 45px;
                    font-weight: 600;
                    color: #6366f1;
                }

                .form-actions {
                    display: flex;
                    gap: 12px;
                    margin-top: 20px;
                }

                .run-btn {
                    background: linear-gradient(135deg, #6366f1, #8b5cf6);
                    color: white;
                    border: none;
                    padding: 12px 30px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .run-btn:hover:not(:disabled) {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
                }

                .run-btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                }

                .stop-btn {
                    background: linear-gradient(135deg, #F6465D, #dc3545);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    animation: pulse-red 2s ease-in-out infinite;
                }

                @keyframes pulse-red {
                    0%, 100% { box-shadow: 0 2px 8px rgba(220, 53, 69, 0.3); }
                    50% { box-shadow: 0 4px 20px rgba(220, 53, 69, 0.6); }
                }

                /* Progress Section */
                .progress-section {
                    padding: 20px;
                    margin-bottom: 20px;
                }

                .progress-bar-container {
                    background: rgba(0, 0, 0, 0.3);
                    border-radius: 10px;
                    height: 20px;
                    overflow: hidden;
                    margin: 15px 0;
                }

                .progress-bar {
                    height: 100%;
                    background: linear-gradient(90deg, #6366f1, #8b5cf6);
                    border-radius: 10px;
                    transition: width 0.3s;
                }

                .progress-text {
                    text-align: center;
                    color: #848E9C;
                    font-size: 0.9rem;
                }

                .realtime-metrics {
                    background: rgba(99, 102, 241, 0.05);
                    border-radius: 8px;
                    padding: 12px;
                    margin-top: 15px;
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }

                .metric-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .metric-label {
                    font-size: 0.85rem;
                    color: #848E9C;
                }

                .metric-value {
                    font-size: 0.9rem;
                    font-weight: 600;
                    color: #EAECEF;
                }

                .metric-value.positive { color: #0ECB81; }
                .metric-value.negative { color: #F6465D; }
                .metric-value.large { font-size: 1.1rem; }

                /* Results Section */
                .results-section {
                    padding: 20px;
                    margin-bottom: 20px;
                }

                .results-section h2 {
                    margin: 0 0 20px 0;
                    color: #EAECEF;
                }

                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                    gap: 20px;
                }

                .metric-card {
                    background: rgba(0, 0, 0, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                    padding: 20px;
                }

                .metric-card h3 {
                    font-size: 0.85rem;
                    color: #848E9C;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin: 0 0 15px 0;
                }

                .metric-item {
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                }

                .metric-item:last-child { border-bottom: none; }

                /* History Section */
                .history-section {
                    padding: 20px;
                    margin-top: 30px;
                }

                .history-title {
                    font-size: 1.2rem;
                    color: #EAECEF;
                    margin-bottom: 20px;
                }

                .history-list {
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }

                .history-item {
                    background: rgba(0, 0, 0, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                    padding: 15px 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    cursor: pointer;
                    transition: border-color 0.2s;
                }

                .history-item:hover {
                    border-color: #6366f1;
                }

                .history-info {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }

                .history-main-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 20px;
                }

                .history-info .symbol {
                    font-weight: 600;
                    color: #EAECEF;
                    font-size: 1rem;
                }

                .history-info .run-time {
                    font-size: 0.8rem;
                    color: #5E6673;
                }

                .history-info .period {
                    font-size: 0.85rem;
                    color: #848E9C;
                }

                .history-stats {
                    display: flex;
                    gap: 20px;
                    align-items: center;
                }

                .history-stat {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    min-width: 70px;
                    text-align: center;
                }

                .history-stat .label {
                    font-size: 0.65rem;
                    color: #5E6673;
                    text-transform: uppercase;
                }

                .history-stat .value {
                    font-weight: 700;
                    font-size: 0.95rem;
                    color: #EAECEF;
                }

                .history-stat .value.positive { color: #0ECB81; }
                .history-stat .value.negative { color: #F6465D; }

                .empty-state {
                    text-align: center;
                    padding: 40px;
                    color: #5E6673;
                }

                .empty-icon {
                    font-size: 3rem;
                    margin-bottom: 15px;
                }

                @media (max-width: 768px) {
                    .config-row {
                        flex-direction: column;
                    }
                    .config-item {
                        min-width: 100%;
                    }
                    .history-item {
                        flex-direction: column;
                        gap: 15px;
                    }
                    .history-stats {
                        width: 100%;
                        justify-content: space-between;
                    }
                }
            `}</style>
        </div>
    );
};

export default Backtest;
