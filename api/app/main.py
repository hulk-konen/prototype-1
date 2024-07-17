from contextlib import asynccontextmanager
import json
import ssl

from dotenv import load_dotenv
import os
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import (
    Table, Column, Integer, String, MetaData, select,
    DateTime, SmallInteger, Boolean, Float, text, func
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Please note: This is extremely unsecure
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

load_dotenv()  

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure the DATABASE_URL is set
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables")

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": ssl_context}
)
AsyncSessionLocal = sessionmaker(class_=AsyncSession, expire_on_commit=False, bind=engine)

metadata = MetaData(schema="lithings")

msgs = Table(
    "msgs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=False), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("sender", SmallInteger(), nullable=True),
    Column("receiver", SmallInteger(), nullable=True),
    Column("msg", SmallInteger(), nullable=True),
    Column("text_msg", String(255), nullable=True),
    Column("latitude", Float(), nullable=True),
    Column("longitude", Float(), nullable=True),
    Column("delivered", Boolean(), nullable=True),
    Column("seen", Boolean(), nullable=True),
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
    await create_tables()
    yield

app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, hopefully ["http://localhost:3000", "https://yourdomain.com"] is possible with sim7080g
#    allow_credentials=True, (enable when origins are specified)
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/latest-text-msg/")
async def get_latest_text_msg(db: AsyncSession = Depends(get_db)):
    query = select(msgs.c.text_msg).order_by(msgs.c.id.desc()).limit(1)
    result = await db.execute(query)
    latest_text_msg = result.scalar_one_or_none()
    if latest_text_msg is None:
        return {"text_msg": "No messages found"}
    return {"text_msg": latest_text_msg}

@app.get("/all-text-msgs/")
async def get_all_text_msgs(db: AsyncSession = Depends(get_db)):
    query = select(msgs.c.text_msg).order_by(msgs.c.id.desc())
    result = await db.execute(query)
    all_text_msgs = result.scalars().all()
    if not all_text_msgs:
        return {"text_msgs": "No messages found"}
    return {"text_msgs": all_text_msgs}

@app.get("/all-msgs/")
async def get_all_text_msgs(db: AsyncSession = Depends(get_db)):
    query = select(msgs.c.msg).order_by(msgs.c.id.desc())
    result = await db.execute(query)
    all_msgs = result.scalars().all()
    if not all_msgs:
        return {"msgs": "No messages found"}
    return {"msgs": all_msgs}

@app.post("/post-msg/")
async def insert_or_update_msg(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        # Attempt to parse the request body as JSON
        parsed_body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    receiver = parsed_body.get("receiver")
    msg = parsed_body.get("msg")

    print(f"Message receiver: {receiver}, msg: {msg}")

    try:
        # Insert or update the latest value in the "tels" table
        result = await db.execute(msgs.insert().values(receiver=receiver, msg=msg))
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok"}


@app.post("/post-text-msg/")
async def insert_or_update_text_msg(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        parsed_body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    receiver = parsed_body.get("receiver")
    text_msg = parsed_body.get("text_msg")

    print(f"Message receiver: {receiver}, text_msg: {text_msg}")

    try:
        result = await db.execute(msgs.insert().values(receiver=receiver, text_msg=text_msg))
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok"}


@app.get("/all-messages/", response_class=HTMLResponse)
async def get_all_messages(db: AsyncSession = Depends(get_db)):
    query = select(
        msgs.c.id,
        msgs.c.msg,
        msgs.c.text_msg,
        msgs.c.created_at,
        msgs.c.receiver
    ).order_by(msgs.c.created_at.desc())
    
    result = await db.execute(query)
    all_messages = result.fetchall()
    
    if not all_messages:
        return "<p>No messages found</p>"
    
    html_table = """
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Receiver</th>
                <th>Msg</th>
                <th>Text Msg</th>
                <th>Timestamp</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for row in all_messages:
        html_table += f"""
            <tr>
                <td>{row.id}</td>
                <td>{row.receiver}</td>
                <td>{row.msg if row.msg is not None else ''}</td>
                <td>{row.text_msg if row.text_msg is not None else ''}</td>
                <td>{row.created_at.strftime('%Y-%m-%d %H:%M:%S') if row.created_at else ''}</td>            </tr>
        """
    
    html_table += """
        </tbody>
    </table>
    """
    
    return html_table