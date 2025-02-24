from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import sqlite3
from flask import g

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# SQLite database setup
DATABASE = 'finance_tracker.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    password TEXT NOT NULL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    date TEXT NOT NULL,
                    description TEXT,
                    payment_method TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,  
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about.html')
def about():
    return render_template('about.html')

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        
        # Fetch transactions from the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,))
        transactions = c.fetchall()
        
        # Compute the sum of transaction amounts for each payment method
        total_amount = sum(transaction[2] for transaction in transactions)
        total_upi = sum(transaction[2] for transaction in transactions if transaction[6] == 'UPI')
        total_cash = sum(transaction[2] for transaction in transactions if transaction[6] == 'Cash')
        
        conn.close()

        return render_template('dashboard.html', username=username, total_amount=total_amount, total_upi=total_upi, total_cash=total_cash)
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]  # Store user_id in session
            session['username'] = user[1]  # Store username in session
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = c.fetchone()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
        else:
            c.execute("INSERT INTO users (username, email, phone, password) VALUES (?, ?, ?, ?)",
                      (username, email, phone, password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('finance_tracker.db') 
        g.db.row_factory = sqlite3.Row
    return g.db

@app.route('/transactions')
def transactions():
    if 'username' in session:
        user_id = session['user_id']
        username = session['username']
        
        page = request.args.get('page', 1, type=int)
        per_page = 10  
        offset = (page - 1) * per_page
        
        search_term = request.args.get('search_term', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        transaction_type = request.args.get('transaction_type', '')

        query = "SELECT * FROM transactions WHERE user_id = ?"
        filters = [user_id]

        if search_term:
            query += " AND (category LIKE ? OR description LIKE ?)"
            filters.extend([f"%{search_term}%", f"%{search_term}%"])
        if start_date:
            query += " AND date >= ?"
            filters.append(start_date)
        if end_date:
            query += " AND date <= ?"
            filters.append(end_date)
        if transaction_type:
            query += " AND transaction_type = ?"
            filters.append(transaction_type)

        query += " LIMIT ? OFFSET ?"
        filters.extend([per_page, offset])

        db = get_db()
        cur = db.execute(query, filters)
        transactions = cur.fetchall()
        cur.close()
        
        total_query = "SELECT COUNT(*) FROM transactions WHERE user_id = ?"
        filters = [user_id]

        if search_term:
            total_query += " AND (category LIKE ? OR description LIKE ?)"
            filters.extend([f"%{search_term}%", f"%{search_term}%"])
        if start_date:
            total_query += " AND date >= ?"
            filters.append(start_date)
        if end_date:
            total_query += " AND date <= ?"
            filters.append(end_date)
        if transaction_type:
            total_query += " AND transaction_type = ?"
            filters.append(transaction_type)

        cur = db.execute(total_query, filters)
        total_count = cur.fetchone()[0]
        cur.close()
        
        total_pages = (total_count + per_page - 1) // per_page

        return render_template('transaction.html', username=username, transactions=transactions, page=page, total_pages=total_pages)
    return redirect(url_for('login'))

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'username' in session:
        user_id = session['user_id']
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        payment_method = request.form['payment_method']
        description = request.form['notes']
        transaction_type = request.form['transaction_type']

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''INSERT INTO transactions (user_id, date, category, amount, payment_method, description, transaction_type) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                  (user_id, date, category, amount, payment_method, description, transaction_type))
        conn.commit()
        conn.close()

        return redirect(url_for('transactions'))
    else:
        return redirect(url_for('login'))

@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'username' in session:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()
        conn.close()
        flash('Transaction deleted successfully.', 'success')
    else:
        flash('You must be logged in to delete a transaction.', 'error')
    return redirect(url_for('transactions'))

@app.route('/daily_spending_data')
def daily_spending_data():
    if 'username' in session:
        user_id = session['user_id']
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT date, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY date", (user_id,))
        data = c.fetchall()
        conn.close()

        labels = [row[0] for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        return redirect(url_for('login'))

@app.route('/monthly_spending_data')
def monthly_spending_data():
    if 'username' in session:
        user_id = session['user_id']
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT strftime('%Y-%m', date) AS month, SUM(amount) FROM transactions WHERE user_id = ? GROUP BY month", (user_id,))
        data = c.fetchall()
        conn.close()

        labels = [datetime.strptime(row[0], '%Y-%m').strftime('%b %Y') for row in data]
        amounts = [row[1] for row in data]

        return jsonify({'labels': labels, 'amounts': amounts})
    else:
        return redirect(url_for('login'))

@app.route('/statistics')
def statistics():
    user_id = session.get('user_id')
    
    if user_id:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Total Expenses
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND transaction_type = 'Expense'", (user_id,))
        total_expenses_result = c.fetchone()
        total_expenses = total_expenses_result[0] if total_expenses_result else 0

        # Total Income
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND transaction_type = 'Income'", (user_id,))
        total_income_result = c.fetchone()
        total_income = total_income_result[0] if total_income_result else 0

        # Expense Breakdown by Category
        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND transaction_type = 'Expense' GROUP BY category", (user_id,))
        expense_by_category_result = c.fetchall()
        expense_by_category = dict(expense_by_category_result) if expense_by_category_result else {}

        # Income Breakdown by Category
        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND transaction_type = 'Income' GROUP BY category", (user_id,))
        income_by_category_result = c.fetchall()
        income_by_category = dict(income_by_category_result) if income_by_category_result else {}

        # Top Spending Categories (Expense)
        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND transaction_type = 'Expense' GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5", (user_id,))
        top_spending_categories_result = c.fetchall()
        top_spending_categories = dict(top_spending_categories_result) if top_spending_categories_result else {}

        # Top Income Categories
        c.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND transaction_type = 'Income' GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5", (user_id,))
        top_income_categories_result = c.fetchall()
        top_income_categories = dict(top_income_categories_result) if top_income_categories_result else {}

        conn.close()

        return render_template('statistics.html', total_expenses=total_expenses, total_income=total_income,
                               expense_by_category=expense_by_category, income_by_category=income_by_category,
                               top_spending_categories=top_spending_categories, top_income_categories=top_income_categories)
    else:
        return redirect(url_for('login'))
    
@app.errorhandler(404)
def page_not_found(error):
    return render_template('error404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
