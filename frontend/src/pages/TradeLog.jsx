import React, { useState, useEffect } from 'react';
import { History, Filter, Download, TrendingUp, TrendingDown } from 'lucide-react';

const TradeLog = () => {
    const [trades, setTrades] = useState([]);
    const [orders, setOrders] = useState([]);
    const [filter, setFilter] = useState('all');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchTrades();
    }, []);

    const fetchTrades = async () => {
        try {
            const res = await fetch('/api/orders');
            if (res.ok) {
                const data = await res.json();
                setOrders(data || []);
            }
        } catch (err) {
            console.error('Error fetching trades:', err);
        } finally {
            setLoading(false);
        }
    };

    // Demo trades for display
    const demoTrades = [
        { id: 1, symbol: 'RELIANCE', side: 'BUY', quantity: 100, entry: 2450.00, exit: 2485.00, pnl: 3500, pnlPct: 1.43, time: '2024-02-06 10:15:00', status: 'closed', reasoning: 'Bullish EMA crossover + RSI oversold' },
        { id: 2, symbol: 'TCS', side: 'SELL', quantity: 50, entry: 3980.00, exit: 3920.00, pnl: 3000, pnlPct: 1.51, time: '2024-02-06 11:30:00', status: 'closed', reasoning: 'Bearish divergence on MACD' },
        { id: 3, symbol: 'INFY', side: 'BUY', quantity: 150, entry: 1580.00, exit: 1545.00, pnl: -5250, pnlPct: -2.22, time: '2024-02-06 12:45:00', status: 'closed', reasoning: 'Failed breakout - stop loss hit' },
        { id: 4, symbol: 'HDFCBANK', side: 'BUY', quantity: 75, entry: 1620.00, exit: null, pnl: 1125, pnlPct: 0.93, time: '2024-02-06 14:00:00', status: 'open', reasoning: 'Strong support bounce with volume' },
        { id: 5, symbol: 'ICICIBANK', side: 'BUY', quantity: 200, entry: 1050.00, exit: 1072.00, pnl: 4400, pnlPct: 2.10, time: '2024-02-05 09:30:00', status: 'closed', reasoning: 'Sector rotation + institutional buying' },
    ];

    const displayTrades = orders.length > 0 ? orders : demoTrades;

    const filteredTrades = displayTrades.filter(t => {
        if (filter === 'all') return true;
        if (filter === 'wins') return t.pnl > 0;
        if (filter === 'losses') return t.pnl < 0;
        if (filter === 'open') return t.status === 'open';
        return true;
    });

    const totalPnL = filteredTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
    const wins = filteredTrades.filter(t => t.pnl > 0).length;
    const losses = filteredTrades.filter(t => t.pnl < 0).length;

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">Trade Log</h1>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn btn-outline">
                        <Download size={16} />
                        Export
                    </button>
                </div>
            </div>

            {/* Summary Stats */}
            <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
                <div className="card stat-card">
                    <div className="stat-value">{filteredTrades.length}</div>
                    <div className="stat-label">Total Trades</div>
                </div>
                <div className="card stat-card">
                    <div className={`stat-value ${totalPnL >= 0 ? 'profit' : 'loss'}`}>
                        ₹{totalPnL.toLocaleString('en-IN')}
                    </div>
                    <div className="stat-label">Total P&L</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value profit">{wins}</div>
                    <div className="stat-label">Winning Trades</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value loss">{losses}</div>
                    <div className="stat-label">Losing Trades</div>
                </div>
            </div>

            {/* Filters */}
            <div className="card">
                <div className="card-header">
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {['all', 'wins', 'losses', 'open'].map(f => (
                            <button
                                key={f}
                                className={`btn ${filter === f ? 'btn-primary' : 'btn-outline'}`}
                                onClick={() => setFilter(f)}
                                style={{ padding: '0.5rem 1rem' }}
                            >
                                {f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        ))}
                    </div>
                    <span className="badge info">{filteredTrades.length} trades</span>
                </div>

                {/* Trades Table */}
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Symbol</th>
                                <th>Side</th>
                                <th>Qty</th>
                                <th>Entry</th>
                                <th>Exit</th>
                                <th>P&L</th>
                                <th>Status</th>
                                <th>Reasoning</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={9} style={{ textAlign: 'center' }}>
                                        <div className="spinner" style={{ margin: '1rem auto' }}></div>
                                    </td>
                                </tr>
                            ) : filteredTrades.length === 0 ? (
                                <tr>
                                    <td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                                        No trades found
                                    </td>
                                </tr>
                            ) : (
                                filteredTrades.map((trade) => (
                                    <tr key={trade.id}>
                                        <td style={{ whiteSpace: 'nowrap' }}>{trade.time}</td>
                                        <td>
                                            <strong>{trade.symbol}</strong>
                                        </td>
                                        <td>
                                            <span className={`badge ${trade.side === 'BUY' ? 'success' : 'danger'}`}>
                                                {trade.side}
                                            </span>
                                        </td>
                                        <td>{trade.quantity}</td>
                                        <td>₹{trade.entry?.toFixed(2)}</td>
                                        <td>{trade.exit ? `₹${trade.exit.toFixed(2)}` : '-'}</td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                                {trade.pnl >= 0 ? <TrendingUp size={14} color="#10b981" /> : <TrendingDown size={14} color="#ef4444" />}
                                                <span style={{ color: trade.pnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                                                    {trade.pnl >= 0 ? '+' : ''}₹{trade.pnl?.toLocaleString()}
                                                </span>
                                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                                    ({trade.pnlPct >= 0 ? '+' : ''}{trade.pnlPct?.toFixed(2)}%)
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            <span className={`badge ${trade.status === 'open' ? 'warning' : 'info'}`}>
                                                {trade.status}
                                            </span>
                                        </td>
                                        <td style={{ maxWidth: '200px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                            {trade.reasoning}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default TradeLog;
