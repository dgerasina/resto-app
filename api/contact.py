from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from db import get_db
from datetime import datetime

router = APIRouter()

#  Контактная информация (1 строка на ключ в t_sys_attr_values)
@router.get("/contact_info")
async def get_contact_info(db=Depends(get_db)):
    query = """
    SELECT attr_name, value
    FROM t_sys_attr_values
    WHERE ent_name = 'contact_info'
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    return {row["attr_name"]: row["value"] for row in rows}

#  Сообщение с сайта / от клиента
class ContactMessageIn(BaseModel):
    name: str
    phone: str
    message: str

@router.post("/contact_message")
async def contact_message(data: ContactMessageIn, db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT IFNULL(MAX(ent_instance_id), 0) + 1 FROM t_sys_attr_values WHERE ent_name = 'support_message'"
    )
    msg_id = (await cursor.fetchone())[0]

    fields = [
        ("name", data.name),
        ("phone", data.phone),
        ("message", data.message),
        ("created_at", datetime.now().isoformat())
    ]

    await db.executemany(
        "INSERT INTO t_sys_attr_values (ent_name, attr_name, ent_instance_id, value) VALUES ('support_message', ?, ?, ?)",
        [(attr, msg_id, val) for attr, val in fields]
    )
    await db.commit()

    return {"status": "received", "message_id": msg_id}
