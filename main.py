from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
import security
import models
import schemas
from database import get_db
from fastapi.security import OAuth2PasswordRequestForm
from security import verify_password, create_access_token

# Create all tables in PostgreSQL (only the ones that don't exist yet)
#לא צריך את זה כיון שמיגרציות אחראיות מעכשיו על מבנה הטבלאות
# models.Base.metadata.create_all(bind=engine)
app = FastAPI(title="Tasks API")


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == form_data.username))
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}
# ============================================================
#                          USERS
# ============================================================

@app.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.User).where(models.User.email == data.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    user = models.User(
        name=data.name,
        email=data.email,
        password_hash=security.hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users", response_model=list[schemas.UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(models.User)).all()


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, data: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = data.model_dump(exclude_unset=True)

    # If the email is being changed, make sure nobody else already uses it
    if "email" in changes:
        taken = db.scalar(
            select(models.User).where(
                models.User.email == changes["email"],
                models.User.id != user_id,
            )
        )
        if taken:
            raise HTTPException(status_code=400, detail="Email already exists")

    for field, value in changes.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # PostgreSQL won't let us delete a user that still has tasks
    has_tasks = db.scalar(select(models.Task.id).where(models.Task.user_id == user_id).limit(1))
    if has_tasks:
        raise HTTPException(status_code=409, detail="User still has tasks. Delete or reassign them first")

    db.delete(user)
    db.commit()


@app.get("/users/{user_id}/tasks", response_model=list[schemas.TaskResponse])
def get_user_tasks(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return db.scalars(select(models.Task).where(models.Task.user_id == user_id)).all()


# ============================================================
#                         PROJECTS
# ============================================================

@app.post("/projects", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(data: schemas.ProjectCreate, db: Session = Depends(get_db)):
    project = models.Project(**data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/projects", response_model=list[schemas.ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(models.Project)).all()


@app.get("/projects/{project_id}", response_model=schemas.ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.put("/projects/{project_id}", response_model=schemas.ProjectResponse)
def update_project(project_id: int, data: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    has_tasks = db.scalar(select(models.Task.id).where(models.Task.project_id == project_id).limit(1))
    if has_tasks:
        raise HTTPException(status_code=409, detail="Project still has tasks. Delete them first")

    db.delete(project)
    db.commit()


@app.get("/projects/{project_id}/tasks", response_model=list[schemas.TaskResponse])
def get_project_tasks(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.scalars(select(models.Task).where(models.Task.project_id == project_id)).all()


# ============================================================
#                           TASKS
# ============================================================

@app.post("/tasks", response_model=schemas.TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(data: schemas.TaskCreate, db: Session = Depends(get_db)):
    # The task must belong to an existing user and an existing project
    if not db.get(models.User, data.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if not db.get(models.Project, data.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    task = models.Task(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/tasks", response_model=list[schemas.TaskResponse])
def list_tasks(
    task_status: str | None = None,
    priority: int | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = select(models.Task)

    if task_status is not None:
        query = query.where(models.Task.status == task_status)
    if priority is not None:
        query = query.where(models.Task.priority == priority)
    if user_id is not None:
        query = query.where(models.Task.user_id == user_id)
    if project_id is not None:
        query = query.where(models.Task.project_id == project_id)

    return db.scalars(query).all()


@app.get("/tasks/{task_id}", response_model=schemas.TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=schemas.TaskResponse)
def update_task(task_id: int, data: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()