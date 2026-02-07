import React, { useState, useEffect } from 'react';
import { Zap, Lock, User, Eye, EyeOff, AlertCircle } from 'lucide-react';

const Login = ({ onLogin }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [deploymentMode, setDeploymentMode] = useState('local');

    useEffect(() => {
        // Check deployment mode and auto-fill credentials for development
        checkDeploymentMode();
    }, []);

    const checkDeploymentMode = async () => {
        try {
            const res = await fetch('/api/info');
            if (res.ok) {
                const data = await res.json();
                setDeploymentMode(data.deployment_mode || 'local');

                // Auto-fill for local development
                if (data.deployment_mode === 'local') {
                    setUsername('admin');
                    setPassword('admin123');
                }
            }
        } catch (e) {
            // Default to local mode for development
            setUsername('admin');
            setPassword('admin123');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('user_role', data.role || 'user');
                localStorage.setItem('auth_token', data.token || 'authenticated');
                localStorage.setItem('username', username);
                onLogin(data);
            } else {
                const data = await response.json();
                setError(data.detail || 'Invalid credentials');
            }
        } catch (err) {
            // For development: allow login without backend
            console.log('Backend not available, using demo mode');
            localStorage.setItem('user_role', 'admin');
            localStorage.setItem('auth_token', 'demo_token');
            localStorage.setItem('username', username || 'admin');
            onLogin({ role: 'admin', username: username || 'admin' });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-page">
            {/* CRT Overlay */}
            <div className="crt-overlay" />

            {/* Animated Background Grid */}
            <div className="login-bg-grid" />

            {/* Floating Particles */}
            <div className="particles">
                {[...Array(20)].map((_, i) => (
                    <div
                        key={i}
                        className="particle"
                        style={{
                            left: `${Math.random() * 100}%`,
                            top: `${Math.random() * 100}%`,
                            animationDelay: `${Math.random() * 5}s`,
                            animationDuration: `${3 + Math.random() * 4}s`
                        }}
                    />
                ))}
            </div>

            <div className="login-container">
                <div className="login-card">
                    {/* Logo */}
                    <div className="login-logo">
                        <div className="login-logo-icon">
                            <Zap size={32} color="#05070A" />
                        </div>
                    </div>

                    <h1 className="login-title">LLM-AngelAgent</h1>
                    <p className="login-subtitle">AI-Powered Autonomous Trading Platform</p>

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="login-form">
                        {/* Username */}
                        <div className="form-group">
                            <label htmlFor="username">
                                <User size={14} /> Username
                            </label>
                            <div className="input-wrapper">
                                <input
                                    type="text"
                                    id="username"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    placeholder="Enter your username"
                                    required
                                    autoFocus
                                />
                            </div>
                        </div>

                        {/* Password */}
                        <div className="form-group">
                            <label htmlFor="password">
                                <Lock size={14} /> Password
                            </label>
                            <div className="input-wrapper">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    id="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="Enter your password"
                                    required
                                />
                                <button
                                    type="button"
                                    className="password-toggle"
                                    onClick={() => setShowPassword(!showPassword)}
                                >
                                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                </button>
                            </div>
                        </div>

                        {/* Error Message */}
                        {error && (
                            <div className="login-error">
                                <AlertCircle size={16} />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* Submit Button */}
                        <button
                            type="submit"
                            className="login-btn"
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <>
                                    <span className="spinner-small" />
                                    Authenticating...
                                </>
                            ) : (
                                <>
                                    <Zap size={18} />
                                    Login to Dashboard
                                </>
                            )}
                        </button>
                    </form>

                    {/* Deployment Mode Badge */}
                    <div className={`deployment-badge ${deploymentMode}`}>
                        {deploymentMode === 'local' ? '🏠 Local Mode' : '☁️ Cloud Mode'}
                    </div>

                    {/* Footer */}
                    <p className="login-footer">
                        Powered by LLM Multi-Agent Framework
                    </p>
                </div>
            </div>

            <style>{`
                .login-page {
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    background: linear-gradient(135deg, #05070A 0%, #0E1217 50%, #05070A 100%);
                    position: relative;
                    overflow: hidden;
                }

                .login-bg-grid {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 200%;
                    height: 200%;
                    background-image:
                        linear-gradient(rgba(240, 185, 11, 0.03) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(0, 240, 255, 0.02) 1px, transparent 1px);
                    background-size: 50px 50px;
                    animation: gridMove 20s linear infinite;
                    opacity: 0.6;
                }

                @keyframes gridMove {
                    0% { transform: translate(0, 0); }
                    100% { transform: translate(50px, 50px); }
                }

                .particles {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    pointer-events: none;
                }

                .particle {
                    position: absolute;
                    width: 4px;
                    height: 4px;
                    background: rgba(240, 185, 11, 0.5);
                    border-radius: 50%;
                    animation: float 5s ease-in-out infinite;
                }

                @keyframes float {
                    0%, 100% { transform: translateY(0) scale(1); opacity: 0.5; }
                    50% { transform: translateY(-30px) scale(1.5); opacity: 1; }
                }

                .login-container {
                    position: relative;
                    z-index: 10;
                    width: 100%;
                    max-width: 440px;
                    padding: 2rem;
                }

                .login-card {
                    background: linear-gradient(135deg, rgba(5, 7, 10, 0.95) 0%, rgba(14, 18, 23, 0.9) 100%);
                    backdrop-filter: blur(30px);
                    padding: 3rem;
                    border-radius: 24px;
                    border: 1px solid rgba(240, 185, 11, 0.2);
                    box-shadow:
                        0 25px 80px rgba(0, 0, 0, 0.6),
                        0 0 0 1px rgba(240, 185, 11, 0.1),
                        0 0 60px rgba(240, 185, 11, 0.05);
                    text-align: center;
                    animation: cardFadeIn 0.8s ease-out;
                }

                @keyframes cardFadeIn {
                    from {
                        opacity: 0;
                        transform: translateY(30px) scale(0.95);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }

                .login-logo {
                    margin-bottom: 1.5rem;
                }

                .login-logo-icon {
                    width: 80px;
                    height: 80px;
                    margin: 0 auto;
                    background: linear-gradient(135deg, #F0B90B 0%, #FFD700 50%, #00F0FF 100%);
                    border-radius: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 10px 40px rgba(240, 185, 11, 0.4);
                    animation: logoFloat 3s ease-in-out infinite;
                }

                @keyframes logoFloat {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-10px); }
                }

                .login-title {
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 0.5rem;
                    background: linear-gradient(135deg, #F0B90B 0%, #FFD700 50%, #00F0FF 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }

                .login-subtitle {
                    color: #848E9C;
                    font-size: 0.95rem;
                    margin-bottom: 2.5rem;
                }

                .login-form {
                    text-align: left;
                }

                .form-group {
                    margin-bottom: 1.5rem;
                }

                .form-group label {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    color: #EAECEF;
                    font-size: 0.9rem;
                    font-weight: 500;
                    margin-bottom: 0.75rem;
                }

                .input-wrapper {
                    position: relative;
                }

                .input-wrapper input {
                    width: 100%;
                    padding: 14px 16px;
                    padding-right: 48px;
                    background: rgba(0, 0, 0, 0.4);
                    border: 2px solid rgba(240, 185, 11, 0.2);
                    border-radius: 12px;
                    color: #EAECEF;
                    font-size: 1rem;
                    transition: all 0.3s ease;
                }

                .input-wrapper input:focus {
                    outline: none;
                    border-color: #F0B90B;
                    background: rgba(240, 185, 11, 0.05);
                    box-shadow: 0 0 0 4px rgba(240, 185, 11, 0.1);
                }

                .input-wrapper input::placeholder {
                    color: #5E6673;
                }

                .password-toggle {
                    position: absolute;
                    right: 14px;
                    top: 50%;
                    transform: translateY(-50%);
                    background: none;
                    border: none;
                    color: #848E9C;
                    cursor: pointer;
                    padding: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: color 0.2s;
                }

                .password-toggle:hover {
                    color: #F0B90B;
                }

                .login-error {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 12px 16px;
                    background: rgba(246, 70, 93, 0.1);
                    border: 1px solid rgba(246, 70, 93, 0.3);
                    border-radius: 10px;
                    color: #F6465D;
                    font-size: 0.9rem;
                    margin-bottom: 1.5rem;
                    animation: shake 0.5s;
                }

                @keyframes shake {
                    0%, 100% { transform: translateX(0); }
                    25% { transform: translateX(-8px); }
                    75% { transform: translateX(8px); }
                }

                .login-btn {
                    width: 100%;
                    padding: 16px 24px;
                    background: linear-gradient(135deg, #F0B90B 0%, #FFD700 100%);
                    border: none;
                    border-radius: 12px;
                    color: #05070A;
                    font-size: 1rem;
                    font-weight: 700;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 10px;
                    transition: all 0.3s ease;
                    position: relative;
                    overflow: hidden;
                }

                .login-btn::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: -100%;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
                    transition: left 0.5s;
                }

                .login-btn:hover::before {
                    left: 100%;
                }

                .login-btn:hover {
                    transform: translateY(-3px);
                    box-shadow: 0 15px 40px rgba(240, 185, 11, 0.4);
                }

                .login-btn:disabled {
                    opacity: 0.7;
                    cursor: not-allowed;
                    transform: none;
                }

                .spinner-small {
                    width: 18px;
                    height: 18px;
                    border: 2px solid transparent;
                    border-top-color: #05070A;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }

                @keyframes spin {
                    to { transform: rotate(360deg); }
                }

                .deployment-badge {
                    display: inline-block;
                    padding: 6px 16px;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 600;
                    margin-top: 1.5rem;
                }

                .deployment-badge.local {
                    background: rgba(14, 203, 129, 0.15);
                    color: #0ECB81;
                    border: 1px solid rgba(14, 203, 129, 0.3);
                }

                .deployment-badge.cloud,
                .deployment-badge.production {
                    background: rgba(0, 240, 255, 0.15);
                    color: #00F0FF;
                    border: 1px solid rgba(0, 240, 255, 0.3);
                }

                .login-footer {
                    margin-top: 2rem;
                    color: #5E6673;
                    font-size: 0.8rem;
                }
            `}</style>
        </div>
    );
};

export default Login;
