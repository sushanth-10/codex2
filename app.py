from datetime import date, datetime
import sqlite3
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def format_inr(value):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    integer = int(amount)
    decimal = f"{amount:.2f}".split(".")[1]
    s = str(integer)
    if len(s) > 3:
        head = s[:-3]
        tail = s[-3:]
        chunks = []
        while len(head) > 2:
            chunks.insert(0, head[-2:])
            head = head[:-2]
        if head:
            chunks.insert(0, head)
        s = ",".join(chunks + [tail])
    return f"{sign}₹{s}.{decimal}"


app.jinja_env.filters["inr"] = format_inr


def init_db():
    conn = get_db_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS inventory_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0,
            last_restocked TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            segment TEXT NOT NULL,
            total_orders INTEGER NOT NULL DEFAULT 0,
            total_spent REAL NOT NULL DEFAULT 0,
            last_purchase TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            items_count INTEGER NOT NULL DEFAULT 1,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            order_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            segment TEXT NOT NULL,
            target_customers INTEGER NOT NULL DEFAULT 0,
            expected_roi REAL NOT NULL DEFAULT 0,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft'
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            expense_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assistant_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS business_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            owner_name TEXT NOT NULL,
            business_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            business_type TEXT NOT NULL,
            monthly_revenue REAL NOT NULL DEFAULT 0,
            monthly_expenses REAL NOT NULL DEFAULT 0,
            marketing_spend REAL NOT NULL DEFAULT 0,
            growth_target REAL NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    seed_demo_data(conn)
    conn.close()


def seed_demo_data(conn):
    counts = {
        "inventory": conn.execute("SELECT COUNT(*) FROM inventory_products").fetchone()[0],
        "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "campaigns": conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
        "expenses": conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0],
        "assistant": conn.execute("SELECT COUNT(*) FROM assistant_messages").fetchone()[0],
    }

    today = date.today().isoformat()
    if counts["inventory"] == 0:
        conn.executemany(
            """
            INSERT INTO inventory_products
            (name, sku, category, stock, reorder_level, price, last_restocked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Wireless Earbuds", "WE-001", "Electronics", 45, 20, 7999, today),
                ("Smart Watch", "SW-002", "Electronics", 12, 15, 11999, today),
                ("Phone Case", "PC-003", "Accessories", 156, 50, 1299, today),
                ("USB Cable", "UC-004", "Accessories", 8, 30, 899, today),
            ],
        )
    if counts["customers"] == 0:
        conn.executemany(
            """
            INSERT INTO customers
            (name, email, phone, segment, total_orders, total_spent, last_purchase)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Sarah Johnson", "sarah.j@email.com", "555-0101", "VIP", 12, 145688, today),
                ("Michael Chen", "mchen@email.com", "555-0102", "Regular", 8, 89234, today),
                ("Emma Davis", "emma.d@email.com", "555-0103", "VIP", 15, 172543, today),
                ("James Wilson", "jwilson@email.com", "555-0104", "New", 3, 22108, today),
            ],
        )
    if counts["orders"] == 0:
        conn.executemany(
            """
            INSERT INTO orders
            (order_code, customer_name, items_count, total_amount, status, priority, order_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("ORD-1001", "Sarah Johnson", 3, 31497, "Delivered", "Low", today),
                ("ORD-1002", "Michael Chen", 1, 19999, "Shipped", "Medium", today),
                ("ORD-1003", "Emma Davis", 5, 18745, "Processing", "High", today),
                ("ORD-1004", "James Wilson", 2, 10498, "Pending", "Medium", today),
            ],
        )
    if counts["campaigns"] == 0:
        conn.executemany(
            """
            INSERT INTO campaigns
            (title, description, segment, target_customers, expected_roi, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("VIP Early Access Campaign", "Offer early access to new products.", "VIP", 20, 340, "High", "Ready"),
                ("Win-Back Campaign", "Re-engage customers inactive for 60 days.", "At Risk", 23, 180, "Medium", "Ready"),
                ("New Customer Welcome Series", "Automated onboarding education campaign.", "New", 67, 215, "Medium", "Draft"),
            ],
        )
    if counts["expenses"] == 0:
        conn.executemany(
            """
            INSERT INTO expenses
            (category, description, amount, expense_date)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("Inventory", "Product restock - Electronics", 542000, today),
                ("Marketing", "Social media ads campaign", 85000, today),
                ("Utilities", "Monthly electricity bill", 32000, today),
                ("Salaries", "Staff salaries - April", 680000, today),
            ],
        )
    if counts["assistant"] == 0:
        conn.execute(
            """
            INSERT INTO assistant_messages (role, message, created_at)
            VALUES (?, ?, ?)
            """,
            (
                "assistant",
                "Hello! I can help with inventory, orders, marketing, finance, and customer insights. Ask me anything about your business.",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    conn.commit()


def query_metrics(conn):
    profile = get_business_profile(conn)
    baseline_revenue = profile["monthly_revenue"] if profile else 0
    baseline_expenses = profile["monthly_expenses"] if profile else 0
    marketing_spend = profile["marketing_spend"] if profile else 0

    revenue_from_orders = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0]
    expenses_from_records = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
    revenue = max(revenue_from_orders, baseline_revenue)
    expenses = max(expenses_from_records, baseline_expenses + marketing_spend)
    net_profit = revenue - expenses
    active_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status IN ('Pending', 'Processing', 'Shipped')"
    ).fetchone()[0]
    low_stock = conn.execute(
        "SELECT COUNT(*) FROM inventory_products WHERE stock <= reorder_level"
    ).fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    vip_customers = conn.execute(
        "SELECT COUNT(*) FROM customers WHERE segment = 'VIP'"
    ).fetchone()[0]
    avg_customer_value = conn.execute(
        "SELECT COALESCE(AVG(total_spent), 0) FROM customers"
    ).fetchone()[0]
    inventory_value = conn.execute(
        "SELECT COALESCE(SUM(price * stock), 0) FROM inventory_products"
    ).fetchone()[0]
    return {
        "revenue": revenue,
        "expenses": expenses,
        "net_profit": net_profit,
        "active_orders": active_orders,
        "low_stock": low_stock,
        "total_customers": total_customers,
        "vip_customers": vip_customers,
        "avg_customer_value": avg_customer_value,
        "inventory_value": inventory_value,
    }


def get_business_profile(conn):
    return conn.execute("SELECT * FROM business_profile WHERE id = 1").fetchone()


def business_profile_required():
    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    return profile is not None


@app.context_processor
def inject_business_profile():
    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    if profile:
        owner_name = profile["owner_name"]
        business_name = profile["business_name"]
        avatar = "".join([part[0].upper() for part in owner_name.split()[:2]]) or "DB"
    else:
        owner_name = "Owner Account"
        business_name = "Demo Business"
        avatar = "DB"
    return {
        "owner_name": owner_name,
        "business_name": business_name,
        "avatar_text": avatar,
    }


@app.route("/")
def root():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO business_profile
            (id, owner_name, business_name, email, phone, business_type, monthly_revenue, monthly_expenses, marketing_spend, growth_target)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                owner_name = excluded.owner_name,
                business_name = excluded.business_name,
                email = excluded.email,
                phone = excluded.phone,
                business_type = excluded.business_type,
                monthly_revenue = excluded.monthly_revenue,
                monthly_expenses = excluded.monthly_expenses,
                marketing_spend = excluded.marketing_spend,
                growth_target = excluded.growth_target
            """,
            (
                request.form["owner_name"],
                request.form["business_name"],
                request.form["email"],
                request.form["phone"],
                request.form["business_type"],
                float(request.form["monthly_revenue"] or 0),
                float(request.form["monthly_expenses"] or 0),
                float(request.form["marketing_spend"] or 0),
                float(request.form["growth_target"] or 0),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    return render_template("login.html", profile=profile)


@app.route("/dashboard")
def dashboard():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    profile = get_business_profile(conn)
    metrics = query_metrics(conn)
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    revenue_series = [0] * len(month_labels)
    expense_series = [0] * len(month_labels)
    current_month = date.today().month
    for i in range(6):
        month = ((current_month - 5 + i - 1) % 12) + 1
        monthly_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE CAST(strftime('%m', order_date) AS INTEGER)=?",
            (month,),
        ).fetchone()[0]
        monthly_expense = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE CAST(strftime('%m', expense_date) AS INTEGER)=?",
            (month,),
        ).fetchone()[0]
        revenue_series[i] = monthly_revenue
        expense_series[i] = monthly_expense
    if profile and all(value == 0 for value in revenue_series):
        revenue_series[-1] = profile["monthly_revenue"]
    if profile and all(value == 0 for value in expense_series):
        expense_series[-1] = profile["monthly_expenses"] + profile["marketing_spend"]
    conn.close()
    return render_template(
        "dashboard.html",
        active_page="dashboard",
        metrics=metrics,
        month_labels=month_labels,
        revenue_series=revenue_series,
        expense_series=expense_series,
    )


@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO inventory_products (name, sku, category, stock, reorder_level, price, last_restocked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["name"],
                request.form["sku"],
                request.form["category"],
                int(request.form["stock"] or 0),
                int(request.form["reorder_level"] or 0),
                float(request.form["price"] or 0),
                request.form["last_restocked"] or date.today().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("inventory"))

    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = "SELECT * FROM inventory_products WHERE 1=1"
    params = []
    if q:
        query += " AND (name LIKE ? OR sku LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    categories = conn.execute(
        "SELECT DISTINCT category FROM inventory_products ORDER BY category"
    ).fetchall()
    metrics = query_metrics(conn)
    conn.close()
    return render_template(
        "inventory.html",
        active_page="inventory",
        products=rows,
        categories=[row["category"] for row in categories],
        selected_category=category,
        q=q,
        metrics=metrics,
    )


@app.post("/inventory/restock/<int:product_id>")
def restock_product(product_id):
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE inventory_products
        SET stock = stock + reorder_level,
            last_restocked = ?
        WHERE id = ?
        """,
        (date.today().isoformat(), product_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("inventory"))


@app.route("/orders", methods=["GET", "POST"])
def orders():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1001 FROM orders").fetchone()[0]
        order_code = f"ORD-{next_id}"
        conn.execute(
            """
            INSERT INTO orders
            (order_code, customer_name, items_count, total_amount, status, priority, order_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_code,
                request.form["customer_name"],
                int(request.form["items_count"] or 1),
                float(request.form["total_amount"] or 0),
                request.form["status"],
                request.form["priority"],
                request.form["order_date"] or date.today().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("orders"))

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if q:
        query += " AND (order_code LIKE ? OR customer_name LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    metrics = query_metrics(conn)
    conn.close()
    return render_template(
        "orders.html",
        active_page="orders",
        orders=rows,
        selected_status=status,
        q=q,
        metrics=metrics,
    )


@app.post("/orders/<int:order_id>/status")
def update_order_status(order_id):
    if not business_profile_required():
        return redirect(url_for("login"))
    new_status = request.form.get("status", "Processing")
    conn = get_db_connection()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    return redirect(url_for("orders"))


@app.route("/marketing", methods=["GET", "POST"])
def marketing():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO campaigns (title, description, segment, target_customers, expected_roi, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["title"],
                request.form["description"],
                request.form["segment"],
                int(request.form["target_customers"] or 0),
                float(request.form["expected_roi"] or 0),
                request.form["priority"],
                "Ready",
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("marketing"))

    campaigns = conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
    segment_rows = conn.execute(
        "SELECT segment, COUNT(*) as total FROM customers GROUP BY segment"
    ).fetchall()
    category_rows = conn.execute(
        "SELECT category, SUM(price * stock) as value FROM inventory_products GROUP BY category"
    ).fetchall()
    metrics = query_metrics(conn)
    conn.close()
    return render_template(
        "marketing.html",
        active_page="marketing",
        campaigns=campaigns,
        segments=segment_rows,
        categories=category_rows,
        metrics=metrics,
    )


@app.post("/marketing/<int:campaign_id>/launch")
def launch_campaign(campaign_id):
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    conn.execute("UPDATE campaigns SET status = 'Launched' WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("marketing"))


@app.route("/finance", methods=["GET", "POST"])
def finance():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO expenses (category, description, amount, expense_date)
            VALUES (?, ?, ?, ?)
            """,
            (
                request.form["category"],
                request.form["description"],
                float(request.form["amount"] or 0),
                request.form["expense_date"] or date.today().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("finance"))

    expenses = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
    monthly_rev = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now')"
    ).fetchone()[0]
    monthly_exp = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE strftime('%Y-%m', expense_date) = strftime('%Y-%m', 'now')"
    ).fetchone()[0]
    metrics = query_metrics(conn)
    forecast_revenue = monthly_rev * 1.05
    forecast_expenses = monthly_exp * 1.02
    expense_breakdown = conn.execute(
        "SELECT category, COALESCE(SUM(amount), 0) as total FROM expenses GROUP BY category"
    ).fetchall()
    conn.close()
    return render_template(
        "finance.html",
        active_page="finance",
        expenses=expenses,
        monthly_revenue=monthly_rev,
        monthly_expenses=monthly_exp,
        forecast_revenue=forecast_revenue,
        forecast_expenses=forecast_expenses,
        expense_breakdown=expense_breakdown,
        metrics=metrics,
    )


@app.route("/customers", methods=["GET", "POST"])
def customers():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO customers
            (name, email, phone, segment, total_orders, total_spent, last_purchase)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["name"],
                request.form["email"],
                request.form["phone"],
                request.form["segment"],
                int(request.form["total_orders"] or 0),
                float(request.form["total_spent"] or 0),
                request.form["last_purchase"] or date.today().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("customers"))

    rows = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    metrics = query_metrics(conn)
    conn.close()
    return render_template(
        "customers.html",
        active_page="customers",
        customers=rows,
        metrics=metrics,
    )


@app.route("/assistant", methods=["GET", "POST"])
def assistant():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        user_message = request.form["message"].strip()
        if user_message:
            now = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO assistant_messages (role, message, created_at) VALUES (?, ?, ?)",
                ("user", user_message, now),
            )
            metrics = query_metrics(conn)
            response = (
                f"Current snapshot: Revenue {format_inr(metrics['revenue'])}, "
                f"Net Profit {format_inr(metrics['net_profit'])}, "
                f"Low Stock Alerts {metrics['low_stock']}, Active Orders {metrics['active_orders']}. "
                "Add or update records in Inventory, Orders, Customers, and Finance tabs for smarter recommendations."
            )
            conn.execute(
                "INSERT INTO assistant_messages (role, message, created_at) VALUES (?, ?, ?)",
                ("assistant", response, now),
            )
            conn.commit()
        return redirect(url_for("assistant"))

    messages = conn.execute(
        "SELECT * FROM assistant_messages ORDER BY id ASC LIMIT 30"
    ).fetchall()
    metrics = query_metrics(conn)
    conn.close()
    return render_template(
        "assistant.html",
        active_page="assistant",
        messages=messages,
        metrics=metrics,
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True)