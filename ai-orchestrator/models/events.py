from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ApplicationRequest(BaseModel):
    name: str
    creditScore: int
    utilization: float
    addressMismatch: Optional[bool] = False
    delinquencies: Optional[int] = 0
    annualIncome: Optional[float] = None
    channel: Optional[str] = "WEB"


class ApplicationReceivedEvent(BaseModel):
    correlationId: str
    receivedAt: datetime
    channel: str
    application: ApplicationRequest
    eventVersion: str = "1.0"
