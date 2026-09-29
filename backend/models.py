from pydantic import BaseModel, Field
from typing import Literal

Objective = Literal["fastest", "shortest", "balanced", "low_congestion"]
Vehicle = Literal["car", "van", "truck"]

class OptimizeRequest(BaseModel):
    source: int = 0
    destination: int = 17
    waypoints: list[int] = Field(default_factory=list)
    objective: Objective = "balanced"
    vehicle: Vehicle = "car"
    particles: int = Field(default=28, ge=8, le=100)
    iterations: int = Field(default=60, ge=10, le=300)
    seed: int = Field(default=42, ge=0, le=999999)

class RouteCheckRequest(BaseModel):
    path: list[int]
    vehicle: Vehicle = "car"

class ScenarioRequest(BaseModel):
    mode: Literal["normal", "rush_hour", "incident"] = "normal"
    severity: float = Field(default=0.65, ge=0.0, le=1.0)
    seed: int = Field(default=42, ge=0, le=999999)
