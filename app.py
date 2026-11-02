from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal, InvalidOperation
from functools import wraps
from datetime import datetime
import base64
import hashlib
import hmac
import json
import mysql.connector
from mysql.connector import Error
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ============================================================
# INTERIOR DESIGN MANAGEMENT SYSTEM
# Flask + MySQL / XAMPP
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "interior-design-system-secret-key-change-this"
)

RAZORPAY_KEY_ID = "rzp_test_Tn0ueBHkOSSMYr"
RAZORPAY_KEY_SECRET ="RFgtCyWKdYKakOLbiutpZGiZ"
RAZORPAY_API_URL = "https://api.razorpay.com"

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
        "suppliers",
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


def deduct_product_stock(product_id, quantity, customer_order_id):
    """Deduct sold stock and queue a supplier order when it reaches zero."""
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT stock_quantity, supplier_id
            FROM products
            WHERE id = %s
            FOR UPDATE
            """,
            (product_id,),
        )
        product = cursor.fetchone()

        if not product:
            connection.rollback()
            return "failed"

        stock_before = int(product["stock_quantity"] or 0)
        stock_after = max(stock_before - quantity, 0)
        cursor.execute(
            """
            UPDATE products
            SET stock_quantity = %s
            WHERE id = %s
            """,
            (stock_after, product_id),
        )

        result = "updated"
        if stock_before > 0 and stock_after == 0:
            if product["supplier_id"]:
                cursor.execute(
                    """
                    INSERT INTO supplier_orders
                        (supplier_id, product_id, customer_order_id, quantity)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        product["supplier_id"],
                        product_id,
                        customer_order_id,
                        quantity,
                    ),
                )
                result = "requested"
            else:
                result = "no_supplier"

        connection.commit()
        return result

    except Error as error:
        if connection:
            connection.rollback()
        print("PRODUCT STOCK / SUPPLIER ORDER ERROR:", error)
        return "failed"

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


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


@app.before_request
def require_site_authentication():
    public_endpoints = {
        "index",
        "home",
        "about",
        "services",
        "designer",
        "gallery",
        "login",
        "register",
        "admin_login",
        "designer_login",
        "contractor_login",
        "supplier_login",
        "static",
    }

    if request.endpoint in public_endpoints:
        return None

    if not session.get("user_id"):
        return redirect(
            url_for(
                "login",
                next=request.full_path,
            )
        )

    current_user = get_current_user()
    if not current_user or current_user.get("status") != "active":
        session.clear()
        flash(
            "Your account is inactive or no longer exists. Please log in again.",
            "warning",
        )
        return redirect(url_for("login"))

    return None


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
def home():
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

        next_page = request.args.get("next", "")

        if (
            next_page.startswith("/")
            and not next_page.startswith("//")
            and "\\" not in next_page
        ):
            return redirect(next_page)

        dashboard_endpoint = {
            "admin": "admin_dashboard",
            "designer": "designer_dashboard",
            "contractor": "contractor_dashboard",
            "supplier": "supplier_dashboard",
        }.get(session.get("role"), "customer_dashboard")
        return redirect(url_for(dashboard_endpoint))

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

        address = request.form.get(
            "address",
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


@app.route("/store/product/<int:product_id>")
def store_product(product_id):
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
        flash("Product not found.", "error")
        return redirect(url_for("store"))

    return render_template(
        "store_product.html",
        product=product,
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

    next_url = request.values.get("next", "")
    if (
        next_url.startswith("/")
        and not next_url.startswith("//")
        and "\\" not in next_url
    ):
        return redirect(next_url)

    return redirect(url_for("cart"))


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

    current_quantity = int(cart[item_key]["quantity"])
    action = request.form.get("action")

    if action == "increase":
        quantity = current_quantity + 1
    elif action == "decrease":
        quantity = current_quantity - 1
    else:
        try:
            quantity = int(
                request.form.get(
                    "quantity",
                    current_quantity,
                )
            )
        except (ValueError, TypeError):
            quantity = current_quantity

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
                    if quantity > stock:
                        quantity = stock
                        flash(
                            f"Only {stock} item(s) are available.",
                            "warning",
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
# Razorpay Test Mode orders are created server-side and a payment is
# recorded only after verifying the Razorpay signature and captured status.
# ============================================================

def razorpay_api_request(path, method="GET", payload=None):
    credentials = base64.b64encode(
        f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")
    ).decode("ascii")
    body = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )
    api_request = Request(
        f"{RAZORPAY_API_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method=method,
    )

    with urlopen(api_request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not isinstance(result, dict):
        raise ValueError("Unexpected Razorpay API response.")

    return result


def razorpay_test_mode_configured():
    return (
        RAZORPAY_KEY_ID.startswith("rzp_test_")
        and bool(RAZORPAY_KEY_SECRET)
    )


@app.route("/payment/razorpay/order", methods=["POST"])
def create_razorpay_order():
    if session.get("role") != "customer":
        return jsonify({"error": "Customer login is required."}), 403

    if not request.is_json:
        return jsonify({"error": "Invalid order request."}), 415

    if not razorpay_test_mode_configured():
        return jsonify({
            "error": "Razorpay Test Mode is not configured. Set a Test Key ID (rzp_test_...) and RAZORPAY_KEY_SECRET.",
        }), 503

    items, total = get_cart_items()
    if not items or total <= 0:
        return jsonify({"error": "Your cart is empty."}), 400

    amount_paise = int((total * 100).quantize(Decimal("1")))
    receipt = f"cart_{uuid.uuid4().hex[:24]}"

    try:
        gateway_order = razorpay_api_request(
            "/orders",
            method="POST",
            payload={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": {"user_id": str(session["user_id"])},
            },
        )
    except HTTPError as error:
        try:
            error_body = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_body = {}
        if not isinstance(error_body, dict):
            error_body = {}

        gateway_error = error_body.get("error", {})
        if not isinstance(gateway_error, dict):
            gateway_error = {}

        error_code = str(gateway_error.get("code", "HTTP_ERROR"))
        error_description = str(gateway_error.get(
            "description",
            "Razorpay rejected the order request.",
        ))
        print(
            "RAZORPAY ORDER ERROR:",
            error.code,
            error_code,
            error_description,
        )
        return jsonify({
            "error": (
                f"Razorpay rejected the order ({error_code}): "
                f"{error_description}"
            ),
        }), 502
    except URLError as error:
        print("RAZORPAY ORDER CONNECTION ERROR:", error.reason)
        return jsonify({
            "error": (
                "Could not connect to Razorpay. Check your internet "
                f"connection and try again. Details: {error.reason}"
            ),
        }), 502
    except (TimeoutError, OSError) as error:
        print("RAZORPAY ORDER CONNECTION ERROR:", error)
        return jsonify({
            "error": "The connection to Razorpay failed or timed out. Please retry.",
        }), 502
    except ValueError as error:
        print("RAZORPAY ORDER RESPONSE ERROR:", error)
        return jsonify({
            "error": "Razorpay returned an unreadable response. Please retry.",
        }), 502

    if (
        not gateway_order.get("id")
        or gateway_order.get("amount") != amount_paise
        or gateway_order.get("currency") != "INR"
    ):
        print("RAZORPAY ORDER ERROR: unexpected order response")
        return jsonify({
            "error": "Razorpay returned an invalid order. Please try again.",
        }), 502

    session["razorpay_order_id"] = gateway_order["id"]
    session["razorpay_order_amount"] = amount_paise

    return jsonify({
        "key": RAZORPAY_KEY_ID,
        "order_id": gateway_order["id"],
        "amount": amount_paise,
        "currency": "INR",
    })


@app.route(
    "/payment",
    methods=["GET", "POST"],
)
def payment():

    if session.get("role") != "customer":
        flash("Checkout is available to customer accounts only.", "error")
        return redirect(url_for("index"))

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

        if payment_method == "razorpay":
            razorpay_order_id = request.form.get(
                "razorpay_order_id",
                "",
            ).strip()
            razorpay_payment_id = request.form.get(
                "razorpay_payment_id",
                "",
            ).strip()
            razorpay_signature = request.form.get(
                "razorpay_signature",
                "",
            ).strip()
            expected_order_id = session.get("razorpay_order_id")
            expected_amount = session.get("razorpay_order_amount")
            signature_payload = (
                f"{razorpay_order_id}|{razorpay_payment_id}"
            )
            expected_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode("utf-8"),
                signature_payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest() if RAZORPAY_KEY_SECRET else ""

            if (
                not razorpay_test_mode_configured()
                or not razorpay_order_id
                or not razorpay_payment_id
                or not razorpay_signature
                or not razorpay_payment_id.startswith("pay_")
                or not razorpay_payment_id[4:].isalnum()
                or len(razorpay_signature) != 64
                or not all(
                    character in "0123456789abcdef"
                    for character in razorpay_signature.lower()
                )
                or razorpay_order_id != expected_order_id
                or expected_amount != int((total * 100).quantize(Decimal("1")))
                or not hmac.compare_digest(
                    expected_signature,
                    razorpay_signature,
                )
            ):
                flash(
                    "Razorpay payment verification failed. Please try again.",
                    "error",
                )
                return redirect(url_for("payment"))

            try:
                gateway_payment = razorpay_api_request(
                    f"/payments/{razorpay_payment_id}"
                )
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                print("RAZORPAY VERIFICATION ERROR:", error)
                flash(
                    "We could not verify your Razorpay payment. Please contact support before retrying.",
                    "error",
                )
                return redirect(url_for("payment"))

            if (
                gateway_payment.get("order_id") != razorpay_order_id
                or gateway_payment.get("amount") != expected_amount
                or gateway_payment.get("status") != "captured"
            ):
                flash(
                    "Razorpay has not confirmed a captured payment. Please try again or contact support.",
                    "error",
                )
                return redirect(url_for("payment"))

            payment_method = "razorpay"

        if payment_method != "razorpay":
            if "upi" in payment_method:
                payment_method = "upi"
            elif "card" in payment_method:
                payment_method = "card"
            elif "net" in payment_method or "bank" in payment_method:
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
        supplier_order_failures = 0
        products_without_supplier = 0

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

            if item.get("product_id"):
                stock_result = deduct_product_stock(
                    item["product_id"],
                    item["quantity"],
                    order_id,
                )
                if stock_result == "failed":
                    supplier_order_failures += 1
                elif stock_result == "no_supplier":
                    products_without_supplier += 1

        # ----------------------------------------------------
        # Save payment using actual payments table.
        # ----------------------------------------------------
        transaction_id = (
            request.form.get("razorpay_payment_id", "").strip()
            if payment_method == "razorpay"
            else (
                "TXN-"
                + datetime.now().strftime("%Y%m%d%H%M%S")
                + "-"
                + uuid.uuid4().hex[:6].upper()
            )
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
        session.pop("razorpay_order_id", None)
        session.pop("razorpay_order_amount", None)

        flash(
            "Order and payment completed successfully!",
            "success",
        )
        if supplier_order_failures:
            flash(
                "The customer order completed, but an automatic supplier order "
                "could not be created. Please review the stock and supplier setup.",
                "warning",
            )
        if products_without_supplier:
            flash(
                "Some products reached zero stock without a linked supplier. "
                "Assign a supplier in the admin dashboard.",
                "warning",
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
            payment_method=payment_method,
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
        razorpay_test_enabled=razorpay_test_mode_configured(),
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

    if not user or user.get("role") != "customer":
        flash(
            "Customer dashboard is available to customer accounts only.",
            "warning",
        )
        return redirect(url_for("index"))

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
                s.name AS service_name,
                d.full_name AS designer_name,
                d.specialization AS designer_specialization,
                designer_user.email AS designer_email,
                designer_user.phone AS designer_phone
            FROM consultations c
            LEFT JOIN services s
                ON c.service_id = s.id
            LEFT JOIN designers d
                ON c.designer_id = d.id
            LEFT JOIN users designer_user
                ON d.user_id = designer_user.id
            WHERE c.customer_id = %s
            ORDER BY c.id DESC
            """,
            (customer["id"],),
        )

        for consultation in consultations:
            message = consultation.get("message") or ""
            consultation["preferred_time"] = next(
                (
                    line.partition(":")[2].strip()
                    for line in message.splitlines()
                    if line.strip().lower().startswith("preferred time:")
                ),
                "",
            )
            preferred_date = consultation.get("preferred_date")
            consultation["display_date"] = (
                preferred_date.strftime("%d/%m/%Y")
                if hasattr(preferred_date, "strftime")
                else preferred_date or "Date not set"
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
            SELECT
                p.*,
                d.full_name AS designer_name,
                latest_update.title AS latest_update_title,
                latest_update.description AS latest_update_description,
                latest_update.progress_percent AS project_progress
            FROM projects p
            LEFT JOIN designers d
                ON p.designer_id = d.id
            LEFT JOIN project_updates latest_update
                ON latest_update.id = (
                    SELECT pu.id
                    FROM project_updates pu
                    WHERE pu.project_id = p.id
                    ORDER BY pu.created_at DESC, pu.id DESC
                    LIMIT 1
                )
            WHERE p.customer_id = %s
            ORDER BY p.id DESC
            """,
            (customer["id"],),
        )

        for project in projects:
            try:
                progress = int(project.get("project_progress") or 0)
            except (TypeError, ValueError):
                progress = 0
            project["project_progress"] = min(max(progress, 0), 100)
            for field in ("start_date", "expected_end_date"):
                value = project.get(field)
                if hasattr(value, "strftime"):
                    project[f"display_{field}"] = value.strftime("%d/%m/%Y")
                else:
                    project[f"display_{field}"] = value or "Not set"

        registration_date = (
            customer.get("created_at")
            or user.get("created_at")
        )
        customer["registration_date_display"] = (
            registration_date.strftime("%d/%m/%Y")
            if hasattr(registration_date, "strftime")
            else registration_date or "Unavailable"
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


@app.route(
    "/customer/profile",
    methods=["POST"],
)
@login_required
def update_customer_profile():
    user = get_current_user()

    if not user or user.get("role") != "customer":
        flash(
            "Customer profile can only be updated by a customer account.",
            "warning",
        )
        return redirect(url_for("index"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not name or not email:
        flash(
            "Name and email are required.",
            "error",
        )
        return redirect(url_for("customer_dashboard"))

    existing_user = fetch_one(
        """
        SELECT id
        FROM users
        WHERE email = %s
          AND id <> %s
        LIMIT 1
        """,
        (email, user["id"]),
    )

    if existing_user:
        flash(
            "That email address is already in use.",
            "error",
        )
        return redirect(url_for("customer_dashboard"))

    customer = ensure_customer_for_logged_in_user()

    if not customer:
        flash(
            "Your customer profile could not be loaded.",
            "error",
        )
        return redirect(url_for("customer_dashboard"))

    updated = execute_query(
        """
        UPDATE users AS u
        JOIN customers AS c
            ON c.user_id = u.id
        SET
            u.name = %s,
            u.email = %s,
            u.phone = %s,
            u.address = %s,
            c.full_name = %s,
            c.email = %s,
            c.phone = %s,
            c.address = %s
        WHERE u.id = %s
        """,
        (
            name,
            email,
            phone,
            address,
            name,
            email,
            phone,
            address,
            user["id"],
        ),
    )

    if not updated:
        flash(
            "Your profile could not be updated. Please try again.",
            "error",
        )
        return redirect(url_for("customer_dashboard"))

    flash(
        "Your profile has been updated.",
        "success",
    )
    return redirect(url_for("customer_dashboard"))


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
# STAFF LOGIN / DASHBOARDS
# ADMIN / DESIGNER / CONTRACTOR / SUPPLIER
# ============================================================

def role_required(required_role):
    """
    Allow access only to a logged-in user with the required role.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):

            # User must be logged in
            if not session.get("user_id"):
                flash("Please login to continue.", "warning")
                return redirect(url_for("login"))

            # Check logged-in user's role
            user = get_current_user()

            if not user:
                session.clear()
                flash("User account not found.", "error")
                return redirect(url_for("login"))

            user_role = str(
                user.get("role", "")
            ).strip().lower()

            if user_role != required_role.lower():
                flash(
                    "You do not have permission to access this page.",
                    "error"
                )

                # Send customer to customer dashboard
                if user_role == "customer":
                    return redirect(url_for("customer_dashboard"))

                return redirect(url_for("index"))

            return view(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error"
            )
            return render_template("admin_login.html")

        user = fetch_one(
            """
            SELECT *
            FROM users
            WHERE email = %s
              AND role = 'admin'
              AND status = 'active'
            LIMIT 1
            """,
            (email,)
        )

        if not user:
            flash(
                "Invalid admin email or password.",
                "error"
            )
            return render_template("admin_login.html")

        stored_hash = user.get("password_hash")

        password_valid = False

        if stored_hash:
            try:
                password_valid = check_password_hash(
                    stored_hash,
                    password
                )
            except Exception:
                password_valid = False

        if not password_valid:
            flash(
                "Invalid admin email or password.",
                "error"
            )
            return render_template("admin_login.html")

        session["user_id"] = user["id"]
        session["role"] = "admin"

        flash(
            "Admin login successful!",
            "success"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template("admin_login.html")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():

    users = fetch_all(
        """
        SELECT id, name, email, phone, role, status
        FROM users
        ORDER BY id DESC
        """
    )

    customers = fetch_all(
        """
        SELECT *
        FROM customers
        ORDER BY id DESC
        """
    )

    designers = fetch_all(
        """
        SELECT
            d.*,
            u.name AS account_name,
            (
                SELECT COUNT(*)
                FROM consultations c
                WHERE c.designer_id = d.id
                  AND c.status IN ('pending', 'contacted', 'confirmed')
            ) AS active_consultations,
            (
                SELECT COUNT(*)
                FROM projects p
                WHERE p.designer_id = d.id
                  AND p.status IN (
                      'new', 'planning', 'design', 'approval',
                      'in_progress', 'on_hold'
                  )
            ) AS active_projects,
            (
                SELECT COUNT(*)
                FROM appointments a
                WHERE a.designer_id = d.id
                  AND a.status IN ('pending', 'confirmed')
                  AND a.appointment_date >= CURDATE()
            ) AS upcoming_appointments
        FROM designers d
        LEFT JOIN users u
            ON d.user_id = u.id
        ORDER BY d.id DESC
        """
    )
    for designer in designers:
        designer["workload_count"] = (
            (designer.get("active_consultations") or 0)
            + (designer.get("active_projects") or 0)
            + (designer.get("upcoming_appointments") or 0)
        )
        designer["availability_label"] = (
            "Busy" if designer["workload_count"] else "Available"
        )

    services = fetch_all(
        """
        SELECT *
        FROM services
        ORDER BY id DESC
        """
    )

    products = fetch_all(
        """
        SELECT
            p.*,
            s.company_name AS supplier_name,
            s.contact_person AS supplier_contact
        FROM products p
        LEFT JOIN suppliers s
            ON p.supplier_id = s.id
        ORDER BY p.id DESC
        """
    )

    consultations = fetch_all(
        """
        SELECT
            c.*,
            s.name AS service_name,
            cu.full_name AS customer_name,
            cu.email AS customer_email,
            d.full_name AS designer_name
        FROM consultations c
        LEFT JOIN services s
            ON c.service_id = s.id
        LEFT JOIN customers cu
            ON c.customer_id = cu.id
        LEFT JOIN designers d
            ON c.designer_id = d.id
        ORDER BY c.id DESC
        """
    )

    for consultation in consultations:
        preferred_date = consultation.get("preferred_date")
        consultation["display_date"] = (
            preferred_date.strftime("%d/%m/%Y")
            if hasattr(preferred_date, "strftime")
            else preferred_date or "Not set"
        )

    available_designers = [
        designer for designer in designers
        if designer.get("status") == "active"
    ]
    available_designers.sort(
        key=lambda designer: (
            designer["workload_count"],
            designer.get("full_name") or "",
        )
    )

    available_contractors = fetch_all(
        """
        SELECT id, company_name, contact_person, specialization
        FROM contractors
        WHERE status = 'active'
        ORDER BY company_name, contact_person
        """
    )

    available_suppliers = fetch_all(
        """
        SELECT id, company_name, contact_person
        FROM suppliers
        WHERE status = 'active'
        ORDER BY company_name, contact_person
        """
    )

    quotations = fetch_all(
        """
        SELECT *
        FROM quotations
        ORDER BY id DESC
        """
    )

    projects = fetch_all(
        """
        SELECT
            p.*,
            c.full_name AS customer_name,
            d.full_name AS designer_name,
            co.company_name AS contractor_name,
            co.contact_person AS contractor_contact
        FROM projects p
        LEFT JOIN customers c
            ON p.customer_id = c.id
        LEFT JOIN designers d
            ON p.designer_id = d.id
        LEFT JOIN contractors co
            ON p.contractor_id = co.id
        ORDER BY p.id DESC
        """
    )

    supplier_orders = fetch_all(
        """
        SELECT
            so.id,
            so.quantity,
            so.status,
            so.created_at,
            so.customer_order_id,
            p.name AS product_name,
            s.company_name AS supplier_name,
            s.contact_person AS supplier_contact
        FROM supplier_orders so
        JOIN products p
            ON so.product_id = p.id
        JOIN suppliers s
            ON so.supplier_id = s.id
        ORDER BY so.id DESC
        """
    )

    orders = fetch_all(
        """
        SELECT *
        FROM orders
        ORDER BY id DESC
        """
    )

    return render_template(
        "admin_dashboard.html",
        users=users,
        customers=customers,
        designers=designers,
        services=services,
        products=products,
        consultations=consultations,
        available_designers=available_designers,
        available_contractors=available_contractors,
        available_suppliers=available_suppliers,
        quotations=quotations,
        projects=projects,
        orders=orders,
        supplier_orders=supplier_orders
    )


@app.route("/admin/accounts")
@role_required("admin")
def admin_accounts():
    accounts = fetch_all(
        """
        SELECT
            u.id,
            u.name,
            u.email,
            u.phone,
            u.address,
            u.role,
            u.status,
            c.city,
            COALESCE(s.company_name, co.company_name) AS company_name,
            COALESCE(s.contact_person, co.contact_person) AS contact_person,
            COALESCE(d.specialization, co.specialization) AS specialization
        FROM users u
        LEFT JOIN customers c
            ON c.user_id = u.id
        LEFT JOIN designers d
            ON d.user_id = u.id
        LEFT JOIN contractors co
            ON co.user_id = u.id
        LEFT JOIN suppliers s
            ON s.user_id = u.id
        WHERE u.role IN ('customer', 'designer', 'contractor', 'supplier')
        ORDER BY FIELD(u.role, 'customer', 'supplier', 'contractor', 'designer'),
                 u.id DESC
        """
    )
    return render_template("admin_accounts.html", accounts=accounts)


@app.route("/admin/accounts/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_edit_account(user_id):
    account = fetch_one(
        """
        SELECT
            u.id,
            u.name,
            u.email,
            u.phone,
            u.address,
            u.role,
            u.status,
            c.city,
            COALESCE(s.company_name, co.company_name) AS company_name,
            COALESCE(s.contact_person, co.contact_person) AS contact_person,
            COALESCE(d.specialization, co.specialization) AS specialization
        FROM users u
        LEFT JOIN customers c
            ON c.user_id = u.id
        LEFT JOIN designers d
            ON d.user_id = u.id
        LEFT JOIN contractors co
            ON co.user_id = u.id
        LEFT JOIN suppliers s
            ON s.user_id = u.id
        WHERE u.id = %s
          AND u.role IN ('customer', 'designer', 'contractor', 'supplier')
        LIMIT 1
        """,
        (user_id,),
    )

    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("admin_accounts"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        company_name = request.form.get("company_name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        contact_person = request.form.get("contact_person", "").strip() or name
        role = account["role"]

        if not name or not email:
            flash("Name and email are required.", "error")
            return render_template("admin_account_edit.html", account=account)

        if role in {"supplier", "contractor"} and not company_name:
            flash("Company name is required for this account.", "error")
            return render_template("admin_account_edit.html", account=account)

        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE users
                SET name = %s, email = %s, phone = %s, address = %s
                WHERE id = %s
                """,
                (name, email, phone, address, user_id),
            )

            if role == "customer":
                cursor.execute(
                    "SELECT id FROM customers WHERE user_id = %s LIMIT 1",
                    (user_id,),
                )
                if cursor.fetchone():
                    cursor.execute(
                        """
                        UPDATE customers
                        SET full_name = %s, email = %s, phone = %s,
                            address = %s, city = %s
                        WHERE user_id = %s
                        """,
                        (name, email, phone, address, city or None, user_id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO customers
                            (user_id, full_name, email, phone, address, city)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, name, email, phone, address, city or None),
                    )
            elif role == "designer":
                cursor.execute(
                    "SELECT id FROM designers WHERE user_id = %s LIMIT 1",
                    (user_id,),
                )
                if cursor.fetchone():
                    cursor.execute(
                        """
                        UPDATE designers
                        SET full_name = %s, specialization = %s
                        WHERE user_id = %s
                        """,
                        (name, specialization or None, user_id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO designers (user_id, full_name, specialization, status)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (user_id, name, specialization or None, account["status"]),
                    )
            elif role == "contractor":
                cursor.execute(
                    "SELECT id FROM contractors WHERE user_id = %s LIMIT 1",
                    (user_id,),
                )
                if cursor.fetchone():
                    cursor.execute(
                        """
                        UPDATE contractors
                        SET company_name = %s, contact_person = %s,
                            phone = %s, email = %s, specialization = %s
                        WHERE user_id = %s
                        """,
                        (
                            company_name,
                            contact_person,
                            phone,
                            email,
                            specialization or None,
                            user_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO contractors
                            (user_id, company_name, contact_person, phone, email, specialization, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            company_name,
                            contact_person,
                            phone,
                            email,
                            specialization or None,
                            account["status"],
                        ),
                    )
            else:
                cursor.execute(
                    "SELECT id FROM suppliers WHERE user_id = %s LIMIT 1",
                    (user_id,),
                )
                if cursor.fetchone():
                    cursor.execute(
                        """
                        UPDATE suppliers
                        SET company_name = %s, contact_person = %s,
                            phone = %s, email = %s, address = %s
                        WHERE user_id = %s
                        """,
                        (
                            company_name,
                            contact_person,
                            phone,
                            email,
                            address,
                            user_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO suppliers
                            (user_id, company_name, contact_person, phone, email, address, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            company_name,
                            contact_person,
                            phone,
                            email,
                            address,
                            account["status"],
                        ),
                    )

            connection.commit()
        except Error as error:
            if connection:
                connection.rollback()
            print("ADMIN ACCOUNT UPDATE ERROR:", error)
            flash(
                "Account update failed. Check that the email address is not already in use.",
                "error",
            )
            return render_template("admin_account_edit.html", account=account)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        flash("Account updated successfully.", "success")
        return redirect(url_for("admin_accounts"))

    return render_template("admin_account_edit.html", account=account)


@app.route("/admin/accounts/<int:user_id>/status", methods=["POST"])
@role_required("admin")
def admin_toggle_account_status(user_id):
    account = fetch_one(
        """
        SELECT id, role, status
        FROM users
        WHERE id = %s
          AND role IN ('customer', 'designer', 'contractor', 'supplier')
        LIMIT 1
        """,
        (user_id,),
    )
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("admin_accounts"))

    new_status = "inactive" if account["status"] == "active" else "active"
    profile_table = {
        "designer": "designers",
        "contractor": "contractors",
        "supplier": "suppliers",
    }.get(account["role"])

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET status = %s WHERE id = %s",
            (new_status, user_id),
        )
        if profile_table:
            cursor.execute(
                f"UPDATE `{profile_table}` SET status = %s WHERE user_id = %s",
                (new_status, user_id),
            )
        connection.commit()
    except Error as error:
        if connection:
            connection.rollback()
        print("ADMIN ACCOUNT STATUS UPDATE ERROR:", error)
        flash("Account status could not be updated.", "error")
        return redirect(url_for("admin_accounts"))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    flash(f"Account marked {new_status}.", "success")
    return redirect(url_for("admin_accounts"))


@app.route("/admin/accounts/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def admin_delete_account(user_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM users
            WHERE id = %s
              AND role IN ('customer', 'designer', 'contractor', 'supplier')
            """,
            (user_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            flash("Account not found or cannot be deleted.", "error")
            return redirect(url_for("admin_accounts"))
        connection.commit()
    except Error as error:
        if connection:
            connection.rollback()
        print("ADMIN ACCOUNT DELETE ERROR:", error)
        flash("Account could not be deleted because related records prevent it.", "error")
        return redirect(url_for("admin_accounts"))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    flash("Account and its related records were deleted.", "success")
    return redirect(url_for("admin_accounts"))


@app.route(
    "/admin/consultations/<int:consultation_id>/assign-designer",
    methods=["POST"],
)
@role_required("admin")
def assign_consultation_designer(consultation_id):
    designer_id = request.form.get("designer_id", type=int)

    if not designer_id:
        flash("Please select a designer.", "error")
        return redirect(url_for("admin_dashboard"))

    consultation = fetch_one(
        """
        SELECT id
        FROM consultations
        WHERE id = %s
        LIMIT 1
        """,
        (consultation_id,),
    )

    if not consultation:
        flash("Consultation not found.", "error")
        return redirect(url_for("admin_dashboard"))

    designer = fetch_one(
        """
        SELECT id
        FROM designers
        WHERE id = %s
          AND status = 'active'
        LIMIT 1
        """,
        (designer_id,),
    )

    if not designer:
        flash("Please select an active designer.", "error")
        return redirect(url_for("admin_dashboard"))

    status_column = fetch_one(
        "SHOW COLUMNS FROM consultations LIKE 'status'"
    )

    supports_confirmed = (
        status_column
        and "confirmed" in str(status_column.get("Type", "")).lower()
    )
    if supports_confirmed:
        updated = execute_query(
            """
            UPDATE consultations
            SET designer_id = %s,
                status = 'confirmed'
            WHERE id = %s
            """,
            (designer_id, consultation_id),
        )
    else:
        updated = execute_query(
            """
            UPDATE consultations
            SET designer_id = %s
            WHERE id = %s
            """,
            (designer_id, consultation_id),
        )

    if not updated:
        flash(
            "Designer assignment failed. Please try again.",
            "error",
        )
        return redirect(url_for("admin_dashboard"))

    flash(
        "Designer assigned and consultation confirmed."
        if supports_confirmed
        else "Designer assigned. Consultation status was left unchanged because "
             "the database does not support the confirmed status.",
        "success",
    )
    return redirect(url_for("admin_dashboard"))


@app.route(
    "/admin/projects/<int:project_id>/assign-designer",
    methods=["POST"],
)
@role_required("admin")
def assign_project_designer(project_id):
    designer_id = request.form.get("designer_id", type=int)

    if not designer_id:
        flash("Please select a designer.", "error")
        return redirect(url_for("admin_dashboard"))

    project = fetch_one(
        "SELECT id FROM projects WHERE id = %s LIMIT 1",
        (project_id,),
    )
    if not project:
        flash("Project not found.", "error")
        return redirect(url_for("admin_dashboard"))

    designer = fetch_one(
        """
        SELECT id
        FROM designers
        WHERE id = %s
          AND status = 'active'
        LIMIT 1
        """,
        (designer_id,),
    )
    if not designer:
        flash("Please select an active designer.", "error")
        return redirect(url_for("admin_dashboard"))

    updated = execute_query(
        "UPDATE projects SET designer_id = %s WHERE id = %s",
        (designer_id, project_id),
    )
    if not updated:
        flash("Designer assignment failed. Please try again.", "error")
        return redirect(url_for("admin_dashboard"))

    flash("Designer assigned to the project.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route(
    "/admin/products/<int:product_id>/assign-supplier",
    methods=["POST"],
)
@role_required("admin")
def assign_product_supplier(product_id):
    supplier_value = request.form.get("supplier_id", "").strip()
    supplier_id = None

    if supplier_value:
        try:
            supplier_id = int(supplier_value)
        except ValueError:
            flash("Please select a valid supplier.", "error")
            return redirect(url_for("admin_dashboard"))

    product = fetch_one(
        "SELECT id FROM products WHERE id = %s LIMIT 1",
        (product_id,),
    )
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if supplier_id is not None:
        supplier = fetch_one(
            """
            SELECT id
            FROM suppliers
            WHERE id = %s
              AND status = 'active'
            LIMIT 1
            """,
            (supplier_id,),
        )
        if not supplier:
            flash("Please select an active supplier.", "error")
            return redirect(url_for("admin_dashboard"))

    updated = execute_query(
        "UPDATE products SET supplier_id = %s WHERE id = %s",
        (supplier_id, product_id),
    )
    if not updated:
        flash("Supplier assignment failed. Please try again.", "error")
        return redirect(url_for("admin_dashboard"))

    flash(
        "Supplier assigned to the product."
        if supplier_id is not None
        else "Supplier assignment removed from the product.",
        "success",
    )
    return redirect(url_for("admin_dashboard"))


@app.route(
    "/admin/projects/<int:project_id>/assign-contractor",
    methods=["POST"],
)
@role_required("admin")
def assign_project_contractor(project_id):
    contractor_value = request.form.get("contractor_id", "").strip()
    contractor_id = None

    if contractor_value:
        try:
            contractor_id = int(contractor_value)
        except ValueError:
            flash("Please select a valid contractor.", "error")
            return redirect(url_for("admin_dashboard"))

    project = fetch_one(
        "SELECT id FROM projects WHERE id = %s LIMIT 1",
        (project_id,),
    )
    if not project:
        flash("Project not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if contractor_id is not None:
        contractor = fetch_one(
            """
            SELECT id
            FROM contractors
            WHERE id = %s
              AND status = 'active'
            LIMIT 1
            """,
            (contractor_id,),
        )
        if not contractor:
            flash("Please select an active contractor.", "error")
            return redirect(url_for("admin_dashboard"))

    updated = execute_query(
        """
        UPDATE projects
        SET contractor_id = %s
        WHERE id = %s
        """,
        (contractor_id, project_id),
    )
    if not updated:
        flash("Contractor assignment failed. Please try again.", "error")
        return redirect(url_for("admin_dashboard"))

    flash(
        "Contractor assigned to the project."
        if contractor_id is not None
        else "Contractor assignment removed from the project.",
        "success",
    )
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/payments")
@role_required("admin")
def admin_payments_dashboard():
    payment_summary = fetch_one(
        """
        SELECT
            COUNT(*) AS transaction_count,
            COALESCE(SUM(
                CASE WHEN status = 'paid' THEN amount ELSE 0 END
            ), 0) AS captured_total,
            SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS captured_count
        FROM payments
        WHERE payment_method = 'razorpay'
        """
    ) or {
        "transaction_count": 0,
        "captured_total": Decimal("0.00"),
        "captured_count": 0,
    }

    payments = fetch_all(
        """
        SELECT
            p.id,
            p.order_id,
            p.amount,
            p.transaction_id,
            p.status,
            p.paid_at,
            p.created_at,
            COALESCE(c.full_name, u.name, 'Customer') AS customer_name,
            u.email AS customer_email
        FROM payments p
        INNER JOIN orders o
            ON p.order_id = o.id
        LEFT JOIN customers c
            ON o.customer_id = c.id
        LEFT JOIN users u
            ON c.user_id = u.id
        WHERE p.payment_method = 'razorpay'
        ORDER BY p.id DESC
        LIMIT 100
        """
    )

    return render_template(
        "admin_payments.html",
        payment_summary=payment_summary,
        payments=payments,
    )


# ============================================================
# DESIGNER LOGIN
# ============================================================

@app.route("/designer/login", methods=["GET", "POST"])
def designer_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error"
            )
            return render_template("designer_login.html")

        user = fetch_one(
            """
            SELECT *
            FROM users
            WHERE email = %s
              AND role = 'designer'
              AND status = 'active'
            LIMIT 1
            """,
            (email,)
        )

        if not user:
            flash(
                "Invalid designer email or password.",
                "error"
            )
            return render_template("designer_login.html")

        stored_hash = user.get("password_hash")

        password_valid = False

        if stored_hash:
            try:
                password_valid = check_password_hash(
                    stored_hash,
                    password
                )
            except Exception:
                password_valid = False

        if not password_valid:
            flash(
                "Invalid designer email or password.",
                "error"
            )
            return render_template("designer_login.html")

        session["user_id"] = user["id"]
        session["role"] = "designer"

        flash(
            "Designer login successful!",
            "success"
        )

        return redirect(
            url_for("designer_dashboard")
        )

    return render_template("designer_login.html")


# ============================================================
# DESIGNER DASHBOARD
# ============================================================

@app.route("/designer/dashboard")
@role_required("designer")
def designer_dashboard():

    user = get_current_user()

    designer = fetch_one(
        """
        SELECT *
        FROM designers
        WHERE user_id = %s
        LIMIT 1
        """,
        (user["id"],)
    )

    consultations = fetch_all(
        """
        SELECT
            c.*,
            s.name AS service_name,
            cu.full_name AS customer_name,
            d.full_name AS designer_name
        FROM consultations c
        LEFT JOIN services s
            ON c.service_id = s.id
        LEFT JOIN customers cu
            ON c.customer_id = cu.id
        LEFT JOIN designers d
            ON c.designer_id = d.id
        ORDER BY c.id DESC
        """
    )

    projects = fetch_all(
        """
        SELECT *
        FROM projects
        ORDER BY id DESC
        """
    )

    quotations = fetch_all(
        """
        SELECT *
        FROM quotations
        ORDER BY id DESC
        """
    )

    return render_template(
        "designer_dashboard.html",
        user=user,
        designer=designer,
        consultations=consultations,
        projects=projects,
        quotations=quotations
    )


# ============================================================
# CONTRACTOR LOGIN
# ============================================================

@app.route("/contractor/login", methods=["GET", "POST"])
def contractor_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error"
            )
            return render_template("contractor_login.html")

        user = fetch_one(
            """
            SELECT *
            FROM users
            WHERE email = %s
              AND role = 'contractor'
              AND status = 'active'
            LIMIT 1
            """,
            (email,)
        )

        if not user:
            flash(
                "Invalid contractor email or password.",
                "error"
            )
            return render_template("contractor_login.html")

        stored_hash = user.get("password_hash")

        password_valid = False

        if stored_hash:
            try:
                password_valid = check_password_hash(
                    stored_hash,
                    password
                )
            except Exception:
                password_valid = False

        if not password_valid:
            flash(
                "Invalid contractor email or password.",
                "error"
            )
            return render_template("contractor_login.html")

        session["user_id"] = user["id"]
        session["role"] = "contractor"

        flash(
            "Contractor login successful!",
            "success"
        )

        return redirect(
            url_for("contractor_dashboard")
        )

    return render_template("contractor_login.html")


# ============================================================
# CONTRACTOR DASHBOARD
# ============================================================

@app.route("/contractor/dashboard")
@role_required("contractor")
def contractor_dashboard():

    user = get_current_user()

    projects = fetch_all(
        """
        SELECT *
        FROM projects
        ORDER BY id DESC
        """
    )

    project_updates = fetch_all(
        """
        SELECT *
        FROM project_updates
        ORDER BY id DESC
        """
    )

    return render_template(
        "contractor_dashboard.html",
        user=user,
        projects=projects,
        updates=project_updates,
        project_updates=project_updates
    )


# ============================================================
# SUPPLIER LOGIN
# ============================================================

@app.route("/supplier/login", methods=["GET", "POST"])
def supplier_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error"
            )
            return render_template("supplier_login.html")

        user = fetch_one(
            """
            SELECT *
            FROM users
            WHERE email = %s
              AND role = 'supplier'
              AND status = 'active'
            LIMIT 1
            """,
            (email,)
        )

        if not user:
            flash(
                "Invalid supplier email or password.",
                "error"
            )
            return render_template("supplier_login.html")

        stored_hash = user.get("password_hash")

        password_valid = False

        if stored_hash:
            try:
                password_valid = check_password_hash(
                    stored_hash,
                    password
                )
            except Exception:
                password_valid = False

        if not password_valid:
            flash(
                "Invalid supplier email or password.",
                "error"
            )
            return render_template("supplier_login.html")

        session["user_id"] = user["id"]
        session["role"] = "supplier"

        flash(
            "Supplier login successful!",
            "success"
        )

        return redirect(
            url_for("supplier_dashboard")
        )

    return render_template("supplier_login.html")


# ============================================================
# SUPPLIER DASHBOARD
# ============================================================

@app.route("/supplier/dashboard")
@role_required("supplier")
def supplier_dashboard():

    user = get_current_user()

    supplier = fetch_one(
        """
        SELECT id, company_name
        FROM suppliers
        WHERE user_id = %s
        LIMIT 1
        """,
        (user["id"],),
    ) if user else None

    products = []
    orders = []
    supplier_orders = []
    if supplier:
        products = fetch_all(
            """
            SELECT *
            FROM products
            WHERE supplier_id = %s
            ORDER BY id DESC
            """,
            (supplier["id"],),
        )

        orders = fetch_all(
            """
            SELECT DISTINCT o.*
            FROM orders o
            JOIN order_items oi
                ON oi.order_id = o.id
            JOIN products p
                ON p.id = oi.product_id
            WHERE p.supplier_id = %s
            ORDER BY o.id DESC
            """,
            (supplier["id"],),
        )

        supplier_orders = fetch_all(
            """
            SELECT
                so.id,
                so.quantity,
                so.status,
                so.created_at,
                so.customer_order_id,
                p.name AS product_name,
                p.category AS product_category
            FROM supplier_orders so
            JOIN products p
                ON so.product_id = p.id
            WHERE so.supplier_id = %s
            ORDER BY so.id DESC
            """,
            (supplier["id"],),
        )

    return render_template(
        "supplier_dashboard.html",
        user=user,
        supplier=supplier,
        products=products,
        orders=orders,
        supplier_orders=supplier_orders
    )
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
