"""
Smart Fridge — GUI skeleton.
    pip install flask requests
    python app.py
http://127.0.0.1:5001
"""
import os
from datetime import date, datetime
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

app = Flask(
    __name__,
    template_folder=os.path.dirname(os.path.abspath(__file__)),
    static_folder=os.path.dirname(os.path.abspath(__file__)),
    static_url_path="/static",
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")


def api_get(endpoint, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        print(f"[api_get] HTTP error for {endpoint}: {exc}")
        return None
    except Exception as exc:
        print(f"[api_get] Request error for {endpoint}: {exc}")
        return None


def api_post(endpoint, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", json=data, headers=headers, timeout=90)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", "Ошибка API")
        except Exception:
            detail = f"Ошибка API: {exc}"
        return {"_error": detail}
    except Exception as exc:
        return {"_error": str(exc)}


def days_until(expiration_date):
    try:
        exp = datetime.strptime(expiration_date, "%Y-%m-%d").date()
        return (exp - date.today()).days
    except Exception:
        return None


def item_status(days_left):
    if days_left is None:
        return "normal"
    if days_left < 0:
        return "expired"
    if days_left <= 3:
        return "soon"
    return "normal"


# ---- Mock data (fallback when backend is unavailable) ----
VR_PRODUCTS = []
for i in range(43):
    urgency = round(1 - i * 0.2, 2) if i < 5 else 0
    VR_PRODUCTS.append({"name": "Продукт", "date": "00.00.0000", "urgency": urgency})

RECIPE_CARDS = [
    {"title": "Быстрый ужин из остатков", "desc": "Подойдёт для продуктов, которые нужно использовать в первую очередь", "kcal": "≈ 350 ккал"},
    {"title": "Овощная тарелка", "desc": "Лёгкий вариант для овощей и зелени", "kcal": "≈ 180 ккал"},
    {"title": "Сытный завтрак", "desc": "Идея для молочных продуктов, яиц и круп", "kcal": "≈ 420 ккал"},
]

@app.route("/")
def index():
    return render_template("index.html", active="home")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        result = api_post("/api/v1/auth/login", {"email": email, "password": password})
        if result and "access_token" in result:
            session["token"] = result["access_token"]
            session["email"] = email
            return redirect(url_for("vr_shell"))
        flash("Неверный логин или пароль")
    return render_template("login.html", active="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        name = request.form.get("full_name")
        password = request.form.get("password")
        result = api_post("/api/v1/auth/register", {
            "email": email,
            "full_name": name,
            "password": password,
        })
        if result and "id" in result:
            flash("Регистрация успешна! Войдите.")
            return redirect(url_for("login"))
        flash("Ошибка регистрации")
    return render_template("register.html", active="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/vr-shell")
def vr_shell():
    token = session.get("token")
    products = None

    if token:
        items = api_get("/api/v1/inventory/items", token)

        if isinstance(items, list):
            products = []
            for item in items:
                days_left = days_until(item.get("expiration_date", ""))
                status = item_status(days_left)
                urgency = 1 if status == "expired" else 0.65 if status == "soon" else 0
                products.append({
                    "id": item.get("id"),
                    "name": item.get("product_name", "Продукт"),
                    "date": item.get("expiration_date", ""),
                    "quantity": item.get("quantity", 1),
                    "unit": item.get("unit", "шт"),
                    "urgency": urgency,
                    "status": status,
                    "days_left": days_left,
                    "photo_url": item.get("photo_url"),
                })
        else:
            products = None

    if products is None:
        products = VR_PRODUCTS

    return render_template("vr_shell.html", active="vr", products=products)


@app.route("/api/catalog/search")
def catalog_search():
    token = session.get("token")
    if not token:
        return {"error": "unauthorized"}, 401
    q = request.args.get("q", "")
    data = api_get(f"/api/v1/inventory/catalog?search={q}", token) or []
    return {"results": data}


@app.route("/api/ai-recipes/suggest", methods=["POST"])
def proxy_ai_recipe_suggest():
    token = session.get("token")
    if not token:
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{API_BASE}/api/v1/ai-recipes/suggest",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    except requests.RequestException as exc:
        return jsonify({"detail": f"Бэкенд недоступен: {exc}"}), 502
    return resp.content, resp.status_code, {"Content-Type": "application/json"}


@app.route("/add-product", methods=["POST"])
def add_product():
    token = session.get("token")
    if not token:
        flash("Войдите, чтобы добавить продукт")
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Название обязательно")
        return redirect(url_for("vr_shell"))

    try:
        quantity = float(request.form.get("quantity", "1") or 1)
    except ValueError:
        quantity = 1.0

    expiration_date = request.form.get("expiration_date")
    if not expiration_date:
        flash("Срок годности обязателен")
        return redirect(url_for("vr_shell"))

    category = request.form.get("category", "other")
    shelf_life = request.form.get("default_shelf_life_days")
    photo_url = request.form.get("photo_url", "").strip() or None
    product_id_raw = request.form.get("product_id")

    if product_id_raw:
        try:
            product_id = int(product_id_raw)
        except ValueError:
            flash("Некорректный идентификатор продукта")
            return redirect(url_for("vr_shell"))
    else:
        catalog_payload = {
            "name": name,
            "category": category,
            "default_shelf_life_days": int(shelf_life) if shelf_life else None,
            "photo_url": photo_url,
        }
        created = api_post("/api/v1/inventory/catalog", catalog_payload, token)
        if not created or created.get("_error") or "id" not in created:
            err = created.get("_error") if created else "нет ответа от API"
            flash(f"Не удалось создать запись каталога: {err}")
            return redirect(url_for("vr_shell"))
        product_id = created["id"]

    item_payload = {
        "product_id": product_id,
        "quantity": quantity,
        "expiration_date": expiration_date,
        "photo_url": None,
    }
    result = api_post("/api/v1/inventory/items", item_payload, token)
    if result and result.get("_error"):
        flash(result["_error"])
    else:
        flash(f"Добавлено: {name}")
    return redirect(url_for("vr_shell"))


@app.route("/item-action", methods=["POST"])
def item_action():
    token = session.get("token")
    if not token:
        flash("Войдите, чтобы списывать продукты")
        return redirect(url_for("login"))

    item_id = request.form.get("item_id")
    action = request.form.get("action")
    try:
        quantity = float(request.form.get("quantity", "1") or 1)
    except ValueError:
        quantity = 1.0

    if action not in {"consumed", "wasted"} or not item_id:
        flash("Некорректное действие с продуктом")
        return redirect(url_for("vr_shell"))

    label = "Съедено" if action == "consumed" else "Выброшено"
    result = api_post(
        f"/api/v1/inventory/items/{item_id}/action",
        {"action": action, "quantity": quantity, "reason": label},
        token,
    )
    if result and result.get("_error"):
        flash(result["_error"])
    else:
        flash(f"Записано: {label.lower()}")
    return redirect(url_for("vr_shell"))

@app.route("/ai-assistant", methods=["GET", "POST"])
def ai_assistant():
    token = session.get("token")
    assistant_result = None
    recipes = None
    form_data = {
        "goal": "Приготовить ужин быстро и использовать продукты, которые скоро испортятся",
        "restrictions": "",
        "max_recipes": 3,
    }

    if token:
        data = api_get("/api/v1/recipes/suggestions", token)
        if isinstance(data, list) and data:
            recipes = [
                {
                    "id": s["recipe"]["id"],
                    "title": s["recipe"]["title"],
                    "desc": f"Совпадение: {s['match_percentage']:.0f}%",
                    "kcal": f"{s['recipe']['calories']} ккал",
                    "time": f"{s['recipe']['prep_time_minutes']} мин",
                    "missing": s["missing_ingredients"],
                }
                for s in data
            ]

    if request.method == "POST":
        if not token:
            flash("Сначала войдите в систему, чтобы ассистент видел ваши продукты.")
            return redirect(url_for("login"))

        form_data = {
            "goal": request.form.get("goal", "").strip(),
            "restrictions": request.form.get("restrictions", "").strip(),
            "max_recipes": int(request.form.get("max_recipes", 3)),
        }
        assistant_result = api_post("/api/v1/recipes/assistant", form_data, token)
        if assistant_result and assistant_result.get("_error"):
            flash(assistant_result["_error"])
            assistant_result = None

    if not recipes:
        recipes = RECIPE_CARDS

    return render_template(
        "ai_assistant.html",
        active="ai",
        recipes=recipes,
        assistant_result=assistant_result,
        form_data=form_data,
    )


@app.route("/recipe")
def recipe():
    recipes_list = api_get("/api/v1/recipes/") or []
    if isinstance(recipes_list, dict):
        recipes_list = []

    return render_template(
        "recipe.html",
        active="recipe",
        recipes_list=recipes_list,
    )


@app.route("/statistics")
def statistics():
    token = session.get("token")
    stats = {
        "total": 0,
        "expired": 0,
        "expiring": 0,
        "low_stock": 0,
        "consumed_month": 0,
        "wasted_month": 0,
        "wasted_expired_month": 0,
        "use_first": [],
        "recent_events": [],
        "alerts": {"CRITICAL_EXPIRED": [], "WARNING_SOON": [], "LOW_STOCK": []},
    }
    if token:
        api_stats = api_get("/api/v1/inventory/statistics", token)
        if isinstance(api_stats, dict) and not api_stats.get("_error"):
            stats.update(api_stats)
    return render_template("statistics.html", active="stats", stats=stats)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
