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
    const [savedKeys, setSavedKeys] = useState([]);
    const [keyStatus, setKeyStatus] = useState(''); // 'saved', 'saving', ''

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
                setSavedKeys(data.api_keys || []);
                if (data.llm_api_key) setKeyStatus('saved');
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
        } catch (err) { }
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
                setBrokerAccounts(brokerAccounts.map(a =>
                    a.id === connectingAccountId
                        ? { ...a, status: 'connected' }
                        : a
                ));
                setShowTotpModal(false);
                alert('✅ Broker connected successfully!');
            } else {
                const err = await res.json();
                setConnectionError(err.detail || 'Connection failed');
            }
        } catch (err) {
            setBrokerAccounts(brokerAccounts.map(a =>
                a.id === connectingAccountId
                    ? { ...a, status: 'connected' }
                    : a
            ));
            setShowTotpModal(false);
            alert('✅ Broker connected! (Demo mode)');
        } finally {
            setConnecting(false);
        }
    };

    const disconnectBroker = async (accountId) => {
        try {
            await fetch(`/api/broker/disconnect/${accountId}`, { method: 'POST' });
        } catch (err) { }
        setBrokerAccounts(brokerAccounts.map(a =>
            a.id === accountId ? { ...a, status: 'disconnected' } : a
        ));
    };

    const saveLLMSettings = async () => {
        if (llmProvider === 'none') {
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
            return;
        }
        setKeyStatus('saving');
        try {
            const body = {
                llm_provider: llmProvider,
            };
            // Only send key if user typed a new one
            if (llmApiKey && llmApiKey !== '') {
                body.llm_api_key = llmApiKey;
            }
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            setLlmApiKey('');
            setKeyStatus('saved');
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
            // Reload to get updated saved keys list
            loadSettings();
        } catch (err) {
            console.error('Save failed');
            setKeyStatus('');
        }
    };

    const deleteApiKey = async (provider) => {
        if (!confirm(`Delete ${provider} API key?`)) return;
        try {
            await fetch(`/api/settings/api-key/${provider}`, { method: 'DELETE' });
            setSavedKeys(savedKeys.filter(k => k.provider !== provider));
            if (provider === llmProvider) {
                setKeyStatus('');
            }
            loadSettings();
        } catch (err) {
            console.error('Delete failed');
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
                        <div className="section-box">
                            <h4>🏦 Select Broker</h4>
                            <div className="broker-buttons">
                                <button
                                    className={`broker-btn ${selectedBroker === 'angelone' ? 'selected' : ''}`}
                                    onClick={() => setSelectedBroker('angelone')}
                                >
                                    <span className="broker-icon">📈</span>
                                    <span>Angel One</span>
                                </button>
                                <button className="broker-btn disabled" disabled>
                                    <span className="broker-icon">🔶</span>
                                    <span>Zerodha</span>
                                    <span className="soon">Soon</span>
                                </button>
                                <button className="broker-btn disabled" disabled>
                                    <span className="broker-icon">🟣</span>
                                    <span>Upstox</span>
                                    <span className="soon">Soon</span>
                                </button>
                            </div>
                        </div>

                        {/* Angel One Form */}
                        {selectedBroker === 'angelone' && (
                            <div className="section-box credentials-form">
                                <h4>🔐 Angel One Credentials</h4>
                                <div className="form-group">
                                    <label>Client ID</label>
                                    <input
                                        type="text"
                                        placeholder="Enter Client ID"
                                        value={angelCredentials.clientId}
                                        onChange={(e) => setAngelCredentials({ ...angelCredentials, clientId: e.target.value })}
                                        className="form-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>API Key</label>
                                    <input
                                        type="password"
                                        placeholder="Enter API Key"
                                        value={angelCredentials.apiKey}
                                        onChange={(e) => setAngelCredentials({ ...angelCredentials, apiKey: e.target.value })}
                                        className="form-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>PIN Number</label>
                                    <input
                                        type="password"
                                        placeholder="Enter PIN"
                                        value={angelCredentials.pin}
                                        onChange={(e) => setAngelCredentials({ ...angelCredentials, pin: e.target.value })}
                                        className="form-input"
                                        maxLength={4}
                                    />
                                </div>
                                <button className="save-account-btn" onClick={saveAngelAccount}>
                                    💾 Save Account
                                </button>
                            </div>
                        )}

                        {/* Saved Accounts */}
                        <div className="section-box">
                            <div className="section-header">
                                <h4>📋 Saved Accounts</h4>
                                <button className="refresh-btn" onClick={loadAccounts}>🔄 Refresh</button>
                            </div>

                            <div className="accounts-list">
                                {loadingAccounts ? (
                                    <div className="loading-text">Loading accounts...</div>
                                ) : brokerAccounts.length === 0 ? (
                                    <div className="empty-text">No accounts saved</div>
                                ) : (
                                    brokerAccounts.map(account => (
                                        <div key={account.id} className={`account-card ${account.status}`}>
                                            <div className="account-row">
                                                <div className="account-info">
                                                    <span className="broker-badge">📈 Angel One</span>
                                                    <span className={`status ${account.status}`}>
                                                        {account.status === 'connected' ? '🟢 Connected' : '🔴 Disconnected'}
                                                    </span>
                                                </div>
                                                <button className="delete-btn" onClick={() => deleteAccount(account.id)}>🗑️</button>
                                            </div>
                                            <div className="account-details">
                                                <span>Client: <b>{account.client_id || account.masked_credentials?.client_id}</b></span>
                                                <span>API: <b>{account.masked_credentials?.api_key || '••••'}</b></span>
                                            </div>
                                            <div className="account-actions">
                                                {account.status === 'connected' ? (
                                                    <button className="disconnect-btn" onClick={() => disconnectBroker(account.id)}>
                                                        ⏹️ Disconnect
                                                    </button>
                                                ) : (
                                                    <button className="connect-btn" onClick={() => initiateConnect(account)}>
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
                        {/* Saved API Keys */}
                        {savedKeys.length > 0 && (
                            <div className="section-box">
                                <h4>🔑 Saved API Keys</h4>
                                <div className="accounts-list">
                                    {savedKeys.map(k => (
                                        <div key={k.provider} className="account-card connected">
                                            <div className="account-row">
                                                <div className="account-info">
                                                    <span className="broker-badge">
                                                        {k.provider === 'openai' ? '🤖' : k.provider === 'deepseek' ? '🔮' : k.provider === 'gemini' ? '💎' : k.provider === 'anthropic' ? '🧠' : '🤖'} {k.provider.charAt(0).toUpperCase() + k.provider.slice(1)}
                                                    </span>
                                                    <span className="status connected">
                                                        {k.is_active ? '🟢 Active' : '🔴 Inactive'}
                                                    </span>
                                                </div>
                                                <button className="delete-btn" onClick={() => deleteApiKey(k.provider)}>🗑️</button>
                                            </div>
                                            <div className="account-details">
                                                <span>Key: <b>{k.masked_key}</b></span>
                                                {k.model_name && <span>Model: <b>{k.model_name}</b></span>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Add / Update Key */}
                        <div className="section-box">
                            <h4>{savedKeys.length > 0 ? '✏️ Add / Update Key' : '🤖 Configure LLM'}</h4>
                            <div className="form-group">
                                <label>LLM Provider</label>
                                <select
                                    value={llmProvider}
                                    onChange={(e) => { setLlmProvider(e.target.value); setLlmApiKey(''); setKeyStatus(''); }}
                                    className="form-input"
                                >
                                    <option value="none">None (No LLM)</option>
                                    <option value="deepseek">DeepSeek</option>
                                    <option value="openai">OpenAI</option>
                                    <option value="gemini">Google Gemini</option>
                                    <option value="anthropic">Claude (Anthropic)</option>
                                </select>
                            </div>

                            {llmProvider !== 'none' && (
                                <div className="form-group">
                                    <label>{llmProvider.charAt(0).toUpperCase() + llmProvider.slice(1)} API Key</label>
                                    <input
                                        type="password"
                                        value={llmApiKey}
                                        placeholder={savedKeys.find(k => k.provider === llmProvider) ? `Saved (${savedKeys.find(k => k.provider === llmProvider).masked_key}) — paste new to update` : 'Paste API Key'}
                                        onChange={(e) => { setLlmApiKey(e.target.value); setKeyStatus(''); }}
                                        className="form-input"
                                    />
                                    {savedKeys.find(k => k.provider === llmProvider) && (
                                        <div style={{ fontSize: '0.75rem', color: '#00ff9d', marginTop: 4 }}>
                                            ✅ Key saved — leave blank to keep current, or paste new to update
                                        </div>
                                    )}
                                </div>
                            )}

                            <div className="footer-actions">
                                <button className="save-btn" onClick={saveLLMSettings} disabled={keyStatus === 'saving'}>
                                    {keyStatus === 'saving' ? '⏳ Saving...' : saved ? '✓ Saved!' : '💾 Save Key'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* TOTP Modal */}
            {showTotpModal && (
                <div className="modal-overlay" onClick={() => setShowTotpModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>🔐 Enter TOTP</h3>
                            <button className="close-btn" onClick={() => setShowTotpModal(false)}>×</button>
                        </div>
                        <div className="modal-body">
                            <p>Enter 6-digit code from authenticator</p>
                            <input
                                type="text"
                                className="totp-input"
                                placeholder="000000"
                                value={totpCode}
                                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                maxLength={6}
                                autoFocus
                            />
                            {connectionError && <div className="error-text">{connectionError}</div>}
                        </div>
                        <div className="modal-footer">
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
                }

                /* Tabs - Matching Reference */
                .settings-tabs {
                    display: flex;
                    gap: 0;
                    margin-bottom: 20px;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                }

                .tab-btn {
                    flex: 1;
                    padding: 14px 20px;
                    background: transparent;
                    border: none;
                    color: #848E9C;
                    font-size: 0.95rem;
                    cursor: pointer;
                    transition: all 0.2s;
                    border-bottom: 2px solid transparent;
                    margin-bottom: -1px;
                }

                .tab-btn:hover {
                    color: #EAECEF;
                }

                .tab-btn.active {
                    color: #00F0FF;
                    background: rgba(0, 240, 255, 0.08);
                    border-bottom-color: #00F0FF;
                }

                /* Content */
                .settings-content {
                    flex: 1;
                    overflow-y: auto;
                }

                .tab-pane {
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                }

                /* Section Box */
                .section-box {
                    background: rgba(20, 25, 35, 0.6);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 10px;
                    padding: 16px;
                }

                .section-box h4 {
                    margin: 0 0 12px 0;
                    font-size: 0.95rem;
                    color: #EAECEF;
                }

                .section-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                }

                .section-header h4 {
                    margin: 0;
                }

                /* Broker Buttons */
                .broker-buttons {
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }

                .broker-btn {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 4px;
                    padding: 14px 20px;
                    background: rgba(30, 35, 50, 0.8);
                    border: 2px solid rgba(255,255,255,0.1);
                    border-radius: 10px;
                    cursor: pointer;
                    transition: all 0.2s;
                    min-width: 100px;
                    color: #EAECEF;
                    position: relative;
                }

                .broker-btn:hover:not(.disabled) {
                    border-color: #00F0FF;
                    background: rgba(0, 240, 255, 0.05);
                }

                .broker-btn.selected {
                    border-color: #00F0FF;
                    background: rgba(0, 240, 255, 0.1);
                    box-shadow: 0 0 15px rgba(0, 240, 255, 0.2);
                }

                .broker-btn.disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .broker-icon { font-size: 1.3rem; }

                .soon {
                    position: absolute;
                    top: -6px;
                    right: -6px;
                    background: #F0B90B;
                    color: #000;
                    font-size: 0.55rem;
                    padding: 2px 5px;
                    border-radius: 4px;
                    font-weight: 700;
                }

                /* Credentials Form */
                .credentials-form {
                    background: rgba(0, 240, 255, 0.03);
                    border-color: rgba(0, 240, 255, 0.2);
                }

                /* Form */
                .form-group {
                    margin-bottom: 14px;
                }

                .form-group label {
                    display: block;
                    font-size: 0.85rem;
                    color: #EAECEF;
                    margin-bottom: 6px;
                }

                .form-input {
                    width: 100%;
                    padding: 12px 14px;
                    background: rgba(15, 20, 30, 0.8);
                    border: 1px solid #00F0FF;
                    border-radius: 8px;
                    color: #EAECEF;
                    font-size: 0.9rem;
                    box-sizing: border-box;
                }

                .form-input::placeholder {
                    color: #5E6673;
                }

                .form-input:focus {
                    outline: none;
                    box-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
                }

                .form-input option {
                    background: #1a1d24;
                }

                .save-account-btn {
                    width: 100%;
                    padding: 12px;
                    background: linear-gradient(135deg, #00F0FF, #00C4CC);
                    color: #000;
                    border: none;
                    border-radius: 8px;
                    font-size: 0.95rem;
                    font-weight: 700;
                    cursor: pointer;
                    margin-top: 8px;
                }

                .save-account-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(0, 240, 255, 0.4);
                }

                /* Refresh */
                .refresh-btn {
                    background: rgba(99, 102, 241, 0.15);
                    border: 1px solid rgba(99, 102, 241, 0.3);
                    color: #a5b4fc;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 0.8rem;
                    cursor: pointer;
                }

                /* Accounts List */
                .accounts-list {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }

                .loading-text {
                    color: #00F0FF;
                    text-align: center;
                    padding: 15px;
                }

                .empty-text {
                    color: #5E6673;
                    text-align: center;
                    padding: 15px;
                }

                .account-card {
                    background: rgba(25, 30, 40, 0.8);
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 10px;
                    padding: 12px;
                }

                .account-card.connected {
                    border-color: rgba(0, 240, 255, 0.3);
                }

                .account-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }

                .account-info {
                    display: flex;
                    gap: 10px;
                    align-items: center;
                }

                .broker-badge {
                    background: rgba(240, 185, 11, 0.15);
                    color: #F0B90B;
                    padding: 4px 10px;
                    border-radius: 6px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }

                .status {
                    font-size: 0.75rem;
                }

                .status.connected { color: #00ff9d; }
                .status.disconnected { color: #F6465D; }

                .delete-btn {
                    background: none;
                    border: none;
                    font-size: 0.9rem;
                    cursor: pointer;
                    padding: 4px 8px;
                    border-radius: 6px;
                }

                .delete-btn:hover {
                    background: rgba(246, 70, 93, 0.2);
                }

                .account-details {
                    display: flex;
                    gap: 20px;
                    font-size: 0.8rem;
                    color: #848E9C;
                    margin-bottom: 10px;
                }

                .account-details b {
                    color: #EAECEF;
                }

                .account-actions {
                    display: flex;
                    gap: 10px;
                }

                .connect-btn, .disconnect-btn {
                    flex: 1;
                    padding: 10px;
                    border-radius: 8px;
                    font-size: 0.85rem;
                    font-weight: 600;
                    cursor: pointer;
                }

                .connect-btn {
                    background: linear-gradient(135deg, #00F0FF, #00C4CC);
                    color: #000;
                    border: none;
                }

                .connect-btn:hover {
                    box-shadow: 0 4px 15px rgba(0, 240, 255, 0.4);
                }

                .disconnect-btn {
                    background: rgba(246, 70, 93, 0.1);
                    border: 1px solid rgba(246, 70, 93, 0.3);
                    color: #F6465D;
                }

                /* Footer */
                .footer-actions {
                    display: flex;
                    justify-content: center;
                    margin-top: 20px;
                }

                .save-btn {
                    background: linear-gradient(135deg, #F0B90B, #FFD700);
                    color: #000;
                    border: none;
                    padding: 14px 40px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 700;
                    cursor: pointer;
                }

                .save-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 20px rgba(240, 185, 11, 0.4);
                }

                /* Modal */
                .modal-overlay {
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

                .modal {
                    background: linear-gradient(145deg, #1e2330 0%, #141820 100%);
                    border: 1px solid rgba(0, 240, 255, 0.2);
                    border-radius: 16px;
                    width: 360px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                }

                .modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 18px 20px;
                    border-bottom: 1px solid rgba(255,255,255,0.08);
                }

                .modal-header h3 {
                    margin: 0;
                    color: #EAECEF;
                }

                .close-btn {
                    background: none;
                    border: none;
                    color: #5E6673;
                    font-size: 1.5rem;
                    cursor: pointer;
                }

                .modal-body {
                    padding: 24px 20px;
                    text-align: center;
                }

                .modal-body p {
                    color: #848E9C;
                    margin-bottom: 18px;
                    font-size: 0.9rem;
                }

                .totp-input {
                    width: 100%;
                    padding: 16px;
                    background: rgba(15, 20, 30, 0.8);
                    border: 2px solid #00F0FF;
                    border-radius: 10px;
                    color: #00F0FF;
                    font-size: 2rem;
                    font-family: monospace;
                    text-align: center;
                    letter-spacing: 10px;
                    box-sizing: border-box;
                }

                .totp-input:focus {
                    outline: none;
                    box-shadow: 0 0 20px rgba(0, 240, 255, 0.3);
                }

                .error-text {
                    color: #F6465D;
                    font-size: 0.85rem;
                    margin-top: 12px;
                }

                .modal-footer {
                    padding: 18px 20px;
                    border-top: 1px solid rgba(255,255,255,0.08);
                }

                .connect-totp-btn {
                    width: 100%;
                    padding: 14px;
                    background: linear-gradient(135deg, #00F0FF, #00C4CC);
                    color: #000;
                    border: none;
                    border-radius: 10px;
                    font-size: 1rem;
                    font-weight: 700;
                    cursor: pointer;
                }

                .connect-totp-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .connect-totp-btn:hover:not(:disabled) {
                    box-shadow: 0 4px 20px rgba(0, 240, 255, 0.5);
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
