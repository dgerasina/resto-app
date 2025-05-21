from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from db import get_db
from datetime import datetime

router = APIRouter()

#  Модель регистрации
class UserRegisterIn(BaseModel):
    name: str
    phone: str
    city: str
    street: str
    house: str
    building: str = ""
    floor: str = ""
    flat: str = ""

#  POST /register
@router.post("/register")
async def register_user(user: UserRegisterIn, db=Depends(get_db)):
    # Проверка по телефону
    check_query = """
    SELECT ent_instance_id FROM t_sys_attr_values
    WHERE ent_name = 'user' AND attr_name = 'phone' AND value = ?
    """
    cursor = await db.execute(check_query, (user.phone,))
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="Пользователь с таким телефоном уже зарегистрирован")

    # Получаем новый user_id
    cursor = await db.execute(
        "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'user'"
    )
    user_id = (await cursor.fetchone())[0]

    # Все поля + лояльность
    fields = [
        ('name', user.name),
        ('phone', user.phone),
        ('city', user.city),
        ('street', user.street),
        ('house', user.house),
        ('building', user.building),
        ('floor', user.floor),
        ('flat', user.flat),
        ('created_at', datetime.now().isoformat()),
        ('loyalty_discount', "3"),      # стартовая скидка 3%
        ('loyalty_total', "0")          # сумма заказов
    ]

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('user', ?, ?, ?)",
        [(attr, user_id, val) for attr, val in fields]
    )
    await db.commit()

    return {"status": "registered", "user_id": user_id}

#  GET /user/{user_id}
@router.get("/user/{user_id}")
async def get_user_profile(user_id: int, db=Depends(get_db)):
    query = """
    SELECT attr_name, value
    FROM t_sys_attr_values
    WHERE ent_name = 'user' AND ent_instance_id = ?
    """
    cursor = await db.execute(query, (user_id,))
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    profile = {row["attr_name"]: row["value"] for row in rows}
    profile["user_id"] = user_id
    return profile

# Получение всех пользователей
@router.get("/users")
async def get_all_users(db=Depends(get_db)):
    query_ids = """
    SELECT DISTINCT ent_instance_id AS user_id
    FROM t_sys_attr_values
    WHERE ent_name = 'user'
    ORDER BY user_id
    """
    cursor = await db.execute(query_ids)
    users = await cursor.fetchall()
    result = []

    for row in users:
        user_id = row["user_id"]
        cursor = await db.execute(
            "SELECT attr_name, value FROM t_sys_attr_values WHERE ent_name = 'user' AND ent_instance_id = ?",
            (user_id,)
        )
        attrs = {r["attr_name"]: r["value"] for r in await cursor.fetchall()}
        result.append({
            "user_id": user_id,
            "name": attrs.get("name"),
            "phone": attrs.get("phone"),
            "city": attrs.get("city"),
            "loyalty_discount": attrs.get("loyalty_discount"),
            "loyalty_total": attrs.get("loyalty_total")
        })

    return result

class LoginIn(BaseModel):
    phone: str

@router.post("/login")
async def login_user(data: LoginIn, db=Depends(get_db)):
    # Ищем user_id по телефону
    query = """
    SELECT ent_instance_id FROM t_sys_attr_values
    WHERE ent_name = 'user' AND attr_name = 'phone' AND value = ?
    """
    cursor = await db.execute(query, (data.phone,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user_id = row["ent_instance_id"]

    # Получаем имя
    cursor = await db.execute("""
    SELECT value FROM t_sys_attr_values
    WHERE ent_name = 'user' AND attr_name = 'name' AND ent_instance_id = ?
    """, (user_id,))
    name_row = await cursor.fetchone()

    return {
        "user_id": user_id,
        "name": name_row["value"] if name_row else ""
    }
