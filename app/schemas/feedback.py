from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
import uuid
from datetime import datetime

class FeedbackResponse(BaseModel):
    id: uuid.UUID
    description: str
    image_path: Optional[str] = None
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
