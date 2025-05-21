from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from db import get_db

router = APIRouter()

# ✅ Модель отзыва
class ReviewIn(BaseModel):
    user_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = ""
    dish_id: int = None  # либо dish_id
    is_restaurant: bool = False  # либо ресторан

# ✅ POST /review
@router.post("/review")
async def add_review(review: ReviewIn, db=Depends(get_db)):
    if not review.dish_id and not review.is_restaurant:
        raise HTTPException(status_code=400, detail="Нужно указать dish_id или is_restaurant=True")

    # получаем новый review_id
    cursor = await db.execute(
        "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'review'"
    )
    review_id = (await cursor.fetchone())[0]

    data = [
        ("user_id", str(review.user_id)),
        ("rating", str(review.rating)),
        ("comment", review.comment),
        ("created_at", datetime.now().isoformat())
    ]
    if review.dish_id:
        data.append(("dish_id", str(review.dish_id)))
    if review.is_restaurant:
        data.append(("restaurant", "true"))

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('review', ?, ?, ?)",
        [(attr, review_id, val) for attr, val in data]
    )
    await db.commit()
    return {"status": "created", "review_id": review_id}

@router.get("/reviews/dish/{dish_id}")
async def get_reviews_for_dish(dish_id: int, db=Depends(get_db)):
    query = """
    SELECT r1.ent_instance_id AS review_id,
           MAX(CASE WHEN attr_name = 'user_id' THEN value END) AS user_id,
           MAX(CASE WHEN attr_name = 'rating' THEN value END) AS rating,
           MAX(CASE WHEN attr_name = 'comment' THEN value END) AS comment,
           MAX(CASE WHEN attr_name = 'created_at' THEN value END) AS created_at
    FROM t_sys_attr_values r1
    WHERE ent_name = 'review'
      AND ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'review' AND attr_name = 'dish_id' AND value = ?
      )
    GROUP BY r1.ent_instance_id
    ORDER BY created_at DESC
    """
    cursor = await db.execute(query, (str(dish_id),))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

@router.get("/reviews/restaurant")
async def get_reviews_for_restaurant(db=Depends(get_db)):
    query = """
    SELECT r1.ent_instance_id AS review_id,
           MAX(CASE WHEN attr_name = 'user_id' THEN value END) AS user_id,
           MAX(CASE WHEN attr_name = 'rating' THEN value END) AS rating,
           MAX(CASE WHEN attr_name = 'comment' THEN value END) AS comment,
           MAX(CASE WHEN attr_name = 'created_at' THEN value END) AS created_at
    FROM t_sys_attr_values r1
    WHERE ent_name = 'review'
      AND ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'review' AND attr_name = 'restaurant' AND value = 'true'
      )
    GROUP BY r1.ent_instance_id
    ORDER BY created_at DESC
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

@router.get("/rating/dish/{dish_id}")
async def get_dish_rating(dish_id: int, db=Depends(get_db)):
    query = """
    SELECT AVG(CAST(value AS FLOAT)) AS avg_rating
    FROM t_sys_attr_values
    WHERE ent_name = 'review' AND attr_name = 'rating'
      AND ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'review' AND attr_name = 'dish_id' AND value = ?
      )
    """
    cursor = await db.execute(query, (str(dish_id),))
    row = await cursor.fetchone()
    return {"dish_id": dish_id, "avg_rating": float(row["avg_rating"]) if row["avg_rating"] else None}

@router.get("/rating/restaurant")
async def get_restaurant_rating(db=Depends(get_db)):
    query = """
    SELECT AVG(CAST(value AS FLOAT)) AS avg_rating
    FROM t_sys_attr_values
    WHERE ent_name = 'review' AND attr_name = 'rating'
      AND ent_instance_id IN (
        SELECT ent_instance_id FROM t_sys_attr_values
        WHERE ent_name = 'review' AND attr_name = 'restaurant' AND value = 'true'
      )
    """
    cursor = await db.execute(query)
    row = await cursor.fetchone()
    return {"avg_rating": float(row["avg_rating"]) if row["avg_rating"] else None}

