import React, { useState, useEffect } from 'react';
import { Shield, AlertTriangle, TrendingDown, Wallet, Activity, XCircle } from 'lucide-react';

const RiskPanel = () => {
    const [riskStatus, setRiskStatus] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchRiskStatus();
        const interval = setInterval(fetchRiskStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    const fetchRiskStatus = async () => {
        try {
            const res = await fetch('/api/risk');
            if (res.ok) {
                setRiskStatus(await res.json());
            }
        } catch (err) {
            console.error('Error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleKillSwitch = async (activate) => {
        try {
            await fetch(`/api/risk/kill-switch?activate=${activate}`, { method: 'POST' });
            fetchRiskStatus();
        } catch (err) {
            console.error('Error:', err);
        }
    };

    // Default values
    const status = riskStatus || {
        daily_pnl: 0,
        daily_trades: 0,
        max_daily_loss: 50000,
        max_trades: 20,
        open_positions: 0,
        kill_switch: false,
        drawdown_pct: 0
    };

    const pnlColor = status.daily_pnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
    const lossProgress = Math.min(100, (Math.abs(status.daily_pnl) / status.max_daily_loss) * 100);
    const tradesProgress = (status.daily_trades / status.max_trades) * 100;

    if (loading) {
        return (
            <div className="loading">
                <div className="spinner"></div>
            </div>
        );
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">Risk Management</h1>
                <div className="trading-status">
                    <Shield size={16} />
                    <span>Risk Controls Active</span>
                </div>
            </div>

            {/* Kill Switch */}
            <div className={`kill-switch ${status.kill_switch ? 'active' : ''}`} style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
                    <AlertTriangle size={24} color={status.kill_switch ? '#ef4444' : '#f59e0b'} />
                    <div>
                        <div style={{ fontWeight: 700, fontSize: '1.125rem' }}>
                            {status.kill_switch ? 'KILL SWITCH ACTIVE' : 'Kill Switch'}
                        </div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                            {status.kill_switch ? 'All trading halted' : 'Press to halt all trading'}
                        </div>
                    </div>
                    <button
                        className={`btn ${status.kill_switch ? 'btn-success' : 'btn-danger'}`}
                        onClick={() => handleKillSwitch(!status.kill_switch)}
                    >
                        {status.kill_switch ? 'Deactivate' : 'Activate'}
                    </button>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
                <div className="card stat-card">
                    <div className="stat-value" style={{ color: pnlColor }}>
                        {status.daily_pnl >= 0 ? '+' : ''}₹{status.daily_pnl.toLocaleString('en-IN')}
                    </div>
                    <div className="stat-label">Daily P&L</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value">{status.daily_trades} / {status.max_trades}</div>
                    <div className="stat-label">Trades Today</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value">{status.open_positions}</div>
                    <div className="stat-label">Open Positions</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value loss">{status.drawdown_pct.toFixed(2)}%</div>
                    <div className="stat-label">Current Drawdown</div>
                </div>
            </div>

            <div className="grid-2">
                {/* Daily Loss Limit */}
                <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}>Daily Loss Limit</h3>

                    <div style={{ marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Current Loss</span>
                            <span style={{ color: status.daily_pnl < 0 ? 'var(--color-loss)' : 'var(--text-primary)' }}>
                                ₹{Math.abs(status.daily_pnl < 0 ? status.daily_pnl : 0).toLocaleString()}
                            </span>
                        </div>
                        <div style={{
                            height: '8px',
                            background: 'var(--bg-tertiary)',
                            borderRadius: '4px',
                            overflow: 'hidden'
                        }}>
                            <div style={{
                                width: `${lossProgress}%`,
                                height: '100%',
                                background: lossProgress > 80 ? 'var(--color-loss)' : lossProgress > 50 ? 'var(--color-warning)' : 'var(--color-profit)',
                                borderRadius: '4px',
                                transition: 'width 0.3s ease'
                            }} />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            <span>₹0</span>
                            <span>Max: ₹{status.max_daily_loss.toLocaleString()}</span>
                        </div>
                    </div>

                    <div style={{
                        padding: '1rem',
                        background: 'var(--bg-tertiary)',
                        borderRadius: '8px',
                        marginTop: '1rem'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                            <TrendingDown size={16} color="var(--color-loss)" />
                            <span style={{ fontWeight: 600 }}>Loss Protection</span>
                        </div>
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                            Trading will automatically halt when daily loss reaches ₹{status.max_daily_loss.toLocaleString()}
                        </div>
                    </div>
                </div>

                {/* Trade Limits */}
                <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}>Trade Limits</h3>

                    <div style={{ marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Trades Used</span>
                            <span>{status.daily_trades} / {status.max_trades}</span>
                        </div>
                        <div style={{
                            height: '8px',
                            background: 'var(--bg-tertiary)',
                            borderRadius: '4px',
                            overflow: 'hidden'
                        }}>
                            <div style={{
                                width: `${tradesProgress}%`,
                                height: '100%',
                                background: 'var(--accent-primary)',
                                borderRadius: '4px',
                                transition: 'width 0.3s ease'
                            }} />
                        </div>
                    </div>

                    {/* Risk Parameters */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1.5rem' }}>
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            padding: '0.75rem 1rem',
                            background: 'var(--bg-tertiary)',
                            borderRadius: '8px'
                        }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Max Position Size</span>
                            <span style={{ fontWeight: 600 }}>₹1,00,000</span>
                        </div>
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            padding: '0.75rem 1rem',
                            background: 'var(--bg-tertiary)',
                            borderRadius: '8px'
                        }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Default Stop Loss</span>
                            <span style={{ fontWeight: 600 }}>2.0%</span>
                        </div>
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            padding: '0.75rem 1rem',
                            background: 'var(--bg-tertiary)',
                            borderRadius: '8px'
                        }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Max Drawdown</span>
                            <span style={{ fontWeight: 600 }}>5.0%</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Risk Events */}
            <div className="card" style={{ marginTop: '1.5rem' }}>
                <h3 className="card-title" style={{ marginBottom: '1rem' }}>Recent Risk Events</h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {[
                        { type: 'info', message: 'Position size adjusted for TCS (exceeded limit)', time: '21:15:00' },
                        { type: 'warning', message: 'High volatility detected in RELIANCE', time: '20:45:00' },
                        { type: 'success', message: 'Stop loss triggered for INFY (+₹1,250 saved)', time: '20:30:00' },
                    ].map((event, idx) => (
                        <div
                            key={idx}
                            style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: '0.75rem 1rem',
                                background: 'var(--bg-tertiary)',
                                borderRadius: '8px',
                                borderLeft: `3px solid ${event.type === 'warning' ? 'var(--color-warning)' : event.type === 'success' ? 'var(--color-profit)' : 'var(--color-info)'}`
                            }}
                        >
                            <span style={{ color: 'var(--text-secondary)' }}>{event.message}</span>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{event.time}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default RiskPanel;
