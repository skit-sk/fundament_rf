# 📋 Структура шаблона card.html

## 1. Заголовок (строка 7)
```html
<h2>{{ obj.name }} <button onclick="refreshCard('{{ obj.id }}', this)" ...>🔄</button>
<span id="cardRefreshTimer"></span></h2>
```
- `{{ obj.name }}` - название объекта (напр ADA #9)
- Кнопка 🔄 для обновления
- `cardRefreshTimer` - отображение времени обновления в мс

---

## 2. Переменные (строки 9-12)
```jinja
{% set entry = obj.data.get('emoji_entry', {}) %}
{% set upd = obj.data.get('emoji_upd', {}) %}
{% set ohlc = obj.data.get('ohlc', {}) %}
{% set stats = obj.data.get('stats', {}) %}
```

---

## 3. Строка 1: emoji_entry (строки 15-26)
| Элемент | Значение | Описание |
|---------|-----------|-----------|
| 🏗️ | `entry.number` | номер сделки |
| 🚏 | `entry.symbol` | символ (ADA) |
| 🧾 | `entry.entry_price` | цена входа |
| 📆 | `entry.entry_date` | дата входа |
| 🕒 | `entry.entry_time` | дней в позиции |
| 🧱 | `entry.volume` | объём |
| 🫧 | `entry.pnl_percent` | % PnL (без leverage) |
| 🪙 | `entry.pnl_usdt` | PnL в USDT |
| 📦 | `entry.result` | 🟢/🔴 |
| ⬆️ | `obj.data.leverage` | плечо |

---

## 4. Строка 2: emoji_upd (строки 29-42)
| Элемент | Значение | Описание |
|---------|-----------|-----------|
| 🏗️ | `entry.number` | номер |
| 🚏 | `entry.symbol` | символ |
| 🧾 | `entry.entry_price` | цена входа |
| 📆 | `entry.entry_date` | дата входа |
| 🕒 | `upd.entry_time` | дней сейчас |
| 🧾 | `upd.current_price` | текущая цена |
| 📆 | `obj.data.chart_updated` | дата обновления |
| 🧱 | `entry.volume` | объём |
| 🫧 | `upd.pnl_percent` | % PnL (без leverage) |
| 🪙 | `upd.pnl_usdt` | PnL в USDT |
| 📦 | `upd.result` | 🟢/🔴 |
| ⬆️ | `leverage` | плечо |

---

## 5. График (строки 50-60)
- `chartContainer` - контейнер графика
- `loaderSpinner` - спиннер загрузки
- `loaderTimer` - время загрузки в мс
- `chartSummary` - сводка данных
- `canvas#chart` - холст графика

---

## 6. JavaScript (строки 240-279)

### load() - загрузка данных
```javascript
async function load() {
    // Запрос к /graphics/chart/{objId}
    // Отрисовка графика
    // Отображение summary
}
```

### refreshCard() - обновление
```javascript
async function refreshCard(objId, btn) {
    // Таймер обратного отсчёта
    // Запрос к /graphics/chart/{objId}
    // Отображение ms
    // Через 10 сек возврат 🔄
}
```

---

## 📊 Данные из API (/graphics/chart/)

### emoji_upd (возвращается)
```json
{
  "current_price": 0.2546,
  "entry_time": 68,
  "pnl_percent": -0.58,
  "pnl_percent_leveraged": -6,
  "pnl_usdt": -0.17,
  "result": "🔴"
}
```

### summary
```json
{
  "symbol": "ADA",
  "entry_price": 0.25608,
  "entry_date": "2026-02-18",
  "current_price": 0.2546,
  "total_deviation_usdt": -0.17,
  "total_deviation_percent": -0.58,
  "profitable": false,
  "max_usdt": 1.45,
  "min_usdt": -0.41
}
```

### ohlc
```json
{
  "current": {
    "high": 0.3134,
    "low": 0.233,
    "body": 0.00148,
    "body_pct": 0.58,
    "upper_wick": 0.057,
    "lower_wick": 0.022,
    "pct": -0.58,
    "pct_x": -5.78
  },
  "max": {
    "price": 0.3134,
    "pct": 22.38,
    "pct_x": 223.84,
    "volatility": 0.080
  },
  "min": {
    "price": 0.233,
    "pct": -9.01,
    "pct_x": -90.13
  }
}
```

### stats
```json
{
  "dn": 1,  // дней в минусе
  "dp": 1,  // дней в плюсе
  "da": 0   // дней около 0
}
```

---

## 🧮 Формулы расчёта

### pnl_percent (без leverage)
```
pnl_percent = (current_price - entry_price) / entry_price × 100
```

### pnl_percent_leveraged (🫧)
```
bubble = round(pnl_percent × leverage)
```

### pnl_usdt (🪙)
```
pnl_usdt = bubble × volume / 100
```

---

## ✅ Кнопка refreshCard
- Показывает обратный отсчёт (1мс, 2мс...)
- Фиксирует результат (ms)
- Через 10 сек возвращает 🔄 и перезагружает