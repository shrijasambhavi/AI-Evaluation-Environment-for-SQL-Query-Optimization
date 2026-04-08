import sqlite3
import random

def setup_easy_db() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)')
    cursor.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)')
    cursor.execute('INSERT INTO users (id, name) VALUES (1, "Alice"), (2, "Bob")')
    cursor.execute('INSERT INTO orders (id, user_id, amount) VALUES (1, 1, 100.0), (2, 1, 50.0)')
    conn.commit()
    return conn

def setup_medium_db() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER)')
    cursor.execute('CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT)')
    cursor.execute('CREATE INDEX idx_emp_dept ON employees(department_id)')
    cursor.execute('INSERT INTO departments (id, name) VALUES (1, "Engineering"), (2, "HR")')
    cursor.execute('INSERT INTO employees (id, name, department_id) VALUES (1, "Alice", 1), (2, "Bob", 1), (3, "Charlie", 2)')
    # Add dummy 1000 rows to ensure SQLite might use an index
    for i in range(4, 1000):
        cursor.execute('INSERT INTO employees (id, name, department_id) VALUES (?, ?, ?)', (i, f"Emp{i}", 1))
    # Gather stats so EXPLAIN QUERY PLAN uses indices
    cursor.execute('ANALYZE')
    conn.commit()
    return conn

def setup_hard_db() -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE customers (id INTEGER PRIMARY KEY, region TEXT)')
    cursor.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT)')
    cursor.execute('CREATE TABLE order_items (order_id INTEGER, product_id INTEGER, quantity INTEGER, price REAL)')
    
    cursor.execute('INSERT INTO customers VALUES (1, "North"), (2, "South"), (3, "North")')
    cursor.execute('INSERT INTO orders VALUES (1, 1, "2023-01-10"), (2, 2, "2023-01-15"), (3, 3, "2023-02-05")')
    cursor.execute('INSERT INTO order_items VALUES (1, 101, 2, 50.0), (1, 102, 1, 100.0), (2, 101, 1, 50.0), (3, 103, 5, 10.0)')
    conn.commit()
    return conn

TASKS = {
    "easy": {
        "description": "Fix a syntactically broken SQL query. Target: Find users who placed an order, including user name and order amount.",
        "schema_info": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);",
        "initial_query": "SELECT user.name, orders.amount FROM users JOIN orders;",
        "setup_fn": setup_easy_db
    },
    "medium": {
        "description": "Optimize a slow query. Target: Get the names of employees in the 'Engineering' department. Ensure you use an explicit JOIN to leverage the index rather than an unoptimized IN/subquery.",
        "schema_info": "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER); CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT); CREATE INDEX idx_emp_dept ON employees(department_id);",
        "initial_query": "SELECT name FROM employees WHERE department_id IN (SELECT id FROM departments WHERE name='Engineering')",
        "setup_fn": setup_medium_db
    },
    "hard": {
        "description": "Rewrite a multi-table query from scratch. Target: Output total revenue per region for January 2023. Columns should be region, total_revenue. You are restricted on the query length (must be under 200 characters).",
        "schema_info": "CREATE TABLE customers (id INTEGER PRIMARY KEY, region TEXT); CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT); CREATE TABLE order_items (order_id INTEGER, product_id INTEGER, quantity INTEGER, price REAL);",
        "initial_query": "",
        "setup_fn": setup_hard_db
    }
}

class Graders:
    @staticmethod
    def grade_easy(conn: sqlite3.Connection, submitted_query: str) -> (float, str):
        try:
            cursor = conn.cursor()
            cursor.execute(submitted_query)
            rows = cursor.fetchall()
            
            golden_query = "SELECT users.name, orders.amount FROM users JOIN orders ON users.id = orders.user_id;"
            cursor.execute(golden_query)
            golden_rows = cursor.fetchall()
            
            if rows == golden_rows:
                return 1.0, "Success! The results match exactly."
            else:
                return 0.5, "The query executed, but the results do not match the expected output. Golden rows had different results."
        except Exception as e:
            return 0.0, f"Error executing query: {str(e)}"

    @staticmethod
    def grade_medium(conn: sqlite3.Connection, submitted_query: str) -> (float, str):
        try:
            cursor = conn.cursor()
            cursor.execute(submitted_query)
            rows = cursor.fetchall()
            
            golden_query = "SELECT employees.name FROM employees JOIN departments ON employees.department_id = departments.id WHERE departments.name = 'Engineering';"
            cursor.execute(golden_query)
            golden_rows = cursor.fetchall()

            if set(rows) != set(golden_rows):
                return 0.2, "Query executed, but results do not match. Only partial execution reward."
            
            # Check EXPLAIN QUERY PLAN
            # We want to see if it uses the index SEARCH TABLE employees USING INDEX idx_emp_dept
            # rather than SCAN TABLE employees (which a bad optimizer might do for an IN loop although SQLite is pretty smart sometimes)
            cursor.execute(f"EXPLAIN QUERY PLAN {submitted_query}")
            plan = cursor.fetchall()
            plan_str = " ".join([str(p) for p in plan])
            
            # For the sake of the exercise, enforce a strict JOIN clause to emulate "optimization"
            is_join = "JOIN" in submitted_query.upper()

            if is_join and "SCAN TABLE employees" not in plan_str:
                return 1.0, "Success! Results match and the query is optimized (JOIN used)."
            else:
                return 0.6, "Results match, but query uses suboptimal operations (e.g. missing explicit JOIN or using table scan instead of covering index lookups)."
        except Exception as e:
            return 0.0, f"Error executing query: {str(e)}"

    @staticmethod
    def grade_hard(conn: sqlite3.Connection, submitted_query: str) -> (float, str):
        # Enforce character limit
        if len(submitted_query) > 200:
            return 0.1, "Query exceeded token/character budget limit of 200."
            
        try:
            cursor = conn.cursor()
            cursor.execute(submitted_query)
            rows = cursor.fetchall()
            
            golden_query = '''
            SELECT c.region, SUM(oi.quantity * oi.price) 
            FROM customers c 
            JOIN orders o ON c.id = o.customer_id 
            JOIN order_items oi ON o.id = oi.order_id 
            WHERE o.order_date LIKE '2023-01%' 
            GROUP BY c.region;
            '''
            cursor.execute(golden_query)
            golden_rows = cursor.fetchall()
            
            if set(rows) == set(golden_rows) and len(rows) == len(golden_rows):
                return 1.0, "Success! The complex report matches perfectly within budget."
            else:
                return 0.5, f"Query executed but the output was not correctly grouped or aggregated."
        except Exception as e:
            return 0.0, f"Error executing query: {str(e)}"
