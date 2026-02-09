import React, { useState, useEffect } from 'react';
import {
    LayoutDashboard, TrendingUp, History, Settings,
    Play, Square, Pause, BarChart3, Shield, Activity, Zap,
    AlertTriangle, Wallet, Bot, RefreshCw, LogOut, X
} from 'lucide-react';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import TradeLog from './pages/TradeLog';
import AgentChat from './pages/AgentChat';
import RiskPanel from './pages/RiskPanel';
import SettingsPage from './pages/Settings';

const App = () => {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [user, setUser] = useState(null);
    const [currentPage, setCurrentPage] = useState('dashboard');
    const [mode, setMode] = useState('paper');
    const [isRunning, setIsRunning] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [systemStatus, setSystemStatus] = useState(null);
    const [cycleCount, setCycleCount] = useState(0);
    const [equity, setEquity] = useState(0);
    const [interval, setIntervalValue] = useState('1');
    const [showSettings, setShowSettings] = useState(false);
    const [ws, setWs] = useState(null);

    // Check if user is already logged in
    useEffect(() => {
        const token = localStorage.getItem('auth_token');
        const username = localStorage.getItem('username');
        const role = localStorage.getItem('user_role');

        if (token && username) {
            setIsAuthenticated(true);
            setUser({ username, role });
        }
    }, []);

    // Fetch initial status when authenticated
    useEffect(() => {
        if (!isAuthenticated) return;

        fetchStatus();

        // Connect WebSocket
        try {
            const websocket = new WebSocket(`ws://${window.location.hostname}:8000/ws`);
            websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'status') {
                    setSystemStatus(data.data);
                    setIsRunning(data.data.is_running);
                    setCycleCount(data.data.cycle_count || 0);
                    // Don't override mode from WS - let user control it
                }
            };
            websocket.onerror = () => {
                console.log('WebSocket connection failed, using polling');
            };
            setWs(websocket);

            return () => websocket.close();
        } catch (err) {
            console.log('WebSocket not available');
        }
    }, [isAuthenticated]);

    const [modeLoaded, setModeLoaded] = useState(false);

    const fetchStatus = async () => {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            setSystemStatus(data);
            setIsRunning(data.is_running);
            setCycleCount(data.cycle_count || 0);
            // Only set mode on first load
            if (!modeLoaded && data.mode) {
                setMode(data.mode);
                setModeLoaded(true);
            }

            // Fetch funds for header display
            fetchFunds();
        } catch (err) {
            console.log('Status fetch failed, using defaults');
        }
    };

    const fetchFunds = async () => {
        try {
            const res = await fetch('/api/account/funds');
            if (res.ok) {
                const data = await res.json();
                // Calculate Total Equity = Available Cash + Utilized Margin + Collateral
                const totalEquity = (data.available || 0) + (data.utilized || 0) + (data.collateral || 0);
                setEquity(totalEquity);
            }
        } catch (err) {
            console.error('Failed to fetch funds:', err);
        }
    };

    const handleLogin = (userData) => {
        setIsAuthenticated(true);
        setUser(userData);
    };

    const handleLogout = () => {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('username');
        localStorage.removeItem('user_role');
        setIsAuthenticated(false);
        setUser(null);
    };

    const handleControl = async (action) => {
        try {
            if (action === 'start') {
                await fetch('/api/trading/start', { method: 'POST' });
                setIsRunning(true);
                setIsPaused(false);
            } else if (action === 'pause') {
                setIsPaused(!isPaused);
            } else if (action === 'stop') {
                await fetch('/api/trading/stop', { method: 'POST' });
                setIsRunning(false);
                setIsPaused(false);
            }
        } catch (err) {
            console.error('Control action failed:', err);
            // Toggle for demo purposes
            if (action === 'start') { setIsRunning(true); setIsPaused(false); }
            if (action === 'stop') { setIsRunning(false); setIsPaused(false); }
            if (action === 'pause') { setIsPaused(!isPaused); }
        }
    };

    const handleModeChange = async (newMode) => {
        try {
            const res = await fetch('/api/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: newMode })
            });
            const data = await res.json();
            setMode(newMode);
            
            // Warn if switching to live without broker
            if (newMode === 'live' && data.broker_connected === false) {
                alert('⚠️ Live mode active but no broker connected.\nGo to Settings → Accounts to connect your broker with TOTP.');
            }
            
            // Re-fetch funds immediately after mode change so header equity updates
            setTimeout(() => {
                fetchFunds();
                fetchStatus();
            }, 300);
        } catch (err) {
            console.error('Failed to change mode:', err);
            setMode(newMode);
        }
    };

    // Show login page if not authenticated
    if (!isAuthenticated) {
        return <Login onLogin={handleLogin} />;
    }

    const getStatusBadge = () => {
        if (!isRunning) return { text: 'STOPPED', class: 'stopped' };
        if (isPaused) return { text: 'PAUSED', class: 'paused' };
        return { text: 'RUNNING', class: 'running' };
    };

    const statusBadge = getStatusBadge();

    return (
        <div className="app-wrapper">
            {/* CRT Scanline Overlay */}
            <div className="crt-overlay" />

            <div className="container">
                {/* Header - Exact Copy from Reference */}
                <header className="glass-panel header">
                    <div className="logo">
                        <span className="icon">🤖</span>
                        <div className="logo-text">
                            <h1>LLM-AngelAgent</h1>
                            <span className="tagline">AI-Powered Trading Platform</span>
                        </div>
                    </div>

                    <div className="status-indicators">
                        <div className="controls">
                            {/* Mode Toggle: Paper / Live */}
                            <div className="mode-toggle-container">
                                <button
                                    className={`mode-toggle-btn ${mode === 'paper' ? 'active' : ''}`}
                                    onClick={() => handleModeChange('paper')}
                                    title="Paper Mode - Simulated Trading"
                                >
                                    📝 Paper
                                </button>
                                <button
                                    className={`mode-toggle-btn ${mode === 'live' ? 'active' : ''}`}
                                    onClick={() => handleModeChange('live')}
                                    title="Live Mode - Real Trading"
                                >
                                    💰 Live
                                </button>
                            </div>

                            {/* Settings Button */}
                            <button className="btn-settings-elegant" onClick={() => setShowSettings(true)}>
                                <span className="settings-icon">⚙️</span>
                                <span className="settings-text">Settings</span>
                            </button>

                            {/* Backtest Button */}
                            <button
                                className="btn-settings-elegant"
                                onClick={() => setCurrentPage(currentPage === 'backtest' ? 'dashboard' : 'backtest')}
                                style={{ marginLeft: '10px' }}
                            >
                                <span className="settings-icon">{currentPage === 'backtest' ? '🏠' : '🔬'}</span>
                                <span className="settings-text">{currentPage === 'backtest' ? 'Dashboard' : 'BackTest'}</span>
                            </button>

                            {/* Logout Button */}
                            <button
                                className="btn-settings-elegant"
                                onClick={handleLogout}
                                style={{ marginLeft: '10px' }}
                            >
                                <span className="settings-icon">🚪</span>
                                <span className="settings-text">Exit</span>
                            </button>

                            {/* Control Buttons */}
                            <button
                                className="btn-control start"
                                onClick={() => handleControl('start')}
                                title="Start Trading"
                            >▶</button>
                            <button
                                className="btn-control pause"
                                onClick={() => handleControl('pause')}
                                title="Pause Trading"
                            >⏸</button>
                            <button
                                className="btn-control stop"
                                onClick={() => handleControl('stop')}
                                title="Stop System"
                            >⏹</button>

                            {/* Interval Selector */}
                            <select
                                className="interval-selector"
                                value={interval}
                                onChange={(e) => setIntervalValue(e.target.value)}
                            >
                                <option value="0.5">30 sec</option>
                                <option value="1">1 min</option>
                                <option value="3">3 min</option>
                                <option value="5">5 min</option>
                                <option value="15">15 min</option>
                            </select>
                        </div>

                        {/* Status Items */}
                        <div className="status-item">
                            <span className="label">MODE</span>
                            <span className={`value badge ${statusBadge.class}`}>{statusBadge.text}</span>
                        </div>
                        <div className="status-item">
                            <span className="label">ENVIRONMENT</span>
                            <span className="value badge">{mode.toUpperCase()}</span>
                        </div>
                        <div className="status-item">
                            <span className="label">CYCLE</span>
                            <span className="value">#{cycleCount}</span>
                        </div>
                        <div className="status-item">
                            <span className="label">EQUITY</span>
                            <span className="value">₹{equity.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                    </div>
                </header>

                {/* Main Content - Page Routing */}
                {currentPage === 'dashboard' ? (
                    <main className="dashboard-grid">
                        <Dashboard
                            status={systemStatus}
                            mode={mode}
                            cycleCount={cycleCount}
                            isRunning={isRunning}
                        />
                    </main>
                ) : currentPage === 'backtest' ? (
                    <main className="backtest-page-container">
                        <Backtest onBack={() => setCurrentPage('dashboard')} />
                    </main>
                ) : null}
            </div>

            {/* Settings Modal */}
            {showSettings && (
                <div className="modal-overlay" onClick={() => setShowSettings(false)}>
                    <div className="modal-content settings-modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>⚙️ Settings</h3>
                            <button className="btn-close" onClick={() => setShowSettings(false)}>×</button>
                        </div>
                        <div className="settings-body">
                            <SettingsPage embedded={true} />
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                .app-wrapper {
                    min-height: 100vh;
                    position: relative;
                }

                .container {
                    max-width: 100%;
                    padding: 20px;
                    position: relative;
                    z-index: 1;
                }

                .backtest-page-container {
                    flex: 1;
                    overflow-y: auto;
                }

                /* Header */
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 24px;
                    height: 64px;
                    margin-bottom: 20px;
                    background: rgba(2, 3, 4, 0.85);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }

                .logo {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }

                .logo .icon {
                    font-size: 2rem;
                    filter: drop-shadow(0 0 10px rgba(240, 185, 11, 0.5));
                }

                .logo-text h1 {
                    font-size: 1.2rem;
                    font-weight: 700;
                    margin: 0;
                    background: linear-gradient(135deg, #F0B90B 0%, #FFD700 50%, #00F0FF 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }

                .logo-text .tagline {
                    font-size: 0.7rem;
                    color: #848E9C;
                }

                .status-indicators {
                    display: flex;
                    align-items: center;
                    gap: 20px;
                }

                .controls {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }

                /* Mode Toggle */
                .mode-toggle-container {
                    display: flex;
                    background: rgba(0, 0, 0, 0.3);
                    border-radius: 8px;
                    padding: 2px;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                }

                .mode-toggle-btn {
                    padding: 6px 14px;
                    border: none;
                    background: transparent;
                    color: #848E9C;
                    font-size: 0.8rem;
                    font-weight: 600;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }

                .mode-toggle-btn.active {
                    background: linear-gradient(135deg, #F0B90B 0%, #FFD700 100%);
                    color: #05070A;
                    box-shadow: 0 2px 10px rgba(240, 185, 11, 0.3);
                }

                .mode-toggle-btn:hover:not(.active) {
                    color: #EAECEF;
                }

                /* Settings Button */
                .btn-settings-elegant {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 12px;
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: #EAECEF;
                    font-size: 0.8rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }

                .btn-settings-elegant:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-color: rgba(240, 185, 11, 0.3);
                }

                .settings-icon {
                    font-size: 1rem;
                }

                .settings-text {
                    font-weight: 500;
                }

                /* Control Buttons */
                .btn-control {
                    width: 32px;
                    height: 32px;
                    border: none;
                    border-radius: 6px;
                    font-size: 0.9rem;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.2s ease;
                }

                .btn-control.start {
                    background: rgba(14, 203, 129, 0.2);
                    color: #0ECB81;
                    border: 1px solid rgba(14, 203, 129, 0.3);
                }

                .btn-control.start:hover {
                    background: rgba(14, 203, 129, 0.3);
                    box-shadow: 0 0 15px rgba(14, 203, 129, 0.3);
                }

                .btn-control.pause {
                    background: rgba(240, 185, 11, 0.2);
                    color: #F0B90B;
                    border: 1px solid rgba(240, 185, 11, 0.3);
                }

                .btn-control.pause:hover {
                    background: rgba(240, 185, 11, 0.3);
                }

                .btn-control.stop {
                    background: rgba(246, 70, 93, 0.2);
                    color: #F6465D;
                    border: 1px solid rgba(246, 70, 93, 0.3);
                }

                .btn-control.stop:hover {
                    background: rgba(246, 70, 93, 0.3);
                }

                /* Interval Selector */
                .interval-selector {
                    padding: 6px 10px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: #EAECEF;
                    font-size: 0.8rem;
                    cursor: pointer;
                }

                /* Status Items */
                .status-item {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 2px;
                }

                .status-item .label {
                    font-size: 0.65rem;
                    color: #5E6673;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }

                .status-item .value {
                    font-size: 0.85rem;
                    font-weight: 600;
                    font-family: 'IBM Plex Mono', monospace;
                }

                .status-item .badge {
                    padding: 2px 10px;
                    border-radius: 4px;
                    font-size: 0.75rem;
                }

                .status-item .badge.stopped {
                    background: rgba(246, 70, 93, 0.2);
                    color: #F6465D;
                    border: 1px solid rgba(246, 70, 93, 0.3);
                }

                .status-item .badge.running {
                    background: rgba(14, 203, 129, 0.2);
                    color: #0ECB81;
                    border: 1px solid rgba(14, 203, 129, 0.3);
                }

                .status-item .badge.paused {
                    background: rgba(240, 185, 11, 0.2);
                    color: #F0B90B;
                    border: 1px solid rgba(240, 185, 11, 0.3);
                }

                /* Dashboard Grid */
                .dashboard-grid {
                    display: flex;
                    flex-direction: column;
                    gap: 20px;
                }

                /* Modal */
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.8);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                }

                .modal-content {
                    background: linear-gradient(135deg, rgba(5, 7, 10, 0.98) 0%, rgba(14, 18, 23, 0.95) 100%);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    max-width: 600px;
                    width: 90%;
                    max-height: 80vh;
                    overflow: hidden;
                }

                .modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1.25rem 1.5rem;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }

                .modal-header h3 {
                    margin: 0;
                    font-size: 1.1rem;
                    color: #EAECEF;
                }

                .btn-close {
                    background: none;
                    border: none;
                    color: #848E9C;
                    font-size: 1.5rem;
                    cursor: pointer;
                    line-height: 1;
                }

                .btn-close:hover {
                    color: #F6465D;
                }

                .settings-body {
                    padding: 1.5rem;
                    max-height: 60vh;
                    overflow-y: auto;
                }

                /* Responsive */
                @media (max-width: 1200px) {
                    .header {
                        flex-direction: column;
                        height: auto;
                        gap: 1rem;
                        padding: 1rem;
                    }

                    .status-indicators {
                        flex-wrap: wrap;
                        justify-content: center;
                    }

                    .controls {
                        flex-wrap: wrap;
                        justify-content: center;
                    }
                }
            `}</style>
        </div>
    );
};

export default App;
