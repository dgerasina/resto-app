from fastapi import APIRouter, Depends, HTTPException
from db import get_db
from pydantic import BaseModel

router = APIRouter()

class CartItemIn(BaseModel):
    user_id: int
    dish_id: int
    quantity: int

@router.post("/cart/add")
async def add_to_cart(item: CartItemIn, db=Depends(get_db)):
    # Ищем cart_id пользователя
    get_cart_id_query = """
    SELECT ent_instance_id FROM t_sys_attr_values
    WHERE ent_name = 'cart' AND attr_name = 'user_id' AND value = ?
    """
    cursor = await db.execute(get_cart_id_query, (str(item.user_id),))
    row = await cursor.fetchone()

    # Если корзина не существует — создаём новую
    if row:
        cart_id = row["ent_instance_id"]
    else:
        # создаём новую корзину
        await db.execute(
            "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('cart', 'user_id', (SELECT IFNULL(MAX(ent_instance_id), 0)+1 FROM t_sys_attr_values WHERE ent_name = 'cart'), ?)",
            (str(item.user_id),)
        )
        await db.commit()

        cursor = await db.execute(get_cart_id_query, (str(item.user_id),))
        row = await cursor.fetchone()
        cart_id = row["ent_instance_id"]

    # Ищем, есть ли уже этот dish в корзине
    get_item_query = """
    SELECT val_id, value FROM t_sys_attr_values
    WHERE ent_name = 'cart_item' AND attr_name = 'quantity'
    AND ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'cart_item' AND attr_name = 'dish_id' AND value = ?
        INTERSECT
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'cart_item' AND attr_name = 'cart_id' AND value = ?
    )
    """
    cursor = await db.execute(get_item_query, (str(item.dish_id), str(cart_id)))
    existing = await cursor.fetchone()

    if existing:
        # обновляем количество
        new_qty = int(existing["value"]) + item.quantity
        await db.execute(
            "UPDATE t_sys_attr_values SET value = ? WHERE val_id = ?",
            (str(new_qty), existing["val_id"])
        )
    else:
        # создаём новую строку cart_item (три записи: cart_id, dish_id, quantity)
        new_id_query = "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'cart_item'"
        cursor = await db.execute(new_id_query)
        new_id = (await cursor.fetchone())[0]

        await db.executemany(
            "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('cart_item', ?, ?, ?)",
            [
                ('cart_id', new_id, str(cart_id)),
                ('dish_id', new_id, str(item.dish_id)),
                ('quantity', new_id, str(item.quantity)),
            ]
        )
    await db.commit()
    return {"status": "added", "cart_id": cart_id}

@router.get("/cart/{user_id}")
async def get_cart(user_id: int, db=Depends(get_db)):
    # 1. Получаем cart_id пользователя
    get_cart_query = """
    SELECT ent_instance_id FROM t_sys_attr_values
    WHERE ent_name = 'cart' AND attr_name = 'user_id' AND value = ?
    """
    cursor = await db.execute(get_cart_query, (str(user_id),))
    row = await cursor.fetchone()
    if not row:
        return {"cart": [], "message": "Корзина пуста"}

    cart_id = row["ent_instance_id"]

    # 2. Находим все cart_item, где cart_id совпадает
    get_cart_items_query = """
    SELECT ci.ent_instance_id AS cart_item_id,
           MAX(CASE WHEN ci.attr_name = 'dish_id' THEN ci.value END) AS dish_id,
           MAX(CASE WHEN ci.attr_name = 'quantity' THEN ci.value END) AS quantity
    FROM t_sys_attr_values ci
    WHERE ci.ent_name = 'cart_item'
      AND ci.ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'cart_item' AND attr_name = 'cart_id' AND value = ?
      )
    GROUP BY ci.ent_instance_id
    """
    cursor = await db.execute(get_cart_items_query, (str(cart_id),))
    cart_items = await cursor.fetchall()

    result = []

    for row in cart_items:
        dish_id = row["dish_id"]
        quantity = int(row["quantity"])

        # 3. Получаем название и цену блюда из dish
        get_dish_query = """
        SELECT 
            MAX(CASE WHEN attr_name = 'name' THEN value END) AS name,
            MAX(CASE WHEN attr_name = 'price' THEN value END) AS price
        FROM t_sys_attr_values
        WHERE ent_name = 'dish' AND ent_instance_id = ?
        """
        cursor = await db.execute(get_dish_query, (dish_id,))
        dish = await cursor.fetchone()

        result.append({
            "dish_id": dish_id,
            "name": dish["name"],
            "price": float(dish["price"]),
            "quantity": quantity,
            "total": quantity * float(dish["price"]),
        })

    return {"cart": result, "cart_id": cart_id}

@router.delete("/cart/{user_id}/{dish_id}")
async def delete_cart_item(user_id: int, dish_id: int, db=Depends(get_db)):
    # Получаем cart_id пользователя
    get_cart_query = """
    SELECT ent_instance_id FROM t_sys_attr_values
    WHERE ent_name = 'cart' AND attr_name = 'user_id' AND value = ?
    """
    cursor = await db.execute(get_cart_query, (str(user_id),))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Корзина не найдена")

    cart_id = row["ent_instance_id"]

    # Находим cart_item.ent_instance_id по cart_id и dish_id
    get_cart_item_id_query = """
    SELECT ci.ent_instance_id
    FROM t_sys_attr_values ci
    WHERE ent_name = 'cart_item'
    GROUP BY ci.ent_instance_id
    HAVING 
        SUM(CASE WHEN attr_name = 'cart_id' AND value = ? THEN 1 ELSE 0 END) > 0
        AND SUM(CASE WHEN attr_name = 'dish_id' AND value = ? THEN 1 ELSE 0 END) > 0
    """
    cursor = await db.execute(get_cart_item_id_query, (str(cart_id), str(dish_id)))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Позиция в корзине не найдена")

    cart_item_id = row["ent_instance_id"]

    # Удаляем все записи для этого cart_item
    await db.execute(
        "DELETE FROM t_sys_attr_values WHERE ent_name = 'cart_item' AND ent_instance_id = ?",
        (cart_item_id,)
    )
    await db.commit()

    return {"status": "deleted", "cart_item_id": cart_item_id}
