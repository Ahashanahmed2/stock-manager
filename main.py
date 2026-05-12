# main.py
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, date
import os
from typing import Optional, List
import json

app = FastAPI(title="Stock Manager")

# MongoDB Connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.stock_manager
stocks_collection = db.stocks
watchlist_collection = db.watchlist

# Templates
templates = Jinja2Templates(directory="templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Helper function to serialize MongoDB documents
def serialize_doc(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

# ==================== ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page with stock table"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    """Watchlist page"""
    return templates.TemplateResponse("watchlist.html", {"request": request})

# ==================== API ENDPOINTS ====================

# Head API for UptimeRobot
@app.head("/api/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint for UptimeRobot"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# Stock Data CRUD
@app.post("/api/stocks")
async def create_stock(
    symbol: str = Form(...),
    buy_price: float = Form(...),
    quantity: int = Form(...),
    date: str = Form(default=None)
):
    """Add new stock entry"""
    try:
        stock_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    except:
        stock_date = datetime.now()
    
    stock_data = {
        "symbol": symbol.upper(),
        "buy_price": buy_price,
        "quantity": quantity,
        "date": stock_date,
        "created_at": datetime.now()
    }
    
    result = await stocks_collection.insert_one(stock_data)
    
    if result.inserted_id:
        return JSONResponse({"success": True, "message": "Stock added successfully"})
    raise HTTPException(status_code=400, detail="Failed to add stock")

@app.get("/api/stocks")
async def get_stocks(date: Optional[str] = None, search: Optional[str] = None):
    """Get stocks with optional date filter or symbol search"""
    query = {}
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = filter_date.replace(hour=0, minute=0, second=0)
            end_date = filter_date.replace(hour=23, minute=59, second=59)
            query["date"] = {"$gte": start_date, "$lte": end_date}
        except:
            pass
    
    if search:
        query["symbol"] = {"$regex": search.upper(), "$options": "i"}
    
    stocks = await stocks_collection.find(query).sort("date", -1).to_list(1000)
    serialized_stocks = [serialize_doc(stock) for stock in stocks]
    
    return JSONResponse({"stocks": serialized_stocks})

@app.get("/api/stocks/{stock_id}")
async def get_stock(stock_id: str):
    """Get single stock by ID"""
    try:
        stock = await stocks_collection.find_one({"_id": ObjectId(stock_id)})
        if stock:
            return JSONResponse({"stock": serialize_doc(stock)})
        raise HTTPException(status_code=404, detail="Stock not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

@app.put("/api/stocks/{stock_id}")
async def update_stock(
    stock_id: str,
    symbol: str = Form(...),
    buy_price: float = Form(...),
    quantity: int = Form(...),
    date: str = Form(...)
):
    """Update stock entry"""
    try:
        stock_date = datetime.strptime(date, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    update_data = {
        "symbol": symbol.upper(),
        "buy_price": buy_price,
        "quantity": quantity,
        "date": stock_date,
        "updated_at": datetime.now()
    }
    
    result = await stocks_collection.update_one(
        {"_id": ObjectId(stock_id)},
        {"$set": update_data}
    )
    
    if result.modified_count:
        return JSONResponse({"success": True, "message": "Stock updated"})
    raise HTTPException(status_code=404, detail="Stock not found")

@app.delete("/api/stocks/{stock_id}")
async def delete_stock(stock_id: str):
    """Delete single stock"""
    try:
        result = await stocks_collection.delete_one({"_id": ObjectId(stock_id)})
        if result.deleted_count:
            return JSONResponse({"success": True, "message": "Stock deleted"})
        raise HTTPException(status_code=404, detail="Stock not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

@app.delete("/api/stocks/date/{date}")
async def delete_stocks_by_date(date: str):
    """Delete all stocks for a specific date"""
    try:
        filter_date = datetime.strptime(date, "%Y-%m-%d")
        start_date = filter_date.replace(hour=0, minute=0, second=0)
        end_date = filter_date.replace(hour=23, minute=59, second=59)
        
        result = await stocks_collection.delete_many({
            "date": {"$gte": start_date, "$lte": end_date}
        })
        
        return JSONResponse({
            "success": True,
            "message": f"Deleted {result.deleted_count} stocks from {date}"
        })
    except:
        raise HTTPException(status_code=400, detail="Invalid date")

# Watchlist CRUD
@app.post("/api/watchlist")
async def add_to_watchlist(
    symbol: str = Form(...),
    date: str = Form(default=None)
):
    """Add symbol to watchlist"""
    try:
        watch_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    except:
        watch_date = datetime.now()
    
    # Check if already exists
    existing = await watchlist_collection.find_one({
        "symbol": symbol.upper(),
        "date": {
            "$gte": watch_date.replace(hour=0, minute=0, second=0),
            "$lte": watch_date.replace(hour=23, minute=59, second=59)
        }
    })
    
    if existing:
        return JSONResponse({"success": False, "message": "Symbol already in watchlist for this date"})
    
    watchlist_data = {
        "symbol": symbol.upper(),
        "date": watch_date,
        "created_at": datetime.now()
    }
    
    result = await watchlist_collection.insert_one(watchlist_data)
    
    if result.inserted_id:
        return JSONResponse({"success": True, "message": "Added to watchlist"})
    raise HTTPException(status_code=400, detail="Failed to add")

@app.get("/api/watchlist")
async def get_watchlist(date: Optional[str] = None, search: Optional[str] = None):
    """Get watchlist with filters"""
    query = {}
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d")
            query["date"] = {
                "$gte": filter_date.replace(hour=0, minute=0, second=0),
                "$lte": filter_date.replace(hour=23, minute=59, second=59)
            }
        except:
            pass
    
    if search:
        query["symbol"] = {"$regex": search.upper(), "$options": "i"}
    
    watchlist = await watchlist_collection.find(query).sort("date", -1).to_list(1000)
    serialized_watchlist = [serialize_doc(item) for item in watchlist]
    
    return JSONResponse({"watchlist": serialized_watchlist})

@app.put("/api/watchlist/{item_id}")
async def update_watchlist(item_id: str, symbol: str = Form(...)):
    """Update watchlist item"""
    try:
        result = await watchlist_collection.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {"symbol": symbol.upper(), "updated_at": datetime.now()}}
        )
        if result.modified_count:
            return JSONResponse({"success": True, "message": "Watchlist updated"})
        raise HTTPException(status_code=404, detail="Item not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

@app.delete("/api/watchlist/{item_id}")
async def delete_from_watchlist(item_id: str):
    """Remove from watchlist"""
    try:
        result = await watchlist_collection.delete_one({"_id": ObjectId(item_id)})
        if result.deleted_count:
            return JSONResponse({"success": True, "message": "Removed from watchlist"})
        raise HTTPException(status_code=404, detail="Item not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

# Get available dates
@app.get("/api/dates")
async def get_available_dates():
    """Get all unique dates from stocks"""
    pipeline = [
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}}}},
        {"$sort": {"_id": -1}}
    ]
    dates_cursor = stocks_collection.aggregate(pipeline)
    dates = []
    async for doc in dates_cursor:
        if doc["_id"]:
            dates.append(doc["_id"])
    
    return JSONResponse({"dates": dates})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
