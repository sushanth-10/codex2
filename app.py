from datetime import date, datetime
import json
import os
import sqlite3
import google.generativeai as genai
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

app.config["GEMINI_API_KEY"] = ""
app.config["GEMINI_MODEL"] = "gemini-pro"

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

        CREATE TABLE IF NOT EXISTS monthly_financials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_month TEXT NOT NULL UNIQUE,
            revenue REAL,
            expenses REAL,
            source TEXT NOT NULL DEFAULT 'manual'
        );
        """
    )
    # Lightweight migration for existing databases.
    try:
        conn.execute(
            "ALTER TABLE inventory_products ADD COLUMN last_restock_amount INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass
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


def month_key_for(dt):
    return dt.strftime("%Y-%m")


def month_label(month_key):
    return datetime.strptime(month_key, "%Y-%m").strftime("%b %Y")


def previous_month_key(reference_date=None):
    current = reference_date or date.today()
    year = current.year
    month = current.month - 1
    if month == 0:
        month = 12
        year -= 1
    return f"{year}-{month:02d}"


def save_selected_month_financial(conn, form):
    selected_month = (form.get("financial_month") or "").strip() or previous_month_key()
    month_none = form.get("financial_month_none") == "on"
    if month_none:
        upsert_monthly_financial(conn, selected_month, None, None, source="manual")
        return

    selected_revenue_raw = form.get("selected_month_revenue", "").strip()
    selected_expenses_raw = form.get("selected_month_expenses", "").strip()
    if selected_revenue_raw or selected_expenses_raw:
        upsert_monthly_financial(
            conn,
            selected_month,
            float(selected_revenue_raw or 0),
            float(selected_expenses_raw or 0),
            source="manual",
        )


def pick_text(form, key, fallback=""):
    raw = (form.get(key) or "").strip()
    return raw if raw else fallback


def pick_float(form, key, fallback=0.0):
    raw = (form.get(key) or "").strip()
    if raw == "":
        return float(fallback or 0)
    try:
        return float(raw)
    except ValueError:
        return float(fallback or 0)


def upsert_monthly_financial(conn, year_month, revenue, expenses, source="manual"):
    conn.execute(
        """
        INSERT INTO monthly_financials (year_month, revenue, expenses, source)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(year_month) DO UPDATE SET
            revenue = excluded.revenue,
            expenses = excluded.expenses,
            source = excluded.source
        """,
        (year_month, revenue, expenses, source),
    )


def update_current_month_snapshot(conn, revenue, expenses):
    if revenue is None and expenses is None:
        return
    upsert_monthly_financial(
        conn,
        month_key_for(date.today()),
        revenue,
        expenses,
        source="profile",
    )


def get_chart_series(conn, profile):
    rows = conn.execute(
        "SELECT year_month, revenue, expenses FROM monthly_financials ORDER BY year_month ASC"
    ).fetchall()
    if rows:
        rows = rows[-6:]
        labels = [month_label(row["year_month"]) for row in rows]
        revenue = [float(row["revenue"] or 0) for row in rows]
        expenses = [float(row["expenses"] or 0) for row in rows]
        return labels, revenue, expenses

    # Fallback for older DBs with no monthly snapshots yet.
    current_month_key = month_key_for(date.today())
    monthly_rev = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE strftime('%Y-%m', order_date) = ?",
        (current_month_key,),
    ).fetchone()[0]
    monthly_exp = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE strftime('%Y-%m', expense_date) = ?",
        (current_month_key,),
    ).fetchone()[0]
    if monthly_rev == 0 and profile:
        monthly_rev = profile["monthly_revenue"]
    if monthly_exp == 0 and profile:
        monthly_exp = profile["monthly_expenses"] + profile["marketing_spend"]
    return [month_label(current_month_key)], [monthly_rev], [monthly_exp]


def build_ai_context(conn):
    metrics = query_metrics(conn)
    profile = get_business_profile(conn)
    latest_financials = conn.execute(
        """
        SELECT year_month, revenue, expenses
        FROM monthly_financials
        ORDER BY year_month DESC
        LIMIT 3
        """
    ).fetchall()
    financial_lines = "; ".join(
        [f"{row['year_month']}: revenue {row['revenue'] or 0}, expenses {row['expenses'] or 0}" for row in latest_financials]
    )
    return {
        "profile": dict(profile) if profile else {},
        "metrics": metrics,
        "recent_financials": financial_lines,
    }


def _gemini_api_key():
    return (
        (app.config.get("GEMINI_API_KEY") or "").strip()
        or (os.environ.get("GOOGLE_API_KEY") or "").strip()
    )


def call_gemini(conn, user_message):
    """All assistant replies go through Google Gemini when an API key is set."""
    api_key = _gemini_api_key()
    if not api_key:
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        return (
            "The Gemini package is not installed. Run: pip install google-generativeai"
        )

    try:
        genai.configure(api_key=api_key)
        model_name = (app.config.get("GEMINI_MODEL") or "gemini-1.5-flash").strip()
        context = build_ai_context(conn)
        prompt = (
            "You are a friendly business assistant for BizAssist AI. "
            "Answer in plain, simple language for non-technical users. "
            "Use the business context below when the question is about this business; "
            "otherwise give short, practical general business advice.\n\n"
            f"Business context (JSON):\n{json.dumps(context, default=str)}\n\n"
            f"User question:\n{user_message}"
        )
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        try:
            text = (response.text or "").strip()
        except ValueError:
            text = ""
        if text:
            return text
        return (
            "Gemini returned no text (it may have been blocked for safety). "
            "Try rephrasing your question."
        )
    except Exception as exc:
        return f"Gemini error: {exc!s}. Check GEMINI_MODEL and your API key."


def build_assistant_response(conn, user_message):
    reply = call_gemini(conn, user_message)
    if reply is not None:
        return reply
    return (
        "Set your Google Gemini API key: put it in app.py as GEMINI_API_KEY = \"your-key\" "
        "or set the GOOGLE_API_KEY environment variable, install google-generativeai, then restart the app."
    )


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
        monthly_revenue = float(request.form["monthly_revenue"] or 0)
        monthly_expenses = float(request.form["monthly_expenses"] or 0)
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
                monthly_revenue,
                monthly_expenses,
                float(request.form["marketing_spend"] or 0),
                float(request.form["growth_target"] or 0),
            ),
        )
        update_current_month_snapshot(conn, monthly_revenue, monthly_expenses)
        save_selected_month_financial(conn, request.form)
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    selected_month = previous_month_key()
    selected_row = conn.execute(
        "SELECT revenue, expenses FROM monthly_financials WHERE year_month = ?",
        (selected_month,),
    ).fetchone()
    conn.close()
    return render_template(
        "login.html",
        profile=None,
        active_page="business_profile",
        form_mode="login",
        selected_financial_month=selected_month,
        selected_month_revenue=(selected_row["revenue"] if selected_row else ""),
        selected_month_expenses=(selected_row["expenses"] if selected_row else ""),
    )


@app.route("/business-profile", methods=["GET", "POST"])
def business_profile():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    if request.method == "POST":
        existing = get_business_profile(conn)
        existing_data = dict(existing) if existing else {}
        monthly_revenue = pick_float(request.form, "monthly_revenue", existing_data.get("monthly_revenue", 0))
        monthly_expenses = pick_float(request.form, "monthly_expenses", existing_data.get("monthly_expenses", 0))
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
                pick_text(request.form, "owner_name", existing_data.get("owner_name", "Owner Account")),
                pick_text(request.form, "business_name", existing_data.get("business_name", "Demo Business")),
                pick_text(request.form, "email", existing_data.get("email", "owner@example.com")),
                pick_text(request.form, "phone", existing_data.get("phone", "0000000000")),
                pick_text(request.form, "business_type", existing_data.get("business_type", "Retail")),
                monthly_revenue,
                monthly_expenses,
                pick_float(request.form, "marketing_spend", existing_data.get("marketing_spend", 0)),
                pick_float(request.form, "growth_target", existing_data.get("growth_target", 0)),
            ),
        )
        update_current_month_snapshot(conn, monthly_revenue, monthly_expenses)
        save_selected_month_financial(conn, request.form)
        conn.commit()
        conn.close()
        action = request.form.get("action", "stay")
        if action == "dashboard":
            return redirect(url_for("dashboard"))
        return redirect(url_for("business_profile"))

    profile = get_business_profile(conn)
    selected_month = previous_month_key()
    selected_row = conn.execute(
        "SELECT revenue, expenses FROM monthly_financials WHERE year_month = ?",
        (selected_month,),
    ).fetchone()
    conn.close()
    return render_template(
        "login.html",
        profile=profile,
        active_page="business_profile",
        form_mode="profile",
        selected_financial_month=selected_month,
        selected_month_revenue=(selected_row["revenue"] if selected_row else ""),
        selected_month_expenses=(selected_row["expenses"] if selected_row else ""),
    )


@app.route("/dashboard")
def dashboard():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    profile = get_business_profile(conn)
    metrics = query_metrics(conn)
    month_labels, revenue_series, expense_series = get_chart_series(conn, profile)
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
                request.form["sku"] or "NONE",
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
    restock_qty = max(1, int(request.form.get("restock_amount", 0) or 0))
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE inventory_products
        SET stock = stock + ?,
            last_restock_amount = ?,
            last_restocked = ?
        WHERE id = ?
        """,
        (restock_qty, restock_qty, date.today().isoformat(), product_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("inventory"))


@app.post("/inventory/delete/<int:product_id>")
def delete_product(product_id):
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    conn.execute("DELETE FROM inventory_products WHERE id = ?", (product_id,))
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


@app.post("/orders/delete/<int:order_id>")
def delete_order(order_id):
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
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


@app.post("/customers/delete/<int:customer_id>")
def delete_customer(customer_id):
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("customers"))


@app.post("/assistant/reset")
def assistant_reset():
    if not business_profile_required():
        return redirect(url_for("login"))
    conn = get_db_connection()
    conn.execute("DELETE FROM assistant_messages")
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO assistant_messages (role, message, created_at) VALUES (?, ?, ?)",
        (
            "assistant",
            "Chat cleared. Ask me anything about your business, inventory, orders, or finances.",
            now,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("assistant"))


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
            response = build_assistant_response(conn, user_message)
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