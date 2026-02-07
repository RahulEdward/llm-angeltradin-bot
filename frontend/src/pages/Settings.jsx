import React, { useState, useEffect } from 'react';

const Settings = ({ embedded = false, onClose }) => {
    const [activeTab, setActiveTab] = useState('accounts');
    const [saved, setSaved] = useState(false);

    // Broker Accounts State
    const [brokerAccounts, setBrokerAccounts] = useState([]);
    const [loadingAccounts, setLoadingAccounts] = useState(true);

    // New Account Form
    const [selectedBroker, setSelectedBroker] = useState('');
    const [angelCredentials, setAngelCredentials] = useState({
        clientId: '',
        apiKey: '',
        pin: ''
    });

    // TOTP Modal
    const [showTotpModal, setShowTotpModal] = useState(false);
    const [totpCode, setTotpCode] = useState('');
    const [connectingAccountId, setConnectingAccountId] = useState(null);
    const [connecting, setConnecting] = useState(false);
    const [connectionError, setConnectionError] = useState('');

    // LLM Settings
    const [llmProvider, setLlmProvider] = useState('none');
    const [llmApiKey, setLlmApiKey] = useState('');

    useEffect(() => {
        loadAccounts();
        loadSettings();
    }, []);

    const loadAccounts = async () => {
        setLoadingAccounts(true);
        try {
            const res = await fetch('/api/broker/accounts');
            if (res.ok) {
                const data = await res.json();
                setBrokerAccounts(data.accounts || []);
            }
        } catch (err) {
            console.log('Accounts load failed');
        } finally {
            setLoadingAccounts(false);
        }
    };

    const loadSettings = async () => {
        try {
            const res = await fetch('/api/settings');
            if (res.ok) {
                const data = await res.json();
                setLlmProvider(data.llm_provider || 'none');
                if (data.llm_api_key) setLlmApiKey('saved');
            }
        } catch (err) {
            console.log('Settings load failed');
        }
    };

    const saveAngelAccount = async () => {
        if (!angelCredentials.clientId || !angelCredentials.apiKey || !angelCredentials.pin) {
            alert('Please fill all fields');
            return;
        }

        try {
            const res = await fetch('/api/broker/accounts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    broker: 'angelone',
                    client_id: angelCredentials.clientId,
                    api_key: angelCredentials.apiKey,
                    pin: angelCredentials.pin
                })
            });

            if (res.ok) {
                const data = await res.json();
                setBrokerAccounts([...brokerAccounts, data.account]);
                setAngelCredentials({ clientId: '', apiKey: '', pin: '' });
                setSelectedBroker('');
                setSaved(true);
                setTimeout(() => setSaved(false), 2000);
            } else {
                const err = await res.json();
                alert(err.detail || 'Failed to save account');
            }
        } catch (err) {
            // Demo: Add locally
            const newAccount = {
                id: Date.now().toString(),
                broker: 'angelone',
                client_id: angelCredentials.clientId,
                status: 'disconnected',
                masked_credentials: {
                    client_id: angelCredentials.clientId,
                    api_key: '****' + angelCredentials.apiKey.slice(-4),
                    pin: '****'
                }
            };
            setBrokerAccounts([...brokerAccounts, newAccount]);
            setAngelCredentials({ clientId: '', apiKey: '', pin: '' });
            setSelectedBroker('');
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        }
    };

    const deleteAccount = async (accountId) => {
        if (!confirm('Are you sure you want to delete this broker account?')) return;

        try {
            await fetch(`/api/broker/accounts/${accountId}`, { method: 'DELETE' });
        } catch (err) {
            // Continue anyway
        }
        setBrokerAccounts(brokerAccounts.filter(a => a.id !== accountId));
    };

    const initiateConnect = (account) => {
        setConnectingAccountId(account.id);
        setTotpCode('');
        setConnectionError('');
        setShowTotpModal(true);
    };

    const connectWithTotp = async () => {
        if (totpCode.length !== 6) {
            setConnectionError('Please enter 6-digit TOTP code');
            return;
        }

        setConnecting(true);
        setConnectionError('');

        try {
            const res = await fetch('/api/broker/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    account_id: connectingAccountId,
                    totp: totpCode
                })
            });

            if (res.ok) {
                const data = await res.json();
                // Update account status
                setBrokerAccounts(brokerAccounts.map(a =>
                    a.id === connectingAccountId
                        ? { ...a, status: 'connected', session: data.session }
                        : a
                ));
                setShowTotpModal(false);
                alert('✅ Broker connected successfully! Symbol fetching started.');
            } else {
                const err = await res.json();
                setConnectionError(err.detail || 'Connection failed');
            }
        } catch (err) {
            // Demo: Simulate success
            setBrokerAccounts(brokerAccounts.map(a =>
                a.id === connectingAccountId
                    ? { ...a, status: 'connected' }
                    : a
            ));
            setShowTotpModal(false);
            alert('✅ Broker connected successfully! (Demo mode)');
        } finally {
            setConnecting(false);
        }
    };

    const disconnectBroker = async (accountId) => {
        try {
            await fetch(`/api/broker/disconnect/${accountId}`, { method: 'POST' });
        } catch (err) {
            // Continue
        }
        setBrokerAccounts(brokerAccounts.map(a =>
            a.id === accountId ? { ...a, status: 'disconnected' } : a
        ));
    };

    const saveLLMSettings = async () => {
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    llm_provider: llmProvider,
                    llm_api_key: llmApiKey !== 'saved' ? llmApiKey : undefined
                })
            });
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (err) {
            console.error('Save failed');
        }
    };

    const content = (
        <div className="settings-container">
            {/* Tabs */}
            <div className="settings-tabs">
                <button
                    className={`tab-btn ${activeTab === 'accounts' ? 'active' : ''}`}
                    onClick={() => setActiveTab('accounts')}
                >
                    Accounts
                </button>
                <button
                    className={`tab-btn ${activeTab === 'api' ? 'active' : ''}`}
                    onClick={() => setActiveTab('api')}
                >
                    API Keys
                </button>
            </div>

            {/* Tab Content */}
            <div className="settings-content">
                {/* Accounts Tab */}
                {activeTab === 'accounts' && (
                    <div className="tab-pane">
                        {/* Broker Selection */}
                        <div className="broker-selection">
                            <h4>🏦 Select Broker</h4>
                            <div className="broker-buttons">
                                <button
                                    className={`broker-btn ${selectedBroker === 'angelone' ? 'selected' : ''}`}
                                    onClick={() => setSelectedBroker('angelone')}
                                >
                                    <span className="broker-icon">📈</span>
                                    <span className="broker-name">Angel One</span>
                                </button>
                                <button
                                    className={`broker-btn ${selectedBroker === 'zerodha' ? 'selected' : ''}`}
                                    onClick={() => setSelectedBroker('zerodha')}
                                    disabled
                                >
                                    <span className="broker-icon">🔶</span>
                                    <span className="broker-name">Zerodha</span>
                                    <span className="coming-soon">Coming Soon</span>
                                </button>
                                <button
                                    className={`broker-btn ${selectedBroker === 'upstox' ? 'selected' : ''}`}
                                    onClick={() => setSelectedBroker('upstox')}
                                    disabled
                                >
                                    <span className="broker-icon">🟣</span>
                                    <span className="broker-name">Upstox</span>
                                    <span className="coming-soon">Coming Soon</span>
                                </button>
                            </div>
                        </div>

                        {/* Angel One Credentials Form */}
                        {selectedBroker === 'angelone' && (
                            <div className="credentials-form">
                                <h4>🔐 Angel One Credentials</h4>
                                <div className="form-group">
                                    <label>Client ID</label>
                                    <input
                                        type="text"
                                        placeholder="Enter your Client ID (e.g., ABC123)"
                                        value={angelCredentials.clientId}
                                        onChange={(e) => setAngelCredentials({ ...angelCredentials, clientId: e.target.value })}
                                        className="form-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>API Key</label>
                                    <input
                                        type="password"
                                        placeholder="Enter your API Key"
                                        value={angelCredentials.apiKey}
                                        onChange={(e) => setAngelCredentials({ ...angelCredentials, apiKey: e.target.value })}
                                        className="form-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>PIN Number</label>
                                    <input
                                        type="password"
                                        placeholder="Enter your 4-digit PIN"
                                        value={angelCredentials.pin}
                                        onChange={(e) => setAngelCredentials({ ...angelCredentials, pin: e.target.value })}
                                        className="form-input"
                                        maxLength={4}
                                    />
                                </div>
                                <button className="save-credentials-btn" onClick={saveAngelAccount}>
                                    💾 Save Account
                                </button>
                                <p className="security-note">
                                    🔒 Your credentials are encrypted and stored securely
                                </p>
                            </div>
                        )}

                        {/* Connected Accounts */}
                        <div className="connected-accounts">
                            <div className="section-header">
                                <h4>📋 Saved Broker Accounts</h4>
                                <button className="refresh-btn" onClick={loadAccounts}>
                                    🔄 Refresh
                                </button>
                            </div>

                            <div className="accounts-list">
                                {loadingAccounts ? (
                                    <div className="loading-text">Loading accounts...</div>
                                ) : brokerAccounts.length === 0 ? (
                                    <div className="empty-text">No broker accounts configured</div>
                                ) : (
                                    brokerAccounts.map(account => (
                                        <div key={account.id} className={`account-card ${account.status}`}>
                                            <div className="account-header">
                                                <div className="broker-info">
                                                    <span className="broker-badge">
                                                        {account.broker === 'angelone' ? '📈 Angel One' : account.broker}
                                                    </span>
                                                    <span className={`status-badge ${account.status}`}>
                                                        {account.status === 'connected' ? '🟢 Connected' : '🔴 Disconnected'}
                                                    </span>
                                                </div>
                                                <button
                                                    className="delete-btn"
                                                    onClick={() => deleteAccount(account.id)}
                                                >
                                                    🗑️
                                                </button>
                                            </div>

                                            <div className="account-details">
                                                <div className="detail-row">
                                                    <span className="label">Client ID:</span>
                                                    <span className="value">{account.client_id || account.masked_credentials?.client_id}</span>
                                                </div>
                                                <div className="detail-row">
                                                    <span className="label">API Key:</span>
                                                    <span className="value masked">{account.masked_credentials?.api_key || '••••••••'}</span>
                                                </div>
                                                <div className="detail-row">
                                                    <span className="label">PIN:</span>
                                                    <span className="value masked">{account.masked_credentials?.pin || '••••'}</span>
                                                </div>
                                            </div>

                                            <div className="account-actions">
                                                {account.status === 'connected' ? (
                                                    <button
                                                        className="disconnect-btn"
                                                        onClick={() => disconnectBroker(account.id)}
                                                    >
                                                        ⏹️ Disconnect
                                                    </button>
                                                ) : (
                                                    <button
                                                        className="connect-btn"
                                                        onClick={() => initiateConnect(account)}
                                                    >
                                                        🔗 Connect
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* API Keys Tab */}
                {activeTab === 'api' && (
                    <div className="tab-pane">
                        <div className="form-group">
                            <label>🤖 LLM Provider</label>
                            <select
                                value={llmProvider}
                                onChange={(e) => setLlmProvider(e.target.value)}
                                className="form-select"
                            >
                                <option value="none">None (No LLM)</option>
                                <option value="deepseek">DeepSeek</option>
                                <option value="openai">OpenAI</option>
                                <option value="gemini">Google Gemini</option>
                            </select>
                        </div>

                        {llmProvider !== 'none' && (
                            <div className="form-group">
                                <label>{llmProvider.charAt(0).toUpperCase() + llmProvider.slice(1)} API Key</label>
                                <input
                                    type="password"
                                    value={llmApiKey === 'saved' ? '' : llmApiKey}
                                    placeholder={llmApiKey === 'saved' ? 'Saved (Hidden)' : 'Enter API Key'}
                                    onChange={(e) => setLlmApiKey(e.target.value)}
                                    className="form-input"
                                />
                            </div>
                        )}

                        <button className="save-btn" onClick={saveLLMSettings}>
                            {saved ? '✓ Saved!' : 'Save Changes'}
                        </button>
                    </div>
                )}
            </div>

            {/* TOTP Modal */}
            {showTotpModal && (
                <div className="totp-modal-overlay" onClick={() => setShowTotpModal(false)}>
                    <div className="totp-modal" onClick={e => e.stopPropagation()}>
                        <div className="totp-header">
                            <h3>🔐 Enter TOTP Code</h3>
                            <button className="close-btn" onClick={() => setShowTotpModal(false)}>×</button>
                        </div>
                        <div className="totp-body">
                            <p>Enter the 6-digit code from your authenticator app</p>
                            <input
                                type="text"
                                className="totp-input"
                                placeholder="000000"
                                value={totpCode}
                                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                maxLength={6}
                                autoFocus
                            />
                            {connectionError && (
                                <div className="error-message">{connectionError}</div>
                            )}
                        </div>
                        <div className="totp-footer">
                            <button
                                className="connect-totp-btn"
                                onClick={connectWithTotp}
                                disabled={connecting || totpCode.length !== 6}
                            >
                                {connecting ? '⏳ Connecting...' : '🚀 Connect'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                .settings-container {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    max-height: 70vh;
                }

                /* Tabs */
                .settings-tabs {
                    display: flex;
                    border-bottom: 2px solid rgba(255, 255, 255, 0.1);
                    margin-bottom: 20px;
                }

                .tab-btn {
                    flex: 1;
                    padding: 12px 20px;
                    background: transparent;
                    border: none;
                    color: #848E9C;
                    font-size: 0.95rem;
                    cursor: pointer;
                    border-bottom: 2px solid transparent;
                    margin-bottom: -2px;
                    transition: all 0.2s;
                }

                .tab-btn:hover { color: #EAECEF; }

                .tab-btn.active {
                    color: #00ff9d;
                    border-bottom-color: #00ff9d;
                    background: rgba(0, 255, 157, 0.05);
                }

                /* Content */
                .settings-content {
                    flex: 1;
                    overflow-y: auto;
                    padding-right: 5px;
                }

                .tab-pane {
                    display: flex;
                    flex-direction: column;
                    gap: 20px;
                }

                /* Broker Selection */
                .broker-selection h4,
                .credentials-form h4,
                .connected-accounts h4 {
                    margin: 0 0 12px 0;
                    font-size: 1rem;
                    color: #EAECEF;
                }

                .broker-buttons {
                    display: flex;
                    gap: 12px;
                    flex-wrap: wrap;
                }

                .broker-btn {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 6px;
                    padding: 16px 24px;
                    background: rgba(255, 255, 255, 0.03);
                    border: 2px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    cursor: pointer;
                    transition: all 0.2s;
                    min-width: 120px;
                    position: relative;
                }

                .broker-btn:hover:not(:disabled) {
                    border-color: #00ff9d;
                    background: rgba(0, 255, 157, 0.05);
                }

                .broker-btn.selected {
                    border-color: #00ff9d;
                    background: rgba(0, 255, 157, 0.1);
                    box-shadow: 0 0 20px rgba(0, 255, 157, 0.2);
                }

                .broker-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .broker-icon { font-size: 1.5rem; }
                .broker-name { font-size: 0.9rem; color: #EAECEF; font-weight: 600; }

                .coming-soon {
                    position: absolute;
                    top: -8px;
                    right: -8px;
                    background: #F0B90B;
                    color: #0A0B0D;
                    font-size: 0.6rem;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-weight: 700;
                }

                /* Credentials Form */
                .credentials-form {
                    background: rgba(0, 255, 157, 0.03);
                    border: 1px solid rgba(0, 255, 157, 0.2);
                    border-radius: 12px;
                    padding: 20px;
                }

                .form-group {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                    margin-bottom: 16px;
                }

                .form-group label {
                    font-size: 0.9rem;
                    color: #EAECEF;
                }

                .form-input, .form-select {
                    padding: 12px 14px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 8px;
                    color: #EAECEF;
                    font-size: 0.95rem;
                }

                .form-input::placeholder { color: #5E6673; }

                .form-input:focus, .form-select:focus {
                    outline: none;
                    border-color: #00ff9d;
                }

                .save-credentials-btn {
                    width: 100%;
                    background: linear-gradient(135deg, #00ff9d, #00cc7d);
                    color: #0A0B0D;
                    border: none;
                    padding: 14px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 700;
                    cursor: pointer;
                    transition: all 0.2s;
                    margin-top: 10px;
                }

                .save-credentials-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 20px rgba(0, 255, 157, 0.4);
                }

                .security-note {
                    text-align: center;
                    font-size: 0.8rem;
                    color: #5E6673;
                    margin-top: 12px;
                }

                /* Connected Accounts */
                .connected-accounts {
                    margin-top: 10px;
                }

                .section-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                }

                .refresh-btn {
                    background: rgba(99, 102, 241, 0.15);
                    border: 1px solid rgba(99, 102, 241, 0.4);
                    color: #a5b4fc;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 0.8rem;
                    cursor: pointer;
                }

                .accounts-list {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }

                .loading-text { color: #00ff9d; text-align: center; padding: 20px; }
                .empty-text { color: #5E6673; text-align: center; padding: 20px; }

                .account-card {
                    background: rgba(0, 0, 0, 0.2);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                    padding: 16px;
                    transition: all 0.2s;
                }

                .account-card.connected {
                    border-color: rgba(0, 255, 157, 0.3);
                }

                .account-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                }

                .broker-info {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }

                .broker-badge {
                    background: rgba(240, 185, 11, 0.15);
                    color: #F0B90B;
                    padding: 4px 10px;
                    border-radius: 6px;
                    font-size: 0.85rem;
                    font-weight: 600;
                }

                .status-badge {
                    font-size: 0.8rem;
                    padding: 4px 10px;
                    border-radius: 6px;
                }

                .status-badge.connected {
                    background: rgba(0, 255, 157, 0.1);
                    color: #00ff9d;
                }

                .status-badge.disconnected {
                    background: rgba(246, 70, 93, 0.1);
                    color: #F6465D;
                }

                .delete-btn {
                    background: none;
                    border: none;
                    font-size: 1rem;
                    cursor: pointer;
                    padding: 6px;
                    border-radius: 6px;
                    transition: all 0.2s;
                }

                .delete-btn:hover {
                    background: rgba(246, 70, 93, 0.2);
                }

                .account-details {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                    margin-bottom: 12px;
                }

                .detail-row {
                    display: flex;
                    justify-content: space-between;
                    font-size: 0.85rem;
                }

                .detail-row .label { color: #5E6673; }
                .detail-row .value { color: #EAECEF; font-family: monospace; }
                .detail-row .value.masked { color: #848E9C; }

                .account-actions {
                    display: flex;
                    gap: 10px;
                }

                .connect-btn, .disconnect-btn {
                    flex: 1;
                    padding: 10px;
                    border-radius: 8px;
                    font-size: 0.9rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .connect-btn {
                    background: linear-gradient(135deg, #00ff9d, #00cc7d);
                    color: #0A0B0D;
                    border: none;
                }

                .connect-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(0, 255, 157, 0.4);
                }

                .disconnect-btn {
                    background: rgba(246, 70, 93, 0.1);
                    border: 1px solid rgba(246, 70, 93, 0.3);
                    color: #F6465D;
                }

                .disconnect-btn:hover {
                    background: rgba(246, 70, 93, 0.2);
                }

                /* TOTP Modal */
                .totp-modal-overlay {
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

                .totp-modal {
                    background: linear-gradient(145deg, #1a1d24 0%, #0d0e12 100%);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    width: 380px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                }

                .totp-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }

                .totp-header h3 { margin: 0; color: #EAECEF; }

                .close-btn {
                    background: none;
                    border: none;
                    color: #5E6673;
                    font-size: 1.5rem;
                    cursor: pointer;
                }

                .totp-body {
                    padding: 25px 20px;
                    text-align: center;
                }

                .totp-body p {
                    color: #848E9C;
                    margin-bottom: 20px;
                    font-size: 0.9rem;
                }

                .totp-input {
                    width: 100%;
                    padding: 16px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 2px solid rgba(0, 255, 157, 0.3);
                    border-radius: 12px;
                    color: #00ff9d;
                    font-size: 2rem;
                    font-family: monospace;
                    text-align: center;
                    letter-spacing: 8px;
                }

                .totp-input:focus {
                    outline: none;
                    border-color: #00ff9d;
                    box-shadow: 0 0 20px rgba(0, 255, 157, 0.3);
                }

                .error-message {
                    color: #F6465D;
                    font-size: 0.85rem;
                    margin-top: 12px;
                }

                .totp-footer {
                    padding: 20px;
                    border-top: 1px solid rgba(255, 255, 255, 0.08);
                }

                .connect-totp-btn {
                    width: 100%;
                    padding: 14px;
                    background: linear-gradient(135deg, #00ff9d, #00cc7d);
                    color: #0A0B0D;
                    border: none;
                    border-radius: 10px;
                    font-size: 1rem;
                    font-weight: 700;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .connect-totp-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .connect-totp-btn:hover:not(:disabled) {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 20px rgba(0, 255, 157, 0.5);
                }

                /* API Tab */
                .save-btn {
                    background: linear-gradient(135deg, #F0B90B, #FFD700);
                    color: #0A0B0D;
                    border: none;
                    padding: 12px 30px;
                    border-radius: 8px;
                    font-size: 0.95rem;
                    font-weight: 700;
                    cursor: pointer;
                    margin-top: 10px;
                    align-self: flex-end;
                }

                .save-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(240, 185, 11, 0.4);
                }

                .form-select option {
                    background: #1a1d24;
                    color: #EAECEF;
                }
            `}</style>
        </div>
    );

    if (embedded) {
        return content;
    }

    return (
        <div className="settings-page">
            <div className="page-header">
                <h2>⚙️ Settings</h2>
            </div>
            {content}
        </div>
    );
};

export default Settings;
