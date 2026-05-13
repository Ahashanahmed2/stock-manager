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

# MongoDB Connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
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
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    return templates.TemplateResponse("watchlist.html", {"request": request})

# ==================== HEALTH CHECK (UptimeRobot) ====================

@app.head("/api/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

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
        print(f"Error creating stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks")
async def get_stocks(date: Optional[str] = None, search: Optional[str] = None):
    """Get stocks with optional filters"""
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


@app.get("/api/stocks/{stock_id}")
async def get_stock(stock_id: str):
    """Get single stock by ID"""
    try:
        stock = await stocks_collection.find_one({"_id": ObjectId(stock_id)})
        if stock:
            return JSONResponse({"stock": serialize_doc(stock)})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.put("/api/stocks/{stock_id}")
async def update_stock(stock_id: str, request: Request):
    """Update stock entry"""
    try:
        form_data = await request.form()
        
        date_str = form_data.get("date", "")
        try:
            stock_date = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            raise HTTPException(status_code=400, detail="Invalid date")
        
        update_data = {
            "symbol": form_data.get("symbol", "").upper(),
            "buy_price": float(form_data.get("buy_price", 0)),
            "quantity": int(form_data.get("quantity", 0)),
            "date": stock_date,
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
        print(f"Error updating stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/stocks/{stock_id}")
async def delete_stock(stock_id: str):
    """Delete single stock"""
    try:
        result = await stocks_collection.delete_one({"_id": ObjectId(stock_id)})
        if result.deleted_count:
            return JSONResponse({"success": True, "message": "Stock deleted"})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.delete("/api/stocks/date/{date}")
async def delete_stocks_by_date(date: str):
    """Delete all stocks for a specific date"""
    try:
        filter_date = datetime.strptime(date, "%Y-%m-%d")
        result = await stocks_collection.delete_many({
            "date": {
                "$gte": filter_date.replace(hour=0, minute=0, second=0),
                "$lte": filter_date.replace(hour=23, minute=59, second=59)
            }
        })
        return JSONResponse({
            "success": True,
            "message": f"Deleted {result.deleted_count} stocks from {date}"
        })
    except:
        raise HTTPException(status_code=400, detail="Invalid date")


# ==================== WAVE ANALYSIS CRUD ====================

@app.post("/api/advanced-wave-analysis")
async def save_wave_analysis(request: Request):
    """Save Elliott Wave analysis from watchlist.html"""
    try:
        form_data = await request.form()
        
        # Date handle
        date_str = form_data.get("date", "")
        if date_str:
            try:
                analysis_date = datetime.strptime(date_str, "%Y-%m-%d")
            except:
                analysis_date = datetime.now()
        else:
            analysis_date = datetime.now()
        
        # Entry price handle
        entry_price = form_data.get("entry_price", "")
        if entry_price and str(entry_price).strip():
            try:
                entry_price = float(entry_price)
            except:
                entry_price = None
        else:
            entry_price = None
        
        wave_data = {
            # Basic Info
            "symbol": form_data.get("symbol", "").upper(),
            "analysis_date": analysis_date,
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
            
            # Sub Wave A / Wave 1
            "sub_wave_a": {
                "type": form_data.get("sub_a_type", "unknown"),
                "running": form_data.get("sub_a_running", "no"),
                "status": form_data.get("sub_a_status", "running"),
                "current_subwave": form_data.get("sub_a_current", "unknown"),
                "detail": form_data.get("sub_a_detail", "unknown")
            },
            
            # Sub Wave B / Wave 2
            "sub_wave_b": {
                "type": form_data.get("sub_b_type", "unknown"),
                "running": form_data.get("sub_b_running", "no"),
                "status": form_data.get("sub_b_status", "running"),
                "current_position": form_data.get("sub_b_current", "unknown"),
                "detail": form_data.get("sub_b_detail", "unknown"),
                "internal_type": form_data.get("sub_b_internal_type", "unknown"),
                "terminal_type": form_data.get("sub_b_terminal_type", "none")
            },
            
            # Sub Wave C / Wave 3
            "sub_wave_c": {
                "type": form_data.get("sub_c_type", "unknown"),
                "terminal": form_data.get("sub_c_terminal", "no"),
                "status": form_data.get("sub_c_status", "running"),
                "current_subwave": form_data.get("sub_c_current", "unknown"),
                "detail": form_data.get("sub_c_detail", "unknown")
            },
            
            # Wave 4 & 5 (for impulse)
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
            
            # Notes
            "notes": form_data.get("notes", ""),
            
            # Timestamps
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            
            # Verification tracking
            "is_verified": "pending",
            "verification_date": None,
            "was_correct": None,
            "actual_outcome": None
        }
        
        result = await wave_analysis_collection.insert_one(wave_data)
        
        if result.inserted_id:
            # Save to history for tracking
            history_entry = {
                "analysis_id": str(result.inserted_id),
                "symbol": wave_data["symbol"],
                "analysis_date": analysis_date,
                "main_wave": wave_data["main_wave"]["wave_number"],
                "confidence_level": wave_data["confidence_level"],
                "is_verified": "pending",
                "created_at": datetime.now()
            }
            await wave_history_collection.insert_one(history_entry)
            
            return JSONResponse({
                "success": True,
                "message": "Wave analysis saved successfully",
                "analysis_id": str(result.inserted_id)
            })
        else:
            raise HTTPException(status_code=400, detail="Failed to save analysis")
            
    except Exception as e:
        print(f"Error saving wave analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/advanced-wave-analysis")
async def get_wave_analyses(
    symbol: Optional[str] = None,
    date: Optional[str] = None,
    primary_wave: Optional[str] = None
):
    """Get wave analyses with filters"""
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


@app.get("/api/advanced-wave-analysis/{analysis_id}")
async def get_single_wave_analysis(analysis_id: str):
    """Get single wave analysis by ID (for edit)"""
    try:
        analysis = await wave_analysis_collection.find_one({"_id": ObjectId(analysis_id)})
        if analysis:
            return JSONResponse({"analysis": serialize_doc(analysis)})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.put("/api/advanced-wave-analysis/{analysis_id}")
async def update_wave_analysis(analysis_id: str, request: Request):
    """Update wave analysis"""
    try:
        form_data = await request.form()
        
        date_str = form_data.get("date", "")
        try:
            analysis_date = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            analysis_date = datetime.now()
        
        entry_price = form_data.get("entry_price", "")
        if entry_price and str(entry_price).strip():
            try:
                entry_price = float(entry_price)
            except:
                entry_price = None
        else:
            entry_price = None
        
        update_data = {
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
            "updated_at": datetime.now()
        }
        
        result = await wave_analysis_collection.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": update_data}
        )
        
        if result.modified_count:
            return JSONResponse({"success": True, "message": "Analysis updated"})
        raise HTTPException(status_code=404, detail="Not found")
        
    except Exception as e:
        print(f"Error updating analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/advanced-wave-analysis/{analysis_id}")
async def delete_wave_analysis(analysis_id: str):
    """Delete wave analysis"""
    try:
        result = await wave_analysis_collection.delete_one({"_id": ObjectId(analysis_id)})
        if result.deleted_count:
            # Also remove from history
            await wave_history_collection.delete_one({"analysis_id": analysis_id})
            return JSONResponse({"success": True, "message": "Analysis deleted"})
        raise HTTPException(status_code=404, detail="Not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")


@app.post("/api/verify-analysis/{analysis_id}")
async def verify_analysis(request: Request, analysis_id: str):
    """Verify if wave analysis prediction was correct"""
    try:
        form_data = await request.form()
        
        was_correct = form_data.get("was_correct", "false").lower() == "true"
        
        update_data = {
            "is_verified": "verified",
            "verification_date": datetime.now(),
            "actual_outcome": form_data.get("actual_outcome", ""),
            "was_correct": was_correct
        }
        
        result = await wave_analysis_collection.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": update_data}
        )
        
        # Update history
        await wave_history_collection.update_one(
            {"analysis_id": analysis_id},
            {"$set": {
                "is_verified": "verified",
                "was_correct": was_correct,
                "verification_date": datetime.now()
            }}
        )
        
        if result.modified_count:
            return JSONResponse({"success": True, "message": "Analysis verified"})
        raise HTTPException(status_code=404, detail="Not found")
        
    except Exception as e:
        print(f"Error verifying analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis-statistics")
async def get_analysis_statistics(symbol: Optional[str] = None):
    """Get wave analysis accuracy statistics"""
    query = {}
    if symbol:
        query["symbol"] = symbol.upper()
    
    total = await wave_analysis_collection.count_documents(query)
    verified = await wave_analysis_collection.count_documents({**query, "is_verified": "verified"})
    correct = await wave_analysis_collection.count_documents({**query, "was_correct": True})
    
    # Wave distribution
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$main_wave.wave_number",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    wave_stats = []
    try:
        wave_stats = await wave_analysis_collection.aggregate(pipeline).to_list(20)
    except:
        pass
    
    return JSONResponse({
        "total_analyses": total,
        "verified_analyses": verified,
        "correct_analyses": correct,
        "accuracy_rate": round((correct / verified * 100), 1) if verified > 0 else 0,
        "wave_distribution": [{"wave": w["_id"], "count": w["count"]} for w in wave_stats]
    })


@app.get("/api/dates")
async def get_available_dates():
    """Get all unique analysis dates"""
    pipeline = [
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$analysis_date"}}}},
        {"$sort": {"_id": -1}}
    ]
    dates = []
    try:
        dates_cursor = wave_analysis_collection.aggregate(pipeline)
        async for doc in dates_cursor:
            if doc["_id"]:
                dates.append(doc["_id"])
    except:
        pass
    
    return JSONResponse({"dates": dates})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)