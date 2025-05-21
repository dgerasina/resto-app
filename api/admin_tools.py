from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db import get_db
from datetime import datetime

router = APIRouter()

# ------------------------------
#  Работа с блюдами
# ------------------------------

class DishIn(BaseModel):
    name: str
    price: float
    description: str = ""
    category: str
    image_url: str = ""
    is_active: bool = True

@router.post("/admin/dish")
async def create_dish(dish: DishIn, db=Depends(get_db)):
    cursor = await db.execute("SELECT IFNULL(MAX(ent_instance_id), 0)+1 FROM t_sys_attr_values WHERE ent_name = 'dish'")
    dish_id = (await cursor.fetchone())[0]

    fields = [
        ("name", dish.name),
        ("price", str(dish.price)),
        ("description", dish.description),
        ("category", dish.category),
        ("image_url", dish.image_url),
        ("is_active", "true" if dish.is_active else "false"),
        ("created_at", datetime.now().isoformat())
    ]

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('dish', ?, ?, ?)",
        [(attr, dish_id, val) for attr, val in fields]
    )
    await db.commit()
    return {"status": "created", "dish_id": dish_id}

@router.put("/admin/dish/{dish_id}")
async def update_dish(dish_id: int, dish: DishIn, db=Depends(get_db)):
    await db.execute("DELETE FROM t_sys_attr_values WHERE ent_name = 'dish' AND ent_instance_id = ?", (dish_id,))
    fields = [
        ("name", dish.name),
        ("price", str(dish.price)),
        ("description", dish.description),
        ("category", dish.category),
        ("image_url", dish.image_url),
        ("is_active", "true" if dish.is_active else "false"),
        ("updated_at", datetime.now().isoformat())
    ]
    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('dish', ?, ?, ?)",
        [(attr, dish_id, val) for attr, val in fields]
    )
    await db.commit()
    return {"status": "updated", "dish_id": dish_id}

@router.delete("/admin/dish/{dish_id}")
async def delete_dish(dish_id: int, db=Depends(get_db)):
    await db.execute("DELETE FROM t_sys_attr_values WHERE ent_name = 'dish' AND ent_instance_id = ?", (dish_id,))
    await db.commit()
    return {"status": "deleted", "dish_id": dish_id}

# ------------------------------
#  Категории
# ------------------------------

class CategoryIn(BaseModel):
    name: str

@router.post("/admin/category")
async def create_category(data: CategoryIn, db=Depends(get_db)):
    cursor = await db.execute("SELECT IFNULL(MAX(ent_instance_id), 0)+1 FROM t_sys_attr_values WHERE ent_name = 'category'")
    cat_id = (await cursor.fetchone())[0]
    await db.execute(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('category', 'name', ?, ?)",
        (cat_id, data.name)
    )
    await db.commit()
    return {"status": "created", "category": data.name}

@router.delete("/admin/category/{name}")
async def delete_category(name: str, db=Depends(get_db)):
    await db.execute("DELETE FROM t_sys_attr_values WHERE ent_name = 'category' AND attr_name = 'name' AND value = ?", (name,))
    await db.commit()
    return {"status": "deleted", "category": name}

# ------------------------------
#  Универсальные GET / PUT / DELETE
# ------------------------------

class EntityUpdateIn(BaseModel):
    fields: dict

@router.get("/admin/{ent_name}/{ent_id}")
async def get_entity(ent_name: str, ent_id: int, db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT attr_name, value FROM t_sys_attr_values WHERE ent_name = ? AND ent_instance_id = ?",
        (ent_name, ent_id)
    )
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Сущность не найдена")

    result = {"ent_name": ent_name, "ent_id": ent_id}
    for row in rows:
        result[row["attr_name"]] = row["value"]
    return result

@router.put("/admin/{ent_name}/{ent_id}")
async def update_entity(ent_name: str, ent_id: int, data: EntityUpdateIn, db=Depends(get_db)):
    await db.execute("DELETE FROM t_sys_attr_values WHERE ent_name = ? AND ent_instance_id = ?", (ent_name, ent_id))
    now = datetime.now().isoformat()

    field_items = [(k, v) for k, v in data.fields.items()]
    field_items.append(("updated_at", now))

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES (?, ?, ?, ?)",
        [(ent_name, attr, ent_id, val) for attr, val in field_items]
    )
    await db.commit()
    return {"status": "updated", "ent_name": ent_name, "ent_id": ent_id}

@router.delete("/admin/{ent_name}/{ent_id}")
async def delete_entity(ent_name: str, ent_id: int, db=Depends(get_db)):
    await db.execute("DELETE FROM t_sys_attr_values WHERE ent_name = ? AND ent_instance_id = ?", (ent_name, ent_id))
    await db.commit()
    return {"status": "deleted", "ent_name": ent_name, "ent_id": ent_id}

# ------------------------------
#  Список всех сущностей заданного типа
# ------------------------------

@router.get("/admin/{ent_name}")
async def get_entity_list(ent_name: str, db=Depends(get_db)):
    query = f'''
    SELECT ent_instance_id,
           MAX(CASE WHEN attr_name = 'name' THEN value END) AS name,
           MAX(CASE WHEN attr_name = 'title' THEN value END) AS title,
           MAX(CASE WHEN attr_name = 'created_at' THEN value END) AS created_at
    FROM t_sys_attr_values
    WHERE ent_name = ?
    GROUP BY ent_instance_id
    ORDER BY ent_instance_id DESC
    '''
    cursor = await db.execute(query, (ent_name,))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

# ------------------------------
#  Работа с t_sys_ent
# ------------------------------

class SysEntityIn(BaseModel):
    ent_name: str
    ent_app: str

@router.post("/admin/_ent")
async def create_sys_ent(data: SysEntityIn, db=Depends(get_db)):
    await db.execute(
        "INSERT INTO t_sys_ent (ent_name, ent_app) VALUES (?, ?)",
        (data.ent_name, data.ent_app)
    )
    await db.commit()
    return {"status": "created", "ent_name": data.ent_name}

@router.delete("/admin/_ent/{ent_name}")
async def delete_sys_ent(ent_name: str, db=Depends(get_db)):
    await db.execute("DELETE FROM t_sys_ent WHERE ent_name = ?", (ent_name,))
    await db.commit()
    return {"status": "deleted", "ent_name": ent_name}
