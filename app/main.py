
import os
from datetime import datetime
from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import Base, engine, SessionLocal
from .models import Player, Instructor, InstructorPlayer, Metric, CoachNote, Drill, AssignedDrill
from .utils import random_code, age_group, ensure_dirs, send_sms, twilio_enabled

ensure_dirs()
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "devsecret"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
templates.env.globals['now'] = lambda: datetime.utcnow()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def current_player(request: Request, db: Session) -> Player | None:
    pid = request.session.get("player_id")
    return db.get(Player, pid) if pid else None

def current_instructor(request: Request, db: Session) -> Instructor | None:
    iid = request.session.get("instructor_id")
    return db.get(Instructor, iid) if iid else None

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/player/login")
def player_login(request: Request, login_code: str = Form(...), db: Session = Depends(get_db)):
    player = db.scalar(select(Player).where(Player.login_code == login_code.strip()))
    if not player:
        return templates.TemplateResponse("index.html", {"request": request, "error": "Invalid player code."}, status_code=400)
    request.session.clear()
    request.session["player_id"] = player.id
    return RedirectResponse(url="/player/dashboard", status_code=303)

@app.get("/player/dashboard", response_class=HTMLResponse)
def player_dashboard(request: Request, db: Session = Depends(get_db)):
    player = current_player(request, db)
    if not player:
        return RedirectResponse("/", status_code=303)
    metrics = db.scalars(select(Metric).where(Metric.player_id == player.id).order_by(Metric.date.asc())).all()
    ev_data = [{"date": m.date.strftime("%Y-%m-%d"), "ev": m.exit_velocity or 0} for m in metrics][-20:]
    shared_notes = db.scalars(select(CoachNote).where(CoachNote.player_id == player.id, CoachNote.shared_to_player == True).order_by(CoachNote.created_at.desc())).all()
    assigned_rows = db.execute(select(AssignedDrill, Drill).join(Drill, Drill.id==AssignedDrill.drill_id).where(AssignedDrill.player_id==player.id).order_by(AssignedDrill.assigned_at.desc())).all()
    return templates.TemplateResponse("player_dashboard.html", {"request": request, "player": player, "ev_data": ev_data, "notes": shared_notes, "assigned": assigned_rows})

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.get("/instructor/login", response_class=HTMLResponse)
def instructor_login_page(request: Request):
    return templates.TemplateResponse("instructor_login.html", {"request": request})

@app.post("/instructor/login")
def instructor_login(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    code = code.strip()
    master = os.environ.get("INSTRUCTOR_CODE", "")
    if code == master and master:
        return RedirectResponse("/instructor/create", status_code=303)
    inst = db.scalar(select(Instructor).where(Instructor.code == code))
    if not inst:
        return templates.TemplateResponse("instructor_login.html", {"request": request, "error": "Invalid instructor code."}, status_code=400)
    request.session.clear()
    request.session["instructor_id"] = inst.id
    return RedirectResponse("/instructor/dashboard", status_code=303)

@app.get("/instructor/create", response_class=HTMLResponse)
def instructor_create_page(request: Request):
    return templates.TemplateResponse("instructor_create.html", {"request": request})

@app.post("/instructor/create")
def instructor_create(request: Request, name: str = Form(...), master_code: str = Form(...), db: Session = Depends(get_db)):
    if master_code.strip() != os.environ.get("INSTRUCTOR_CODE", ""):
        return templates.TemplateResponse("instructor_create.html", {"request": request, "error": "Invalid master code."}, status_code=400)
    code = f"H4P{random_code(6)}"
    inst = Instructor(name=name.strip(), code=code)
    db.add(inst); db.commit(); db.refresh(inst)
    request.session.clear()
    request.session["instructor_id"] = inst.id
    return templates.TemplateResponse("instructor_created.html", {"request": request, "code": code})

@app.get("/instructor/dashboard", response_class=HTMLResponse)
def instructor_dashboard(request: Request, db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    players = db.scalars(select(Player).order_by(Player.name.asc())).all()
    groups = {"7-9": [], "10-12": [], "13-15": [], "16-18": [], "18+": []}
    for p in players:
        groups[age_group(p.age)].append(p)
    fav_ids = set([ip.player_id for ip in db.scalars(select(InstructorPlayer).where(InstructorPlayer.instructor_id==inst.id, InstructorPlayer.is_favorite==True)).all()])
    return templates.TemplateResponse("instructor_dashboard.html", {"request": request, "inst": inst, "groups": groups, "fav_ids": fav_ids})

@app.get("/instructor/players/new", response_class=HTMLResponse)
def new_player_page(request: Request, db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    return templates.TemplateResponse("create_player.html", {"request": request})

@app.post("/instructor/players/new")
def new_player(request: Request, name: str = Form(...), age: int = Form(...), phone: str = Form(""), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    code = random_code(6)
    player = Player(name=name.strip(), age=age, phone=phone.strip() or None, login_code=code)
    db.add(player); db.commit()
    request.session["flash_success"] = f"Player created. Login code: {code}"
    return RedirectResponse("/instructor/dashboard", status_code=303)

@app.get("/instructor/import", response_class=HTMLResponse)
def import_csv_page(request: Request, db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    return templates.TemplateResponse("import_csv.html", {"request": request})

@app.post("/instructor/import")
async def import_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    content = (await file.read()).decode("utf-8", errors="ignore").splitlines()
    import csv
    reader = csv.DictReader(content)
    created = []
    for row in reader:
        name = (row.get("name") or row.get("Name") or "").strip()
        age = int((row.get("age") or row.get("Age") or "0").strip() or 0)
        phone = (row.get("phone") or row.get("Phone") or "").strip() or None
        if not name or age<=0: 
            continue
        code = random_code(6)
        p = Player(name=name, age=age, phone=phone, login_code=code)
        db.add(p)
        created.append((name, code))
    db.commit()
    msg = "Imported players:\n" + "\n".join([f"{n}: {c}" for (n,c) in created]) if created else "No valid rows found."
    request.session["flash_success"] = msg
    return RedirectResponse("/instructor/dashboard", status_code=303)

@app.get("/instructor/player/{player_id}", response_class=HTMLResponse)
def instructor_player_detail(request: Request, player_id: int, db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    player = db.get(Player, player_id)
    if not player:
        return RedirectResponse("/instructor/dashboard", status_code=303)
    metrics = db.scalars(select(Metric).where(Metric.player_id==player.id).order_by(Metric.date.asc())).all()
    ev_data = [{"date": m.date.strftime("%Y-%m-%d"), "ev": m.exit_velocity or 0} for m in metrics][-20:]
    drills = db.scalars(select(Drill).order_by(Drill.created_at.desc())).all()
    assigned_rows = db.execute(select(AssignedDrill, Drill).join(Drill, Drill.id==AssignedDrill.drill_id).where(AssignedDrill.player_id==player.id).order_by(AssignedDrill.assigned_at.desc())).all()
    return templates.TemplateResponse("instructor_player_detail.html", {"request": request, "player": player, "ev_data": ev_data, "drills": drills, "assigned": assigned_rows})

@app.post("/instructor/player/{player_id}/metric")
def add_metric(request: Request, player_id: int, ev: float = Form(...), la: float = Form(0), sr: float = Form(0), date: str = Form(""), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    player = db.get(Player, player_id)
    if not player: return RedirectResponse("/instructor/dashboard", status_code=303)
    d = datetime.strptime(date, "%Y-%m-%d") if date else datetime.utcnow()
    m = Metric(player_id=player.id, date=d, exit_velocity=ev, launch_angle=la or None, spin_rate=sr or None)
    db.add(m); db.commit()
    if player.phone and twilio_enabled():
        send_sms(player.phone, f"Your metrics were updated: Exit Velo {ev} mph.")
    return RedirectResponse(f"/instructor/player/{player_id}", status_code=303)

@app.post("/instructor/player/{player_id}/avatar")
async def upload_avatar(request: Request, player_id: int, avatar: UploadFile = File(...), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    player = db.get(Player, player_id)
    if not player: return RedirectResponse("/instructor/dashboard", status_code=303)
    os.makedirs("/data/avatars", exist_ok=True)
    fname = f"p{player_id}_{int(datetime.utcnow().timestamp())}_{avatar.filename}"
    path = os.path.join("/data/avatars", fname)
    with open(path, "wb") as f:
        f.write(await avatar.read())
    player.avatar_path = f"/media/avatars/{fname}"
    db.commit()
    return RedirectResponse(f"/instructor/player/{player_id}", status_code=303)

@app.get("/media/avatars/{filename}")
def get_avatar(filename: str):
    path = os.path.join("/data/avatars", filename)
    return FileResponse(path)

@app.get("/media/drills/{filename}")
def get_drill(filename: str):
    path = os.path.join("/data/drills", filename)
    return FileResponse(path)

@app.post("/instructor/player/{player_id}/note")
def add_note(request: Request, player_id: int, content: str = Form(...), share_to_player: bool = Form(False), text_player: bool = Form(False), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    player = db.get(Player, player_id)
    if not player: return RedirectResponse("/instructor/dashboard", status_code=303)
    note = CoachNote(player_id=player.id, instructor_id=inst.id, content=content.strip(), shared_to_player=bool(share_to_player))
    db.add(note); db.commit()
    if text_player and player.phone:
        send_sms(player.phone, f"Coach note: {content.strip()}")
    return RedirectResponse(f"/instructor/player/{player_id}", status_code=303)

@app.get("/instructor/drills", response_class=HTMLResponse)
def drills_page(request: Request, db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    drills = db.scalars(select(Drill).order_by(Drill.created_at.desc())).all()
    return templates.TemplateResponse("drills_library.html", {"request": request, "drills": drills})

@app.post("/instructor/drills/upload")
async def drills_upload(request: Request, title: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    os.makedirs("/data/drills", exist_ok=True)
    fname = f"d{inst.id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
    path = os.path.join("/data/drills", fname)
    with open(path, "wb") as f:
        f.write(await file.read())
    d = Drill(title=title.strip(), filename=fname, uploader_instructor_id=inst.id)
    db.add(d); db.commit()
    return RedirectResponse("/instructor/drills", status_code=303)

@app.post("/instructor/player/{player_id}/assign-drill")
def assign_drill(request: Request, player_id: int, drill_id: int = Form(...), text_player: bool = Form(False), db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return RedirectResponse("/instructor/login", status_code=303)
    player = db.get(Player, player_id); d = db.get(Drill, drill_id)
    if player and d:
        db.add(AssignedDrill(player_id=player.id, drill_id=d.id)); db.commit()
        if text_player and player.phone:
            base = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else ""
            url = f"{base}/media/drills/{d.filename}"
            send_sms(player.phone, f"New drill assigned: {d.title} - {url}")
    return RedirectResponse(f"/instructor/player/{player_id}", status_code=303)

@app.post("/instructor/favorite/{player_id}")
def toggle_favorite(request: Request, player_id: int, db: Session = Depends(get_db)):
    inst = current_instructor(request, db)
    if not inst:
        return JSONResponse({"ok": False, "error": "Not logged in"}, status_code=401)
    ip = db.scalar(select(InstructorPlayer).where(InstructorPlayer.instructor_id==inst.id, InstructorPlayer.player_id==player_id))
    if not ip:
        ip = InstructorPlayer(instructor_id=inst.id, player_id=player_id, is_favorite=True)
        db.add(ip)
    else:
        ip.is_favorite = not ip.is_favorite
    db.commit()
    return JSONResponse({"ok": True, "favorited": ip.is_favorite})
