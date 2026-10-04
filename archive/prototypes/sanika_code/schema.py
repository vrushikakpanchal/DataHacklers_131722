from pydantic import BaseModel
from typing import List


class Slide(BaseModel):

    slide_number: int
    title: str
    layout: str
    key_points: List[str]
    speaker_notes: str


class Presentation(BaseModel):

    presentation_title: str
    slides: List[Slide]