from flask import Flask, render_template, session, redirect, url_for, request
import pyodbc
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change in production

# Get DB config from environment variables (Azure App Service → Configuration)
DB_SERVER = os.environ.get("DB_SERVER", "your-sql-server.database.windows.net")
DB_NAME = os.environ.get("DB_NAME", "StationeryDB")
DB_USER = os.environ.get("DB_USER", "your-username")
DB_PASS = os.environ.get("DB_PASS", "your-password")

# Connection string
conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASS}"
)

def get_db_connection():
    return pyodbc.connect(conn_str)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/items")
def items():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price FROM StationeryItems")
        rows = cursor.fetchall()
        conn.close()
        return render_template("items.html", items=rows)
    except Exception as e:
        return f"Database error: {str(e)}"

@app.route("/add_to_cart/<int:item_id>")
def add_to_cart(item_id):
    cart = session.get("cart", [])
    cart.append(item_id)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    cart = session.get("cart", [])
    if not cart:
        return render_template("cart.html", items=[], total=0)

    conn = get_db_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in cart)
    query = f"SELECT id, name, price FROM StationeryItems WHERE id IN ({placeholders})"
    cursor.execute(query, cart)
    rows = cursor.fetchall()
    conn.close()

    total = sum([row[2] for row in rows])
    return render_template("cart.html", items=rows, total=total)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", [])
    if request.method == "POST" and cart:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Fetch item details
            placeholders = ",".join("?" for _ in cart)
            query = f"SELECT id, name, price FROM StationeryItems WHERE id IN ({placeholders})"
            cursor.execute(query, cart)
            rows = cursor.fetchall()
            total = sum([row[2] for row in rows])

            # Insert into Orders
            cursor.execute("INSERT INTO Orders (total_amount) OUTPUT INSERTED.order_id VALUES (?)", (total,))
            order_id = cursor.fetchone()[0]

            # Insert into OrderItems
            for item in cart:
                cursor.execute("INSERT INTO OrderItems (order_id, item_id, quantity) VALUES (?, ?, ?)", (order_id, item, 1))

            conn.commit()
            conn.close()

            # Clear cart
            session.pop("cart", None)
            return render_template("checkout.html", success=True, order_id=order_id)

        except Exception as e:
            return f"Checkout failed: {str(e)}"

    return render_template("checkout.html", success=False)

@app.route("/admin/orders")
def admin_orders():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.order_id, o.order_date, o.total_amount, i.name, i.price
            FROM Orders o
            JOIN OrderItems oi ON o.order_id = oi.order_id
            JOIN StationeryItems i ON oi.item_id = i.id
            ORDER BY o.order_date DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return render_template("admin_orders.html", orders=rows)
    except Exception as e:
        return f"Failed to fetch orders: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
