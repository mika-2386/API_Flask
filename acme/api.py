import os
import pandas as pd
import psycopg2
import io
import matplotlib.pyplot as plt

from flask import Flask, request, render_template, send_file, session
from werkzeug.utils import redirect


app = Flask(__name__)

db_params = {}
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://mihail:Qwerty12345@localhost:5432/data_flask'


#  Куда сохраняем
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#для хранения данных
analyze_results_upload = {}
name_column_upload = {}

# Загрузка и сохранение в uploaded
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        filename = f.filename
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        f.save(save_path)
        df = pd.read_csv(save_path)
        # print("Колонки файла:", df.columns.tolist())
        name_column = df.columns.tolist()
        name_column_upload[filename] = name_column
        # print(f'name_column_upload: {name_column_upload}')
    return redirect('/')

# удаление
@app.route ('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    os.remove(os.path.join(UPLOAD_FOLDER, filename))
    return redirect ('/')

# параметры БД
@app.route('/set_params', methods=['POST'])
def set_params():
    global db_params
    db_params['host'] = request.form['host']
    db_params['port'] = request.form['port']
    db_params['database'] = request.form['database']
    db_params['user'] = request.form['user']
    db_params['password'] = request.form['password']
    db_params['table_name'] = request.form['table_name']
    return redirect('/')
# Работа с БД
@app.route('/download_table')
def download_table():
    try:
        if not db_params:
            return "Параметры на подключение не введены"
        # подключение
        conn = psycopg2.connect(
            host=db_params['host'],
            port=db_params['port'],
            database=db_params['database'],
            user=db_params['user'],
            password=db_params['password']
        )

        # чтение таблицы
        table_name = db_params['table_name']  # название таблицы
        query = f"SELECT * FROM {table_name};"
        df = pd.read_sql_query(query, conn)
        conn.close()

        # сохранение в CSV
        filename = f'load_{table_name}.csv'
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        df.to_csv(save_path, index=False)
        name_column = df.columns.tolist()
        name_column_upload[filename] = name_column
        # print(f'name_column_DB: {name_column_upload}')

        return redirect('/')
    except Exception as e:
        return f"Ошибка: {str(e)}"


@app.route('/analyze/<filename>')
def analyze_salary(filename):
    table_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(table_path):
        return f"Table {filename} not found "
    df = pd.read_csv(table_path)
    column = request.args.get('column')
    # print(f'name_column_analyze: {column}')

    if not column:
        return f"Пожалуйста, выберите колонку для анализа"


    try:
        mean = df[column].mean()
        median = df[column].median()
        # print(f'name_column_upload_1: {name_column_upload}')
        if 'id' in name_column_upload[filename]:
            correlation = df[['id', column]].corr().iloc[0, 1]
            analyze_results_upload_local = {
                'column': column,
                'mean': round(mean, 2),
                'median': round(median, 2),
                'correlation': round(correlation, 2),
            }

        else:
            analyze_results_upload_local = {
                'column': column,
                'mean': round(mean, 2),
                'median': round(median, 2),
                'correlation': 'нет данных',
            }

        analyze_results_upload[filename] = analyze_results_upload_local

        return redirect('/')

    except Exception as e:
        return f"Ошибка при анализе модели {filename}: {str(e)}"


@app.route('/plot/<filename>')
def plot_graphic(filename):
    # Получение данных из базы
    table_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(table_path):
        return f"Table {filename} not found "
    df = pd.read_csv(table_path)
    col1 = request.args.get('column1')
    col2 = request.args.get('column2')

    # Построение графика
    plt.figure(figsize=(8,6))
    plt.scatter (df[col1], df[col2])
    print (f' {col1} and {col2} have been plotted')

    # Добавляем автоматическую подгонку и наклон подписей
    plt.title(f'{col1} vs {col2}', fontsize=14)
    plt.xlabel(col1, fontsize=12)
    plt.ylabel(col2, fontsize=12)

    plt.tight_layout()
    plt.xticks(rotation=45)

    # plt.title(f'{col1} vs {col2}')
    # plt.ylabel(col1)
    # plt.xlabel(col2)


    # Сохраняем график в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='jpg')
    plt.close()  # закрываем фигуру
    buf.seek(0)

    # Отправляем изображение клиенту
    return send_file(buf, mimetype='image/jpg')


@app.route('/clean_data/<filename>', methods=['POST'])
def clean_data(filename):
    table_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(table_path):
        return f"Файл {filename} не найден"

    # Загружаем данные
    df = pd.read_csv(table_path)

    # Удаление дубликатов
    df = df.drop_duplicates()

    # Заполнение пропусков - пустыми строками для всех колонок
    for col in df.columns:
        df[col] = df[col].fillna('')

    # Сохраняем обратно
    df.to_csv(table_path, index=False)

    return redirect(f'/')  # возвращаем на главную страницу


# -стартовая страница
@app.route('/', methods=['GET'])
def index():
    # отображение списка скаченных файлов
    files = os.listdir(UPLOAD_FOLDER)

    return render_template(template_name_or_list='base.html',
                           files=files,
                           name_column_upload=name_column_upload,
                           analyze_results_upload = analyze_results_upload
                           )