import React, { useState, useEffect } from 'react';
import { Save, Eye, EyeOff, RefreshCw, Plus } from 'lucide-react';

const Settings = ({ embedded = false }) => {
    const [activeTab, setActiveTab] = useState('api-keys');
    const [showPasswords, setShowPasswords] = useState({});
    const [saved, setSaved] = useState(false);
    const [accounts, setAccounts] = useState([]);

    const [settings, setSettings] = useState({
        // Trading Mode
        runMode: 'test',

        // Angel One Broker
        angelApiKey: '',
        angelClientId: '',
        angelPassword: '',
        angelTotpSecret: '',

        // LLM Provider
        llmProvider: 'none',
        deepseekKey: '',
        openaiKey: '',
        claudeKey: '',
        geminiKey: '',
    });

    const [newAccount, setNewAccount] = useState({
        id: '',
        name: '',
        exchange: 'angelone',
        testnet: true
    });

    useEffect(() => {
        // Load saved settings
        const saved = localStorage.getItem('trading_settings');
        if (saved) {
            try {
                setSettings(prev => ({ ...prev, ...JSON.parse(saved) }));
            } catch (e) { }
        }
    }, []);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setSettings(prev => ({ ...prev, [name]: value }));
    };

    const togglePassword = (field) => {
        setShowPasswords(prev => ({ ...prev, [field]: !prev[field] }));
    };

    const handleSave = async () => {
        try {
            // Save to localStorage
            localStorage.setItem('trading_settings', JSON.stringify(settings));

            // Try to save to backend
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            }).catch(() => { });

            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (err) {
            console.error('Save failed:', err);
        }
    };

    const handleAddAccount = () => {
        if (newAccount.id && newAccount.name) {
            setAccounts(prev => [...prev, { ...newAccount }]);
            setNewAccount({ id: '', name: '', exchange: 'angelone', testnet: true });
        }
    };

    const llmProviders = [
        { value: 'none', label: 'None (No LLM)' },
        { value: 'deepseek', label: 'DeepSeek (Default)' },
        { value: 'openai', label: 'OpenAI' },
        { value: 'claude', label: 'Claude (Anthropic)' },
        { value: 'gemini', label: 'Gemini (Google)' }
    ];

    const llmKeyFields = {
        deepseek: { key: 'deepseekKey', placeholder: 'Saved (Hidden)', link: 'https://platform.deepseek.com' },
        openai: { key: 'openaiKey', placeholder: 'sk-...', link: 'https://platform.openai.com' },
        claude: { key: 'claudeKey', placeholder: 'sk-ant-...', link: 'https://console.anthropic.com' },
        gemini: { key: 'geminiKey', placeholder: 'Saved (Hidden)', link: 'https://aistudio.google.com' }
    };

    return (
        <div className="settings-container">
            {/* Tabs */}
            <div className="settings-tabs">
                <button
                    className={`tab-btn ${activeTab === 'api-keys' ? 'active' : ''}`}
                    onClick={() => setActiveTab('api-keys')}
                >
                    API Keys
                </button>
                <button
                    className={`tab-btn ${activeTab === 'accounts' ? 'active' : ''}`}
                    onClick={() => setActiveTab('accounts')}
                >
                    Accounts
                </button>
            </div>

            {/* Tab Content */}
            <div className="settings-body">
                {/* API Keys Tab */}
                {activeTab === 'api-keys' && (
                    <div className="tab-pane">
                        {/* Trading Mode */}
                        <div className="form-group">
                            <label>Trading Mode</label>
                            <select
                                name="runMode"
                                value={settings.runMode}
                                onChange={handleChange}
                                className="form-control mode-select"
                            >
                                <option value="test">Test Mode (Paper Trading)</option>
                                <option value="live">Live Trading (Real Money)</option>
                            </select>
                            <p className="help-text">Requires restart to apply change.</p>
                        </div>

                        <hr className="divider" />

                        {/* Angel One Broker */}
                        <div className="section-title">🏦 Angel One Broker</div>

                        <div className="form-group">
                            <label>API Key</label>
                            <div className="input-with-icon">
                                <input
                                    type={showPasswords.angelApiKey ? 'text' : 'password'}
                                    name="angelApiKey"
                                    value={settings.angelApiKey}
                                    onChange={handleChange}
                                    className="form-control"
                                    placeholder="Saved (Hidden)"
                                />
                                <button
                                    className="btn-icon"
                                    onClick={() => togglePassword('angelApiKey')}
                                >
                                    {showPasswords.angelApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                        </div>

                        <div className="form-group">
                            <label>Client ID</label>
                            <input
                                type="text"
                                name="angelClientId"
                                value={settings.angelClientId}
                                onChange={handleChange}
                                className="form-control"
                                placeholder="Your Angel One Client ID"
                            />
                        </div>

                        <div className="form-group">
                            <label>Password</label>
                            <div className="input-with-icon">
                                <input
                                    type={showPasswords.angelPassword ? 'text' : 'password'}
                                    name="angelPassword"
                                    value={settings.angelPassword}
                                    onChange={handleChange}
                                    className="form-control"
                                    placeholder="Saved (Hidden)"
                                />
                                <button
                                    className="btn-icon"
                                    onClick={() => togglePassword('angelPassword')}
                                >
                                    {showPasswords.angelPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                        </div>

                        <div className="form-group">
                            <label>TOTP Secret</label>
                            <div className="input-with-icon">
                                <input
                                    type={showPasswords.angelTotpSecret ? 'text' : 'password'}
                                    name="angelTotpSecret"
                                    value={settings.angelTotpSecret}
                                    onChange={handleChange}
                                    className="form-control"
                                    placeholder="Your TOTP Secret Key"
                                />
                                <button
                                    className="btn-icon"
                                    onClick={() => togglePassword('angelTotpSecret')}
                                >
                                    {showPasswords.angelTotpSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                        </div>

                        <hr className="divider" />

                        {/* LLM Provider */}
                        <div className="form-group">
                            <label>🤖 LLM Provider</label>
                            <select
                                name="llmProvider"
                                value={settings.llmProvider}
                                onChange={handleChange}
                                className="form-control llm-select"
                            >
                                {llmProviders.map(p => (
                                    <option key={p.value} value={p.value}>{p.label}</option>
                                ))}
                            </select>
                            <p className="help-text">Requires restart to apply.</p>
                        </div>

                        {/* Dynamic LLM API Key Field */}
                        {settings.llmProvider !== 'none' && llmKeyFields[settings.llmProvider] && (
                            <div className="form-group llm-key-field">
                                <label>{llmProviders.find(p => p.value === settings.llmProvider)?.label} API Key</label>
                                <div className="input-with-icon">
                                    <input
                                        type={showPasswords.llmKey ? 'text' : 'password'}
                                        name={llmKeyFields[settings.llmProvider].key}
                                        value={settings[llmKeyFields[settings.llmProvider].key]}
                                        onChange={handleChange}
                                        className="form-control"
                                        placeholder={llmKeyFields[settings.llmProvider].placeholder}
                                    />
                                    <button
                                        className="btn-icon"
                                        onClick={() => togglePassword('llmKey')}
                                    >
                                        {showPasswords.llmKey ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                                <p className="help-text-link">
                                    Get key: <a href={llmKeyFields[settings.llmProvider].link} target="_blank" rel="noreferrer">
                                        {llmKeyFields[settings.llmProvider].link.replace('https://', '')}
                                    </a>
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* Accounts Tab */}
                {activeTab === 'accounts' && (
                    <div className="tab-pane">
                        <div className="form-group">
                            <div className="accounts-header">
                                <label>📊 Trading Accounts</label>
                                <button className="btn-refresh">
                                    <RefreshCw size={14} /> Refresh
                                </button>
                            </div>
                            <div className="accounts-list">
                                {accounts.length === 0 ? (
                                    <p className="empty-text">No accounts configured</p>
                                ) : (
                                    accounts.map((acc, idx) => (
                                        <div key={idx} className="account-item">
                                            <span className="account-name">{acc.name}</span>
                                            <span className="account-id">{acc.id}</span>
                                            <span className={`account-badge ${acc.testnet ? 'testnet' : 'live'}`}>
                                                {acc.testnet ? 'Testnet' : 'Live'}
                                            </span>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        <hr className="divider" />

                        <div className="form-group">
                            <label>➕ Add New Account</label>
                            <div className="form-grid">
                                <input
                                    type="text"
                                    value={newAccount.id}
                                    onChange={(e) => setNewAccount(prev => ({ ...prev, id: e.target.value }))}
                                    className="form-control"
                                    placeholder="Account ID"
                                />
                                <input
                                    type="text"
                                    value={newAccount.name}
                                    onChange={(e) => setNewAccount(prev => ({ ...prev, name: e.target.value }))}
                                    className="form-control"
                                    placeholder="Display Name"
                                />
                            </div>
                            <div className="form-grid" style={{ marginTop: '10px' }}>
                                <select
                                    value={newAccount.exchange}
                                    onChange={(e) => setNewAccount(prev => ({ ...prev, exchange: e.target.value }))}
                                    className="form-control"
                                >
                                    <option value="angelone">Angel One</option>
                                    <option value="zerodha">Zerodha</option>
                                    <option value="upstox">Upstox</option>
                                </select>
                                <label className="checkbox-label">
                                    <input
                                        type="checkbox"
                                        checked={newAccount.testnet}
                                        onChange={(e) => setNewAccount(prev => ({ ...prev, testnet: e.target.checked }))}
                                    />
                                    <span>Testnet Mode</span>
                                </label>
                            </div>
                            <button className="btn-add-account" onClick={handleAddAccount}>
                                <Plus size={16} /> Add Account
                            </button>
                            <p className="help-text">Note: Set API keys in .env with format: ACCOUNT_{'{ID}'}_API_KEY</p>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="modal-footer">
                <button className="btn-save" onClick={handleSave}>
                    <Save size={16} />
                    {saved ? 'Saved!' : 'Save Changes'}
                </button>
            </div>

            <style>{`
                .settings-container {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                }

                .settings-tabs {
                    display: flex;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    background: rgba(0, 0, 0, 0.2);
                }

                .tab-btn {
                    flex: 1;
                    padding: 12px 16px;
                    background: none;
                    border: none;
                    color: #a0aec0;
                    font-size: 0.9rem;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                    border-bottom: 2px solid transparent;
                }

                .tab-btn:hover {
                    color: #fff;
                    background: rgba(255, 255, 255, 0.05);
                }

                .tab-btn.active {
                    color: #00ff9d;
                    border-bottom-color: #00ff9d;
                    background: rgba(0, 255, 157, 0.05);
                }

                .settings-body {
                    flex: 1;
                    padding: 20px;
                    overflow-y: auto;
                    max-height: 50vh;
                }

                .tab-pane {
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                }

                .section-title {
                    font-size: 0.85rem;
                    font-weight: 600;
                    color: #F0B90B;
                    margin-bottom: 8px;
                }

                .form-group {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }

                .form-group label {
                    font-size: 0.85rem;
                    color: #EAECEF;
                    font-weight: 500;
                }

                .form-control {
                    padding: 10px 14px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: #EAECEF;
                    font-size: 0.9rem;
                    width: 100%;
                    transition: all 0.2s;
                }

                .form-control:focus {
                    outline: none;
                    border-color: #F0B90B;
                    box-shadow: 0 0 0 2px rgba(240, 185, 11, 0.1);
                }

                .form-control option {
                    background: #1a202c;
                    color: #EAECEF;
                }

                .mode-select {
                    border-color: #ecc94b;
                }

                .llm-select {
                    border-color: #00ff9d;
                }

                .input-with-icon {
                    position: relative;
                    display: flex;
                }

                .input-with-icon .form-control {
                    padding-right: 40px;
                }

                .btn-icon {
                    position: absolute;
                    right: 10px;
                    top: 50%;
                    transform: translateY(-50%);
                    background: none;
                    border: none;
                    color: #5E6673;
                    cursor: pointer;
                    padding: 4px;
                }

                .btn-icon:hover {
                    color: #EAECEF;
                }

                .help-text {
                    font-size: 0.75rem;
                    color: #a0aec0;
                    margin-top: 4px;
                }

                .help-text-link {
                    font-size: 0.7rem;
                    color: #718096;
                    margin-top: 2px;
                }

                .help-text-link a {
                    color: #00ff9d;
                    text-decoration: none;
                }

                .help-text-link a:hover {
                    text-decoration: underline;
                }

                .divider {
                    border: none;
                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                    margin: 16px 0;
                }

                .llm-key-field {
                    animation: fadeIn 0.2s ease;
                }

                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-5px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                /* Accounts Tab */
                .accounts-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }

                .btn-refresh {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    background: #2d3748;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 0.8rem;
                }

                .btn-refresh:hover {
                    background: #4a5568;
                }

                .accounts-list {
                    background: rgba(0, 0, 0, 0.2);
                    padding: 12px;
                    border-radius: 6px;
                    min-height: 100px;
                    max-height: 200px;
                    overflow-y: auto;
                }

                .empty-text {
                    color: #718096;
                    text-align: center;
                    font-size: 0.85rem;
                }

                .account-item {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 10px;
                    background: rgba(255, 255, 255, 0.03);
                    border-radius: 6px;
                    margin-bottom: 8px;
                }

                .account-name {
                    font-weight: 600;
                    color: #EAECEF;
                }

                .account-id {
                    font-size: 0.8rem;
                    color: #718096;
                    flex: 1;
                }

                .account-badge {
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.7rem;
                    font-weight: 600;
                }

                .account-badge.testnet {
                    background: rgba(168, 85, 247, 0.2);
                    color: #a855f7;
                }

                .account-badge.live {
                    background: rgba(14, 203, 129, 0.2);
                    color: #0ECB81;
                }

                .form-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 10px;
                }

                .checkbox-label {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    cursor: pointer;
                    padding: 10px 14px;
                    background: rgba(0, 0, 0, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                }

                .checkbox-label input[type="checkbox"] {
                    width: 18px;
                    height: 18px;
                    accent-color: #00ff9d;
                }

                .btn-add-account {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    margin-top: 12px;
                    background: #00ff9d;
                    color: #1a202c;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .btn-add-account:hover {
                    background: #00e08a;
                    transform: translateY(-1px);
                }

                /* Footer */
                .modal-footer {
                    padding: 16px 20px;
                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                    display: flex;
                    justify-content: flex-end;
                }

                .btn-save {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 10px 24px;
                    background: linear-gradient(135deg, #F0B90B 0%, #FFD700 100%);
                    color: #05070A;
                    border: none;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 0.9rem;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .btn-save:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 20px rgba(240, 185, 11, 0.4);
                }
            `}</style>
        </div>
    );
};

export default Settings;
