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

app = FastAPI(title="Stock Manager with Elliott Wave")

# MongoDB Connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.stock_manager
stocks_collection = db.stocks
watchlist_collection = db.watchlist
wave_analysis_collection = db.wave_analysis

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
    """Watchlist page with Elliott Wave analysis"""
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

# Elliott Wave Analysis CRUD
@app.post("/api/wave-analysis")
async def create_wave_analysis(
    symbol: str = Form(...),
    date: str = Form(...),
    wave_number: str = Form(default="unknown"),
    wave_type: str = Form(default="unknown"),
    sub_wave: str = Form(default="unknown"),
    notes: str = Form(default=""),
    trend_direction: str = Form(default="unknown"),
    confidence_level: str = Form(default="medium"),
    entry_price: float = Form(default=None),
    target_price: float = Form(default=None),
    stop_loss: float = Form(default=None)
):
    """Add Elliott Wave analysis for a symbol"""
    try:
        analysis_date = datetime.strptime(date, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    wave_data = {
        "symbol": symbol.upper(),
        "date": analysis_date,
        "wave_number": wave_number,
        "wave_type": wave_type,
        "sub_wave": sub_wave,
        "notes": notes,
        "trend_direction": trend_direction,
        "confidence_level": confidence_level,
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    result = await wave_analysis_collection.insert_one(wave_data)
    
    if result.inserted_id:
        return JSONResponse({"success": True, "message": "Wave analysis saved"})
    raise HTTPException(status_code=400, detail="Failed to save")

@app.get("/api/wave-analysis")
async def get_wave_analysis(
    symbol: Optional[str] = None,
    date: Optional[str] = None,
    wave_number: Optional[str] = None
):
    """Get wave analysis with filters"""
    query = {}
    
    if symbol:
        query["symbol"] = symbol.upper()
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d")
            query["date"] = {
                "$gte": filter_date.replace(hour=0, minute=0, second=0),
                "$lte": filter_date.replace(hour=23, minute=59, second=59)
            }
        except:
            pass
    
    if wave_number and wave_number != "all":
        query["wave_number"] = wave_number
    
    analyses = await wave_analysis_collection.find(query).sort("date", -1).to_list(1000)
    serialized = [serialize_doc(a) for a in analyses]
    
    return JSONResponse({"analyses": serialized})

@app.put("/api/wave-analysis/{analysis_id}")
async def update_wave_analysis(
    analysis_id: str,
    symbol: str = Form(...),
    date: str = Form(...),
    wave_number: str = Form(...),
    wave_type: str = Form(...),
    sub_wave: str = Form(...),
    notes: str = Form(default=""),
    trend_direction: str = Form(default="unknown"),
    confidence_level: str = Form(default="medium"),
    entry_price: float = Form(default=None),
    target_price: float = Form(default=None),
    stop_loss: float = Form(default=None)
):
    """Update wave analysis"""
    try:
        analysis_date = datetime.strptime(date, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    update_data = {
        "symbol": symbol.upper(),
        "date": analysis_date,
        "wave_number": wave_number,
        "wave_type": wave_type,
        "sub_wave": sub_wave,
        "notes": notes,
        "trend_direction": trend_direction,
        "confidence_level": confidence_level,
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "updated_at": datetime.now()
    }
    
    result = await wave_analysis_collection.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": update_data}
    )
    
    if result.modified_count:
        return JSONResponse({"success": True, "message": "Wave analysis updated"})
    raise HTTPException(status_code=404, detail="Analysis not found")

@app.delete("/api/wave-analysis/{analysis_id}")
async def delete_wave_analysis(analysis_id: str):
    """Delete wave analysis"""
    try:
        result = await wave_analysis_collection.delete_one({"_id": ObjectId(analysis_id)})
        if result.deleted_count:
            return JSONResponse({"success": True, "message": "Wave analysis deleted"})
        raise HTTPException(status_code=404, detail="Analysis not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

# Get available dates
@app.get("/api/dates")
async def get_available_dates():
    """Get all unique dates from wave analysis"""
    pipeline = [
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}}}},
        {"$sort": {"_id": -1}}
    ]
    dates_cursor = wave_analysis_collection.aggregate(pipeline)
    dates = []
    async for doc in dates_cursor:
        if doc["_id"]:
            dates.append(doc["_id"])
    
    return JSONResponse({"dates": dates})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)