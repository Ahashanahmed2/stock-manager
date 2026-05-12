from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
import os
from typing import Optional

app = FastAPI(title="Advanced Elliott Wave Analyzer")

# MongoDB Connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.stock_manager

# Collections
stocks_collection = db.stocks
wave_analysis_collection = db.wave_analysis
wave_history_collection = db.wave_history  # Track analysis accuracy over time

# Templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def serialize_doc(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc

# ==================== ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request):
    return templates.TemplateResponse("watchlist.html", {"request": request})

@app.get("/wave-analysis", response_class=HTMLResponse)
async def wave_analysis_page(request: Request):
    """New advanced Elliott Wave analysis page"""
    return templates.TemplateResponse("wave_analysis.html", {"request": request})

# Head API for UptimeRobot
@app.head("/api/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ==================== ADVANCED WAVE ANALYSIS API ====================

@app.post("/api/advanced-wave-analysis")
async def create_advanced_wave_analysis(
    symbol: str = Form(...),
    analysis_date: str = Form(...),
    # Grand Supercycle Level
    grand_supercycle_wave: str = Form(default="unknown"),
    grand_supercycle_position: str = Form(default="unknown"),
    # Supercycle Level
    supercycle_wave: str = Form(default="unknown"),
    supercycle_pattern: str = Form(default="unknown"),
    # Cycle Level
    cycle_wave: str = Form(default="unknown"),
    cycle_pattern: str = Form(default="unknown"),
    # Primary Level (Main analysis)
    primary_wave: str = Form(...),
    primary_wave_type: str = Form(default="unknown"),
    primary_pattern: str = Form(default="unknown"),
    primary_subwave: str = Form(default="unknown"),
    primary_subwave_detail: str = Form(default="unknown"),
    # Intermediate Level
    intermediate_wave: str = Form(default="unknown"),
    intermediate_pattern: str = Form(default="unknown"),
    intermediate_subwave: str = Form(default="unknown"),
    # Minor Level
    minor_wave: str = Form(default="unknown"),
    minor_pattern: str = Form(default="unknown"),
    # Minute Level
    minute_wave: str = Form(default="unknown"),
    minute_pattern: str = Form(default="unknown"),
    # Analysis Details
    wave_position: str = Form(default="unknown"),  # starting, middle, ending
    fibonacci_level: str = Form(default=""),
    trend_direction: str = Form(default="unknown"),
    confidence_level: str = Form(default="medium"),
    entry_price: float = Form(default=None),
    target_price: float = Form(default=None),
    stop_loss: float = Form(default=None),
    risk_reward_ratio: str = Form(default=""),
    notes: str = Form(default=""),
    chart_image_url: str = Form(default=""),
    tags: str = Form(default=""),
    # Analysis Accuracy Tracking
    expected_completion_date: str = Form(default=""),
    expected_price_target: float = Form(default=None),
    is_verified: str = Form(default="pending")
):
    """Create advanced Elliott Wave analysis with full hierarchical structure"""
    try:
        analysis_date_obj = datetime.strptime(analysis_date, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    expected_completion = None
    if expected_completion_date:
        try:
            expected_completion = datetime.strptime(expected_completion_date, "%Y-%m-%d")
        except:
            pass
    
    wave_data = {
        # Symbol & Date
        "symbol": symbol.upper(),
        "analysis_date": analysis_date_obj,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        
        # Full Hierarchical Wave Structure
        "grand_supercycle": {
            "wave": grand_supercycle_wave,
            "position": grand_supercycle_position
        },
        "supercycle": {
            "wave": supercycle_wave,
            "pattern": supercycle_pattern
        },
        "cycle": {
            "wave": cycle_wave,
            "pattern": cycle_pattern
        },
        "primary": {
            "wave": primary_wave,
            "type": primary_wave_type,
            "pattern": primary_pattern,
            "subwave": primary_subwave,
            "subwave_detail": primary_subwave_detail
        },
        "intermediate": {
            "wave": intermediate_wave,
            "pattern": intermediate_pattern,
            "subwave": intermediate_subwave
        },
        "minor": {
            "wave": minor_wave,
            "pattern": minor_pattern
        },
        "minute": {
            "wave": minute_wave,
            "pattern": minute_pattern
        },
        
        # Analysis Details
        "wave_position": wave_position,
        "fibonacci_level": fibonacci_level,
        "trend_direction": trend_direction,
        "confidence_level": confidence_level,
        
        # Trading Details
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "risk_reward_ratio": risk_reward_ratio,
        
        # Notes & References
        "notes": notes,
        "chart_image_url": chart_image_url,
        "tags": tags.split(",") if tags else [],
        
        # Accuracy Tracking
        "expected_completion_date": expected_completion,
        "expected_price_target": expected_price_target,
        "is_verified": is_verified,
        "verification_date": None,
        "actual_outcome": None
    }
    
    result = await wave_analysis_collection.insert_one(wave_data)
    
    if result.inserted_id:
        # Also save to history for tracking
        history_entry = {
            "analysis_id": str(result.inserted_id),
            "symbol": symbol.upper(),
            "analysis_date": analysis_date_obj,
            "primary_wave": primary_wave,
            "confidence_level": confidence_level,
            "expected_completion_date": expected_completion,
            "expected_price_target": expected_price_target,
            "is_verified": "pending",
            "created_at": datetime.now()
        }
        await wave_history_collection.insert_one(history_entry)
        
        return JSONResponse({
            "success": True,
            "message": "Advanced wave analysis saved successfully",
            "analysis_id": str(result.inserted_id)
        })
    
    raise HTTPException(status_code=400, detail="Failed to save analysis")

@app.get("/api/advanced-wave-analysis")
async def get_advanced_wave_analyses(
    symbol: Optional[str] = None,
    date: Optional[str] = None,
    primary_wave: Optional[str] = None,
    wave_position: Optional[str] = None,
    confidence_level: Optional[str] = None,
    is_verified: Optional[str] = None,
    limit: int = 100
):
    """Get wave analyses with advanced filters"""
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
    
    if primary_wave:
        query["primary.wave"] = primary_wave
    
    if wave_position:
        query["wave_position"] = wave_position
    
    if confidence_level:
        query["confidence_level"] = confidence_level
    
    if is_verified:
        query["is_verified"] = is_verified
    
    analyses = await wave_analysis_collection.find(query).sort("analysis_date", -1).to_list(limit)
    serialized = [serialize_doc(a) for a in analyses]
    
    return JSONResponse({"analyses": serialized, "count": len(serialized)})

@app.put("/api/advanced-wave-analysis/{analysis_id}")
async def update_advanced_wave_analysis(analysis_id: str):
    """Update specific wave analysis"""
    # Similar to create but with update
    pass

@app.delete("/api/advanced-wave-analysis/{analysis_id}")
async def delete_wave_analysis(analysis_id: str):
    """Delete wave analysis"""
    try:
        result = await wave_analysis_collection.delete_one({"_id": ObjectId(analysis_id)})
        if result.deleted_count:
            # Also remove from history
            await wave_history_collection.delete_one({"analysis_id": analysis_id})
            return JSONResponse({"success": True, "message": "Analysis deleted"})
        raise HTTPException(status_code=404, detail="Analysis not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

@app.post("/api/verify-analysis/{analysis_id}")
async def verify_analysis(
    analysis_id: str,
    actual_outcome: str = Form(...),
    was_correct: bool = Form(...)
):
    """Verify if wave analysis was correct"""
    try:
        update_data = {
            "is_verified": "verified",
            "verification_date": datetime.now(),
            "actual_outcome": actual_outcome,
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
        raise HTTPException(status_code=404, detail="Analysis not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

@app.get("/api/analysis-statistics")
async def get_analysis_statistics(symbol: Optional[str] = None):
    """Get statistics about wave analysis accuracy"""
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
            "_id": "$primary.wave",
            "count": {"$sum": 1},
            "correct": {"$sum": {"$cond": ["$was_correct", 1, 0]}}
        }}
    ]
    
    wave_stats = await wave_analysis_collection.aggregate(pipeline).to_list(10)
    
    return JSONResponse({
        "total_analyses": total,
        "verified_analyses": verified,
        "correct_analyses": correct,
        "accuracy_rate": (correct / verified * 100) if verified > 0 else 0,
        "wave_distribution": [serialize_doc(w) for w in wave_stats]
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)