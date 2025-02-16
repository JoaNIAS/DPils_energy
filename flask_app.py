import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from flask import Flask, render_template_string, jsonify
import plotly.graph_objs as go
import plotly.io as pio
import os

app = Flask(__name__)

# Функция для парсинга данных с Nordpool
def get_nordpool_data():
    data = []
    url = 'https://nordpool.didnt.work/'

    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Находим все даты
        dates = soup.find_all('span', class_='help')
        
        for date in dates:
            current_date = date.text.strip()
            print(f"Обрабатываю данные за {current_date}")

            # Находим таблицу с данными
            table = date.find_next('tbody')
            rows = table.find_all('tr', {'data-hours': True})

            for row in rows:
                time_range = row.find('th').text.strip()
                price_cell = row.find('td', class_='price')
                
                if price_cell:
                    price_text = price_cell.text.strip()
                    extra_decimals = price_cell.find('span', class_='extra-decimals')
                    
                    if extra_decimals:
                        price_text += extra_decimals.text.strip()
                    
                    try:
                        price = float(price_text.replace(',', '.'))
                    except ValueError:
                        print(f"Не удалось преобразовать цену: {price_text}")
                        continue

                    datetime_str = f"{current_date} {time_range.split('-')[0]}:00"
                    
                    try:
                        # Устанавливаем год на текущий, вместо 1900
                        current_year = datetime.now().year
                        datetime_obj = datetime.strptime(datetime_str, '%d. %b %H:%M').replace(year=current_year)
                    except ValueError:
                        print(f"Ошибка при преобразовании даты: {datetime_str}")
                        continue

                    data.append([datetime_obj, price])

        if data:
            df = pd.DataFrame(data, columns=['Datetime', 'Price [EUR]'])
            df['Price [EUR]'] = round(df['Price [EUR]'], 3)
            return df
        else:
            return pd.DataFrame(columns=['Datetime', 'Price [EUR]'])
    else:
        print("Ошибка при запросе данных", response.status_code)
        return pd.DataFrame(columns=['Datetime', 'Price [EUR]'])

import pandas as pd

def get_lowest_price_periods(df):
    if df.empty:
        return []
    
    df['Date'] = df['Datetime'].dt.date  # Создаем колонку 'Date' перед сортировкой
    df = df.sort_values(by=['Datetime', 'Date'])  # Сортируем по времени и дате по возрастанию
    df['Hour'] = df['Datetime'].dt.hour
    lowest_periods = []
    
    for date, group in df.groupby('Date'):
        # Исключаем периоды с 00:00 до 04:00
        filtered_group = group[group['Hour'] >= 4]
        
        if filtered_group.empty:
            continue
        
        max_price = filtered_group['Price [EUR]'].max()
        price_threshold = max_price * 0.7  # Устанавливаем пороговое значение
        
        sorted_group = filtered_group.sort_values(by='Price [EUR]')
        selected_periods = []
        
        for _, row in sorted_group.iterrows():
            stop_time = row['Datetime'] + pd.Timedelta(hours=1)
            stop_row = sorted_group[sorted_group['Datetime'] == stop_time]
            
            if not stop_row.empty:
                stop_price = stop_row.iloc[0]['Price [EUR]']
                
                if row['Price [EUR]'] < price_threshold and stop_price < price_threshold:
                    if not selected_periods or all(abs((row['Datetime'] - p['start']).total_seconds()) >= 14400 for p in selected_periods):
                        if stop_price <= row['Price [EUR]'] * 1.2:  # Оба периода должны иметь низкие цены
                            selected_periods.append({
                                'start': row['Datetime'],
                                'stop': stop_time
                            })
                
            if len(selected_periods) == 3:
                break
        
        lowest_periods.extend(selected_periods)
    
    return [{'start': p['start'].strftime('%H:%M %d %b'), 'stop': p['stop'].strftime('%H:%M %d %b')} for p in lowest_periods]



# Функция для создания графика
def create_plot(df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['Datetime'], 
        y=df['Price [EUR]'], 
        mode='lines+markers',
        name='Price [EUR]'
    ))

    if not df.empty:
        last_datetime = df['Datetime'].iloc[-1]
        last_price = df['Price [EUR]'].iloc[-1]
        
        fig.add_annotation(
            x=last_datetime,
            y=last_price,
            text=f"{last_price} EUR",
            showarrow=True,
            arrowhead=1
        )
    
    fig.update_layout(
        title="Electricity Prices Over Time",
        xaxis_title="Datetime",
        yaxis_title="Price [EUR]",
        xaxis=dict(tickformat='%d %b %H:%M', tickangle=45),
        hovermode="x unified", 
        height=600
    )

    graph_html = pio.to_html(fig, full_html=False)
    return graph_html

# Функция для получения текущего времени
def get_current_time():
    return datetime.now().strftime('%d %b %H:%M')

# Маршрут для отображения таблицы и графика
@app.route('/')
def show_table():
    df = get_nordpool_data()
    last_updated = get_current_time()

    # Добавляем классы Bootstrap к таблице для красивого вида
    table_html = df.to_html(classes='table table-striped table-bordered', index=False)

    dates = df['Datetime'].dt.strftime('%d %b %H:%M').unique() if not df.empty else []
    get_lowest_price_periods

    graph_html = create_plot(df)

    # Используем Bootstrap и собственный CSS
    return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Electricity Prices</title>
            <!-- Bootstrap CSS -->
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <style>
                body {
                    margin: 20px;
                }
                h1 {
                    margin-bottom: 30px;
                    text-align: center;
                }
                .form-container {
                    margin-bottom: 30px;
                    border: 1px solid #dee2e6;
                    padding: 20px;
                    border-radius: 5px;
                    background-color: #f8f9fa;
                }
                .period-list {
                    margin-top: 20px;
                }
                .table-container, .graph-container {
                    margin-top: 20px;
                }
                .update-btn {
                    margin-right: 10px;
                }
                .annotation {
                    font-size: 0.9rem;
                }
            </style>
            <script type="text/javascript">
                var periods = [];

                function updateTable() {
                    $.ajax({
                        url: '/update_table',
                        type: 'GET',
                        success: function(data) {
                            $('#table-container').html(data.table);
                            $('#graph-container').html(data.graph);
                            $('#last-updated').html(data.last_updated);
                        },
                        error: function() {
                            alert('Error updating table');
                        }
                    });
                }

                function validateDates() {
                    var start = new Date(document.getElementById('heating-start').value);
                    var stop = new Date(document.getElementById('heating-stop').value);

                    if (stop < start) {
                        alert("Heating Stop must be later than Heating Start");
                        return false;
                    }
                    
                    periods.push({
                        start: start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + 
                               start.toLocaleDateString([], { day: '2-digit', month: 'short' }),
                        stop:  stop.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + 
                               stop.toLocaleDateString([], { day: '2-digit', month: 'short' })
                    });
                    updatePeriodsList();
                    return false;
                }

                function updatePeriodsList() {
                    var periodList = document.getElementById('period-list');
                    periodList.innerHTML = '';

                    periods.forEach(function(period, index) {
                        var periodItem = document.createElement('li');
                        periodItem.innerHTML = "Start: " + period.start + ", Stop: " + period.stop + 
                                              " <button class='btn btn-sm btn-danger' onclick='removePeriod(" + index + ")'>Remove</button>";
                        periodList.appendChild(periodItem);
                    });
                }

                function removePeriod(index) {
                    periods.splice(index, 1);
                    updatePeriodsList();
                }
            </script>
        </head>
        <body class="container">
            <h1>DPils Energy</h1>

            <div class="form-container">
                <div class="row mb-3">
                    <div class="col-md-6">
                        <label for="heating-start" class="form-label">Heating Start:</label>
                        <select id="heating-start" class="form-select">
                            {% for date in dates %}
                                <option value="{{ date }}">{{ date }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label for="heating-stop" class="form-label">Heating Stop:</label>
                        <select id="heating-stop" class="form-select">
                            {% for date in dates %}
                                <option value="{{ date }}">{{ date }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <button class="btn btn-primary" onclick="return validateDates()">Submit</button>

                <div class="period-list">
                    <h3>Selected Heating Periods:</h3>
                    <ul id="period-list"></ul>
                </div>
                
                <div class="lowest-periods">
                    <h3>Recommended Low Price Periods:</h3>
                    <ul id="lowest-period-list">
                        {% for period in lowest_price_periods %}
                            <li class="low-price-period">
                                Start: {{ period.start }}, Stop: {{ period.stop }}
                            </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>

            <div class="mb-3">
                <button class="btn btn-success update-btn" onclick="updateTable()">Update Prices</button>
                <span class="annotation">Last updated: <span id="last-updated">{{ last_updated }}</span></span>
            </div>

            <div class="row">
                <div class="col-lg-4 table-container" id="table-container">
                    {{ table|safe }}
                </div>
                <div class="col-lg-8 graph-container" id="graph-container">
                    {{ graph|safe }}
                </div>
            </div>
        </body>
        </html>
    """, table=table_html, graph=graph_html, last_updated=last_updated, dates=dates, lowest_price_periods=get_lowest_price_periods(df))

# Маршрут для обновления таблицы через AJAX
@app.route('/update_table', methods=['GET'])
def update_table():
    df = get_nordpool_data()
    last_updated = get_current_time()

    # Оформляем таблицу с классами Bootstrap
    table_html = df.to_html(classes='table table-striped table-bordered', index=False)
    graph_html = create_plot(df)

    return jsonify({'table': table_html, 'graph': graph_html, 'last_updated': last_updated})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

