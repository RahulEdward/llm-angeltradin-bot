"""
Database Models and Setup
SQLite database for users, trades, and settings
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib
import json

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "llm_agent.db"


def get_db_connection():
    """Get database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Broker accounts table with tokens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broker_accounts (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            broker TEXT NOT NULL,
            client_id TEXT NOT NULL,
            api_key_encrypted TEXT NOT NULL,
            api_key_last4 TEXT,
            pin_encrypted TEXT NOT NULL,
            status TEXT DEFAULT 'disconnected',
            feed_token TEXT,
            refresh_token TEXT,
            jwt_token TEXT,
            token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_connected TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT NOT NULL,
            exchange TEXT DEFAULT 'NSE',
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            status TEXT DEFAULT 'open',
            entry_time TIMESTAMP,
            exit_time TIMESTAMP,
            strategy TEXT,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            llm_provider TEXT DEFAULT 'none',
            llm_api_key_encrypted TEXT,
            trading_mode TEXT DEFAULT 'paper',
            risk_per_trade REAL DEFAULT 2.0,
            max_positions INTEGER DEFAULT 5,
            stop_loss_pct REAL DEFAULT 2.0,
            take_profit_pct REAL DEFAULT 4.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # API Keys table — stores LLM provider keys per user, encrypted
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            api_key_encrypted TEXT NOT NULL,
            api_key_last4 TEXT,
            model_name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, provider)
        )
    ''')
    
    # Backtest results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backtests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            initial_capital REAL,
            final_capital REAL,
            total_pnl REAL,
            total_trades INTEGER,
            winning_trades INTEGER,
            losing_trades INTEGER,
            win_rate REAL,
            max_drawdown REAL,
            sharpe_ratio REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            config TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Agent logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            message TEXT,
            level TEXT DEFAULT 'info',
            cycle_id INTEGER,
            symbol TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Paper trading account - persistent balance
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            initial_capital REAL NOT NULL DEFAULT 1000000,
            current_balance REAL NOT NULL DEFAULT 1000000,
            total_pnl REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            losing_trades INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id)
        )
    ''')
    
    # Paper trading trade log - every trade stored
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trade_id TEXT,
            symbol TEXT NOT NULL,
            exchange TEXT DEFAULT 'NSE',
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price REAL,
            exit_price REAL,
            pnl REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            order_type TEXT DEFAULT 'MARKET',
            stop_loss REAL,
            take_profit REAL,
            entry_time TIMESTAMP,
            exit_time TIMESTAMP,
            close_reason TEXT,
            strategy TEXT,
            cycle_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    
    # Create default users if not exist
    create_default_users(cursor)
    conn.commit()
    conn.close()
    
    print(f"Database initialized at: {DB_PATH}")


def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_default_users(cursor):
    """Create default admin and user accounts."""
    default_users = [
        ('admin', 'admin123', 'admin', 'admin@llm-agent.com'),
        ('user', 'user123', 'user', 'user@llm-agent.com'),
        ('guest', 'guest', 'guest', 'guest@llm-agent.com')
    ]
    
    for username, password, role, email in default_users:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (username, password_hash, role, email)
                VALUES (?, ?, ?, ?)
            ''', (username, hash_password(password), role, email))
        except sqlite3.IntegrityError:
            pass  # User already exists


# ============================================
# User Functions
# ============================================

def authenticate_user(username: str, password: str):
    """Authenticate a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    password_hash = hash_password(password)
    
    cursor.execute('''
        SELECT id, username, role, email, is_active
        FROM users
        WHERE username = ? AND password_hash = ?
    ''', (username, password_hash))
    
    user = cursor.fetchone()
    
    if user and user['is_active']:
        # Update last login
        cursor.execute('''
            UPDATE users SET last_login = ? WHERE id = ?
        ''', (datetime.now().isoformat(), user['id']))
        conn.commit()
        
        conn.close()
        return dict(user)
    
    conn.close()
    return None


def get_user_by_id(user_id: int):
    """Get user by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    return dict(user) if user else None


def create_user(username: str, password: str, role: str = 'user', email: str = None):
    """Create a new user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, role, email)
            VALUES (?, ?, ?, ?)
        ''', (username, hash_password(password), role, email))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None  # Username already exists


def get_all_users():
    """Get all users (for admin)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, role, email, created_at, last_login, is_active
        FROM users
    ''')
    users = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return users


# ============================================
# Settings Functions
# ============================================

def get_user_settings(user_id: int = None):
    """Get user settings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('SELECT * FROM settings LIMIT 1')
    
    settings = cursor.fetchone()
    conn.close()
    
    return dict(settings) if settings else {}


def save_user_settings(user_id: int, **kwargs):
    """Save user settings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if settings exist
    cursor.execute('SELECT id FROM settings WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update
        updates = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [user_id]
        cursor.execute(f'''
            UPDATE settings SET {updates}, updated_at = ? WHERE user_id = ?
        ''', values[:-1] + [datetime.now().isoformat(), user_id])
    else:
        # Insert
        columns = ['user_id'] + list(kwargs.keys())
        placeholders = ', '.join(['?' for _ in columns])
        values = [user_id] + list(kwargs.values())
        cursor.execute(f'''
            INSERT INTO settings ({', '.join(columns)})
            VALUES ({placeholders})
        ''', values)
    
    conn.commit()
    conn.close()


# ============================================
# API Key Functions (LLM keys per user)
# ============================================

def _get_fernet():
    """Get Fernet cipher for API key encryption."""
    from cryptography.fernet import Fernet
    key_file = Path(__file__).parent.parent / "data" / ".encryption_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        key = key_file.read_bytes()
    else:
        key = Fernet.generate_key()
        key_file.write_bytes(key)
    return Fernet(key)


def save_api_key(user_id: int, provider: str, api_key: str, model_name: str = None):
    """Save or update an LLM API key for a user (encrypted)."""
    f = _get_fernet()
    encrypted = f.encrypt(api_key.encode()).decode()
    last4 = api_key[-4:] if len(api_key) >= 4 else api_key

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM api_keys WHERE user_id = ? AND provider = ?', (user_id, provider))
    exists = cursor.fetchone()

    if exists:
        cursor.execute('''
            UPDATE api_keys SET api_key_encrypted = ?, api_key_last4 = ?, model_name = ?,
                               is_active = 1, updated_at = ?
            WHERE user_id = ? AND provider = ?
        ''', (encrypted, last4, model_name, datetime.now().isoformat(), user_id, provider))
    else:
        cursor.execute('''
            INSERT INTO api_keys (user_id, provider, api_key_encrypted, api_key_last4, model_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, provider, encrypted, last4, model_name))

    conn.commit()
    conn.close()
    return True


def get_api_keys(user_id: int):
    """Get all saved API keys for a user (masked, not decrypted)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT provider, api_key_last4, model_name, is_active, created_at, updated_at
        FROM api_keys WHERE user_id = ?
    ''', (user_id,))

    keys = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return keys


def get_api_key_decrypted(user_id: int, provider: str):
    """Get decrypted API key for a specific provider."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT api_key_encrypted FROM api_keys
        WHERE user_id = ? AND provider = ? AND is_active = 1
    ''', (user_id, provider))

    row = cursor.fetchone()
    conn.close()

    if row:
        try:
            f = _get_fernet()
            return f.decrypt(row['api_key_encrypted'].encode()).decode()
        except Exception:
            return None
    return None


def delete_api_key(user_id: int, provider: str):
    """Delete an API key for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM api_keys WHERE user_id = ? AND provider = ?', (user_id, provider))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_all_active_api_keys(user_id: int):
    """Get all active API keys decrypted (for loading into settings on startup)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT provider, api_key_encrypted, model_name FROM api_keys
        WHERE user_id = ? AND is_active = 1
    ''', (user_id,))

    keys = {}
    f = _get_fernet()
    for row in cursor.fetchall():
        try:
            decrypted = f.decrypt(row['api_key_encrypted'].encode()).decode()
            keys[row['provider']] = {
                "api_key": decrypted,
                "model_name": row['model_name']
            }
        except Exception:
            pass

    conn.close()
    return keys


# ============================================
# Trade Functions
# ============================================

def save_trade(user_id: int, trade_data: dict):
    """Save a trade record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO trades (user_id, symbol, exchange, side, quantity, entry_price, 
                           exit_price, pnl, status, entry_time, exit_time, strategy, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        trade_data.get('symbol'),
        trade_data.get('exchange', 'NSE'),
        trade_data.get('side'),
        trade_data.get('quantity'),
        trade_data.get('entry_price'),
        trade_data.get('exit_price'),
        trade_data.get('pnl'),
        trade_data.get('status', 'open'),
        trade_data.get('entry_time'),
        trade_data.get('exit_time'),
        trade_data.get('strategy'),
        trade_data.get('notes')
    ))
    
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return trade_id


def get_user_trades(user_id: int = None, limit: int = 100):
    """Get user trades."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('''
            SELECT * FROM trades WHERE user_id = ?
            ORDER BY entry_time DESC LIMIT ?
        ''', (user_id, limit))
    else:
        cursor.execute('SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?', (limit,))
    
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return trades


# ============================================
# Paper Account Functions
# ============================================

def get_paper_account(user_id: int = 1):
    """Get paper trading account. Creates default if not exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM paper_account WHERE user_id = ?', (user_id,))
    account = cursor.fetchone()
    if not account:
        cursor.execute('''
            INSERT INTO paper_account (user_id, initial_capital, current_balance)
            VALUES (?, 1000000, 1000000)
        ''', (user_id,))
        conn.commit()
        cursor.execute('SELECT * FROM paper_account WHERE user_id = ?', (user_id,))
        account = cursor.fetchone()
    conn.close()
    return dict(account) if account else None


def update_paper_account(user_id: int = 1, **kwargs):
    """Update paper account fields."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Ensure account exists
    cursor.execute('SELECT id FROM paper_account WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO paper_account (user_id) VALUES (?)', (user_id,))
    
    updates = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values())
    cursor.execute(f'''
        UPDATE paper_account SET {updates}, updated_at = ? WHERE user_id = ?
    ''', values + [datetime.now().isoformat(), user_id])
    conn.commit()
    conn.close()


def set_paper_capital(user_id: int, capital: float):
    """Set paper trading initial capital and reset balance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM paper_account WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        cursor.execute('''
            UPDATE paper_account SET initial_capital = ?, current_balance = ?,
            total_pnl = 0, total_trades = 0, winning_trades = 0, losing_trades = 0,
            updated_at = ? WHERE user_id = ?
        ''', (capital, capital, datetime.now().isoformat(), user_id))
    else:
        cursor.execute('''
            INSERT INTO paper_account (user_id, initial_capital, current_balance)
            VALUES (?, ?, ?)
        ''', (user_id, capital, capital))
    conn.commit()
    conn.close()


def reset_paper_account(user_id: int = 1):
    """Reset paper account to initial capital, clear all paper trades."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT initial_capital FROM paper_account WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    capital = row['initial_capital'] if row else 1000000
    cursor.execute('''
        UPDATE paper_account SET current_balance = ?, total_pnl = 0,
        total_trades = 0, winning_trades = 0, losing_trades = 0, updated_at = ?
        WHERE user_id = ?
    ''', (capital, datetime.now().isoformat(), user_id))
    cursor.execute('DELETE FROM paper_trades WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return capital


def save_paper_trade(user_id: int, trade: dict):
    """Save a paper trade to DB."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO paper_trades (user_id, trade_id, symbol, exchange, side, quantity,
            entry_price, exit_price, pnl, pnl_pct, status, order_type, stop_loss,
            take_profit, entry_time, exit_time, close_reason, strategy, cycle_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        trade.get('trade_id'),
        trade.get('symbol'),
        trade.get('exchange', 'NSE'),
        trade.get('side'),
        trade.get('quantity', 0),
        trade.get('entry_price'),
        trade.get('exit_price'),
        trade.get('pnl', 0),
        trade.get('pnl_pct', 0),
        trade.get('status', 'open'),
        trade.get('order_type', 'MARKET'),
        trade.get('stop_loss'),
        trade.get('take_profit'),
        trade.get('entry_time'),
        trade.get('exit_time'),
        trade.get('close_reason'),
        trade.get('strategy'),
        trade.get('cycle_number')
    ))
    trade_id = cursor.lastrowid
    
    # Update paper account balance
    pnl = trade.get('pnl', 0)
    if pnl != 0 and trade.get('status') == 'closed':
        cursor.execute('''
            UPDATE paper_account SET 
                current_balance = current_balance + ?,
                total_pnl = total_pnl + ?,
                total_trades = total_trades + 1,
                winning_trades = winning_trades + ?,
                losing_trades = losing_trades + ?,
                updated_at = ?
            WHERE user_id = ?
        ''', (pnl, pnl, 1 if pnl > 0 else 0, 1 if pnl < 0 else 0,
              datetime.now().isoformat(), user_id))
    
    conn.commit()
    conn.close()
    return trade_id


def get_paper_trades(user_id: int = 1, limit: int = 200):
    """Get paper trades."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM paper_trades WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return trades


# ============================================
# Agent Log Functions
# ============================================

def save_agent_log(agent_name: str, message: str, level: str = 'info', 
                   cycle_id: int = None, symbol: str = None):
    """Save agent log."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO agent_logs (agent_name, message, level, cycle_id, symbol)
        VALUES (?, ?, ?, ?, ?)
    ''', (agent_name, message, level, cycle_id, symbol))
    
    conn.commit()
    conn.close()


def get_agent_logs(limit: int = 50):
    """Get recent agent logs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM agent_logs ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return logs


# Initialize database on import
init_db()
