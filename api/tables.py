from fastapi import APIRouter, Depends, HTTPException, Query
from db import get_db
from datetime import datetime, timedelta

router = APIRouter()

#  Все столы
@router.get("/tables")
async def get_all_tables(db=Depends(get_db)):
    query = """
    SELECT ent_instance_id AS table_id,
           MAX(CASE WHEN attr_name = 'number' THEN value END) AS number,
           MAX(CASE WHEN attr_name = 'seats' THEN value END) AS seats,
           MAX(CASE WHEN attr_name = 'location' THEN value END) AS location
    FROM t_sys_attr_values
    WHERE ent_name = 'table'
    GROUP BY ent_instance_id
    ORDER BY number
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

#  Доступность по дате/времени
@router.get("/tables/availability")
async def get_table_availability(datetime: str = Query(...), db=Depends(get_db)):
    table_query = """
    SELECT ent_instance_id AS table_id,
           MAX(CASE WHEN attr_name = 'number' THEN value END) AS number,
           MAX(CASE WHEN attr_name = 'seats' THEN value END) AS seats,
           MAX(CASE WHEN attr_name = 'location' THEN value END) AS location
    FROM t_sys_attr_values
    WHERE ent_name = 'table'
    GROUP BY ent_instance_id
    ORDER BY number
    """
    cursor = await db.execute(table_query)
    tables = await cursor.fetchall()

    result = []
    for row in tables:
        table_id = row["table_id"]

        check_query = """
        SELECT 1 FROM t_sys_attr_values
        WHERE ent_name = 'booking' AND attr_name = 'table_id' AND value = ?
          AND ent_instance_id IN (
            SELECT ent_instance_id FROM t_sys_attr_values
            WHERE ent_name = 'booking' AND attr_name = 'datetime' AND value = ?
          )
        """
        cursor = await db.execute(check_query, (str(table_id), datetime))
        is_busy = await cursor.fetchone()

        result.append({
            "table_id": table_id,
            "number": row["number"],
            "seats": int(row["seats"]),
            "location": row["location"],
            "is_available": not bool(is_busy)
        })

    return result

#  Только свободные с фильтрацией
@router.get("/tables/free")
async def get_free_tables(
    datetime_str: str = Query(..., alias="datetime"),
    duration_minutes: int = Query(120),
    min_seats: int = Query(1),
    location: str = Query(None),
    db=Depends(get_db)
):
    try:
        start = datetime.fromisoformat(datetime_str)
        end = start + timedelta(minutes=duration_minutes)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат времени")

    base_query = """
    SELECT ent_instance_id AS table_id,
           MAX(CASE WHEN attr_name = 'number' THEN value END) AS number,
           MAX(CASE WHEN attr_name = 'seats' THEN value END) AS seats,
           MAX(CASE WHEN attr_name = 'location' THEN value END) AS location
    FROM t_sys_attr_values
    WHERE ent_name = 'table'
    GROUP BY ent_instance_id
    HAVING CAST(MAX(CASE WHEN attr_name = 'seats' THEN value END) AS INT) >= ?
    """
    if location:
        base_query += " AND MAX(CASE WHEN attr_name = 'location' THEN value END) = ?"
        params = (min_seats, location)
    else:
        params = (min_seats,)

    cursor = await db.execute(base_query, params)
    tables = await cursor.fetchall()

    result = []
    for row in tables:
        table_id = row["table_id"]

        booking_query = '''
        SELECT value FROM t_sys_attr_values
        WHERE ent_name = 'booking' AND attr_name = 'datetime' AND ent_instance_id IN (
            SELECT ent_instance_id FROM t_sys_attr_values
            WHERE ent_name = 'booking' AND attr_name = 'table_id' AND value = ?
        )
        '''
        cursor = await db.execute(booking_query, (str(table_id),))
        bookings = await cursor.fetchall()

        conflict = False
        for b in bookings:
            try:
                b_start = datetime.fromisoformat(b["value"])
                b_end = b_start + timedelta(minutes=duration_minutes)
                if (start < b_end) and (end > b_start):
                    conflict = True
                    break
            except:
                continue

        if not conflict:
            result.append({
                "table_id": table_id,
                "number": row["number"],
                "seats": int(row["seats"]),
                "location": row["location"]
            })

    return result
