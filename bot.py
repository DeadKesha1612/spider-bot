def get_next_order_number():
    try:
        # Запрашиваем заказы, сортируем по order_id по убыванию, берем только первый (самый большой)
        url = f"{SUPABASE_URL}/rest/v1/orders?select=order_id&order=order_id.desc&limit=1"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            rows = response.json()
            if rows and len(rows) > 0 and rows[0].get("order_id") is not None:
                return int(rows[0]["order_id"]) + 1
    except Exception as e:
        print(f"Ошибка получения номера заказа: {e}")
    return 1
