from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import menu, cart, order, booking, tables, review, user, analytics, contact, news, admin_tools

app = FastAPI(title="RestoFlow")

# Настройка CORS (разрешить все источники — безопаснее ограничить на проде)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Служебные эндпоинты
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"version": "v1.0.0"}

# Подключение роутеров
app.include_router(menu.router)
app.include_router(cart.router)
app.include_router(order.router)
app.include_router(booking.router)
app.include_router(tables.router)
app.include_router(review.router)
app.include_router(user.router)
app.include_router(analytics.router)
app.include_router(contact.router)
app.include_router(news.router)
app.include_router(admin_tools.router)

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

from fastapi import Depends
from db import get_db

@app.get("/menu")
async def menu_page(request: Request, db=Depends(get_db)):
    query = """
    SELECT ent_instance_id AS dish_id,
           MAX(CASE WHEN attr_name = 'name' THEN value END) AS name,
           MAX(CASE WHEN attr_name = 'price' THEN value END) AS price,
           MAX(CASE WHEN attr_name = 'description' THEN value END) AS description
    FROM t_sys_attr_values
    WHERE ent_name = 'dish'
    GROUP BY ent_instance_id
    ORDER BY dish_id
    """
    cursor = await db.execute(query)
    rows = await cursor.fetchall()
    dishes = [dict(row) for row in rows]
    return templates.TemplateResponse("menu.html", {"request": request, "dishes": dishes})
