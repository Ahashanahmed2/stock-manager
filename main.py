from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
import os
from typing import Optional

app = FastAPI(title="Stock Manager with Elliott Wave")

# MongoDB Connection - Render env থেকে নিবে
MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    print("⚠️ WARNING: MONGODB_URL not set!")
    MONGODB_URL = "mongodb://localhost:27017"

client = AsyncIOMotorClient(MONGODB_URL)
db = client.stock_manager

# Collections
stocks_collection = db.stocks
wave_analysis_collection = db.wave_analysis
wave_history_collection = db.wave_history

# Templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def serialize_doc(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

# ==================== PAGE ROUTES ====================

@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/watchlist", response_class=HTMLResponse)
@app.head("/watchlist")
async def watchlist_page(request: Request):
    return templates.TemplateResponse("watchlist.html", {"request": request})

# ==================== HEALTH CHECK (UptimeRobot) ====================

@app.head("/api/health")
@app.get("/api/health")
async def health_check():
    try:
        # MongoDB connection চেক
        await db.command("ping")
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

# ==================== STOCK CRUD ====================

@app.post("/api/stocks")
async def create_stock(request: Request):
    """Add new stock entry"""
    try:
        form_data = await request.form()
        
        date_str = form_data.get("date", "")
        if date_str:
            try:
                stock_date = datetime.strptime(date_str, "%Y-%m-%d")
            except:
                stock_date = datetime.now()
        else:
            stock_date = datetime.now()
        
        stock_data = {
            "symbol": form_data.get("symbol", "").upper(),
            "buy_price": float(form_data.get("buy_price", 0)),
            "quantity": int(form_data.get("quantity", 0)),
            "date": stock_date,
            "created_at": datetime.now()
        }
        
        result = await stocks_collection.insert_one(stock_data)
        
        if result.inserted_id:
            return JSONResponse({"success": True, "message": "Stock added successfully"})
        raise HTTPException(status_code=400, detail="Failed to add stock")
        
    except Exception as e:
        print(f"ERROR creating stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks")
async def get_stocks(date: Optional[str] = None, search: Optional[str] = None):
    """Get stocks with optional filters"""
    try:
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
        
        stocks = await stocks_collection.find(query).sort("date", -1).to_list(1000)
        return JSONResponse({"stocks": [serialize_doc(s) for s in stocks]})
    except Exception as e:
        print(f"ERROR getting stocks: {e}")
        return JSONResponse({"stocks": [], "error": str(e)})


@app.get("/api/stocks/{stock_id}")
async def get_stock(stock_id: str):
    try:
        stock = await stocks_collection.find_one({"_id": ObjectId(stock_id)})
        if stock:
            return JSONResponse({"stock": serialize_doc(stock)})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.put("/api/stocks/{stock_id}")
async def update_stock(stock_id: str, request: Request):
    try:
        form_data = await request.form()
        
        update_data = {
            "symbol": form_data.get("symbol", "").upper(),
            "buy_price": float(form_data.get("buy_price", 0)),
            "quantity": int(form_data.get("quantity", 0)),
            "date": datetime.strptime(form_data.get("date", ""), "%Y-%m-%d"),
            "updated_at": datetime.now()
        }
        
        result = await stocks_collection.update_one(
            {"_id": ObjectId(stock_id)},
            {"$set": update_data}
        )
        
        if result.modified_count:
            return JSONResponse({"success": True, "message": "Stock updated"})
        raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        print(f"ERROR updating stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/stocks/{stock_id}")
async def delete_stock(stock_id: str):
    try:
        result = await stocks_collection.delete_one({"_id": ObjectId(stock_id)})
        if result.deleted_count:
            return JSONResponse({"success": True, "message": "Stock deleted"})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.delete("/api/stocks/date/{date}")
async def delete_stocks_by_date(date: str):
    try:
        filter_date = datetime.strptime(date, "%Y-%m-%d")
        result = await stocks_collection.delete_many({
            "date": {
                "$gte": filter_date.replace(hour=0, minute=0, second=0),
                "$lte": filter_date.replace(hour=23, minute=59, second=59)
            }
        })
        return JSONResponse({"success": True, "message": f"Deleted {result.deleted_count} stocks"})
    except:
        raise HTTPException(status_code=400, detail="Invalid date")


# ==================== WAVE ANALYSIS CRUD ====================

@app.post("/api/advanced-wave-analysis")
async def save_wave_analysis(request: Request):
    """Save Elliott Wave analysis"""
    try:
        form_data = await request.form()
        
        date_str = form_data.get("date", "")
        if date_str:
            try:
                analysis_date = datetime.strptime(date_str, "%Y-%m-%d")
            except:
                analysis_date = datetime.now()
        else:
            analysis_date = datetime.now()
        
        entry_price = form_data.get("entry_price", "")
        if entry_price and str(entry_price).strip():
            try:
                entry_price = float(entry_price)
            except:
                entry_price = None
        else:
            entry_price = None
        
        wave_data = {
            "symbol": form_data.get("symbol", "").upper(),
            "analysis_date": analysis_date,
            "confidence_level": form_data.get("confidence_level", "medium"),
            "trend_direction": form_data.get("trend_direction", "unknown"),
            "entry_price": entry_price,
            "main_wave": {
                "wave_number": form_data.get("main_wave_number", "unknown"),
                "wave_type": form_data.get("main_wave_type", "unknown"),
                "pattern": form_data.get("main_pattern", "unknown"),
                "position": form_data.get("main_wave_position", "unknown")
            },
            "sub_wave_a": {
                "type": form_data.get("sub_a_type", "unknown"),
                "running": form_data.get("sub_a_running", "no"),
                "status": form_data.get("sub_a_status", "running"),
                "current_subwave": form_data.get("sub_a_current", "unknown"),
                "detail": form_data.get("sub_a_detail", "unknown")
            },
            "sub_wave_b": {
                "type": form_data.get("sub_b_type", "unknown"),
                "running": form_data.get("sub_b_running", "no"),
                "status": form_data.get("sub_b_status", "running"),
                "current_position": form_data.get("sub_b_current", "unknown"),
                "detail": form_data.get("sub_b_detail", "unknown"),
                "internal_type": form_data.get("sub_b_internal_type", "unknown"),
                "terminal_type": form_data.get("sub_b_terminal_type", "none")
            },
            "sub_wave_c": {
                "type": form_data.get("sub_c_type", "unknown"),
                "terminal": form_data.get("sub_c_terminal", "no"),
                "status": form_data.get("sub_c_status", "running"),
                "current_subwave": form_data.get("sub_c_current", "unknown"),
                "detail": form_data.get("sub_c_detail", "unknown")
            },
            "wave_4": {
                "type": form_data.get("wave_4_type", "unknown"),
                "status": form_data.get("wave_4_status", "not_started"),
                "current": form_data.get("wave_4_current", "unknown")
            },
            "wave_5": {
                "type": form_data.get("wave_5_type", "unknown"),
                "status": form_data.get("wave_5_status", "not_started"),
                "current": form_data.get("wave_5_current", "unknown")
            },
            "notes": form_data.get("notes", ""),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "is_verified": "pending",
            "was_correct": None
        }
        
        result = await wave_analysis_collection.insert_one(wave_data)
        
        if result.inserted_id:
            return JSONResponse({
                "success": True,
                "message": "Wave analysis saved",
                "analysis_id": str(result.inserted_id)
            })
        raise HTTPException(status_code=400, detail="Failed to save")
        
    except Exception as e:
        print(f"ERROR saving wave analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/advanced-wave-analysis")
async def get_wave_analyses(
    symbol: Optional[str] = None,
    date: Optional[str] = None,
    primary_wave: Optional[str] = None
):
    try:
        query = {}
        
        if symbol:
            query["symbol"] = symbol.upper()
        
        if date:
            try:
                filter_date = datetime.strptime(date, "%Y-%m-%d")
                query["analysis_date"] = {
                    "$gte": filter_date.replace(hour=0, minute=0, second=0),
                    "$lte": filter_date.replace(hour=23, minute=59, second=59)
                }
            except:
                pass
        
        if primary_wave and primary_wave != "all":
            query["main_wave.wave_number"] = primary_wave
        
        analyses = await wave_analysis_collection.find(query).sort("analysis_date", -1).to_list(100)
        serialized = [serialize_doc(a) for a in analyses]
        
        return JSONResponse({"analyses": serialized, "count": len(serialized)})
    except Exception as e:
        print(f"ERROR getting analyses: {e}")
        return JSONResponse({"analyses": [], "count": 0, "error": str(e)})


@app.delete("/api/advanced-wave-analysis/{analysis_id}")
async def delete_wave_analysis(analysis_id: str):
    try:
        result = await wave_analysis_collection.delete_one({"_id": ObjectId(analysis_id)})
        if result.deleted_count:
            return JSONResponse({"success": True, "message": "Analysis deleted"})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)