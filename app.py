from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Database setup
DATABASE = 'investment_platform.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        
        # Create users table
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT NOT NULL,
                password TEXT NOT NULL,
                balance REAL DEFAULT 100000.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create stocks table with Indian stocks
        db.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                change REAL DEFAULT 0.0
            )
        ''')
        
        # Create portfolio table
        db.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, symbol)
            )
        ''')
        
        # Create transactions table
        db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                total REAL NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Insert sample Indian stocks if not exists
        stocks_data = [
            ('RELIANCE', 'Reliance Industries Ltd', 2450.50, 1.25),
            ('TCS', 'Tata Consultancy Services', 3580.75, -0.85),
            ('INFY', 'Infosys Ltd', 1456.30, 2.10),
            ('HDFCBANK', 'HDFC Bank Ltd', 1625.40, 0.95),
            ('ICICIBANK', 'ICICI Bank Ltd', 982.60, -1.20),
            ('BHARTIARTL', 'Bharti Airtel Ltd', 1185.25, 1.85),
            ('SBIN', 'State Bank of India', 598.90, 0.45),
            ('ITC', 'ITC Ltd', 412.75, -0.35),
            ('WIPRO', 'Wipro Ltd', 445.60, 1.60),
            ('TATAMOTORS', 'Tata Motors Ltd', 765.30, 3.25),
            ('HINDALCO', 'Hindalco Industries Ltd', 512.80, 2.40),
            ('ONGC', 'Oil & Natural Gas Corp', 178.45, -1.05),
            ('MARUTI', 'Maruti Suzuki India Ltd', 9850.20, 0.75),
            ('ASIANPAINT', 'Asian Paints Ltd', 3245.60, -0.60),
            ('BAJFINANCE', 'Bajaj Finance Ltd', 6780.40, 1.95)
        ]
        
        for stock in stocks_data:
            try:
                db.execute('INSERT INTO stocks (symbol, name, price, change) VALUES (?, ?, ?, ?)', stock)
            except sqlite3.IntegrityError:
                pass
        
        db.commit()
        db.close()

# Initialize database
init_db()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match!')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        db = get_db()
        try:
            db.execute('INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)',
                      (name, email, phone, hashed_password))
            db.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!')
            return redirect(url_for('register'))
        finally:
            db.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    # Get portfolio value
    portfolio = db.execute('''
        SELECT p.symbol, p.quantity, p.avg_price, s.price as current_price
        FROM portfolio p
        JOIN stocks s ON p.symbol = s.symbol
        WHERE p.user_id = ?
    ''', (session['user_id'],)).fetchall()
    
    portfolio_value = sum(p['quantity'] * p['current_price'] for p in portfolio)
    total_invested = sum(p['quantity'] * p['avg_price'] for p in portfolio)
    daily_pl = portfolio_value - total_invested
    
    # Get recent transactions
    transactions = db.execute('''
        SELECT * FROM transactions 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    
    db.close()
    
    return render_template('dashboard.html', 
                         user=user,
                         portfolio_value=portfolio_value,
                         total_invested=total_invested,
                         daily_pl=daily_pl,
                         recent_transactions=transactions)

@app.route('/market')
def market():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    stocks = db.execute('SELECT * FROM stocks ORDER BY symbol').fetchall()
    db.close()
    
    return render_template('market.html', stocks=stocks)

@app.route('/portfolio')
def portfolio():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    
    # Get holdings with current prices
    holdings = db.execute('''
        SELECT p.symbol, p.quantity, p.avg_price, s.price as current_price,
               (p.quantity * p.avg_price) as investment,
               (p.quantity * s.price) as current_value,
               ((s.price - p.avg_price) * p.quantity) as pl,
               (((s.price - p.avg_price) / p.avg_price) * 100) as pl_percent
        FROM portfolio p
        JOIN stocks s ON p.symbol = s.symbol
        WHERE p.user_id = ?
    ''', (session['user_id'],)).fetchall()
    
    total_investment = sum(h['investment'] for h in holdings) if holdings else 0
    current_value = sum(h['current_value'] for h in holdings) if holdings else 0
    total_pl = current_value - total_investment
    total_pl_percent = (total_pl / total_investment * 100) if total_investment > 0 else 0
    
    db.close()
    
    return render_template('portfolio.html',
                         holdings=holdings,
                         total_investment=total_investment,
                         current_value=current_value,
                         total_pl=total_pl,
                         total_pl_percent=total_pl_percent)

@app.route('/trade', methods=['POST'])
def trade():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    symbol = request.form['symbol']
    trade_type = request.form['type']
    quantity = int(request.form['quantity'])
    
    db = get_db()
    
    # Get current stock price
    stock = db.execute('SELECT * FROM stocks WHERE symbol = ?', (symbol,)).fetchone()
    if not stock:
        flash('Invalid stock symbol!')
        db.close()
        return redirect(url_for('market'))
    
    price = stock['price']
    total_amount = price * quantity
    
    # Get user balance
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if trade_type == 'BUY':
        if user['balance'] < total_amount:
            flash('Insufficient balance!')
            db.close()
            return redirect(url_for('market'))
        
        # Update user balance
        new_balance = user['balance'] - total_amount
        db.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, session['user_id']))
        
        # Update portfolio
        existing = db.execute('SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?',
                            (session['user_id'], symbol)).fetchone()
        
        if existing:
            new_quantity = existing['quantity'] + quantity
            new_avg_price = ((existing['avg_price'] * existing['quantity']) + total_amount) / new_quantity
            db.execute('UPDATE portfolio SET quantity = ?, avg_price = ? WHERE user_id = ? AND symbol = ?',
                      (new_quantity, new_avg_price, session['user_id'], symbol))
        else:
            db.execute('INSERT INTO portfolio (user_id, symbol, quantity, avg_price) VALUES (?, ?, ?, ?)',
                      (session['user_id'], symbol, quantity, price))
        
    elif trade_type == 'SELL':
        # Check if user has enough quantity
        holding = db.execute('SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?',
                           (session['user_id'], symbol)).fetchone()
        
        if not holding or holding['quantity'] < quantity:
            flash('Insufficient quantity to sell!')
            db.close()
            return redirect(url_for('portfolio'))
        
        # Update user balance
        new_balance = user['balance'] + total_amount
        db.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, session['user_id']))
        
        # Update portfolio
        new_quantity = holding['quantity'] - quantity
        if new_quantity == 0:
            db.execute('DELETE FROM portfolio WHERE user_id = ? AND symbol = ?',
                      (session['user_id'], symbol))
        else:
            db.execute('UPDATE portfolio SET quantity = ? WHERE user_id = ? AND symbol = ?',
                      (new_quantity, session['user_id'], symbol))
    
    # Record transaction
    db.execute('INSERT INTO transactions (user_id, symbol, type, quantity, price, total) VALUES (?, ?, ?, ?, ?, ?)',
              (session['user_id'], symbol, trade_type, quantity, price, total_amount))
    
    db.commit()
    db.close()
    
    flash(f'{trade_type} order executed successfully!')
    return redirect(url_for('portfolio') if trade_type == 'SELL' else url_for('market'))

if __name__ == '__main__':
    app.run(debug=True)