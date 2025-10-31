"""
Volga Vibes - Backend API
Веб-приложение для построения прогулочных маршрутов по Нижнему Новгороду
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from openai import OpenAI
from geopy.distance import geodesic
import math
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Загружаем конфигурацию
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Инициализируем OpenAI клиент для Chutes API
client = OpenAI(
    base_url=config['api']['chutes_base_url'],
    api_key=os.getenv('CHUTES_API_TOKEN')
)

# Загружаем данные о местах
def load_places():
    """Загружает места из Excel файла"""
    import openpyxl
    import re
    wb = openpyxl.load_workbook('nn.xlsx')
    sheet = wb.active
    
    places = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0] and row[1] and row[2]:
            try:
                # Извлекаем координаты из формата POINT (lon lat)
                coords_str = str(row[2]).replace('POINT (', '').replace(')', '')
                lon, lat = map(float, coords_str.split())
                
                # Формируем название из адреса (убираем "Нижний Новгород, ")
                address = str(row[1]) if row[1] else ''
                name = address.replace('Нижний Новгород, ', '').replace('г. Нижний Новгород, ', '')
                
                # Если в описании есть более конкретное название, используем его
                description = str(row[3]) if len(row) > 3 and row[3] else ''
                
                places.append({
                    'id': int(row[0]),
                    'name': name,
                    'address': address,
                    'lat': lat,
                    'lon': lon,
                    'description': description
                })
            except Exception as e:
                print(f"Ошибка обработки места ID {row[0]}: {e}")
                continue
    
    print(f"Загружено {len(places)} мест")  # Отладка
    return places

PLACES = load_places()

def calculate_distance(lat1, lon1, lat2, lon2):
    """Вычисляет расстояние между двумя точками в километрах"""
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers

def filter_places_by_radius(user_lat, user_lon, radius_km):
    """Фильтрует места по радиусу от пользователя"""
    filtered = []
    for place in PLACES:
        distance = calculate_distance(user_lat, user_lon, place['lat'], place['lon'])
        if distance <= radius_km:
            filtered.append({**place, 'distance_from_user': distance})
    
    # Сортируем по расстоянию (ближайшие первыми)
    filtered.sort(key=lambda x: x['distance_from_user'])
    
    print(f"Фильтрация: найдено {len(filtered)} мест в радиусе {radius_km} км")
    if filtered:
        print(f"  Ближайшее: {filtered[0]['name']} ({filtered[0]['distance_from_user']:.2f} км)")
        print(f"  Дальнее: {filtered[-1]['name']} ({filtered[-1]['distance_from_user']:.2f} км)")
    
    return filtered

def filter_diverse_places(places, min_distance_km=0.3):
    """
    Фильтрует места чтобы они были на достаточном расстоянии друг от друга.
    Гарантирует разнообразие локаций.
    """
    if not places:
        return []
    
    diverse_places = [places[0]]  # Всегда берём первое (ближайшее)
    
    for place in places[1:]:
        # Проверяем что это место достаточно далеко от уже выбранных
        is_diverse = True
        for selected in diverse_places:
            distance = calculate_distance(
                place['lat'], place['lon'],
                selected['lat'], selected['lon']
            )
            if distance < min_distance_km:
                is_diverse = False
                print(f"  Пропускаем {place['name']} - слишком близко к {selected['name']} ({distance:.2f} км)")
                break
        
        if is_diverse:
            diverse_places.append(place)
    
    print(f"Диверсификация: осталось {len(diverse_places)} из {len(places)} мест (мин. расстояние {min_distance_km} км)")
    return diverse_places

def build_route(places_list, return_to_start=False):
    """Строит оптимальный маршрут через места (упрощенный алгоритм ближайшего соседа)"""
    if not places_list:
        return []
    
    route = [places_list[0]]
    remaining = places_list[1:]
    
    while remaining:
        last_place = route[-1]
        # Находим ближайшее место
        nearest = min(remaining, key=lambda p: calculate_distance(
            last_place['lat'], last_place['lon'], p['lat'], p['lon']
        ))
        route.append(nearest)
        remaining.remove(nearest)
    
    return route

@app.route('/')
def index():
    """Главная страница"""
    return send_from_directory('static', 'index.html')

@app.route('/api/config')
def get_config():
    """Возвращает публичную конфигурацию"""
    return jsonify({
        'app_name': config['app_name'],
        'privacy_policy_url': config['privacy_policy_url'],
        'map': config['map'],
        'walk_settings': config['walk_settings']
    })

@app.route('/api/generate-route', methods=['POST'])
def generate_route():
    """
    Генерирует персонализированный маршрут на основе предпочтений пользователя
    """
    try:
        data = request.json
        user_name = data.get('name', 'Гость')
        user_age = data.get('age', 25)
        interests = data.get('interests', '')
        user_lat = data.get('latitude', config['map']['default_center'][0])
        user_lon = data.get('longitude', config['map']['default_center'][1])
        duration_hours = data.get('duration', config['walk_settings']['duration']['default'])
        radius_km = data.get('radius', config['walk_settings']['radius']['default'])
        places_count = data.get('places_count', config['walk_settings']['places_count']['default'])
        return_to_start = data.get('return_to_start', False)
        
        # Фильтруем места по радиусу
        nearby_places = filter_places_by_radius(user_lat, user_lon, radius_km)
        
        # Применяем фильтр разнообразия - места должны быть на расстоянии минимум 300м друг от друга
        diverse_places = filter_diverse_places(nearby_places, min_distance_km=0.3)
        
        if len(diverse_places) < places_count:
            return jsonify({
                'error': f'В радиусе {radius_km} км найдено только {len(diverse_places)} разных мест (минимум 300м между ними). Увеличьте радиус поиска или уменьшите количество мест.'
            }), 400
        
        # Используем разнообразные места для дальнейшей обработки
        nearby_places = diverse_places
        
        # Формируем запрос к AI для выбора подходящих мест
        places_info = "\n\n".join([
            f"Место {i+1}: {p['name']}\n"
            f"Адрес: {p['address']}\n"
            f"Расстояние от пользователя: {p['distance_from_user']:.2f} км\n"
            f"Описание: {p['description'][:200]}..."
            for i, p in enumerate(nearby_places[:30])  # Ограничиваем для контекста
        ])
        
        prompt = f"""Ты - эксперт по туризму в Нижнем Новгороде. 

Пользователь: {user_name}, возраст {user_age} лет
Интересы: {interests}

Из следующего списка мест выбери РОВНО {places_count} самых подходящих для этого пользователя:

{places_info}

Верни ответ СТРОГО в формате JSON (без дополнительного текста):
{{
  "selected_places": [
    {{
      "place_name": "ТОЧНОЕ название места из списка выше (скопируй как есть)",
      "reason": "короткое объяснение на русском (2-3 предложения), почему это место подходит {user_name} с учетом интересов: {interests}"
    }},
    ... всего {places_count} мест
  ]
}}

КРИТИЧЕСКИ ВАЖНО: 
- Выбери РОВНО {places_count} места (НЕ меньше, НЕ больше!)
- Если в списке меньше {places_count} мест - выбери все доступные
- КОПИРУЙ названия мест ТОЧНО как в списке (после "Место N:")
- НЕ изменяй названия, НЕ добавляй "г. Нижний Новгород" и другие префиксы
- Объяснение должно быть персонализированным
- Верни ТОЛЬКО JSON, без markdown разметки и комментариев
- В массиве selected_places должно быть РОВНО {places_count} элементов
"""

        # Запрос к Chutes API
        completion = client.chat.completions.create(
            model=config['api']['model'],
            messages=[
                {
                    "role": "system",
                    "content": "Ты - профессиональный гид по Нижнему Новгороду. Отвечай на русском языке. Возвращай только валидный JSON без дополнительного текста."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        
        ai_response = json.loads(completion.choices[0].message.content)
        print(f"AI Response: получено {len(ai_response.get('selected_places', []))} мест")  # Отладка
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: AI должен вернуть РОВНО нужное количество мест
        if len(ai_response.get('selected_places', [])) < places_count:
            print(f"ВНИМАНИЕ: AI вернул только {len(ai_response['selected_places'])} мест вместо {places_count}")
            # Дополняем недостающие места
            missing_count = places_count - len(ai_response['selected_places'])
            for i, place in enumerate(nearby_places[:places_count]):
                if place['name'] not in [p['place_name'] for p in ai_response['selected_places']]:
                    ai_response['selected_places'].append({
                        'place_name': place['name'],
                        'reason': f"Это место находится рядом с вами и может быть интересно для посещения."
                    })
                    if len(ai_response['selected_places']) >= places_count:
                        break
        
        selected_place_names = {p['place_name']: p['reason'] for p in ai_response['selected_places'][:places_count]}
        print(f"Selected place names ({len(selected_place_names)}): {list(selected_place_names.keys())}")  # Отладка
        
        # Находим выбранные места (с гибким поиском)
        selected_places = []
        for place in nearby_places:
            # Ищем точное совпадение или частичное
            for ai_place_name, reason in selected_place_names.items():
                if (place['name'] == ai_place_name or 
                    ai_place_name in place['name'] or 
                    place['name'] in ai_place_name):
                    if place not in selected_places:  # Избегаем дублей
                        place['ai_reason'] = reason
                        selected_places.append(place)
                        print(f"Matched: {place['name']} with {ai_place_name}")  # Отладка
                        break
        
        print(f"Совпадений найдено: {len(selected_places)} из {len(nearby_places)} доступных")  # Отладка
        
        # Если не нашли достаточно мест через AI, берем из оставшихся разнообразных мест
        if len(selected_places) < places_count:
            print(f"Warning: AI выбрал только {len(selected_places)} мест, добавляем недостающие...")
            added = 0
            for place in nearby_places:
                if place not in selected_places:
                    # Проверяем что место достаточно далеко от уже выбранных
                    is_diverse = True
                    for selected in selected_places:
                        distance = calculate_distance(
                            place['lat'], place['lon'],
                            selected['lat'], selected['lon']
                        )
                        if distance < 0.3:  # 300 метров
                            is_diverse = False
                            break
                    
                    if is_diverse:
                        place['ai_reason'] = f"Это место находится рядом с вами и может быть интересно для посещения."
                        selected_places.append(place)
                        added += 1
                        print(f"  Добавлено: {place['name']} ({place['distance_from_user']:.2f} км от вас)")
                        
                    if len(selected_places) >= places_count:
                        break
            
            print(f"Добавлено дополнительных мест: {added}")
        
        # СТРОГО ограничиваем количество мест
        selected_places = selected_places[:places_count]
        print(f"ИТОГО: {len(selected_places)} мест выбрано для маршрута")  # Отладка
        
        # Проверка что у нас есть места
        if not selected_places:
            return jsonify({
                'error': 'Не удалось подобрать места. Попробуйте изменить радиус или интересы.'
            }), 400
        
        # Строим маршрут
        route = build_route(selected_places, return_to_start)
        print(f"Built route with {len(route)} places")  # Отладка
        
        # Вычисляем общее расстояние и время
        total_distance = 0
        for i in range(len(route) - 1):
            total_distance += calculate_distance(
                route[i]['lat'], route[i]['lon'],
                route[i+1]['lat'], route[i+1]['lon']
            )
        
        if return_to_start and route:
            total_distance += calculate_distance(
                route[-1]['lat'], route[-1]['lon'],
                route[0]['lat'], route[0]['lon']
            )
        
        # Примерная скорость ходьбы 4 км/ч + время на осмотр
        walking_time = total_distance / 4  # часы на ходьбу
        viewing_time = len(route) * 0.5  # 30 минут на каждое место
        estimated_time = walking_time + viewing_time
        
        print(f"Route stats: {total_distance:.2f} km, {estimated_time:.1f} hours")  # Отладка
        
        result = {
            'route': route,
            'total_distance_km': round(total_distance, 2),
            'estimated_time_hours': round(estimated_time, 1),
            'user_location': {
                'lat': user_lat,
                'lon': user_lon
            }
        }
        
        print(f"Returning result with {len(result['route'])} places")  # Отладка
        return jsonify(result)
        
    except Exception as e:
        print(f"Ошибка генерации маршрута: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/places')
def get_places():
    """Возвращает все доступные места"""
    return jsonify(PLACES)

if __name__ == '__main__':
    app.run(debug=True, port=8000)

