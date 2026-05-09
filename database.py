import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atm.db")

def get_connection():
    """Zwróć połączenie z bazą danych"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Zainicjalizuj bazę danych z tabelami"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela klientów
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            pin TEXT NOT NULL,
            name TEXT NOT NULL,
            balance REAL DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela stanów banknotów
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banknote_balance (
            denomination INTEGER PRIMARY KEY,
            quantity INTEGER DEFAULT 10
        )
    ''')
    
    # Tabela stanów depozytu (overflow)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS overflow_balance (
            denomination INTEGER PRIMARY KEY,
            quantity INTEGER DEFAULT 0
        )
    ''')
    
    # Tabela transakcji
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
    ''')
    
    # Wstaw domyślnych administratorów jeśli nie istnieje
    cursor.execute('SELECT * FROM clients WHERE client_id = ?', ('0000001',))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO clients (client_id, pin, name, is_admin)
            VALUES (?, ?, ?, 1)
        ''', ('0000001', '12345678', 'Superadministrator'))
    
    # Wstaw konto zwykłego admina
    cursor.execute('SELECT * FROM clients WHERE client_id = ?', ('1014872',))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO clients (client_id, pin, name, is_admin)
            VALUES (?, ?, ?, 1)
        ''', ('1014872', '10221142', 'Administrator'))
    
    # Wstaw domyślne stany banknotów jeśli nie istnieją
    denominations = [10, 20, 50, 100, 200, 500]
    for denom in denominations:
        cursor.execute('SELECT * FROM banknote_balance WHERE denomination = ?', (denom,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO banknote_balance (denomination, quantity)
                VALUES (?, 10)
            ''', (denom,))
        cursor.execute('SELECT * FROM overflow_balance WHERE denomination = ?', (denom,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO overflow_balance (denomination, quantity)
                VALUES (?, 0)
            ''', (denom,))
    
    # Wstaw test klientów
    test_clients = [
        ('1234567', '1234', 'Jan Kowalski', 0),
        ('2345678', '5678', 'Maria Nowak', 0),
    ]
    
    for client_id, pin, name, is_admin in test_clients:
        cursor.execute('SELECT * FROM clients WHERE client_id = ?', (client_id,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO clients (client_id, pin, name, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (client_id, pin, name, is_admin))
    
    conn.commit()
    conn.close()

def verify_login(client_id, pin):
    """Weryfikuj dane logowania, zwróć informacje o kliencie lub None"""
    if len(client_id) != 7 or not client_id.isdigit():
        return None
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT client_id, name, is_admin
        FROM clients
        WHERE client_id = ? AND pin = ?
    ''', (client_id, pin))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'client_id': result['client_id'],
            'name': result['name'],
            'is_admin': result['is_admin'] == 1
        }
    return None

def get_banknote_balance():
    """Pobierz aktualny stan banknotów"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT denomination, quantity FROM banknote_balance ORDER BY denomination DESC')
    rows = cursor.fetchall()
    conn.close()
    
    balance = {}
    for row in rows:
        balance[row['denomination']] = row['quantity']
    
    return balance

def update_banknote_balance(denomination, quantity):
    """Zaktualizuj stan banknotów"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE banknote_balance
        SET quantity = ?
        WHERE denomination = ?
    ''', (quantity, denomination))
    
    conn.commit()
    conn.close()

def get_all_banknote_balances():
    """Pobierz wszystkie stany banknotów jako słownik"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT denomination, quantity FROM banknote_balance')
    rows = cursor.fetchall()
    conn.close()
    
    balance = {}
    for row in rows:
        balance[row['denomination']] = row['quantity']
    
    return balance


def get_all_overflow_balances():
    """Pobierz wszystkie stany depozytu jako słownik"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT denomination, quantity FROM overflow_balance')
    rows = cursor.fetchall()
    conn.close()
    
    overflow = {}
    for row in rows:
        overflow[row['denomination']] = row['quantity']
    
    return overflow


def update_overflow_balance(denomination, quantity):
    """Zaktualizuj stan depozytu"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE overflow_balance
        SET quantity = ?
        WHERE denomination = ?
    ''', (quantity, denomination))
    
    conn.commit()
    conn.close()


def add_transaction(client_id, transaction_type, amount, details=None):
    """Dodaj transakcję do bazy"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO transactions (client_id, transaction_type, amount, details)
        VALUES (?, ?, ?, ?)
    ''', (client_id, transaction_type, amount, details))
    
    conn.commit()
    conn.close()

def get_client_transactions(client_id, limit=10):
    """Pobierz ostatnie transakcje klienta"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM transactions
        WHERE client_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (client_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def get_client_info(client_id):
    """Pobierz informacje o kliencie"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT client_id, name, is_admin
        FROM clients
        WHERE client_id = ?
    ''', (client_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'client_id': result['client_id'],
            'name': result['name'],
            'is_admin': result['is_admin'] == 1
        }
    return None
