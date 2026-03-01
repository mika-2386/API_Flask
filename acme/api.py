import os
import pandas as pd
import psycopg2
import io
import matplotlib.pyplot as plt

from flask import Flask, request, render_template, send_file, session
from werkzeug.utils import redirect
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)


db_params = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

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
        if not f:
            return 'Файл не найден', 400
        filename = f.filename
        # проверка формата
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ['.csv', '.xlsx', '.xls']:
            return 'Формат файла не поддерживается',415
        # cохраняем в папку
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        f.save(save_path)
        # читаем файл
        try:
            if ext == '.csv':
                df = pd.read_csv(save_path)
            else:
                df = pd.read_excel(save_path)
        except Exception:
            return "Ошибка при чтении файла", 400
        # вытаскивае колонки
        # print("Колонки файла:", df.columns.tolist())
        name_column = df.columns.tolist()
        #сохраняем глобально
        name_column_upload[filename] = name_column
        # print(f'name_column_upload: {name_column_upload}')
        return redirect('/')
    return render_template('base.html')

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
            return "Параметры на подключение не введены", 400
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
        if not table_name:
            return 'Не задано имя таблицы',400
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
        return f"Ошибка: {str(e)}", 500

@app.route('/save_table', methods=['GET', 'POST'])
def save_table():
    if request.method == 'POST':
        filename = request.form.get('filename')
        table_name = request.form.get('table_name')
        print(f'filename: {filename}, table_name: {table_name}')
        if not filename or not table_name:
            return "Файл для схранения не выбран", 400
        try:
            if not db_params:
                return "Параметры на подключение не введены", 400
        # подключение
            conn = psycopg2.connect(
                host=db_params['host'],
                port=db_params['port'],
                database=db_params['database'],
                user=db_params['user'],
                password=db_params['password']
            )

            cur = conn.cursor()
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            # Чтение файла
            ext = os.path.splitext(filename)[1].lower()
            if ext == '.csv':
                df = pd.read_csv(file_path)

            else:
                return "Формат файла не поддерживается", 415

                # Создаем таблицу, если не существует, с автоматическим определением типов
            columns_with_types = []
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_type = 'NUMERIC'
                elif pd.api.types.is_datetime64_any_dtype(df[col]):
                    col_type = 'TIMESTAMP'
                else:
                    col_type = 'TEXT'
                columns_with_types.append(f"{col} {col_type}")

            create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_with_types)});"
            cur.execute(create_table_query)
            conn.commit()

                # Очистка таблицы перед вставкой
            cur.execute(f"TRUNCATE TABLE {table_name};")
            conn.commit()

            buffer = io.StringIO()
            df.to_csv(buffer, index=False, header=False)
            buffer.seek(0)
            cur.copy_from(buffer, table_name, sep=',', null='')
            conn.commit()

            cur.close()
            conn.close()

            return f"Данные успешно сохранены в таблицу {table_name}"
        except Exception as e:
            return f"Ошибка: {str(e)}", 500
    return redirect('/')


@app.route('/analyze/<filename>')
def analyze_salary(filename):
    table_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(table_path):
        return f"Таблица {filename} не найдена", 400
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext == '.csv':
            df = pd.read_csv(table_path)
        else:
            df = pd.read_excel(table_path)
    except Exception:
        return "Ошибка при чтении файла", 400

    column = request.args.get('column')
    # print(f'name_column_analyze: {column}')

    if not column:
        return f"Пожалуйста, выберите колонку для анализа", 400
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
        return f"Ошибка при анализе модели {filename}: {str(e)}", 500


@app.route('/clean_data/<filename>', methods=['POST'])
def clean_data(filename):
    table_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(table_path):
        return f"Файл {filename} не найден", 400

    # Загружаем данные
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(table_path, dtype=str)
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(table_path, dtype=str)
        else:
            return "Формат файла не поддерживается", 415
    except Exception:
        return "Ошибка при чтении файла", 400

    # Обработка данных: замена запятых на точки внутри значений и преобразование в числа
    for col in df.columns:
        try:
            # Обрабатываем каждую ячейку
            def fix_number(val):
                val_str = str(val)
                val_str = val_str.replace(',', '.')
                return val_str

            df[col] = df[col].apply(fix_number)
            # Преобразуем в числовой тип с ошибками в NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
        except:
            pass

    # удаление дубликатов
    df = df.drop_duplicates()

    # Заполняем пропуски пустыми строками
    for col in df.columns:
        df[col] = df[col].fillna('')

    # Сохраняем обратно
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.csv':
        df.to_csv(table_path, index=False)
    else:
        df.to_excel(table_path, index=False)
    return redirect('/')


@app.route('/plot/<filename>', methods=['Get'])
def plot_graphic(filename):
    # Получение данных из базы
    table_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(table_path):
        return f"Таблица {filename} не найдена", 400
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
    # Сохраняем график в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='jpg')
    plt.close()  # закрываем фигуру
    buf.seek(0)
    # Отправляем изображение клиенту
    return send_file(buf, mimetype='image/jpg')


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
    app.run(debug=True)