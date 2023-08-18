from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from . import api
from app import db
from db_models import Alert
from sqlalchemy import exc
import numpy as np
import margo_loader
import stockprices_data as sp


def convert_nan2none(value):
    return None if np.isnan(value) else value

def get_first_and_last_day(ticker):
    first_date = sp.all_data[ticker].index[0]
    last_date = sp.all_data[ticker].index[-2]
    return first_date, last_date

def get_nth_value_and_prediction(ticker, n):
    r = sp.all_data[ticker].iloc[n-1].adj_close_price, sp.all_data[ticker].iloc[n-2].predicted_price
    return map(convert_nan2none, r)


@api.route('/stocks/')
@api.route('/stocks/<string:ticker>/')
def stocks(ticker=None):
    tickers = sp.all_data.keys() if ticker is None else [ticker]
    data = {}
    for ticker in tickers:
        first, last = get_first_and_last_day(ticker)
        tv, tp = get_nth_value_and_prediction(ticker, -1)
        yv, yp = get_nth_value_and_prediction(ticker, -2)
        lwv, lwp = get_nth_value_and_prediction(ticker, -8)
        lmv, lmp = get_nth_value_and_prediction(ticker, -31)
        data[ticker] = {
            'name': ticker,
            'firstDate': str(first),
            'lastDate': str(last),
            'todayValue': tv,
            'todayPred': tp,
            'yesterdayValue': yv,
            'yesterdayPred': yp,
            'lastWeekValue': lwv,
            'lastWeekPred': lwp,
            'lastMonthValue': lmv,
            'lastMonthPred': lmp}

    return jsonify(data[ticker]) if len(tickers) == 1 else jsonify(data)

@api.route('/stocks/predictions/')
@api.route('/stocks/predictions/<string:ticker>/')
def predictions(ticker=None):
    tickers = sp.all_data.keys() if ticker is None else [ticker]
    data = {}
    for ticker in tickers:
        df = sp.all_data[ticker][['adj_close_price', 'predicted_price']]
        df = df.rename(columns={'adj_close_price': 'value', 'predicted_price': 'prediction'})
        df = df.reset_index(names=['date']).replace({np.nan: None})
        data[ticker] = df.transpose().to_dict()

    return data[ticker] if len(tickers) == 1 else data


@api.route("/users/stock/notifications", methods=["GET","POST", "DELETE"])
@jwt_required()
def set_notification():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    userid = current_user['id']
    username = current_user['username']

    percentage = request.json['percentage']
    ticker = request.json['ticker'].upper()
    callback_url = request.json['callback_url']
    if request.method == "GET":
        alerts = db.session.query(Alert).all()

        # convert alerts to list of dictionaries
        alerts_dict = [alert.__dict__ for alert in alerts]
        for alert in alerts_dict:
            del alert['_sa_instance_state']

        # return alerts as JSON response
        return jsonify(alerts_dict)
    elif request.method == 'POST':
        new_alert = Alert(userid=userid, percentage=percentage, ticker=ticker, callback_url=callback_url)
        try:
            db.session.add(new_alert)
            db.session.commit()
        except exc.IntegrityError as e:
            return jsonify({'error': f'User \'{username}\' already have a notification set for \'{ticker}\''}), 400
        except exc.DataError as e:
            return jsonify({'error': str(e.orig)}), 400
        else:
            new_alert_dict = new_alert.__dict__
            del new_alert_dict['_sa_instance_state']
            return jsonify(new_alert_dict)
    else:
        alert = db.session.query(Alert).filter_by(userid=userid, ticker=ticker).first()
        # if alert exists, delete it and commit changes
        if alert is not None:
            db.session.delete(alert)
            db.session.commit()

            # return success message as JSON response
            return jsonify({'message': 'Notification deleted successfully'})
        else:
            return jsonify({'error': 'Notification not found'}), 404
