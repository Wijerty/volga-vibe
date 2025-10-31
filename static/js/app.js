/**
 * Volga Vibes - Frontend Application
 * JavaScript логика для работы приложения
 */

// Глобальные переменные
let config = {};
let userData = {
    name: '',
    age: null,
    interests: '',
    latitude: null,
    longitude: null,
    duration: 3,
    radius: 3,
    placesCount: 3,
    returnToStart: false
};
let map = null;
let markers = [];
let routeLine = null;

// Инициализация приложения
document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    initializeEventListeners();
});

// Загрузка конфигурации
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        config = await response.json();
        
        // Устанавливаем ссылку на политику конфиденциальности
        document.getElementById('privacy-link').href = config.privacy_policy_url;
        
        // Устанавливаем значения по умолчанию
        userData.duration = config.walk_settings.duration.default;
        userData.radius = config.walk_settings.radius.default;
        userData.placesCount = config.walk_settings.places_count.default;
        
    } catch (error) {
        console.error('Ошибка загрузки конфигурации:', error);
    }
}

// Инициализация обработчиков событий
function initializeEventListeners() {
    // Экран 2: Форма знакомства
    const nameInput = document.getElementById('user-name');
    const ageInput = document.getElementById('user-age');
    const introForm = document.getElementById('intro-form');
    const introNextBtn = document.getElementById('intro-next-btn');
    
    function checkIntroForm() {
        introNextBtn.disabled = !(nameInput.value.trim() && ageInput.value);
    }
    
    nameInput.addEventListener('input', checkIntroForm);
    ageInput.addEventListener('input', checkIntroForm);
    
    introForm.addEventListener('submit', (e) => {
        e.preventDefault();
        userData.name = nameInput.value.trim();
        userData.age = parseInt(ageInput.value);
        goToScreen('screen-interests');
    });
    
    // Экран 3: Форма интересов
    const interestsInput = document.getElementById('user-interests');
    const interestsForm = document.getElementById('interests-form');
    const interestsNextBtn = document.getElementById('interests-next-btn');
    const charCount = document.getElementById('char-count');
    
    interestsInput.addEventListener('input', () => {
        const length = interestsInput.value.length;
        charCount.textContent = length;
        interestsNextBtn.disabled = length < 10;
        
        if (length > 500) {
            interestsInput.value = interestsInput.value.substring(0, 500);
            charCount.textContent = 500;
        }
    });
    
    interestsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        userData.interests = interestsInput.value.trim();
        goToScreen('screen-settings');
        getUserLocation();
    });
    
    // Экран 4: Настройки прогулки
    const durationSlider = document.getElementById('duration-slider');
    const durationValue = document.getElementById('duration-value');
    const radiusSlider = document.getElementById('radius-slider');
    const radiusValue = document.getElementById('radius-value');
    const placesSelect = document.getElementById('places-select');
    const returnCheckbox = document.getElementById('return-checkbox');
    const settingsForm = document.getElementById('settings-form');
    
    durationSlider.addEventListener('input', () => {
        userData.duration = parseInt(durationSlider.value);
        durationValue.textContent = userData.duration;
    });
    
    radiusSlider.addEventListener('input', () => {
        userData.radius = parseFloat(radiusSlider.value);
        radiusValue.textContent = userData.radius;
    });
    
    placesSelect.addEventListener('change', () => {
        userData.placesCount = parseInt(placesSelect.value);
    });
    
    returnCheckbox.addEventListener('change', () => {
        userData.returnToStart = returnCheckbox.checked;
    });
    
    settingsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        generateRoute();
    });
}

// Переход между экранами
function goToScreen(screenId) {
    const screens = document.querySelectorAll('.screen');
    screens.forEach(screen => screen.classList.remove('active'));
    
    const targetScreen = document.getElementById(screenId);
    if (targetScreen) {
        targetScreen.classList.add('active');
        
        // Инициализируем карту при переходе на экран карты
        if (screenId === 'screen-map' && !map) {
            initMap();
        }
    }
}

// Получение геолокации пользователя
function getUserLocation() {
    const locationStatus = document.getElementById('location-status');
    
    if (!navigator.geolocation) {
        locationStatus.className = 'location-status error';
        locationStatus.innerHTML = '⚠️ Геолокация не поддерживается вашим браузером';
        // Используем координаты центра Нижнего Новгорода по умолчанию
        userData.latitude = config.map.default_center[0];
        userData.longitude = config.map.default_center[1];
        return;
    }
    
    navigator.geolocation.getCurrentPosition(
        (position) => {
            userData.latitude = position.coords.latitude;
            userData.longitude = position.coords.longitude;
            
            locationStatus.className = 'location-status success';
            locationStatus.innerHTML = '✓ Местоположение получено';
        },
        (error) => {
            console.error('Ошибка получения геолокации:', error);
            locationStatus.className = 'location-status error';
            locationStatus.innerHTML = '⚠️ Не удалось получить местоположение. Используем центр города.';
            
            // Используем координаты центра Нижнего Новгорода по умолчанию
            userData.latitude = config.map.default_center[0];
            userData.longitude = config.map.default_center[1];
        }
    );
}

// Инициализация карты
function initMap() {
    if (map) return;
    
    map = L.map('map').setView(config.map.default_center, config.map.default_zoom);
    
    L.tileLayer(config.map.tile_layer, {
        attribution: config.map.attribution,
        maxZoom: 19
    }).addTo(map);
}

// Генерация маршрута
async function generateRoute() {
    goToScreen('screen-map');
    showLoading(true);
    
    try {
        const response = await fetch('/api/generate-route', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка генерации маршрута');
        }
        
        const data = await response.json();
        displayRoute(data);
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при создании маршрута: ' + error.message);
        goToScreen('screen-settings');
    } finally {
        showLoading(false);
    }
}

// Отображение маршрута на карте
function displayRoute(routeData) {
    // Очищаем предыдущие маркеры и линии
    clearMap();
    
    const route = routeData.route;
    const userLocation = routeData.user_location;
    
    // Добавляем маркер пользователя
    const userIcon = L.divIcon({
        className: 'custom-marker user-marker',
        html: '<div>👤</div>',
        iconSize: [32, 32]
    });
    
    const userMarker = L.marker([userLocation.lat, userLocation.lon], {
        icon: userIcon,
        title: 'Ваше местоположение'
    }).addTo(map);
    
    markers.push(userMarker);
    
    // Добавляем маркеры мест
    const routeCoords = [];
    
    route.forEach((place, index) => {
        const icon = L.divIcon({
            className: `custom-marker ${index === 0 ? 'start-marker' : ''}`,
            html: `<div>${index + 1}</div>`,
            iconSize: [32, 32]
        });
        
        const marker = L.marker([place.lat, place.lon], {
            icon: icon,
            title: place.name
        }).addTo(map);
        
        marker.on('click', () => {
            highlightPlace(index);
            scrollToPlace(index);
        });
        
        markers.push(marker);
        routeCoords.push([place.lat, place.lon]);
    });
    
    // Строим ПЕШЕХОДНЫЙ маршрут между точками
    if (routeCoords.length >= 1) {
        // ВАЖНО: Начинаем маршрут от местоположения пользователя!
        const waypoints = [
            L.latLng(userLocation.lat, userLocation.lon), // Стартуем от пользователя
            ...routeCoords.map(coord => L.latLng(coord[0], coord[1])) // Затем все места
        ];
        
        // Если нужно вернуться к началу, добавляем местоположение пользователя в конец
        if (userData.returnToStart) {
            waypoints.push(L.latLng(userLocation.lat, userLocation.lon));
        }
        
        // Создаем роутер с пешеходным профилем
        routeLine = L.Routing.control({
            waypoints: waypoints,
            router: L.Routing.osrmv1({
                serviceUrl: 'https://router.project-osrm.org/route/v1',
                profile: 'foot' // ПЕШЕХОДНЫЙ маршрут
            }),
            lineOptions: {
                styles: [{
                    color: '#2563eb',
                    opacity: 0.8,
                    weight: 5
                }],
                addWaypoints: false
            },
            createMarker: function() { return null; }, // Не создаем дополнительные маркеры
            routeWhileDragging: false,
            show: false, // Скрываем панель инструкций
            addWaypoints: false,
            draggableWaypoints: false,
            fitSelectedRoutes: true
        }).addTo(map);
        
        // Центрируем карту на маршруте
        setTimeout(() => {
            const bounds = L.latLngBounds(routeCoords);
            map.fitBounds(bounds, { padding: [80, 80] });
        }, 500);
    }
    
    // Отображаем информацию о маршруте
    displayRouteInfo(routeData);
}

// Отображение информации о маршруте
function displayRouteInfo(routeData) {
    document.getElementById('total-distance').textContent = `${routeData.total_distance_km} км`;
    document.getElementById('total-time').textContent = `${routeData.estimated_time_hours} ч`;
    
    const placesList = document.getElementById('places-list');
    placesList.innerHTML = '';
    
    routeData.route.forEach((place, index) => {
        const placeCard = document.createElement('div');
        placeCard.className = 'place-card';
        placeCard.dataset.index = index;
        placeCard.onclick = () => {
            highlightPlace(index);
            if (markers[index + 1]) {
                map.setView([place.lat, place.lon], 16);
                markers[index + 1].openPopup();
            }
        };
        
        placeCard.innerHTML = `
            <div class="place-header">
                <span class="place-number">${index + 1}</span>
                <span class="place-name">${place.name}</span>
            </div>
            <div class="place-address">${place.address}</div>
            <div class="place-reason">
                <strong>Почему вам стоит посетить:</strong><br>
                ${place.ai_reason}
            </div>
        `;
        
        placesList.appendChild(placeCard);
    });
}

// Подсветка выбранного места
function highlightPlace(index) {
    const cards = document.querySelectorAll('.place-card');
    cards.forEach(card => card.classList.remove('active'));
    
    const selectedCard = document.querySelector(`.place-card[data-index="${index}"]`);
    if (selectedCard) {
        selectedCard.classList.add('active');
    }
}

// Прокрутка к месту в списке
function scrollToPlace(index) {
    const card = document.querySelector(`.place-card[data-index="${index}"]`);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// Очистка карты
function clearMap() {
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    if (routeLine) {
        // Если это Routing Control, удаляем его специальным образом
        if (routeLine.getPlan) {
            map.removeControl(routeLine);
        } else {
            map.removeLayer(routeLine);
        }
        routeLine = null;
    }
}

// Показ/скрытие панели маршрута
function toggleRoutePanel() {
    const panel = document.querySelector('.route-panel');
    const icon = document.getElementById('panel-toggle-icon');
    
    panel.classList.toggle('collapsed');
    icon.textContent = panel.classList.contains('collapsed') ? '▲' : '▼';
}

// Показ/скрытие overlay загрузки
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (show) {
        overlay.classList.remove('hidden');
    } else {
        overlay.classList.add('hidden');
    }
}

// Начать новый маршрут
function startNewRoute() {
    if (confirm('Вы уверены, что хотите создать новый маршрут?')) {
        // Очищаем данные
        userData = {
            name: '',
            age: null,
            interests: '',
            latitude: null,
            longitude: null,
            duration: config.walk_settings.duration.default,
            radius: config.walk_settings.radius.default,
            placesCount: config.walk_settings.places_count.default,
            returnToStart: false
        };
        
        // Очищаем форму
        document.getElementById('user-name').value = '';
        document.getElementById('user-age').value = '';
        document.getElementById('user-interests').value = '';
        document.getElementById('char-count').textContent = '0';
        document.getElementById('duration-slider').value = config.walk_settings.duration.default;
        document.getElementById('duration-value').textContent = config.walk_settings.duration.default;
        document.getElementById('radius-slider').value = config.walk_settings.radius.default;
        document.getElementById('radius-value').textContent = config.walk_settings.radius.default;
        document.getElementById('places-select').value = config.walk_settings.places_count.default;
        document.getElementById('return-checkbox').checked = false;
        
        // Очищаем карту
        if (map) {
            clearMap();
        }
        
        // Возвращаемся на первый экран
        goToScreen('screen-welcome');
    }
}

