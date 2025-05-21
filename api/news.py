from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db import get_db
from datetime import datetime

router = APIRouter()

#  Модель входа для публикации
class NewsIn(BaseModel):
    title: str
    body: str
    type: str = "news"  # news / promo / event
    image_url: str = ""
    tags: str = ""      # можно передавать через запятую

#  POST /news — создать новость/акцию/событие
@router.post("/news")
async def create_news(data: NewsIn, db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'news'"
    )
    news_id = (await cursor.fetchone())[0]

    fields = [
        ("title", data.title),
        ("body", data.body),
        ("type", data.type),
        ("image_url", data.image_url),
        ("tags", data.tags),
        ("created_at", datetime.now().isoformat())
    ]

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('news', ?, ?, ?)",
        [(attr, news_id, val) for attr, val in fields]
    )
    await db.commit()

    return {"status": "published", "news_id": news_id}

#  GET /news — список всех публикаций
@router.get("/news")
async def get_all_news(db=Depends(get_db)):
    query = """
    SELECT ent_instance_id AS news_id,
           MAX(CASE WHEN attr_name = 'title' THEN value END) AS title,
           MAX(CASE WHEN attr_name = 'body' THEN value END) AS body,
           MAX(CASE WHEN attr_name = 'type' THEN value END) AS type,
           MAX(CASE WHEN attr_name = 'image_url' THEN value END) AS image_url,
           MAX(CASE WHEN attr_name = 'tags' THEN value END) AS tags,
           MAX(CASE WHEN attr_name = 'created_at' THEN value END) AS created_at
    FROM t_sys_attr_values
    WHERE ent_name = 'news'
    GROUP BY ent_instance_id
    ORDER BY created_at DESC
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

#  GET /news/{id} — одна публикация
@router.get("/news/{news_id}")
async def get_news_item(news_id: int, db=Depends(get_db)):
    query = """
    SELECT attr_name, value
    FROM t_sys_attr_values
    WHERE ent_name = 'news' AND ent_instance_id = ?
    """
    cursor = await db.execute(query, (news_id,))
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Новость не найдена")

    result = {"news_id": news_id}
    for row in rows:
        result[row["attr_name"]] = row["value"]

    return result
