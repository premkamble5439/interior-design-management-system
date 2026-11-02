from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal, InvalidOperation
from functools import wraps
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import os
import uuid

# ============================================================
# INTERIOR DESIGN MANAGEMENT SYSTEM
# Flask + MySQL / XAMPP
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "interior-design-system-secret-key-change-this"
)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
# IMPORTANT:
# Your SQL database is named "interior_design".
# If your config.py already contains DB_CONFIG, it will be used.

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "interior_design",
}

try:
    from config import DB_CONFIG as CONFIG_DB
    if isinstance(CONFIG_DB, dict):
        DB_CONFIG.update(CONFIG_DB)
except (ImportError, AttributeError):
    pass


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_all(query, params=()):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params)
        return cursor.fetchall()

    except Error as e:
        print("DATABASE SELECT ERROR:", e)
        return []

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def fetch_one(query, params=()):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params)
        return cursor.fetchone()

    except Error as e:
        print("DATABASE SELECT ERROR:", e)
        return None

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def execute_query(query, params=(), return_lastrowid=False):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()

        if return_lastrowid:
            return cursor.lastrowid

        return True

    except Error as e:
        print("DATABASE WRITE ERROR:", e)

        if connection:
            connection.rollback()

        return None

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def table_columns(table_name):
    """Return column names for a table."""
    allowed = {
        "users",
        "customers",
        "designers",
        "services",
        "gallery",
        "consultations",
        "appointments",
        "projects",
        "project_updates",
        "quotations",
        "products",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "payments",
    }

    if table_name not in allowed:
        return []

    rows = fetch_all(f"SHOW COLUMNS FROM `{table_name}`")
    return [row["Field"] for row in rows]


def dynamic_insert(table_name, data):
    """
    Insert only columns that actually exist in the database table.
    This prevents many schema-mismatch errors.
    """
    columns = table_columns(table_name)

    if not columns:
        return None

    valid = {
        key: value
        for key, value in data.items()
        if key in columns
    }

    if not valid:
        return None

    names = list(valid.keys())
    placeholders = ", ".join(["%s"] * len(names))

    query = f"""
        INSERT INTO `{table_name}`
        (`{"`, `".join(names)}`)
        VALUES ({placeholders})
    """

    return execute_query(
        query,
        tuple(valid[name] for name in names),
        return_lastrowid=True,
    )


# ============================================================
# USER / CUSTOMER HELPERS
# ============================================================

def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return fetch_one(
        """
        SELECT *
        FROM users
        WHERE id = %s
        LIMIT 1
        """,
        (user_id,),
    )


def get_current_customer():
    """
    The database uses customers.id for consultations/orders.
    users.id is linked to customers.user_id.
    """
    user_id = session.get("user_id")

    if not user_id:
        return None

    return fetch_one(
        """
        SELECT *
        FROM customers
        WHERE user_id = %s
        LIMIT 1
        """,
        (user_id,),
    )


def ensure_customer_for_logged_in_user():
    """
    Automatically creates the customer profile if the logged-in user
    does not yet have a row in customers.
    """
    user = get_current_user()

    if not user:
        return None

    customer = get_current_customer()

    if customer:
        return customer

    customer_id = dynamic_insert(
        "customers",
        {
            "user_id": user.get("id"),
            "full_name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "address": user.get("address", ""),
        },
    )

    if not customer_id:
        return None

    return fetch_one(
        """
        SELECT *
        FROM customers
        WHERE id = %s
        LIMIT 1
        """,
        (customer_id,),
    )


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):

        if not session.get("user_id"):
            flash(
                "Please login to continue.",
                "warning",
            )

            return redirect(
                url_for(
                    "login",
                    next=request.path,
                )
            )

        return view(*args, **kwargs)

    return wrapper


# ============================================================
# CART
# ============================================================
#
# The existing store.html contains static products and sends:
#
#   url_for('cart') + ?product=...&price=...
#
# Therefore the cart route below supports BOTH:
#
# 1. Database products using /cart/add/<product_id>
# 2. Existing static store.html using /cart?product=...&price=...
#
# This means you do NOT have to rewrite all 20 product cards.
# ============================================================

def get_cart():
    cart = session.get("cart", {})

    if not isinstance(cart, dict):
        cart = {}

    cleaned = {}

    for key, value in cart.items():

        try:
            quantity = int(value.get("quantity", 1))

            if quantity < 1:
                continue

            cleaned[str(key)] = {
                "product_id": value.get("product_id"),
                "name": value.get("name", "Product"),
                "price": str(value.get("price", "0")),
                "image": value.get("image", ""),
                "quantity": quantity,
            }

        except (ValueError, TypeError, AttributeError):
            continue

    return cleaned


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_count():
    return sum(
        int(item.get("quantity", 0))
        for item in get_cart().values()
    )


def get_cart_items():
    """
    Return cart items and total.

    Database products are refreshed from MySQL.
    Static products from the existing store.html are also supported.
    """
    cart = get_cart()

    items = []
    total = Decimal("0.00")

    for key, cart_item in cart.items():

        product_id = cart_item.get("product_id")

        # ----------------------------------------------------
        # DATABASE PRODUCT
        # ----------------------------------------------------
        if product_id:

            product = fetch_one(
                """
                SELECT
                    id,
                    name,
                    description,
                    category,
                    price,
                    stock_quantity,
                    image
                FROM products
                WHERE id = %s
                  AND is_active = 1
                LIMIT 1
                """,
                (product_id,),
            )

            if not product:
                continue

            name = product["name"]
            price = Decimal(str(product["price"] or 0))
            image = product.get("image") or ""
            quantity = int(cart_item["quantity"])

            stock = int(
                product.get("stock_quantity") or 0
            )

            if stock > 0:
                quantity = min(quantity, stock)

        # ----------------------------------------------------
        # STATIC PRODUCT FROM STORE.HTML
        # ----------------------------------------------------
        else:

            name = cart_item.get("name", "Product")

            try:
                price = Decimal(
                    str(cart_item.get("price", "0"))
                )
            except InvalidOperation:
                price = Decimal("0.00")

            image = cart_item.get("image", "")
            quantity = int(
                cart_item.get("quantity", 1)
            )

        if quantity <= 0:
            continue

        subtotal = price * quantity

        item = {
            "key": key,
            "id": product_id,
            "product_id": product_id,
            "name": name,
            "price": price,
            "image": image,
            "quantity": quantity,
            "cart_quantity": quantity,
            "subtotal": subtotal,
        }

        items.append(item)
        total += subtotal

    return items, total


# ============================================================
# GLOBAL TEMPLATE VARIABLES
# ============================================================

@app.context_processor
def inject_globals():

    user = get_current_user()

    return {
        "current_user": user,
        "logged_in_user": user,
        "cart_count": cart_count(),
        "user_name": (
            user.get("name", "")
            if user
            else ""
        ),
    }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    services_list = fetch_all(
        """
        SELECT
            id,
            name,
            description,
            price_from AS price,
            image
        FROM services
        WHERE is_active = 1
        ORDER BY id
        """
    )

    featured_products = fetch_all(
        """
        SELECT
            id,
            name,
            description,
            category,
            price,
            stock_quantity,
            image
        FROM products
        WHERE is_active = 1
        ORDER BY id DESC
        LIMIT 8
        """
    )

    return render_template(
        "index.html",
        services=services_list,
        featured_products=featured_products,
    )


# Compatibility for templates using url_for('home')
@app.route("/home")
def index():
    return redirect(url_for("index"))


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
def about():
    return render_template("about.html")


# ============================================================
# SERVICES
# ============================================================

@app.route("/services")
def services():

    services_list = fetch_all(
        """
        SELECT
            id,
            name,
            description,
            price_from AS price,
            price_from,
            image
        FROM services
        WHERE is_active = 1
        ORDER BY id
        """
    )

    return render_template(
        "services.html",
        services=services_list,
    )


# ============================================================
# DESIGNERS
# ============================================================

@app.route("/designer")
@app.route("/designers")
def designer():

    designers = fetch_all(
        """
        SELECT *
        FROM designers
        WHERE status = 'active'
        ORDER BY id
        """
    )

    return render_template(
        "designer.html",
        designers=designers,
    )


# ============================================================
# GALLERY
# ============================================================

@app.route("/gallery")
def gallery():

    gallery_items = fetch_all(
        """
        SELECT *
        FROM gallery
        ORDER BY id DESC
        """
    )

    return render_template(
        "gallery.html",
        gallery=gallery_items,
        gallery_items=gallery_items,
    )


# Old endpoint used by some versions of gallery.html
@app.route("/appointment")
def appointment():

    service_id = request.args.get("service_id")

    if service_id:
        return redirect(
            url_for(
                "consultation",
                service_id=service_id,
            )
        )

    return redirect(url_for("consultation"))


# ============================================================
# CONSULTATION
# ============================================================

@app.route("/consultation", methods=["GET", "POST"])
def consultation():

    # IMPORTANT:
    # The services table has price_from, NOT price.
    services_list = fetch_all(
        """
        SELECT
            id,
            name,
            description,
            price_from AS price,
            price_from,
            image
        FROM services
        WHERE is_active = 1
        ORDER BY id
        """
    )

    selected_service_id = request.args.get(
        "service_id",
        type=int,
    )

    if request.method == "POST":

        # ----------------------------------------------------
        # Correct field name from consultation.html:
        # name="service_id"
        # ----------------------------------------------------
        raw_service_id = request.form.get(
            "service_id",
            "",
        ).strip()

        print("CONSULTATION service_id received:", repr(raw_service_id))
        print("CONSULTATION form:", dict(request.form))

        try:
            service_id = int(raw_service_id)
        except (ValueError, TypeError):
            service_id = None

        # ----------------------------------------------------
        # Validate selected service
        # ----------------------------------------------------
        if not service_id:
            flash(
                "Please select a service.",
                "error",
            )

            return render_template(
                "consultation.html",
                services=services_list,
                selected_service_id=None,
            )

        service = fetch_one(
            """
            SELECT
                id,
                name,
                description,
                price_from
            FROM services
            WHERE id = %s
              AND is_active = 1
            LIMIT 1
            """,
            (service_id,),
        )

        if not service:
            flash(
                "Please select a valid service.",
                "error",
            )

            return render_template(
                "consultation.html",
                services=services_list,
                selected_service_id=service_id,
            )

        name = request.form.get(
            "name",
            "",
        ).strip()

        email = request.form.get(
            "email",
            "",
        ).strip()

        phone = request.form.get(
            "phone",
            "",
        ).strip()

        property_type = request.form.get(
            "property_type",
            "",
        ).strip()

        budget = request.form.get(
            "budget",
            "",
        ).strip()

        preferred_date = request.form.get(
            "preferred_date",
            "",
        ).strip()

        preferred_time = request.form.get(
            "preferred_time",
            "",
        ).strip()

        message = request.form.get(
            "message",
            "",
        ).strip()

        if not name:
            flash(
                "Please enter your name.",
                "error",
            )
            return render_template(
                "consultation.html",
                services=services_list,
                selected_service_id=service_id,
            )

        if not email:
            flash(
                "Please enter your email.",
                "error",
            )
            return render_template(
                "consultation.html",
                services=services_list,
                selected_service_id=service_id,
            )

        if not message:
            flash(
                "Please enter your project details.",
                "error",
            )
            return render_template(
                "consultation.html",
                services=services_list,
                selected_service_id=service_id,
            )

        # ----------------------------------------------------
        # The database requires consultations.customer_id.
        # Therefore the user must be logged in.
        # ----------------------------------------------------
        if not session.get("user_id"):

            flash(
                "Please login before submitting the consultation.",
                "warning",
            )

            session["pending_consultation"] = {
                "name": name,
                "email": email,
                "phone": phone,
                "service_id": service_id,
                "property_type": property_type,
                "budget": budget,
                "preferred_date": preferred_date,
                "preferred_time": preferred_time,
                "message": message,
            }

            return redirect(
                url_for(
                    "login",
                    next=url_for(
                        "consultation",
                        service_id=service_id,
                    ),
                )
            )

        customer = ensure_customer_for_logged_in_user()

        if not customer:
            flash(
                "Customer profile could not be created. Please check your users/customers tables.",
                "error",
            )

            return render_template(
                "consultation.html",
                services=services_list,
                selected_service_id=service_id,
            )

        # ----------------------------------------------------
        # ACTUAL DATABASE STRUCTURE:
        #
        # consultations:
        # id
        # customer_id
        # service_id
        # message
        # preferred_date
        # status
        # created_at
        #
        # property_type, budget, preferred_time are not columns
        # in the supplied SQL, so they are safely combined into
        # the message instead of causing SQL errors.
        # ----------------------------------------------------
        complete_message = message

        extra_details = []

        if property_type:
            extra_details.append(
                f"Property Type: {property_type}"
            )

        if budget:
            extra_details.append(
                f"Estimated Budget: {budget}"
            )

        if preferred_time:
            extra_details.append(
                f"Preferred Time: {preferred_time}"
            )

        if extra_details:
            complete_message = (
                message
                + "\n\n"
                + "\n".join(extra_details)
            )

        consultation_id = dynamic_insert(
            "consultations",
            {
                "customer_id": customer["id"],
                "service_id": service_id,
                "message": complete_message,
                "preferred_date": (
                    preferred_date
                    if preferred_date
                    else None
                ),
                "status": "pending",
            },
        )

        if consultation_id:

            # Clear any old pending form.
            session.pop(
                "pending_consultation",
                None,
            )

            flash(
                "Consultation request submitted successfully!",
                "success",
            )

            return redirect(
                url_for(
                    "quotation",
                    consultation_id=consultation_id,
                    service_id=service_id,
                )
            )

        flash(
            "Consultation could not be saved. Please check the database.",
            "error",
        )

    # --------------------------------------------------------
    # If user was redirected from login, restore old form
    # values when possible.
    # --------------------------------------------------------
    pending = session.get(
        "pending_consultation",
        {},
    )

    if pending:
        selected_service_id = (
            pending.get("service_id")
            or selected_service_id
        )

    return render_template(
        "consultation.html",
        services=services_list,
        selected_service_id=selected_service_id,
        pending_consultation=pending,
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            request.form.get("username", ""),
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error",
            )
            return render_template("login.html")

        user = fetch_one(
            """
            SELECT *
            FROM users
            WHERE email = %s
              AND status = 'active'
            LIMIT 1
            """,
            (email,),
        )

        if not user:
            flash(
                "Invalid email or password.",
                "error",
            )
            return render_template("login.html")

        stored_hash = user.get(
            "password_hash"
        )

        password_valid = False

        if stored_hash:

            try:
                password_valid = check_password_hash(
                    stored_hash,
                    password,
                )
            except Exception:
                password_valid = False

        if not password_valid:
            flash(
                "Invalid email or password.",
                "error",
            )
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["role"] = user.get(
            "role",
            "customer",
        )

        # ----------------------------------------------------
        # Restore consultation after login.
        # ----------------------------------------------------
        pending = session.get(
            "pending_consultation"
        )

        if pending:
            session.pop(
                "pending_consultation",
                None,
            )

            # Store it temporarily again so the consultation
            # page can display/submit it.
            session["pending_consultation"] = pending

            flash(
                "Login successful. Please submit your consultation.",
                "success",
            )

            return redirect(
                url_for(
                    "consultation",
                    service_id=pending.get(
                        "service_id"
                    ),
                )
            )

        flash(
            "Login successful!",
            "success",
        )

        next_page = request.args.get("next")

        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        return redirect(
            url_for("customer_dashboard")
        )

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            request.form.get("full_name", ""),
        ).strip()

        email = request.form.get(
            "email",
            "",
        ).strip()

        phone = request.form.get(
            "phone",
            "",
        ).strip()

        role = request.form.get(
            "role",
            "customer",
        ).strip().lower()

        company_name = request.form.get(
            "company_name",
            "",
        ).strip()

        specialization = request.form.get(
            "specialization",
            "",
        ).strip()

        address = request.form.get(
            "address",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            request.form.get("confirm", ""),
        )

        if not name or not email or not password:
            flash(
                "Please fill all required fields.",
                "error",
            )
            return render_template("register.html")

        if role not in {"customer", "designer", "contractor", "supplier"}:
            flash(
                "Choose a customer, designer, contractor, or supplier account.",
                "error",
            )
            return render_template("register.html")

        if role in {"supplier", "contractor"} and not company_name:
            flash(
                "Please enter your company name for this account type.",
                "error",
            )
            return render_template("register.html")

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "error",
            )
            return render_template("register.html")

        existing = fetch_one(
            """
            SELECT id
            FROM users
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )

        if existing:
            flash(
                "An account with this email already exists.",
                "error",
            )
            return redirect(url_for("login"))

        password_hash = generate_password_hash(
            password
        )

        if role in {"supplier", "contractor", "designer"}:
            connection = None
            cursor = None

            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO users
                        (name, email, phone, address, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    """,
                    (name, email, phone, address, password_hash, role),
                )
                user_id = cursor.lastrowid
                if role == "supplier":
                    cursor.execute(
                        """
                        INSERT INTO suppliers
                            (user_id, company_name, contact_person, phone, email, address, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'active')
                        """,
                        (
                            user_id,
                            company_name,
                            name,
                            phone,
                            email,
                            address,
                        ),
                    )
                elif role == "contractor":
                    cursor.execute(
                        """
                        INSERT INTO contractors
                            (user_id, company_name, contact_person, phone, email, specialization, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'active')
                        """,
                        (
                            user_id,
                            company_name,
                            name,
                            phone,
                            email,
                            specialization or None,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO designers
                            (user_id, full_name, specialization, status)
                        VALUES (%s, %s, %s, 'active')
                        """,
                        (user_id, name, specialization or None),
                    )
                connection.commit()
            except Error as error:
                if connection:
                    connection.rollback()
                print(f"{role.upper()} REGISTRATION ERROR:", error)
                flash(
                    "Registration failed. Please try again or contact an administrator.",
                    "error",
                )
                return render_template("register.html")
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
        else:
            user_id = dynamic_insert(
                "users",
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "password_hash": password_hash,
                    "role": "customer",
                    "status": "active",
                },
            )

        if not user_id:
            flash(
                "Registration failed. Please check the users table.",
                "error",
            )
            return render_template("register.html")

        if role == "customer":
            dynamic_insert(
                "customers",
                {
                    "user_id": user_id,
                    "full_name": name,
                    "email": email,
                    "phone": phone,
                    "address": address,
                },
            )

        flash(
            (
                f"{role.title()} registration successful. Sign in using your email and password."
                if role != "customer"
                else "Registration successful. Please login."
            ),
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template("register.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success",
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# STORE
# ============================================================

@app.route("/store")
def store():

    search = request.args.get(
        "search",
        "",
    ).strip()

    category = request.args.get(
        "category",
        "",
    ).strip()

    query = """
        SELECT
            id,
            name,
            description,
            category,
            price,
            stock_quantity,
            image
        FROM products
        WHERE is_active = 1
    """

    params = []

    if search:

        query += """
            AND (
                name LIKE %s
                OR description LIKE %s
                OR category LIKE %s
            )
        """

        keyword = f"%{search}%"

        params.extend([
            keyword,
            keyword,
            keyword,
        ])

    if category:

        query += """
            AND category = %s
        """

        params.append(category)

    query += """
        ORDER BY id DESC
    """

    products = fetch_all(
        query,
        tuple(params),
    )

    categories = fetch_all(
        """
        SELECT DISTINCT category
        FROM products
        WHERE is_active = 1
          AND category IS NOT NULL
          AND category <> ''
        ORDER BY category
        """
    )

    return render_template(
        "store.html",
        products=products,
        categories=categories,
        search=search,
        selected_category=category,
    )


# ============================================================
# ADD DATABASE PRODUCT TO CART
# ============================================================

@app.route(
    "/cart/add/<int:product_id>",
    methods=["POST", "GET"],
)
def add_to_cart(product_id):

    product = fetch_one(
        """
        SELECT
            id,
            name,
            description,
            category,
            price,
            stock_quantity,
            image
        FROM products
        WHERE id = %s
          AND is_active = 1
        LIMIT 1
        """,
        (product_id,),
    )

    if not product:
        flash(
            "Product not found.",
            "error",
        )
        return redirect(url_for("store"))

    try:
        quantity = int(
            request.values.get(
                "quantity",
                1,
            )
        )
    except (ValueError, TypeError):
        quantity = 1

    quantity = max(quantity, 1)

    stock = int(
        product.get("stock_quantity") or 0
    )

    if stock <= 0:
        flash(
            "This product is out of stock.",
            "warning",
        )
        return redirect(url_for("store"))

    cart = get_cart()

    key = f"db_{product_id}"

    old_quantity = int(
        cart.get(
            key,
            {},
        ).get(
            "quantity",
            0,
        )
    )

    new_quantity = old_quantity + quantity

    if new_quantity > stock:
        new_quantity = stock

        flash(
            f"Only {stock} item(s) are available.",
            "warning",
        )

    cart[key] = {
        "product_id": product_id,
        "name": product["name"],
        "price": str(product["price"]),
        "image": product.get("image") or "",
        "quantity": new_quantity,
    }

    save_cart(cart)

    flash(
        f"{product['name']} added to cart.",
        "success",
    )

    return redirect(
        request.values.get(
            "next",
            url_for("cart"),
        )
    )


# ============================================================
# CART PAGE
# ============================================================

@app.route("/cart")
def cart():

    # --------------------------------------------------------
    # COMPATIBILITY WITH THE EXISTING store.html
    #
    # Existing buttons currently submit:
    # /cart?product=Modern%20Sofa&price=24999
    #
    # So we convert those values into a session cart item.
    # --------------------------------------------------------
    legacy_product = request.args.get(
        "product",
        "",
    ).strip()

    legacy_price = request.args.get(
        "price",
        "",
    ).strip()

    if legacy_product:

        try:
            price = Decimal(
                legacy_price or "0"
            )
        except InvalidOperation:
            price = Decimal("0")

        cart = get_cart()

        key = "static_" + legacy_product.lower().replace(
            " ",
            "_",
        )

        if key in cart:

            cart[key]["quantity"] = (
                int(cart[key]["quantity"]) + 1
            )

        else:

            cart[key] = {
                "product_id": None,
                "name": legacy_product,
                "price": str(price),
                "image": "",
                "quantity": 1,
            }

        save_cart(cart)

        flash(
            f"{legacy_product} added to cart.",
            "success",
        )

    items, total = get_cart_items()

    return render_template(
        "cart.html",
        cart_items=items,
        items=items,
        total=total,
        cart_total=total,
    )


# ============================================================
# UPDATE CART
# ============================================================

@app.route(
    "/cart/update/<path:item_key>",
    methods=["POST"],
)
def update_cart(item_key):

    cart = get_cart()

    if item_key not in cart:
        flash(
            "Product is not in the cart.",
            "error",
        )
        return redirect(url_for("cart"))

    try:
        quantity = int(
            request.form.get(
                "quantity",
                1,
            )
        )
    except (ValueError, TypeError):
        quantity = 1

    if quantity <= 0:

        cart.pop(item_key, None)

    else:

        product_id = cart[item_key].get(
            "product_id"
        )

        if product_id:

            product = fetch_one(
                """
                SELECT stock_quantity
                FROM products
                WHERE id = %s
                LIMIT 1
                """,
                (product_id,),
            )

            if product:

                stock = int(
                    product.get(
                        "stock_quantity"
                    ) or 0
                )

                if stock > 0:
                    quantity = min(
                        quantity,
                        stock,
                    )

        cart[item_key]["quantity"] = quantity

    save_cart(cart)

    flash(
        "Cart updated.",
        "success",
    )

    return redirect(
        url_for("cart")
    )


# ============================================================
# REMOVE CART ITEM
# ============================================================

@app.route(
    "/cart/remove/<path:item_key>",
    methods=["POST", "GET"],
)
def remove_from_cart(item_key):

    cart = get_cart()

    if item_key in cart:
        cart.pop(item_key)
        save_cart(cart)

        flash(
            "Product removed from cart.",
            "success",
        )

    return redirect(
        url_for("cart")
    )


# ============================================================
# CLEAR CART
# ============================================================

@app.route(
    "/cart/clear",
    methods=["POST", "GET"],
)
def clear_cart():

    save_cart({})

    flash(
        "Cart cleared.",
        "success",
    )

    return redirect(
        url_for("cart")
    )


# ============================================================
# CART COUNT API
# ============================================================

@app.route("/cart/count")
def cart_count_api():

    return jsonify({
        "count": cart_count()
    })


# ============================================================
# PAYMENT PAGE
# ============================================================
#
# GET is intentionally NOT login_required.
# This ensures the payment page can open even before login.
#
# Final order creation requires a logged-in customer because
# the database orders table requires customer_id.
# ============================================================

@app.route(
    "/payment",
    methods=["GET", "POST"],
)
def payment():

    items, total = get_cart_items()

    # --------------------------------------------------------
    # SUCCESS PAGE
    # --------------------------------------------------------
    if request.method == "POST":

        if not items:
            flash(
                "Your cart is empty.",
                "warning",
            )
            return redirect(
                url_for("store")
            )

        # ----------------------------------------------------
        # Database orders require customer_id.
        # ----------------------------------------------------
        if not session.get("user_id"):

            flash(
                "Please login before completing payment.",
                "warning",
            )

            session["payment_return"] = True

            return redirect(
                url_for(
                    "login",
                    next=url_for("payment"),
                )
            )

        customer = ensure_customer_for_logged_in_user()

        if not customer:

            flash(
                "Customer profile could not be found.",
                "error",
            )

            return redirect(
                url_for("customer_dashboard")
            )

        user = get_current_user()

        customer_name = request.form.get(
            "customer_name",
            request.form.get(
                "name",
                customer.get(
                    "full_name",
                    user.get("name", "")
                    if user
                    else "",
                ),
            ),
        ).strip()

        email = request.form.get(
            "email",
            customer.get(
                "email",
                user.get("email", "")
                if user
                else "",
            ),
        ).strip()

        phone = request.form.get(
            "phone",
            customer.get(
                "phone",
                "",
            ),
        ).strip()

        address = request.form.get(
            "address",
            customer.get(
                "address",
                "",
            ),
        ).strip()

        payment_method = request.form.get(
            "payment_method",
            "cash",
        ).strip().lower()

        # Normalize payment method to actual SQL ENUM:
        # cash / upi / card / net_banking
        if "upi" in payment_method:
            payment_method = "upi"

        elif "card" in payment_method:
            payment_method = "card"

        elif (
            "net" in payment_method
            or "bank" in payment_method
        ):
            payment_method = "net_banking"

        else:
            payment_method = "cash"

        if not customer_name:
            flash(
                "Please enter your name.",
                "error",
            )
            return redirect(url_for("payment"))

        if not email:
            flash(
                "Please enter your email.",
                "error",
            )
            return redirect(url_for("payment"))

        if not address:
            flash(
                "Please enter your address.",
                "error",
            )
            return redirect(url_for("payment"))

        # ----------------------------------------------------
        # Create order using ACTUAL database structure:
        #
        # orders:
        # customer_id
        # total_amount
        # shipping_address
        # status
        # ----------------------------------------------------
        order_id = dynamic_insert(
            "orders",
            {
                "customer_id": customer["id"],
                "total_amount": total,
                "shipping_address": address,
                "status": "placed",
            },
        )

        if not order_id:

            flash(
                "Order could not be created. Check the orders table.",
                "error",
            )

            return redirect(
                url_for("cart")
            )

        # ----------------------------------------------------
        # Save order items.
        #
        # Actual table:
        # order_id
        # product_id
        # quantity
        # unit_price
        # ----------------------------------------------------
        order_items_saved = True

        for item in items:

            item_id = dynamic_insert(
                "order_items",
                {
                    "order_id": order_id,
                    "product_id": item.get(
                        "product_id"
                    ),
                    "quantity": item["quantity"],
                    "unit_price": item["price"],
                },
            )

            if item_id is None:
                order_items_saved = False

            # Reduce stock only for real database products.
            if item.get("product_id"):

                execute_query(
                    """
                    UPDATE products
                    SET stock_quantity =
                        GREATEST(
                            stock_quantity - %s,
                            0
                        )
                    WHERE id = %s
                    """,
                    (
                        item["quantity"],
                        item["product_id"],
                    ),
                )

        # ----------------------------------------------------
        # Save payment using actual payments table.
        # ----------------------------------------------------
        transaction_id = (
            "TXN-"
            + datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )
            + "-"
            + uuid.uuid4().hex[:6].upper()
        )

        dynamic_insert(
            "payments",
            {
                "order_id": order_id,
                "amount": total,
                "payment_method": payment_method,
                "transaction_id": transaction_id,
                "status": "paid",
                "paid_at": datetime.now(),
            },
        )

        save_cart({})

        flash(
            "Order and payment completed successfully!",
            "success",
        )

        return render_template(
            "payment.html",
            cart_items=[],
            items=[],
            total=Decimal("0.00"),
            cart_total=Decimal("0.00"),
            payment_success=True,
            order_id=order_id,
            transaction_id=transaction_id,
        )

    # --------------------------------------------------------
    # GET PAYMENT PAGE
    # --------------------------------------------------------
    return render_template(
        "payment.html",
        cart_items=items,
        items=items,
        total=total,
        cart_total=total,
        payment_success=False,
    )


# ============================================================
# CUSTOMER DASHBOARD
# ============================================================

@app.route(
    "/customer-dashboard"
)
@app.route(
    "/customer_dashboard"
)
@app.route(
    "/dashboard"
)
@login_required
def customer_dashboard():

    user = get_current_user()
    customer = ensure_customer_for_logged_in_user()

    consultations = []
    quotations = []
    projects = []
    orders = []

    if customer:

        consultations = fetch_all(
            """
            SELECT
                c.*,
                s.name AS service_name
            FROM consultations c
            LEFT JOIN services s
                ON c.service_id = s.id
            WHERE c.customer_id = %s
            ORDER BY c.id DESC
            """,
            (customer["id"],),
        )

        quotations = fetch_all(
            """
            SELECT *
            FROM quotations
            WHERE customer_id = %s
            ORDER BY id DESC
            """,
            (customer["id"],),
        )

        projects = fetch_all(
            """
            SELECT *
            FROM projects
            WHERE customer_id = %s
            ORDER BY id DESC
            """,
            (customer["id"],),
        )

        orders = fetch_all(
            """
            SELECT *
            FROM orders
            WHERE customer_id = %s
            ORDER BY id DESC
            """,
            (customer["id"],),
        )

    return render_template(
        "customer_dashboard.html",
        user=user,
        customer=customer,
        consultations=consultations,
        quotations=quotations,
        projects=projects,
        orders=orders,
    )


# ============================================================
# QUOTATION
# ============================================================
#
# This route is compatible with the supplied quotations table.
# The table uses customer_id, amount, final_amount, description,
# quotation_number, etc.
# ============================================================

@app.route(
    "/quotation",
    methods=["GET", "POST"],
)
@login_required
def quotation():

    services_list = fetch_all(
        """
        SELECT
            id,
            name,
            description,
            price_from AS price,
            price_from,
            image
        FROM services
        WHERE is_active = 1
        ORDER BY id
        """
    )

    customer = ensure_customer_for_logged_in_user()

    if not customer:

        flash(
            "Customer profile not found.",
            "error",
        )

        return redirect(
            url_for("customer_dashboard")
        )

    consultation_id = request.args.get(
        "consultation_id",
        type=int,
    )

    selected_service_id = request.args.get(
        "service_id",
        type=int,
    )

    if request.method == "POST":

        service_id = request.form.get(
            "service_id",
            type=int,
        )

        if not service_id:

            flash(
                "Please select a service.",
                "error",
            )

            return render_template(
                "quotation.html",
                services=services_list,
                selected_service_id=None,
                consultation_id=consultation_id,
            )

        service = fetch_one(
            """
            SELECT
                id,
                name,
                price_from
            FROM services
            WHERE id = %s
              AND is_active = 1
            LIMIT 1
            """,
            (service_id,),
        )

        if not service:

            flash(
                "Please select a valid service.",
                "error",
            )

            return render_template(
                "quotation.html",
                services=services_list,
                selected_service_id=service_id,
                consultation_id=consultation_id,
            )

        details = request.form.get(
            "project_details",
            request.form.get(
                "requirements",
                "",
            ),
        ).strip()

        budget_raw = request.form.get(
            "estimated_budget",
            "",
        ).strip()

        try:
            amount = Decimal(
                budget_raw
            ) if budget_raw else Decimal(
                str(service["price_from"] or 0)
            )
        except InvalidOperation:
            amount = Decimal(
                str(service["price_from"] or 0)
            )

        if amount < 0:
            amount = Decimal("0.00")

        quotation_number = (
            "QTN-"
            + datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )
            + "-"
            + uuid.uuid4().hex[:4].upper()
        )

        quotation_id = dynamic_insert(
            "quotations",
            {
                "project_id": None,
                "customer_id": customer["id"],
                "quotation_number": quotation_number,
                "amount": amount,
                "tax_amount": Decimal("0.00"),
                "discount_amount": Decimal("0.00"),
                "final_amount": amount,
                "description": (
                    f"Service: {service['name']}\n"
                    f"{details}"
                ),
                "valid_until": None,
                "status": "draft",
            },
        )

        if quotation_id:

            flash(
                "Quotation request created successfully!",
                "success",
            )

            return redirect(
                url_for(
                    "project_tracking"
                )
            )

        flash(
            "Quotation could not be saved.",
            "error",
        )

    return render_template(
        "quotation.html",
        services=services_list,
        selected_service_id=selected_service_id,
        consultation_id=consultation_id,
    )


# ============================================================
# PROJECT TRACKING
# ============================================================

@app.route(
    "/project-tracking"
)
@app.route(
    "/project_tracking"
)
@login_required
def project_tracking():

    customer = ensure_customer_for_logged_in_user()

    projects = []

    if customer:

        projects = fetch_all(
            """
            SELECT *
            FROM projects
            WHERE customer_id = %s
            ORDER BY id DESC
            """,
            (customer["id"],),
        )

        # Attach latest project update.
        for project in projects:

            updates = fetch_all(
                """
                SELECT *
                FROM project_updates
                WHERE project_id = %s
                ORDER BY id DESC
                """,
                (project["id"],),
            )

            project["updates"] = updates

    return render_template(
        "project_tracking.html",
        projects=projects,
    )


# ============================================================
# DATABASE TEST
# ============================================================

@app.route("/test-db")
def test_db():

    try:

        connection = get_db_connection()

        if connection.is_connected():

            connection.close()

            return """
                <h1>Database Connected Successfully</h1>
                <p>Flask is connected to MySQL/MariaDB.</p>
                <p>Database: interior_design</p>
                <p><a href="/">Go to Home</a></p>
            """

    except Error as e:

        return f"""
            <h1>Database Connection Failed</h1>
            <p>{e}</p>
            <p><a href="/">Go to Home</a></p>
        """, 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    try:
        return render_template(
            "404.html"
        ), 404

    except Exception:

        return """
            <h1>404 - Page Not Found</h1>
            <p>The requested page does not exist.</p>
            <a href="/">Go to Home</a>
        """, 404


@app.errorhandler(500)
def internal_server_error(error):

    try:
        return render_template(
            "500.html"
        ), 500

    except Exception:

        return """
            <h1>500 - Internal Server Error</h1>
            <p>Something went wrong.</p>
            <a href="/">Go to Home</a>
        """, 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("INTERIOR DESIGN MANAGEMENT SYSTEM")
    print("=" * 60)
    print("Database:", DB_CONFIG.get("database"))
    print("Starting Flask...")
    print("Open: http://127.0.0.1:5000")
    print("=" * 60)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
