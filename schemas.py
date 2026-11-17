from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# ---------- Users ----------
class UserCreate(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8, max_length=72)

class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    created_at: datetime


# ---------- Projects ----------
class ProjectCreate(BaseModel):
    name: str
    description: str | None = None

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    created_at: datetime


# ---------- Tasks ----------
class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "todo"
    priority: int = 1
    user_id: int
    project_id: int

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: int | None = None

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    status: str
    priority: int
    user_id: int
    project_id: int
    created_at: datetime