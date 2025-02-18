from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from io import StringIO
import pandas as pd
from sqlalchemy.sql import text

app = Flask(__name__)
uri = 'sqlite:///mydatabase.db'
app.config['SQLALCHEMY_DATABASE_URI'] = uri

db = SQLAlchemy(app)

@app.route('/get_office_1', methods=['GET'])
def get_office_1():
    query = """SELECT name, id, address_name, price_limit, `Европейская кухня`,
                    `Паназиатская кухня`, `Русская кухня`, `Американская кухня`,
                    `Грузинская кухня`, `Постное меню`, `Вегетарианское меню`,
                    price_limit, office_1_time,  reviews_general_rating, reviews_general_review_count FROM Place WHERE near_office_1=TRUE"""
    df = pd.read_sql(query, db.engine)
    return df.to_csv()
    
@app.route('/get_office_2', methods=['GET'])
def get_office_2():
    query = """SELECT name, id, address_name, price_limit, `Европейская кухня`,
                    `Паназиатская кухня`, `Русская кухня`, `Американская кухня`,
                    `Грузинская кухня`, `Постное меню`, `Вегетарианское меню`,
                    price_limit, office_2_time,  reviews_general_rating, reviews_general_review_count FROM Place WHERE near_office_2=TRUE"""
    df = pd.read_sql(query, db.engine)
    return df.to_csv()

@app.route('/get_office_3', methods=['GET'])
def get_office_3():
    query = """SELECT name, id, address_name, price_limit, `Европейская кухня`,
                    `Паназиатская кухня`, `Русская кухня`, `Американская кухня`,
                    `Грузинская кухня`, `Постное меню`, `Вегетарианское меню`,
                    price_limit, office_3_time,  reviews_general_rating, reviews_general_review_count FROM Place WHERE near_office_3=TRUE"""
    df = pd.read_sql(query, db.engine)
    return df.to_csv()


def preprocess_csv(csv_data):
    required_columns = required_columns = ['name', 'id', 'address_name', 'Европейская кухня',
                    'Паназиатская кухня', 'Русская кухня', 'Американская кухня',
                    'Грузинская кухня', 'Постное меню', 'Вегетарианское меню',
                    'Average bill', 'point_lat', 'point_lon',
                    'near_office_1', 'near_office_2', 'near_office_3',
                    'office_1_time', 'office_2_time', 'office_3_time',
                    'reviews_general_review_count', 'reviews_general_rating']
    csv_file = StringIO(csv_data)
    df = pd.read_csv(csv_file)
    df['near_office_1'] = df['near_office_1'].fillna(False)
    df['near_office_2'] = df['near_office_2'].fillna(False)
    df['near_office_3'] = df['near_office_3'].fillna(False)
    df = df[required_columns]
    df = df.dropna(subset=required_columns)
    df = df.rename(columns={'Cuisine':'wanted_cuisines', 'Average bill': 'price_limit'})
    df.to_sql('Place', db.engine)

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    with app.app_context():
        db.session.execute(text('DROP TABLE IF EXISTS Place;'))
        db.session.commit()
    file = request.files.get('data')
    csv_data = file.read().decode('utf-8')
    preprocess_csv(csv_data)
    return "Данные из CSV успешно добавлены в базу данных.", 200

@app.route('/places')
def get_places():
    query = "SELECT name, address_name FROM Place"
    df = pd.read_sql(query, db.engine)
    print(df['name'])
    return df.to_csv()

@app.route('/hello', methods=['POST'])
def hello():
    return 'hello'

@app.route('/')
def index_page():
    return 'hello'

if __name__ == '__main__':
    app.run(debug=True)