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
                        datetime_obj = datetime.strptime(datetime_str, '%d. %b %H:%M').replace(year=1900)
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

# Функция для создания графика
def create_plot(df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['Datetime'], 
        y=df['Price [EUR]'], 
        mode='lines+markers',
        name='Price [EUR]'
    ))

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

    table_html = df.to_html(index=False)

    dates = df['Datetime'].dt.strftime('%d %b %H:%M').unique()

    graph_html = create_plot(df)

    return render_template_string("""
        <html>
        <head>
            <title>Electricity Prices</title>
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <style>
                .container {
                    display: flex;
                    justify-content: space-around;
                    align-items: flex-start;
                }
                .table-container {
                    width: 18%;
                }
                .graph-container {
                    width: 82%;
                }
                .form-container {
                    margin-bottom: 15px;
                }
                .period-list {
                    margin-top: 10px;
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
                    
                    periods.push({start: start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + start.toLocaleDateString([], { day: '2-digit', month: 'short' }), stop: stop.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + stop.toLocaleDateString([], { day: '2-digit', month: 'short' })});
                    updatePeriodsList();
                    return false;
                }

                function updatePeriodsList() {
                    var periodList = document.getElementById('period-list');
                    periodList.innerHTML = '';

                    periods.forEach(function(period, index) {
                        var periodItem = document.createElement('li');
                        periodItem.innerHTML = "Start: " + period.start + ", Stop: " + period.stop + 
                                              " <button onclick='removePeriod(" + index + ")'>Remove</button>";
                        periodList.appendChild(periodItem);
                    });
                }

                function removePeriod(index) {
                    periods.splice(index, 1);
                    updatePeriodsList();
                }
            </script>
        </head>
        <body>
            <h1>DPils Energy</h1>
            <div class="form-container">
                <label for="heating-start">Heating Start:</label>
                <select id="heating-start">
                    {% for date in dates %}
                        <option value="{{ date }}">{{ date }}</option>
                    {% endfor %}
                </select>

                <label for="heating-stop">Heating Stop:</label>
                <select id="heating-stop">
                    {% for date in dates %}
                        <option value="{{ date }}">{{ date }}</option>
                    {% endfor %}
                </select>

                <button onclick="return validateDates()">Submit</button>

                <div class="period-list">
                    <h3>Selected Heating Periods:</h3>
                    <ul id="period-list"></ul>
                </div>
            </div>

            <button onclick="updateTable()">Update Prices</button>
            <p>Last updated: <span id="last-updated">{{ last_updated }}</span></p>
            <div class="container">
                <div class="table-container" id="table-container">
                    {{ table | safe }}
                </div>
                <div class="graph-container" id="graph-container">
                    {{ graph | safe }}
                </div>
            </div>
        </body>
        </html>
    """, table=table_html, graph=graph_html, last_updated=last_updated, dates=dates)

# Маршрут для обновления таблицы через AJAX
@app.route('/update_table', methods=['GET'])
def update_table():
    df = get_nordpool_data()
    last_updated = get_current_time()

    table_html = df.to_html(index=False)
    graph_html = create_plot(df)

    return jsonify({'table': table_html, 'graph': graph_html, 'last_updated': last_updated})

port = int(os.environ.get("PORT", 10000))
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)