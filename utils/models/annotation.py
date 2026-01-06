from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Class labels for meter types
MeterClass = Literal[0, 1, 2]  # 0=cold_water, 1=hot_water, 2=electricity

CLASS_LABELS = {
    0: "cold_water",
    1: "hot_water",
    2: "electricity",
}

CLASS_DISPLAY_NAMES = {
    0: "Cold Water",
    1: "Hot Water",
    2: "Electricity",
}

# Colors for each class (CSS rgba)
CLASS_COLORS = {
    0: {"fill": "rgba(0, 150, 255, 0.3)", "stroke": "#0096ff"},  # Blue for cold water
    1: {"fill": "rgba(255, 100, 0, 0.3)", "stroke": "#ff6400"},  # Orange for hot water
    2: {"fill": "rgba(0, 255, 0, 0.3)", "stroke": "#00ff00"},  # Green for electricity
}

# Distinct colors for detection indices (to tell boxes apart visually)
DETECTION_COLORS = [
    {"fill": "rgba(255, 0, 0, 0.3)", "stroke": "#ff0000"},  # Red
    {"fill": "rgba(0, 255, 0, 0.3)", "stroke": "#00ff00"},  # Green
    {"fill": "rgba(0, 100, 255, 0.3)", "stroke": "#0064ff"},  # Blue
    {"fill": "rgba(255, 255, 0, 0.3)", "stroke": "#ffff00"},  # Yellow
    {"fill": "rgba(255, 0, 255, 0.3)", "stroke": "#ff00ff"},  # Magenta
    {"fill": "rgba(0, 255, 255, 0.3)", "stroke": "#00ffff"},  # Cyan
    {"fill": "rgba(255, 128, 0, 0.3)", "stroke": "#ff8000"},  # Orange
    {"fill": "rgba(128, 0, 255, 0.3)", "stroke": "#8000ff"},  # Purple
]


def get_detection_color(index: int) -> dict:
    """Get color for a detection by index, cycling through palette."""
    return DETECTION_COLORS[index % len(DETECTION_COLORS)]


class OBBCoordinates(BaseModel):
    """Oriented Bounding Box coordinates - 4 corners normalized 0-1."""

    x1: float
    y1: float
    x2: float
    y2: float
    x3: float
    y3: float
    x4: float
    y4: float

    def to_yolo_format(self, class_id: int) -> str:
        """Convert to YOLO OBB format: class_id x1 y1 x2 y2 x3 y3 x4 y4"""
        return f"{class_id} {self.x1} {self.y1} {self.x2} {self.y2} {self.x3} {self.y3} {self.x4} {self.y4}"

    def to_list(self) -> list[float]:
        """Convert to list format for JSON storage."""
        return [self.x1, self.y1, self.x2, self.y2, self.x3, self.y3, self.x4, self.y4]

    @classmethod
    def from_list(cls, coords: list[float]) -> "OBBCoordinates":
        """Create from list format."""
        return cls(
            x1=coords[0],
            y1=coords[1],
            x2=coords[2],
            y2=coords[3],
            x3=coords[4],
            y3=coords[5],
            x4=coords[6],
            y4=coords[7],
        )


class Detection(BaseModel):
    """A single meter detection within an image."""

    class_label: MeterClass
    obb: OBBCoordinates
    annotator_reading: int | None = None

    def to_dict(self) -> dict:
        """Convert to dict for JSON storage."""
        return {
            "class_label": self.class_label,
            "obb": self.obb.to_list(),
            "annotator_reading": self.annotator_reading,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Detection":
        """Create from dict (JSON storage format)."""
        return cls(
            class_label=data["class_label"],
            obb=OBBCoordinates.from_list(data["obb"]),
            annotator_reading=data.get("annotator_reading"),
        )


class Annotation(BaseModel):
    """A completed annotation record with multiple detections."""

    id: int | None = None
    source_client: str
    source_reading_id: int
    image_url: str
    detections: list[Detection] = []  # Empty list means no meters present
    annotated_by: str
    annotated_at: datetime | None = None

    @property
    def has_meters(self) -> bool:
        return len(self.detections) > 0

    @property
    def is_multi_meter(self) -> bool:
        return len(self.detections) > 1

    @property
    def meter_count(self) -> int:
        return len(self.detections)

    def detections_to_json(self) -> str:
        """Serialize detections to JSON string for database storage."""
        import json

        return json.dumps([d.to_dict() for d in self.detections])

    @classmethod
    def detections_from_json(cls, json_str: str) -> list[Detection]:
        """Deserialize detections from JSON string."""
        import json

        data = json.loads(json_str)
        return [Detection.from_dict(d) for d in data]


class SourceReading(BaseModel):
    """A meter reading record from the source database."""

    reading_id: int
    meter_no: str
    utility_type: str | None  # 'cold_water', 'hot_water', 'electricity'
    image_url: str
    reading_new: float | None = None  # The reading captured in this image
    reading_old: float | None = None  # The previous reading

    @property
    def utility_type_display(self) -> str:
        """Human-readable utility type."""
        if self.utility_type == "cold_water":
            return "Cold Water"
        elif self.utility_type == "hot_water":
            return "Hot Water"
        elif self.utility_type == "electricity":
            return "Electricity"
        return "Unknown"

    @property
    def reading_new_whole(self) -> int | None:
        """Whole number part of the new reading."""
        if self.reading_new is None:
            return None
        return int(self.reading_new)

    @property
    def reading_old_whole(self) -> int | None:
        """Whole number part of the old reading."""
        if self.reading_old is None:
            return None
        return int(self.reading_old)


class ClassDistribution(BaseModel):
    """Current distribution of annotated classes."""

    cold_water_count: int = 0
    hot_water_count: int = 0
    electricity_count: int = 0
    no_meter_count: int = 0

    @property
    def total_images(self) -> int:
        """Total number of annotated images."""
        return (
            self.cold_water_count
            + self.hot_water_count
            + self.electricity_count
            + self.no_meter_count
        )

    @property
    def total_detections(self) -> int:
        """This is now tracked differently - see database function."""
        return self.cold_water_count + self.hot_water_count + self.electricity_count
