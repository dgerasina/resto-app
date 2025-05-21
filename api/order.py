from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db import get_db

router = APIRouter()

class OrderIn(BaseModel):
    user_id: int
    address_id: int
    status: str = "pending"  # по умолчанию

@router.post("/order")
async def place_order(order: OrderIn, db=Depends(get_db)):
    # Получаем cart_id
    cursor = await db.execute(
        "SELECT ent_instance_id FROM t_sys_attr_values WHERE ent_name = 'cart' AND attr_name = 'user_id' AND value = ?",
        (str(order.user_id),)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Корзина пуста")
    cart_id = row["ent_instance_id"]

    # Получаем все cart_item для cart_id
    query = """
    SELECT ent_instance_id AS cart_item_id,
           MAX(CASE WHEN attr_name = 'dish_id' THEN value END) AS dish_id,
           MAX(CASE WHEN attr_name = 'quantity' THEN value END) AS quantity
    FROM t_sys_attr_values
    WHERE ent_name = 'cart_item'
      AND ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'cart_item' AND attr_name = 'cart_id' AND value = ?
      )
    GROUP BY ent_instance_id
    """
    cursor = await db.execute(query, (str(cart_id),))
    cart_items = await cursor.fetchall()
    if not cart_items:
        raise HTTPException(status_code=404, detail="Корзина пуста")

    # Получаем новый order_id
    cursor = await db.execute(
        "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'order'"
    )
    order_id = (await cursor.fetchone())[0]

    # Считаем сумму заказа
    total_price = 0.0
    for item in cart_items:
        cursor = await db.execute(
            "SELECT value FROM t_sys_attr_values WHERE ent_name = 'dish' AND attr_name = 'price' AND ent_instance_id = ?",
            (item["dish_id"],)
        )
        price = float((await cursor.fetchone())["value"])
        total_price += price * int(item["quantity"])

    # Добавляем order (user_id, address_id, created_at, status, total_price)
    from datetime import datetime
    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('order', ?, ?, ?)",
        [
            ('user_id', order_id, str(order.user_id)),
            ('address_id', order_id, str(order.address_id)),
            ('status', order_id, order.status),
            ('total_price', order_id, str(total_price)),
            ('created_at', order_id, datetime.now().isoformat()),
        ]
    )

    # Добавляем order_item для каждого блюда
    for item in cart_items:
        cursor = await db.execute(
            "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'order_item'"
        )
        order_item_id = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT value FROM t_sys_attr_values WHERE ent_name = 'dish' AND attr_name = 'price' AND ent_instance_id = ?",
            (item["dish_id"],)
        )
        price = (await cursor.fetchone())["value"]

        await db.executemany(
            "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('order_item', ?, ?, ?)",
            [
                ('order_id', order_item_id, str(order_id)),
                ('dish_id', order_item_id, str(item["dish_id"])),
                ('quantity', order_item_id, str(item["quantity"])),
                ('price', order_item_id, price),
            ]
        )

    # Очищаем корзину
    await db.execute(
        "DELETE FROM t_sys_attr_values WHERE ent_name = 'cart_item' AND ent_instance_id IN (" +
        ",".join(str(row["cart_item_id"]) for row in cart_items) + ")"
    )

    await db.commit()

    return {
        "status": "success",
        "order_id": order_id,
        "total": total_price,
        "items": len(cart_items)
    }

@router.get("/orders/{user_id}")
async def get_user_orders(user_id: int, db=Depends(get_db)):
    # Находим все заказы пользователя
    query = """
    SELECT ent_instance_id AS order_id
    FROM t_sys_attr_values
    WHERE ent_name = 'order' AND attr_name = 'user_id' AND value = ?
    """
    cursor = await db.execute(query, (str(user_id),))
    rows = await cursor.fetchall()

    if not rows:
        return {"orders": []}

    order_ids = [row["order_id"] for row in rows]
    result = []

    for order_id in order_ids:
        # Получаем все атрибуты заказа
        order_data_query = """
        SELECT attr_name, value
        FROM t_sys_attr_values
        WHERE ent_name = 'order' AND ent_instance_id = ?
        """
        cursor = await db.execute(order_data_query, (order_id,))
        attrs = {row["attr_name"]: row["value"] for row in await cursor.fetchall()}

        # Получаем order_items
        order_items_query = """
        SELECT ent_instance_id AS order_item_id,
               MAX(CASE WHEN attr_name = 'dish_id' THEN value END) AS dish_id,
               MAX(CASE WHEN attr_name = 'quantity' THEN value END) AS quantity,
               MAX(CASE WHEN attr_name = 'price' THEN value END) AS price
        FROM t_sys_attr_values
        WHERE ent_name = 'order_item'
          AND ent_instance_id IN (
            SELECT ent_instance_id FROM t_sys_attr_values
            WHERE ent_name = 'order_item' AND attr_name = 'order_id' AND value = ?
          )
        GROUP BY ent_instance_id
        """
        cursor = await db.execute(order_items_query, (str(order_id),))
        items = await cursor.fetchall()

        result.append({
            "order_id": order_id,
            "status": attrs.get("status", "unknown"),
            "total_price": float(attrs.get("total_price", 0)),
            "created_at": attrs.get("created_at", "unknown"),
            "address_id": int(attrs.get("address_id", 0)),
            "items": [
                {
                    "dish_id": int(item["dish_id"]),
                    "quantity": int(item["quantity"]),
                    "price": float(item["price"]),
                    "total": float(item["price"]) * int(item["quantity"])
                }
                for item in items
            ]
        })

    return {"orders": result}

@router.get("/orders")
async def get_all_orders(db=Depends(get_db)):
    # Получаем все уникальные order_id
    query = """
    SELECT DISTINCT ent_instance_id AS order_id
    FROM t_sys_attr_values
    WHERE ent_name = 'order'
    """
    cursor = await db.execute(query)
    order_rows = await cursor.fetchall()

    if not order_rows:
        return {"orders": []}

    result = []

    for row in order_rows:
        order_id = row["order_id"]

        # Получаем атрибуты заказа
        query_attrs = """
        SELECT attr_name, value
        FROM t_sys_attr_values
        WHERE ent_name = 'order' AND ent_instance_id = ?
        """
        cursor = await db.execute(query_attrs, (order_id,))
        attrs = {r["attr_name"]: r["value"] for r in await cursor.fetchall()}

        result.append({
            "order_id": order_id,
            "user_id": int(attrs.get("user_id", 0)),
            "address_id": int(attrs.get("address_id", 0)),
            "status": attrs.get("status", "unknown"),
            "total_price": float(attrs.get("total_price", 0)),
            "created_at": attrs.get("created_at", "unknown")
        })

    return {"orders": result}
