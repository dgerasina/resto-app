from fastapi import APIRouter, Depends
from db import get_db

router = APIRouter()

#  Ежедневное количество заказов
@router.get("/analytics/daily-orders")
async def daily_orders(db=Depends(get_db)):
    query = '''
    SELECT DATE(value) AS day, COUNT(DISTINCT ent_instance_id) AS order_count
    FROM t_sys_attr_values
    WHERE ent_name = 'order' AND attr_name = 'created_at'
    GROUP BY day
    ORDER BY day DESC
    '''
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

#  Популярные блюда (по количеству)
@router.get("/analytics/popular-dishes")
async def popular_dishes(db=Depends(get_db)):
    query = '''
    SELECT value AS dish_id, SUM(CAST(quantity.value AS INT)) AS total_quantity
    FROM t_sys_attr_values AS dish
    JOIN t_sys_attr_values AS quantity
      ON dish.ent_instance_id = quantity.ent_instance_id
     AND dish.ent_name = 'order_item'
     AND quantity.ent_name = 'order_item'
     AND quantity.attr_name = 'quantity'
    WHERE dish.attr_name = 'dish_id'
    GROUP BY value
    ORDER BY total_quantity DESC
    LIMIT 10
    '''
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

#  Выручка по дням
@router.get("/analytics/revenue-by-day")
async def revenue_by_day(db=Depends(get_db)):
    query = '''
    SELECT DATE(created.value) AS day,
           SUM(CAST(total.value AS FLOAT)) AS total_revenue
    FROM t_sys_attr_values AS created
    JOIN t_sys_attr_values AS total
      ON created.ent_instance_id = total.ent_instance_id
     AND created.ent_name = 'order'
     AND total.ent_name = 'order'
     AND total.attr_name = 'total_price'
    WHERE created.attr_name = 'created_at'
    GROUP BY day
    ORDER BY day DESC
    '''
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

#  Загруженность столов по времени (heatmap)
@router.get("/analytics/booking-heatmap")
async def booking_heatmap(db=Depends(get_db)):
    query = '''
    SELECT SUBSTR(value, 0, 11) AS date,
           SUBSTR(value, 12, 5) AS time,
           COUNT(*) AS count
    FROM t_sys_attr_values
    WHERE ent_name = 'booking' AND attr_name = 'datetime'
    GROUP BY date, time
    ORDER BY date DESC, time
    '''
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

#  Лояльность пользователей
@router.get("/analytics/user-loyalty")
async def user_loyalty(db=Depends(get_db)):
    query = '''
    SELECT ent_instance_id AS user_id,
           MAX(CASE WHEN attr_name = 'name' THEN value END) AS name,
           MAX(CASE WHEN attr_name = 'phone' THEN value END) AS phone,
           MAX(CASE WHEN attr_name = 'loyalty_total' THEN value END) AS loyalty_total,
           MAX(CASE WHEN attr_name = 'loyalty_discount' THEN value END) AS loyalty_discount
    FROM t_sys_attr_values
    WHERE ent_name = 'user'
    GROUP BY ent_instance_id
    ORDER BY CAST(loyalty_total AS FLOAT) DESC
    '''
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.get("/analytics/staff/shifts")
async def staff_shifts(db=Depends(get_db)):
    query = """
    SELECT ent_instance_id AS shift_id,
           MAX(CASE WHEN attr_name = 'user_id' THEN value END) AS user_id,
           MAX(CASE WHEN attr_name = 'start_time' THEN value END) AS start_time,
           MAX(CASE WHEN attr_name = 'end_time' THEN value END) AS end_time
    FROM t_sys_attr_values
    WHERE ent_name = 'staff_shift'
    GROUP BY ent_instance_id
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()

    from collections import defaultdict
    from datetime import datetime

    shift_summary = defaultdict(lambda: {"total_hours": 0, "shift_count": 0})

    for row in rows:
        user_id = row["user_id"]
        try:
            start = datetime.fromisoformat(row["start_time"])
            end = datetime.fromisoformat(row["end_time"])
            hours = round((end - start).total_seconds() / 3600, 2)
        except:
            hours = 0
        shift_summary[user_id]["total_hours"] += hours
        shift_summary[user_id]["shift_count"] += 1

    # форматируем
    result = [
        {"user_id": uid, "total_hours": data["total_hours"], "shift_count": data["shift_count"]}
        for uid, data in shift_summary.items()
    ]
    return result

@router.get("/analytics/staff/revenue")
async def staff_revenue(db=Depends(get_db)):
    query = """
    SELECT o.ent_instance_id AS order_id,
           MAX(CASE WHEN o.attr_name = 'waiter_id' THEN o.value END) AS waiter_id,
           MAX(CASE WHEN p.attr_name = 'total_price' THEN p.value END) AS total_price
    FROM t_sys_attr_values o
    JOIN t_sys_attr_values p ON o.ent_instance_id = p.ent_instance_id
    WHERE o.ent_name = 'order' AND p.ent_name = 'order'
    GROUP BY o.ent_instance_id
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()

    from collections import defaultdict

    revenue = defaultdict(float)
    for row in rows:
        if row["waiter_id"] and row["total_price"]:
            revenue[row["waiter_id"]] += float(row["total_price"])

    return [{"waiter_id": waiter_id, "total_revenue": round(total, 2)} for waiter_id, total in revenue.items()]
