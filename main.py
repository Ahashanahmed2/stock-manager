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
    """Convert MongoDB document to JSON serializable format"""
    if doc is None:
        return None
    
    if isinstance(doc, datetime):
        return doc.isoformat()
    
    if isinstance(doc, ObjectId):
        return str(doc)
    
    if isinstance(doc, dict):
        serialized = {}
        for key, value in doc.items():
            if key == "_id":
                serialized[key] = str(value)
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                serialized[key] = str(value)
            elif isinstance(value, dict):
                serialized[key] = serialize_doc(value)
            elif isinstance(value, list):
                serialized[key] = [serialize_doc(item) for item in value]
            else:
                serialized[key] = value
        return serialized
    
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

# ==================== STOCK CRUD ====================

@app.post("/api/stocks")
async def create_stock(request: Request):
    """Add new stock entry"""
    try:
        form_data = await request.form()
        
        symbol = form_data.get("symbol", "").strip()
        buy_price = form_data.get("buy_price", "0")
        quantity = form_data.get("quantity", "0")
        date_str = form_data.get("date", "")
        
        # Validation
        if not symbol:
            return JSONResponse({"success": False, "message": "Symbol is required"}, status_code=400)
        
        # Date handle
        if date_str:
            try:
                stock_date = datetime.strptime(date_str, "%Y-%m-%d")
            except:
                stock_date = datetime.now()
        else:
            stock_date = datetime.now()
        
        # Price & Quantity handle
        try:
            buy_price = float(buy_price)
        except:
            buy_price = 0.0
            
        try:
            quantity = int(quantity)
        except:
            quantity = 0
        
        stock_data = {
            "symbol": symbol.upper(),
            "buy_price": buy_price,
            "quantity": quantity,
            "date": stock_date,
            "created_at": datetime.now()
        }
        
        print(f"📝 Saving stock: {stock_data}")
        
        result = await stocks_collection.insert_one(stock_data)
        
        if result.inserted_id:
            print(f"✅ Stock saved with ID: {result.inserted_id}")
            return JSONResponse({
                "success": True, 
                "message": "Stock added successfully",
                "id": str(result.inserted_id)
            })
        else:
            return JSONResponse({"success": False, "message": "Failed to add stock"}, status_code=400)
        
    except Exception as e:
        print(f"❌ ERROR creating stock: {e}")
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


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

        # Serialize each stock
        serialized_stocks = []
        for stock in stocks:
            serialized_stock = serialize_doc(stock)
            serialized_stocks.append(serialized_stock)

        return JSONResponse({"stocks": serialized_stocks})

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
        
        # Debug: print all received data
        print("📥 Received form data:")
        for key, value in form_data.items():
            print(f"   {key}: {value}")
        
        # FIX: use "analysis_date" to match HTML form
        date_str = form_data.get("analysis_date", "") or form_data.get("date", "")
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
            "timeframe": form_data.get("timeframe", "daily"),
            "confidence_level": form_data.get("confidence_level", "medium"),
            "trend_direction": form_data.get("trend_direction", "unknown"),
            "entry_price": entry_price,
            
            # Main Wave Structure
            "main_wave": {
                "wave_number": form_data.get("main_wave_number", "unknown"),
                "wave_type": form_data.get("main_wave_type", "unknown"),
                "pattern": form_data.get("main_pattern", "unknown"),
                "position": form_data.get("main_wave_position", "unknown")
            },
            
            # Sub Wave A
            "sub_wave_a": {
                "status": form_data.get("sub_a_status", "running"),
                "type": form_data.get("sub_a_type", "unknown"),
                "current": form_data.get("sub_a_current", "unknown"),
                "running": form_data.get("sub_a_running", "no"),
                "detail": form_data.get("sub_a_detail", "unknown")
            },
            
            # Sub Wave B
            "sub_wave_b": {
                "status": form_data.get("sub_b_status", "running"),
                "type": form_data.get("sub_b_type", "unknown"),
                "current": form_data.get("sub_b_current", "unknown"),
                "running": form_data.get("sub_b_running", "no"),
                "detail": form_data.get("sub_b_detail", "unknown"),
                "internal_type": form_data.get("sub_b_internal_type", "unknown"),
                "terminal_type": form_data.get("sub_b_terminal_type", "none")
            },
            
            # Sub Wave C
            "sub_wave_c": {
                "status": form_data.get("sub_c_status", "running"),
                "type": form_data.get("sub_c_type", "unknown"),
                "current": form_data.get("sub_c_current", "unknown"),
                "terminal": form_data.get("sub_c_terminal", "no"),
                "detail": form_data.get("sub_c_detail", "unknown")
            },
            
            # Wave 4 & 5
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
        
        print(f"📝 Saving wave data: {wave_data['symbol']} - Wave {wave_data['main_wave']['wave_number']}")
        
        result = await wave_analysis_collection.insert_one(wave_data)
        
        if result.inserted_id:
            print(f"✅ Wave analysis saved with ID: {result.inserted_id}")
            return JSONResponse({
                "success": True,
                "message": "Wave analysis saved successfully!",
                "analysis_id": str(result.inserted_id)
            })
        else:
            raise HTTPException(status_code=400, detail="Failed to save")
            
    except Exception as e:
        print(f"❌ ERROR saving wave analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
            


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
