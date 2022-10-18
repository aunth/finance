from crypt import methods
from email import message
import os
import json
from time import asctime
import hashlib

import sqlite3
from urllib import response
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash                                                                                                         

from helpers import login_required, lookup, usd, toFixed

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = sqlite3.connect('./finance.db', check_same_thread=False)
cursor = db.cursor()
#db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")
    
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
@login_required
def index():
    return render_template('about.html', message="TODO")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        stocks = request.form.get("symbol")
        respone = lookup(stocks)
        if not respone:
            return render_template("failed.html", message="Invalid symbol of stocks")
        try:
            shares = int(request.form.get("shares"))
            if shares <= 0:
                return render_template("failed.html", message="Number must be a pisitive")
            respone["volume"] = shares
        except ValueError:
            return render_template("failed.html", message="You type invalid number")
        current_balance = cursor.execute("SELECT cash FROM users WHERE id=(?)", (int(session["user_id"]),)).fetchall()[0][0]# respone is [(cash,)]
        if current_balance < shares * respone["price"]:
            return render_template("failed.html", message="You balance is low")
        current_balance = current_balance - (shares * respone["price"])
        users_stocks = cursor.execute("SELECT volume FROM user_stocks WHERE symbol=? AND id=?", (stocks, session["user_id"])).fetchall()
        db.commit()
        if users_stocks:
            cursor.execute("UPDATE user_stocks SET volume=? WHERE id=? AND name_of_stocks=?", 
            (int(shares + users_stocks[0][0]),session["user_id"], respone["name"]))
        else:
            cursor.execute("INSERT INTO user_stocks VALUES(?, ?, ?, ?)", (session["user_id"],
            respone["name"], stocks, shares))
            db.commit()
        cursor.execute("INSERT INTO transactions values (?, ?, ?, ?, ?, ?, ?)", (session["user_id"], respone["name"], shares, shares * respone["price"], toFixed(current_balance, 2), asctime(), "buy"))
        cursor.execute("UPDATE users SET cash=? WHERE id=?", (toFixed(current_balance, 2), session["user_id"]))
        db.commit()
        return render_template("transaction.html", respone=respone)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transaction = cursor.execute("SELECT * FROM transactions WHERE id=(?)", (session["user_id"],)).fetchall()
    if transaction:
        return render_template("history.html", transaction=transaction)
    return render_template("page.html", message="First you need to buy a stocks")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("/failed.html", message="must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template('/failed.html', message="must provide password")

        # Query database for username
        try:
            rows = cursor.execute("SELECT id, hash FROM users WHERE username = (?)", (request.form.get("username"),)).fetchall()
        except Exception as e:
            return render_template("/failed.html", message=e)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][1], request.form.get("password")):
            return render_template("/failed.html", message="invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0][0]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("search.html")
    else:
        stonks = request.form.get("stocks")
        try:
            respone = lookup(stonks)
        except json.JSONDecodeError:
            return render_template("failed.html", message="You type incorect symbol of stocks")
        return render_template("quote.html", respone=respone)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        user_password = request.form.get("password")
        confirmed_password = request.form.get("confirmation")
        if not username:
            return render_template("failed.html", message="Must give username")
        if not user_password:
            return render_template("failed.hmlt", message="Must give password")
        if not confirmed_password:
            return render_template("failed.html", message="Must give confirmator")
        if confirmed_password != user_password:
            return render_template("/failed.html", message="Password didn't confirme")
        try:
            cursor.execute("INSERT INTO users (username, hash) values (?, ?)", 
            (username, generate_password_hash(user_password)))
            db.commit()
            return render_template("success.html")
        except:
            return render_template("failed.html", message='This username already exist')
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol_of_stocks = request.form.get("symbol")
        try:
            volume_to_sell = int(request.form.get("volume"))
            if volume_to_sell <= 0:
                return render_template("failed.html", message="Number must be positive")
        except ValueError:
            return render_template("failed.html", message="You must give volume as number")
        info_about_stocks = lookup(symbol_of_stocks)
        if not info_about_stocks:
            return render_template('failed.html', message="You type incorrect symbol")
        try:
            user_symbol_of_stocks = cursor.execute("SELECT volume FROM user_stocks WHERE name_of_stocks=? AND id=?", 
            (info_about_stocks["name"], session["user_id"])).fetchall()[0][0]# respone is something like [(number,)] and i want grab number
        except IndexError:
            return render_template("failed.html", message="First you must buy a stocks")
        print(user_symbol_of_stocks)
        if user_symbol_of_stocks:
            if user_symbol_of_stocks >= volume_to_sell:
                user_symbol_of_stocks -= volume_to_sell
                current_balance = cursor.execute("SELECT cash FROM users WHERE id=?", (session["user_id"],)).fetchall()[0][0]
                current_balance += volume_to_sell * info_about_stocks["price"]
                cursor.execute('UPDATE users SET cash=? WHERE id=?', (current_balance, session["user_id"]))
                db.commit()
                cursor.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?)", 
                (session["user_id"], info_about_stocks["name"], volume_to_sell, volume_to_sell * info_about_stocks['price'], 
                current_balance, asctime(), "sell"))
                db.commit()
                cursor.execute("UPDATE user_stocks SET volume=? WHERE id=? AND name_of_stocks=?", 
                (user_symbol_of_stocks, session["user_id"], info_about_stocks["name"]))
                db.commit()
                return render_template("success.html")
            else:
                return render_template("failed.html", message=f"You haven't {info_about_stocks['name']} stocks")
        else:
            pass
    return render_template("selling.html")

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        user_password = request.form.get("c_password")
        if not user_password:
            return render_template("failed.html", message="must provide current password")
        user_new_password = request.form.get("n_password")
        if not user_new_password:
            return render_template("failed.html", message="must provide new password")
        user_confirm_password = request.form.get("confimator")
        if not user_confirm_password:
            return render_template("failed.html", message="must confirm password")
        if user_confirm_password != user_new_password:
            return render_template("failed.html", message="You didn't confirm new password")
        current_hash = cursor.execute("SELECT hash FROM users WHERE id=?", (session["user_id"],)).fetchall()[0][0] # respone like [(hash,)]
        if not check_password_hash(current_hash, user_password):
            return render_template("failed.html", message="You typed another password")
        cursor.execute("UPDATE users SET hash=? WHERE id=?", (generate_password_hash(user_new_password), session["user_id"]))
        db.commit()
        return render_template("success.html")
    return render_template("change_password.html")