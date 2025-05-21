from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db import get_db
from datetime import datetime

router = APIRouter()

class BookingIn(BaseModel):
    user_id: int
    datetime: str  # ISO формат
    table_id: int
    guests: int
    comment: str = ""

@router.post("/booking")
async def create_booking(booking: BookingIn, db=Depends(get_db)):
    # Проверка: существует ли стол
    cursor = await db.execute(
        "SELECT value FROM t_sys_attr_values WHERE ent_name = 'table' AND attr_name = 'seats' AND ent_instance_id = ?",
        (booking.table_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Столик не найден")

    seats = int(row["value"])
    if booking.guests > seats:
        raise HTTPException(
            status_code=400,
            detail=f"Столик рассчитан на {seats} человек, а гостей: {booking.guests}"
        )

    # Получаем новый booking_id
    cursor = await db.execute(
        "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'booking'"
    )
    booking_id = (await cursor.fetchone())[0]

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('booking', ?, ?, ?)",
        [
            ('user_id', booking_id, str(booking.user_id)),
            ('datetime', booking_id, booking.datetime),
            ('table_id', booking_id, str(booking.table_id)),
            ('guests', booking_id, str(booking.guests)),
            ('comment', booking_id, booking.comment),
            ('created_at', booking_id, datetime.now().isoformat())
        ]
    )

    await db.commit()
    return {"status": "created", "booking_id": booking_id}


@router.get("/booking/{user_id}")
async def get_user_bookings(user_id: int, db=Depends(get_db)):
    query = """
    SELECT ent_instance_id AS booking_id
    FROM t_sys_attr_values
    WHERE ent_name = 'booking' AND attr_name = 'user_id' AND value = ?
    """
    cursor = await db.execute(query, (str(user_id),))
    rows = await cursor.fetchall()
    if not rows:
        return {"bookings": []}

    result = []
    for row in rows:
        bid = row["booking_id"]

        cursor = await db.execute(
            "SELECT attr_name, value FROM t_sys_attr_values WHERE ent_name = 'booking' AND ent_instance_id = ?",
            (bid,)
        )
        booking_attrs = {r["attr_name"]: r["value"] for r in await cursor.fetchall()}
        table_id = int(booking_attrs.get("table_id", 0))

        cursor = await db.execute(
            "SELECT attr_name, value FROM t_sys_attr_values WHERE ent_name = 'table' AND ent_instance_id = ?",
            (table_id,)
        )
        table_attrs = {r["attr_name"]: r["value"] for r in await cursor.fetchall()}

        result.append({
            "booking_id": bid,
            "datetime": booking_attrs.get("datetime"),
            "guests": int(booking_attrs.get("guests", 0)),
            "table": {
                "id": table_id,
                "number": int(table_attrs.get("number", 0)),
                "seats": int(table_attrs.get("seats", 0)),
                "location": table_attrs.get("location", "")
            },
            "comment": booking_attrs.get("comment", ""),
            "created_at": booking_attrs.get("created_at")
        })

    return {"bookings": result}


@router.get("/booking")
async def get_all_bookings(db=Depends(get_db)):
    query = """
    SELECT DISTINCT ent_instance_id AS booking_id
    FROM t_sys_attr_values
    WHERE ent_name = 'booking'
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    if not rows:
        return {"bookings": []}

    result = []
    for row in rows:
        bid = row["booking_id"]

        cursor = await db.execute(
            "SELECT attr_name, value FROM t_sys_attr_values WHERE ent_name = 'booking' AND ent_instance_id = ?",
            (bid,)
        )
        booking_attrs = {r["attr_name"]: r["value"] for r in await cursor.fetchall()}
        table_id = int(booking_attrs.get("table_id", 0))

        cursor = await db.execute(
            "SELECT attr_name, value FROM t_sys_attr_values WHERE ent_name = 'table' AND ent_instance_id = ?",
            (table_id,)
        )
        table_attrs = {r["attr_name"]: r["value"] for r in await cursor.fetchall()}

        result.append({
            "booking_id": bid,
            "user_id": int(booking_attrs.get("user_id", 0)),
            "datetime": booking_attrs.get("datetime"),
            "guests": int(booking_attrs.get("guests", 0)),
            "table": {
                "id": table_id,
                "number": int(table_attrs.get("number", 0)),
                "seats": int(table_attrs.get("seats", 0)),
                "location": table_attrs.get("location", "")
            },
            "comment": booking_attrs.get("comment", ""),
            "created_at": booking_attrs.get("created_at")
        })

    return {"bookings": result}