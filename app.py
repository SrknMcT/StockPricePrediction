from flask import Flask, render_template, request, jsonify,Response
from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth
from flask_jwt_extended import create_access_token
from flask_jwt_extended import JWTManager

import io, psycopg2, os
import pandas as pd
import numpy as np
import margo_loader
import requests

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED

import finance_db
import stockprices_data as sp

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
auth = HTTPBasicAuth()

app_settings = os.getenv(
    'APP_SETTINGS',
    'config.DevelopmentConfig'
)
app.config.from_object(app_settings)

db = SQLAlchemy(app)

from db_models import Alert

USER_DATA = {
    "uysm": "pecnet",
}

set_parameter=True

jwt = JWTManager(app)


@app.route("/login", methods=["POST"])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)

    if not username or not password:
        return jsonify({'message': 'Username and password are required.'}), 400

    # Fetch username and password from the database
    with psycopg2.connect(finance_db.db_url) as db_conn:
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            result = cursor.fetchone()

    if not result or result[1] != password:
        return jsonify({'message': 'Invalid username or password.'}), 401

    access_token = create_access_token(identity={"username": username, "id": result[0]})
    return jsonify(access_token=access_token)

@auth.verify_password
def verify(username, password):
   if not (username and password):
       return False
   return USER_DATA.get(username) == password

@app.route('/plot/<type>')
def plot_png(type):
    if type=='real':
        data = plot_real_data()
    else:
        data = plot_prediction_data()
    output = io.BytesIO()
    FigureCanvas(data).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

def plot_real_data():
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)

    axis.set_ylabel('ClosePrice ($)', fontsize=16)
    axis.set_title("StockPrices", fontsize=16)

    for ticker in sp.ticker_list:
        axis.plot(sp.all_data[ticker].index, sp.all_data[ticker]["adj_close_price"], label=ticker)

    axis.legend()
    return fig


def plot_prediction_data():
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)

    axis.set_ylabel('Prediction ($)', fontsize=16)
    axis.set_title("StockPrices", fontsize=16)

    for ticker in sp.ticker_list:
        axis.plot(sp.all_data[ticker].index, sp.all_data[ticker]["predicted_price"], label=ticker)

    axis.legend()
    return fig

@app.get("/")
def home():
    table= sp.get_prediction_df().to_html()
    return render_template('template.html', table=table)

@app.get("/finance/<string:ticker>")
@auth.login_required
def get_predictions(ticker):
    return jsonify({"predictionset":finance_db.get_predictions_from_db(ticker)})


@app.get("/finance/<string:ticker>/<string:pdate>")
@auth.login_required
def get_prediction(ticker,pdate):
    return jsonify({"predictionset":finance_db.get_predictions_from_db(ticker,pdate)})


@app.get("/finance/<string:ticker>/start=<string:dateStart>&end=<string:dateEnd>")
@auth.login_required
def get_predictions_by_range(ticker,dateStart,dateEnd):
    return jsonify({"predictionset":finance_db.get_predictions_from_db(ticker,dateStart,dateEnd)})

def send_notifications():
    table = sp.get_prediction_df()
    for ticker in table.index:
        _, close, prediction, _ = table.loc[ticker]
        if not np.isnan(close) and not np.isnan(prediction):
            process(ticker, close, prediction)


def update_predictions():
    global set_parameter
    if(set_parameter):
        scheduler = BackgroundScheduler()
        scheduler.add_job(sp.get_predictions_and_save, 'interval' , minutes = 2)
        scheduler.add_job(send_notifications, 'interval', minutes=1)
        scheduler.start()
        set_parameter=False

update_predictions()

def process(ticker, close, prediction):
    print('processing', ticker, close, prediction)

    with app.app_context():
        alerts = db.session.query(Alert).all()
        val = abs((close - prediction) / close)
        for alert in alerts:
            print(f'percentage: {alert.percentage}, value={val}')
            if val >= alert.percentage and alert.ticker == ticker:
                print(f'need to send alert for {ticker} {val} {alert.percentage}')
                requests.post(alert.callback_url, json={'ticker': ticker, 'close': close, 'prediction': prediction})

from api import api as api_blueprint
app.register_blueprint(api_blueprint)

