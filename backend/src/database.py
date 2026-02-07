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
    
    # Broker accounts table
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
