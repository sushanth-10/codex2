from datetime import date, datetime
import json
import os
import re
import sqlite3
import google.generativeai as genai
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-bizassist-secret-change-me")
import json
from openai import OpenAI
from flask import jsonify
'''client = OpenAI(api_key="    ")'''

def ai_extract_command(text):
    prompt = f"""
    You are a smart business assistant.

    Extract intent and data from user input.

    Supported intents:
    - add_customer
    - update_customer
    - add_order
    - add_expense

    Return JSON ONLY:
    {{
        "intent": "",
        "name": "",
        "email": "",
        "phone": "",
        "segment": "",
        "items": 0,
        "amount": 0
    }}

    Input: {text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.choices[0].message.content)

@app.route("/voice_assistant", methods=["POST"])
def voice_assistant():
    conn = get_db_connection()
    data = request.get_json()
    user_message = data.get("message", "")

    now = datetime.now().isoformat(timespec="seconds")

    conn.execute(
        "INSERT INTO assistant_messages (role, message, created_at) VALUES (?, ?, ?)",
        ("user", user_message, now),
    )

    try:
        command = ai_extract_command(user_message)
        intent = command.get("intent")

        response = "Done."

        # ADD CUSTOMER
        if intent == "add_customer":
            conn.execute(
                """
                INSERT INTO customers
                (name, email, phone, segment, total_orders, total_spent, last_purchase)
                VALUES (?, ?, ?, ?, 0, 0, ?)
                """,
                (
                    command["name"],
                    command["email"],
                    command["phone"],
                    command.get("segment", "New"),
                    date.today().isoformat(),
                ),
            )
            response = f"Customer {command['name']} added."

        # UPDATE CUSTOMER
        elif intent == "update_customer":
            conn.execute(
                """
                UPDATE customers
                SET email = COALESCE(?, email),
                    phone = COALESCE(?, phone),
                    segment = COALESCE(?, segment)
                WHERE name = ?
                """,
                (
                    command.get("email"),
                    command.get("phone"),
                    command.get("segment"),
                    command["name"],
                ),
            )
            response = f"Customer {command['name']} updated."

        # ADD ORDER
        elif intent == "add_order":
            conn.execute(
                """
                INSERT INTO orders
                (order_code, customer_name, items_count, total_amount, status, priority, order_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ORD-{int(datetime.now().timestamp())}",
                    command["name"],
                    command.get("items", 1),
                    command.get("amount", 0),
                    "Pending",
                    "Medium",
                    date.today().isoformat(),
                ),
            )
            response = "Order added."

        # ADD EXPENSE
        elif intent == "add_expense":
            conn.execute(
                """
                INSERT INTO expenses (category, description, amount, expense_date)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "General",
                    "Voice entry",
                    command.get("amount", 0),
                    date.today().isoformat(),
                ),
            )
            response = "Expense added."

        else:
            metrics = query_metrics(conn)
            response = f"Revenue {format_inr(metrics['revenue'])}, Profit {format_inr(metrics['net_profit'])}"

    except Exception:
        response = "Sorry, I couldn't understand."

    conn.execute(
        "INSERT INTO assistant_messages (role, message, created_at) VALUES (?, ?, ?)",
        ("assistant", response, now),
    )

    conn.commit()
    conn.close()

    return jsonify({"reply": response})
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
            growth_target REAL NOT NULL DEFAULT 0,
            account_type TEXT NOT NULL DEFAULT 'business',
            location TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS shop_discounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            discount_percent REAL NOT NULL,
            shop_location TEXT NOT NULL,
            shop_name TEXT,
            created_at TEXT NOT NULL
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
    for stmt in (
        "ALTER TABLE business_profile ADD COLUMN account_type TEXT NOT NULL DEFAULT 'business'",
        "ALTER TABLE business_profile ADD COLUMN location TEXT NOT NULL DEFAULT ''",
    ):
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS shop_discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                discount_percent REAL NOT NULL,
                shop_location TEXT NOT NULL,
                shop_name TEXT,
                created_at TEXT NOT NULL
            );
            """
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
                assistant_reset_welcome(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    discount_count = conn.execute("SELECT COUNT(*) FROM shop_discounts").fetchone()[0]
    if discount_count == 0:
        demo_loc = normalize_location("Demo Metro Area")
        now = datetime.now().isoformat(timespec="seconds")
        conn.executemany(
            """
            INSERT INTO shop_discounts (product_name, discount_percent, shop_location, shop_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("Organic vegetables box", 15.0, demo_loc, "GreenBasket Market", now),
                ("LED desk lamp", 12.5, demo_loc, "BrightHome", now),
                ("Running shoes", 20.0, demo_loc, "Stride Sports", now),
                ("Noise cancelling earbuds", 18.0, demo_loc, "TechNest", now),
                ("Office chair ergonomic", 22.0, demo_loc, "ComfortSeat Co.", now),
                ("Stainless steel bottle", 8.0, demo_loc, "EcoWare", now),
                ("Yoga mat premium", 14.0, demo_loc, "ZenFit Studio", now),
                ("Breakfast cereal bundle", 10.0, demo_loc, "MorningGoods", now),
                ("Portable charger 20k mAh", 16.0, demo_loc, "PowerUp", now),
                ("Winter jacket", 25.0, demo_loc, "Urban Outerwear", now),
            ],
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


def normalize_assistant_question(text):
    """Normalize user text for matching canned assistant replies (offline-friendly, punctuation-insensitive)."""
    if text is None:
        return ""
    s = str(text).strip().lower()
    # Curly quotes / apostrophes → ascii, then drop apostrophes so "don't" and "dont" match.
    for ch in ("\u2019", "\u2018", "\u201c", "\u201d", "`"):
        s = s.replace(ch, "'")
    s = s.replace("'", "")
    # Letters and digits only; collapses punctuation around words.
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Thirty built-in Q&A pairs (exact match after normalization). Extend keys with aliases where helpful.
CANNED_ASSISTANT_RESPONSES = {
    normalize_assistant_question("What is BizAssist AI?"): (
        "BizAssist AI is a simple business companion app in your browser: it helps you track inventory, orders, "
        "customers, expenses, marketing campaigns, and discounts. Personal accounts can browse local offers that "
        "match the location on your profile."
    ),
    normalize_assistant_question("How do I track inventory?"): (
        "Open the Inventory tab from the sidebar. There you can see stock levels, reorder levels, and prices. "
        "Low-stock items are counted in dashboard metrics."
    ),
    normalize_assistant_question("How do I add a new product?"): (
        "Go to Inventory and use the form to add a product with name, SKU, category, stock, reorder level, price, "
        "and restock date. Saving updates your catalog immediately."
    ),
    normalize_assistant_question("What is net profit?"): (
        "Net profit here is revenue minus expenses (including marketing spend from your business profile when "
        "no detailed records exceed the baseline). Check the Dashboard and Finance sections for the current view."
    ),
    normalize_assistant_question("How do I view my orders?"): (
        "Click Orders in the sidebar. You will see order code, customer, totals, status, and priority. "
        "Statuses like Pending and Processing count as active orders on the dashboard."
    ),
    normalize_assistant_question("How do I add a customer?"): (
        "Open the Customers page and fill in name, email, phone, and segment (for example VIP, New, or Regular). "
        "Segments are used for marketing campaigns."
    ),
    normalize_assistant_question("What are low stock alerts?"): (
        "Low stock alerts count products where current stock is at or below the reorder level you set in Inventory. "
        "The dashboard shows how many items need attention."
    ),
    normalize_assistant_question("How do I update my business profile?"): (
        "Go to Business Profile (or My account for personal users). Update owner name, contact details, "
        "business type, revenue, expenses, targets, and location—location is used to match shop discounts with "
        "personal shoppers in the same area."
    ),
    normalize_assistant_question("How do I create a marketing campaign?"): (
        "Open Marketing while signed in as a business user. Under Add Campaign, enter title, segment, targets, "
        "expected ROI, priority, and description, then save. You can launch campaigns from the same page."
    ),
    normalize_assistant_question("How do I publish a discount for customers?"): (
        "On Marketing, use Add product discount. Enter product name and discount percentage. "
        "Discounts are stored by your normalized business location so personal accounts with the same location "
        "text see them on Local offers."
    ),
    normalize_assistant_question("Where can I see local offers as a shopper?"): (
        "Create or sign in to a personal account, set your location under My account, then open Local offers "
        "(Marketing). Offers come from the shared database and update when businesses add or remove discounts "
        "for that location."
    ),
    normalize_assistant_question("How do I record an expense?"): (
        "Use the Finance section: add category, description, amount, and date. Expenses feed into profit "
        "calculations alongside order revenue."
    ),
    normalize_assistant_question("What is ROI?"): (
        "ROI (return on investment) in campaigns is the expected percentage return you enter when creating "
        "a campaign. It is a planning field to compare campaign ideas."
    ),
    normalize_assistant_question("How do I delete a discount?"): (
        "On Marketing as a business user, find Your published discounts and click Delete next to the offer. "
        "Personal Local offers refresh automatically because they read the same discount list."
    ),
    normalize_assistant_question("What segments can I target?"): (
        "Campaigns use customer segments such as VIP, New, At Risk, or Regular—match the segment labels you use "
        "on customer records so targeting stays consistent."
    ),
    normalize_assistant_question("How does the dashboard work?"): (
        "The Dashboard summarizes revenue, expenses, profit, active orders, low-stock count, and customer counts. "
        "Figures combine order/expense tables with values from your business profile when needed."
    ),
    normalize_assistant_question("What financial reports are available?"): (
        "Finance shows expense entries and monthly snapshots; the Dashboard charts recent monthly revenue and "
        "expenses when monthly_financials data exists."
    ),
    normalize_assistant_question("How do I launch a campaign?"): (
        "On Marketing, find your campaign card and click Launch Campaign. The status updates to Launched."
    ),
    normalize_assistant_question("What is monthly revenue?"): (
        "Monthly revenue is the revenue attributed to the current reporting month—computed from orders for that "
        "month and compared with the revenue figure saved in your business profile and monthly_financials."
    ),
    normalize_assistant_question("Is my data secure?"): (
        "This project stores data in a local SQLite file. Use a strong FLASK_SECRET_KEY in production, "
        "protect file permissions, and host behind HTTPS—standard practices for small Flask deployments."
    ),
    normalize_assistant_question("Can I use this on mobile?"): (
        "The interface is a responsive web app. Open it in your phone browser; layout adapts on smaller screens."
    ),
    normalize_assistant_question("What currency is displayed?"): (
        "Amounts are formatted as INR (Indian Rupees) using the app's number formatting."
    ),
    normalize_assistant_question("How do I clear the AI chat history?"): (
        "Messages are stored in the assistant_messages table; a reset endpoint can clear them if enabled. "
        "Otherwise ask short new questions—the page shows the latest conversation window."
    ),
    normalize_assistant_question("What is Gemini?"): (
        "Gemini is Google's generative AI. If GEMINI_API_KEY or GOOGLE_API_KEY is set and google-generativeai "
        "is installed, this assistant answers via Gemini; otherwise you see setup instructions."
    ),
    normalize_assistant_question("How do I improve profit?"): (
        "Raise revenue (orders), control expenses and marketing spend, manage inventory to avoid stockouts, "
        "and focus campaigns on high-ROI segments—then review Dashboard and Finance regularly."
    ),
    normalize_assistant_question("What is a VIP customer?"): (
        "VIP is a segment label you can assign on the Customers page. Campaigns can target VIP alongside other segments."
    ),
    normalize_assistant_question("How do discounts sync to personal accounts?"): (
        "Both account types use the same SQLite database. Businesses insert rows into shop_discounts with a "
        "normalized location; personal Local offers query that table for your normalized profile location, "
        "so new or deleted discounts appear on refresh without a separate sync step."
    ),
    normalize_assistant_question("What does normalized location mean?"): (
        "Your location text is lowercased and extra spaces are removed before matching. "
        "Enter the same area text on business and personal profiles to see the same offers."
    ),
    normalize_assistant_question("How do I see the top offers in my area?"): (
        "Open Local offers on a personal account. The Top 10 section ranks the highest discounts for your "
        "location; demo picks fill in if there are fewer than ten real offers."
    ),
    normalize_assistant_question("Why don't I see any offers?"): (
        "Set a location under My account. It must match the normalized location businesses used when posting "
        "discounts. If nothing matches, you will still see featured demo suggestions in Top 10 when enabled."
    ),
}

# Display strings for the assistant page (same 30 as CANNED_ASSISTANT_RESPONSES keys, pre-normalization).
ASSISTANT_SUGGESTED_QUESTIONS = [
    "What is BizAssist AI?",
    "How do I track inventory?",
    "How do I add a new product?",
    "What is net profit?",
    "How do I view my orders?",
    "How do I add a customer?",
    "What are low stock alerts?",
    "How do I update my business profile?",
    "How do I create a marketing campaign?",
    "How do I publish a discount for customers?",
    "Where can I see local offers as a shopper?",
    "How do I record an expense?",
    "What is ROI?",
    "How do I delete a discount?",
    "What segments can I target?",
    "How does the dashboard work?",
    "What financial reports are available?",
    "How do I launch a campaign?",
    "What is monthly revenue?",
    "Is my data secure?",
    "Can I use this on mobile?",
    "What currency is displayed?",
    "How do I clear the AI chat history?",
    "What is Gemini?",
    "How do I improve profit?",
    "What is a VIP customer?",
    "How do discounts sync to personal accounts?",
    "What does normalized location mean?",
    "How do I see the top offers in my area?",
    "Why don't I see any offers?",
]


# Fallback “area” offers when fewer than ten real discounts exist (same DB; labeled in the UI).
BUILTIN_AREA_OFFER_PAD = [
    ("Fresh produce bundle", 18.0, "Neighborhood Fresh"),
    ("Household essentials kit", 12.0, "City Mart"),
    ("Weekend bakery box", 22.0, "Rise & Shine Bakery"),
    ("Mobile accessories pack", 15.0, "Tech Corner"),
    ("Coffee & snacks combo", 20.0, "Daily Grind Café"),
    ("Sportswear clearance", 25.0, "ActiveWear Outlet"),
    ("Books & stationery set", 10.0, "Pages & Pens"),
    ("Skincare sampler", 17.0, "Glow Beauty"),
    ("Kids apparel bundle", 14.0, "Little Steps"),
    ("DIY hardware starter", 11.0, "FixIt Hardware"),
]


def row_to_offer_dict(row, builtin=False):
    d = {k: row[k] for k in row.keys()}
    d["builtin"] = builtin
    return d


def merge_top_ten_area_offers(db_rows, user_norm):
    """Return up to 10 offer dicts: real DB rows first (by discount), then padded builtins."""
    rows = list(db_rows)
    rows.sort(key=lambda r: (-float(r["discount_percent"]), -int(r["id"])))
    out = []
    seen_product = set()
    for r in rows:
        pn = (r["product_name"] or "").strip().lower()
        if pn in seen_product:
            continue
        seen_product.add(pn)
        out.append(row_to_offer_dict(r, builtin=False))
        if len(out) >= 10:
            return out
    for prod, pct, shop in BUILTIN_AREA_OFFER_PAD:
        if len(out) >= 10:
            break
        pn = prod.strip().lower()
        if pn in seen_product:
            continue
        seen_product.add(pn)
        out.append(
            {
                "id": None,
                "product_name": prod,
                "discount_percent": pct,
                "shop_location": user_norm,
                "shop_name": shop,
                "created_at": "",
                "builtin": True,
            }
        )
    return out


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
    nq = normalize_assistant_question(user_message)
    if nq and nq in CANNED_ASSISTANT_RESPONSES:
        return CANNED_ASSISTANT_RESPONSES[nq]
    reply = call_gemini(conn, user_message)
    if reply is not None:
        return reply
    return (
        "No AI API key is configured, so only the built-in questions (buttons above) get full answers offline. "
        "Tap a suggested question and press Send, or add GEMINI_API_KEY / GOOGLE_API_KEY for open-ended chat."
    )


def assistant_reset_welcome():
    return (
        "Hello! I can answer the 30 built-in questions without any API key. "
        "For other topics, add a Gemini API key in settings or environment."
    )


def get_business_profile(conn):
    return conn.execute("SELECT * FROM business_profile WHERE id = 1").fetchone()


def normalize_location(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def get_account_type(profile):
    if not profile:
        return None
    try:
        raw = profile["account_type"]
    except (KeyError, IndexError):
        raw = None
    t = (raw or "business").strip().lower()
    return t if t in ("business", "personal") else "business"


def session_matches_profile(profile):
    """True when the user completed account choice login for this stored profile."""
    if not profile:
        return False
    auth = session.get("account_auth")
    if auth not in ("business", "personal"):
        return False
    return auth == get_account_type(profile)


def require_business_user():
    """Return a Flask redirect if visitor has no matching session/profile or is a personal account."""
    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    if not profile or not session_matches_profile(profile):
        return redirect(url_for("root"))
    if get_account_type(profile) == "personal":
        return redirect(url_for("marketing"))
    return None


def business_profile_required():
    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    return profile is not None and session_matches_profile(profile)


@app.context_processor
def inject_business_profile():
    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    if profile:
        owner_name = profile["owner_name"]
        business_name = profile["business_name"]
        avatar = "".join([part[0].upper() for part in owner_name.split()[:2]]) or "DB"
        is_personal_account = get_account_type(profile) == "personal"
    else:
        owner_name = "Owner Account"
        business_name = "Demo Business"
        avatar = "DB"
        is_personal_account = False
    return {
        "owner_name": owner_name,
        "business_name": business_name,
        "avatar_text": avatar,
        "is_personal_account": is_personal_account,
    }


@app.route("/")
def root():
    conn = get_db_connection()
    profile = get_business_profile(conn)
    conn.close()
    if profile and session_matches_profile(profile):
        if get_account_type(profile) == "personal":
            return redirect(url_for("marketing"))
        return redirect(url_for("dashboard"))
    return render_template("account_choice.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("root"))


@app.route("/personal-signup", methods=["GET", "POST"])
def personal_signup():
    conn = get_db_connection()
    existing = get_business_profile(conn)
    if existing and session_matches_profile(existing):
        conn.close()
        if get_account_type(existing) == "personal":
            return redirect(url_for("marketing"))
        return redirect(url_for("dashboard"))
    conn.close()

    if request.method == "POST":
        loc = pick_text(request.form, "location", "")
        if not loc:
            return render_template(
                "personal_signup.html",
                error="Please enter your location so we can show nearby shop offers.",
            ), 400
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO business_profile
            (id, owner_name, business_name, email, phone, business_type, monthly_revenue, monthly_expenses, marketing_spend, growth_target, account_type, location)
            VALUES (1, ?, 'Personal', ?, ?, 'Personal', 0, 0, 0, 0, 'personal', ?)
            ON CONFLICT(id) DO UPDATE SET
                owner_name = excluded.owner_name,
                business_name = excluded.business_name,
                email = excluded.email,
                phone = excluded.phone,
                business_type = excluded.business_type,
                monthly_revenue = excluded.monthly_revenue,
                monthly_expenses = excluded.monthly_expenses,
                marketing_spend = excluded.marketing_spend,
                growth_target = excluded.growth_target,
                account_type = 'personal',
                location = excluded.location
            """,
            (
                pick_text(request.form, "owner_name", "Member"),
                pick_text(request.form, "email", "member@example.com"),
                pick_text(request.form, "phone", ""),
                loc,
            ),
        )
        conn.commit()
        conn.close()
        session["account_auth"] = "personal"
        return redirect(url_for("marketing"))

    return render_template("personal_signup.html", error=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db_connection()
    existing = get_business_profile(conn)
    if request.method == "GET" and existing and session_matches_profile(existing):
        conn.close()
        if get_account_type(existing) == "personal":
            return redirect(url_for("marketing"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        loc = pick_text(request.form, "location", "")
        if not loc:
            conn.close()
            selected_month = previous_month_key()
            selected_row = None
            existing_profile = existing if existing and get_account_type(existing) == "business" else None
            return render_template(
                "login.html",
                profile=existing_profile,
                active_page="business_profile",
                form_mode="login",
                selected_financial_month=selected_month,
                selected_month_revenue="",
                selected_month_expenses="",
                location_error="Please enter your shop or business location.",
            ), 400
        monthly_revenue = float(request.form["monthly_revenue"] or 0)
        monthly_expenses = float(request.form["monthly_expenses"] or 0)
        conn.execute(
            """
            INSERT INTO business_profile
            (id, owner_name, business_name, email, phone, business_type, monthly_revenue, monthly_expenses, marketing_spend, growth_target, account_type, location)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'business', ?)
            ON CONFLICT(id) DO UPDATE SET
                owner_name = excluded.owner_name,
                business_name = excluded.business_name,
                email = excluded.email,
                phone = excluded.phone,
                business_type = excluded.business_type,
                monthly_revenue = excluded.monthly_revenue,
                monthly_expenses = excluded.monthly_expenses,
                marketing_spend = excluded.marketing_spend,
                growth_target = excluded.growth_target,
                account_type = 'business',
                location = excluded.location
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
                loc,
            ),
        )
        update_current_month_snapshot(conn, monthly_revenue, monthly_expenses)
        save_selected_month_financial(conn, request.form)
        conn.commit()
        conn.close()
        session["account_auth"] = "business"
        return redirect(url_for("dashboard"))

    selected_month = previous_month_key()
    selected_row = conn.execute(
        "SELECT revenue, expenses FROM monthly_financials WHERE year_month = ?",
        (selected_month,),
    ).fetchone()
    conn.close()
    login_profile = existing if existing and get_account_type(existing) == "business" else None
    return render_template(
        "login.html",
        profile=login_profile,
        active_page="business_profile",
        form_mode="login",
        selected_financial_month=selected_month,
        selected_month_revenue=(selected_row["revenue"] if selected_row else ""),
        selected_month_expenses=(selected_row["expenses"] if selected_row else ""),
        location_error="",
    )


@app.route("/business-profile", methods=["GET", "POST"])
def business_profile():
    if not business_profile_required():
        return redirect(url_for("root"))
    conn = get_db_connection()
    profile = get_business_profile(conn)
    if get_account_type(profile) == "personal":
        if request.method == "POST":
            loc = pick_text(request.form, "location", "")
            if not loc:
                conn.close()
                return render_template(
                    "personal_profile.html",
                    profile=profile,
                    error="Location is required so offers match your area.",
                    active_page="business_profile",
                ), 400
            conn.execute(
                """
                UPDATE business_profile SET
                    owner_name = ?,
                    email = ?,
                    phone = ?,
                    location = ?
                WHERE id = 1
                """,
                (
                    pick_text(request.form, "owner_name", profile["owner_name"]),
                    pick_text(request.form, "email", profile["email"]),
                    pick_text(request.form, "phone", profile["phone"]),
                    loc,
                ),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("marketing"))
        conn.close()
        return render_template(
            "personal_profile.html",
            profile=profile,
            error=None,
            active_page="business_profile",
        )

    if request.method == "POST":
        existing = profile
        existing_data = dict(existing) if existing else {}
        monthly_revenue = pick_float(request.form, "monthly_revenue", existing_data.get("monthly_revenue", 0))
        monthly_expenses = pick_float(request.form, "monthly_expenses", existing_data.get("monthly_expenses", 0))
        loc = pick_text(request.form, "location", existing_data.get("location", ""))
        if not loc:
            conn.close()
            return render_template(
                "login.html",
                profile=profile,
                active_page="business_profile",
                form_mode="profile",
                selected_financial_month=previous_month_key(),
                selected_month_revenue="",
                selected_month_expenses="",
                location_error="Please enter your shop or business location.",
            ), 400
        conn.execute(
            """
            INSERT INTO business_profile
            (id, owner_name, business_name, email, phone, business_type, monthly_revenue, monthly_expenses, marketing_spend, growth_target, account_type, location)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'business', ?)
            ON CONFLICT(id) DO UPDATE SET
                owner_name = excluded.owner_name,
                business_name = excluded.business_name,
                email = excluded.email,
                phone = excluded.phone,
                business_type = excluded.business_type,
                monthly_revenue = excluded.monthly_revenue,
                monthly_expenses = excluded.monthly_expenses,
                marketing_spend = excluded.marketing_spend,
                growth_target = excluded.growth_target,
                account_type = 'business',
                location = excluded.location
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
                loc,
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
        location_error="",
    )


@app.route("/dashboard")
def dashboard():
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("DELETE FROM inventory_products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory"))


@app.route("/orders", methods=["GET", "POST"])
def orders():
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    new_status = request.form.get("status", "Processing")
    conn = get_db_connection()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    return redirect(url_for("orders"))


@app.post("/orders/delete/<int:order_id>")
def delete_order(order_id):
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("orders"))


@app.route("/marketing", methods=["GET", "POST"])
def marketing():
    if not business_profile_required():
        return redirect(url_for("root"))
    conn = get_db_connection()
    profile = get_business_profile(conn)
    acc = get_account_type(profile)

    if request.method == "POST" and acc == "business":
        action = request.form.get("form_action", "campaign")
        if action == "discount":
            pname = pick_text(request.form, "product_name", "")
            pct = pick_float(request.form, "discount_percent", 0)
            loc = normalize_location(profile["location"] or "")
            if pname and pct > 0 and loc:
                now = datetime.now().isoformat(timespec="seconds")
                conn.execute(
                    """
                    INSERT INTO shop_discounts (product_name, discount_percent, shop_location, shop_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pname, pct, loc, profile["business_name"], now),
                )
            conn.commit()
            conn.close()
            return redirect(url_for("marketing"))
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

    if request.method == "POST" and acc == "personal":
        conn.close()
        return redirect(url_for("marketing"))

    search_q = request.args.get("q", "").strip()
    user_norm = normalize_location(profile["location"] or "")

    discounts_for_template = []
    top_10_offers = []
    if acc == "personal":
        if user_norm:
            if search_q:
                like = f"%{search_q}%"
                discounts_for_template = conn.execute(
                    """
                    SELECT * FROM shop_discounts
                    WHERE shop_location = ?
                      AND (lower(product_name) LIKE lower(?) OR lower(IFNULL(shop_name,'')) LIKE lower(?))
                    ORDER BY discount_percent DESC, id DESC
                    """,
                    (user_norm, like, like),
                ).fetchall()
            else:
                discounts_for_template = conn.execute(
                    """
                    SELECT * FROM shop_discounts
                    WHERE shop_location = ?
                    ORDER BY discount_percent DESC, id DESC
                    """,
                    (user_norm,),
                ).fetchall()
            rows_for_top = conn.execute(
                """
                SELECT * FROM shop_discounts
                WHERE shop_location = ?
                ORDER BY discount_percent DESC, id DESC
                """,
                (user_norm,),
            ).fetchall()
            top_10_offers = merge_top_ten_area_offers(rows_for_top, user_norm)

    recent_all_discounts = []
    if acc == "personal":
        recent_all_discounts = conn.execute(
            """
            SELECT * FROM shop_discounts
            ORDER BY id DESC
            LIMIT 25
            """
        ).fetchall()

    campaigns = []
    segment_rows = []
    category_rows = []
    metrics = None
    if acc == "business":
        campaigns = conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
        segment_rows = conn.execute(
            "SELECT segment, COUNT(*) as total FROM customers GROUP BY segment"
        ).fetchall()
        category_rows = conn.execute(
            "SELECT category, SUM(price * stock) as value FROM inventory_products GROUP BY category"
        ).fetchall()
        metrics = query_metrics(conn)
        if user_norm:
            discounts_for_template = conn.execute(
                """
                SELECT * FROM shop_discounts WHERE shop_location = ?
                ORDER BY discount_percent DESC, id DESC
                """,
                (user_norm,),
            ).fetchall()
        else:
            discounts_for_template = conn.execute(
                "SELECT * FROM shop_discounts ORDER BY discount_percent DESC, id DESC"
            ).fetchall()

    conn.close()
    return render_template(
        "marketing.html",
        active_page="marketing",
        is_personal=(acc == "personal"),
        campaigns=campaigns,
        segments=segment_rows,
        categories=category_rows,
        metrics=metrics,
        discounts=discounts_for_template,
        top_10_offers=top_10_offers,
        recent_all_discounts=recent_all_discounts,
        user_location_display=(profile["location"] or ""),
        search_q=search_q,
    )


@app.post("/marketing/<int:campaign_id>/launch")
def launch_campaign(campaign_id):
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("UPDATE campaigns SET status = 'Launched' WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("marketing"))


@app.post("/marketing/discount/<int:discount_id>/delete")
def delete_discount(discount_id):
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("DELETE FROM shop_discounts WHERE id = ?", (discount_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("marketing"))


@app.route("/finance", methods=["GET", "POST"])
def finance():
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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


@app.post("/finance/expense/<int:expense_id>/delete")
def delete_expense(expense_id):
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("finance"))


@app.post("/finance/expense/<int:expense_id>/update")
def update_expense(expense_id):
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE expenses SET
            category = ?,
            description = ?,
            amount = ?,
            expense_date = ?
        WHERE id = ?
        """,
        (
            pick_text(request.form, "category", "General"),
            pick_text(request.form, "description", ""),
            float(request.form.get("amount") or 0),
            pick_text(request.form, "expense_date", date.today().isoformat()),
            expense_id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("finance"))


@app.route("/customers", methods=["GET", "POST"])
def customers():
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("customers"))


@app.post("/assistant/reset")
def assistant_reset():
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
    conn = get_db_connection()
    conn.execute("DELETE FROM assistant_messages")
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO assistant_messages (role, message, created_at) VALUES (?, ?, ?)",
        ("assistant", assistant_reset_welcome(), now),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("assistant"))


@app.route("/assistant", methods=["GET", "POST"])
def assistant():
    if not business_profile_required():
        return redirect(url_for("root"))
    redir = require_business_user()
    if redir:
        return redir
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
        suggested_questions=ASSISTANT_SUGGESTED_QUESTIONS,
    )




init_db()

if __name__ == "__main__":
    app.run(debug=True)