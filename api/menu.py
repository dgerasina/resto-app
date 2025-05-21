from fastapi import APIRouter, Depends
from db import get_db

router = APIRouter()

@router.get("/menu")
async def get_menu(db=Depends(get_db)):
    query = """
    SELECT
        ent_instance_id AS dish_id,
        MAX(CASE WHEN attr_name = 'name' THEN value END) AS name,
        MAX(CASE WHEN attr_name = 'price' THEN value END) AS price
    FROM t_sys_attr_values
    WHERE ent_name = 'dish'
    GROUP BY ent_instance_id
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
