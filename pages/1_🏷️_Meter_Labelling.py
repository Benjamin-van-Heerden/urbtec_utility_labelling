from io import BytesIO
from pathlib import Path

import httpx
import streamlit as st
from PIL import Image

from components.streamlit_drawable_canvas import st_canvas
from utils.database import (
    fetch_random_reading,
    get_class_distribution,
    init_local_db,
    save_annotation,
)
from utils.models.annotation import (
    CLASS_DISPLAY_NAMES,
    Annotation,
    Detection,
    SourceReading,
    get_detection_color,
)
from utils.obb import calculate_obb_from_fabric_object, validate_bounding_box
from utils.session_state import get_session_state

st.set_page_config(
    page_title="Meter Labelling",
    page_icon="🏷️",
)

state = get_session_state()

# Initialize local database
init_local_db()

# Constants
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
DEFAULT_RECT_SIZE = 150

st.title("🏷️ Label Meter Image")

# Example images directory
EXAMPLES_DIR = Path(__file__).parent.parent / "assets" / "examples"

# Instructions expander
with st.expander("📖 Instructions & Examples", expanded=False):
    st.markdown("""
    ### How to annotate meter images

    1. Click **"Load New Image"** to fetch a meter image from the database
    2. For each meter visible in the image, click the appropriate button to add a bounding box:
       - **+ Water** (for both cold and hot water meters)
       - **+ Electricity**
    3. Adjust each bounding box:
       - **Move**: Drag the box to position it over the meter face
       - **Resize**: Use the corner handles to resize
       - **Rotate**: Use the rotation handle (circle above the box) to match the meter's orientation
    4. Enter the meter reading for each detection (whole numbers only - ignore decimals)
    5. Check the confirmation box when satisfied
    6. Click **Submit Annotation**

    ### What to annotate

    **Draw the bounding box around the ENTIRE METER FACE** - this includes:
    - The full display area showing all digits (both whole and decimal)
    - The meter face housing/frame
    - Rotate the box to align with the meter's orientation using the rotation handle
    - It is important that the top of the box is aligned with the top of the meter face

    **For the reading value:** Enter only the **whole number** portion (ignore any decimal digits).

    Example: If the meter shows `12345.678`, draw the box around the entire meter face, but enter `12345` as the reading.

    ### Multiple meters
    - If multiple meters are visible, annotate **ALL** of them
    - Each meter gets its own bounding box and class

    ### When to submit with no detections
    - The image doesn't show a meter at all
    - The image shows something completely unrelated
    - The meter face is not visible (e.g., photo of the back of a meter)

    **Note:** Blurry or hard-to-read meters should still be annotated if the meter face is visible.
    """)

    st.markdown("### Examples")

    # Water meter examples
    st.markdown("#### Water Meters")
    water_examples = [
        EXAMPLES_DIR / "cold_water_1.png",
        EXAMPLES_DIR / "cold_water_2.png",
        EXAMPLES_DIR / "cold_water_3.png",
        EXAMPLES_DIR / "cold_water_4.png",
        EXAMPLES_DIR / "cold_water_5.png",
        EXAMPLES_DIR / "cold_water_6.png",
        EXAMPLES_DIR / "hot_water_1.png",
    ]

    cols = st.columns(2)
    for i, example in enumerate(water_examples):
        with cols[i % 2]:
            if example.exists():
                st.image(str(example), use_container_width=True)

    # Multi-meter example
    st.markdown("#### Multiple Meters")
    multi_example = EXAMPLES_DIR / "multi_1.png"
    if multi_example.exists():
        st.image(str(multi_example), width=400)

    # Electricity meter examples
    st.markdown("#### Electricity Meters")
    electricity_examples = [
        EXAMPLES_DIR / "electricity_1.png",
        EXAMPLES_DIR / "electricity_2.png",
        EXAMPLES_DIR / "electricity_3.png",
        EXAMPLES_DIR / "electricity_4.png",
        EXAMPLES_DIR / "electricity_5.png",
        EXAMPLES_DIR / "electricity_6.png",
        EXAMPLES_DIR / "electricity_7.png",
        EXAMPLES_DIR / "electricity_8.png",
        EXAMPLES_DIR / "electricity_9.png",
    ]

    cols = st.columns(2)
    for i, example in enumerate(electricity_examples):
        with cols[i % 2]:
            if example.exists():
                st.image(str(example), use_container_width=True)

# Display stats
distribution = get_class_distribution()
col_stats1, col_stats2, col_stats3 = st.columns(3)

with col_stats1:
    st.metric("Total Images", distribution.total_images)
with col_stats2:
    st.metric("Water", distribution.water_count)
with col_stats3:
    st.metric("Electricity", distribution.electricity_count)

st.divider()

# Session state for current image and detections
if "current_reading" not in st.session_state:
    st.session_state.current_reading = None
if "current_image" not in st.session_state:
    st.session_state.current_image = None
if "image_load_error" not in st.session_state:
    st.session_state.image_load_error = None
if "detections" not in st.session_state:
    st.session_state.detections = []  # List of {"class_label": int, "rect": dict}
if "canvas_key" not in st.session_state:
    st.session_state.canvas_key = 0
if "current_client" not in st.session_state:
    st.session_state.current_client = None  # Which client the current image is from


def load_new_image():
    """Load a new image from one of the source databases."""
    st.session_state.image_load_error = None
    st.session_state.current_image = None
    st.session_state.current_reading = None
    st.session_state.current_client = None
    st.session_state.detections = []
    st.session_state.canvas_key += 1

    # Try to fetch a reading (with retries for failed image downloads)
    max_attempts = 5
    failed_readings: list[tuple[int, str]] = []  # (reading_id, client_name)

    for _ in range(max_attempts):
        result = fetch_random_reading()

        if result is None:
            st.session_state.image_load_error = "No more images available to annotate."
            return

        reading, client_name = result

        # Skip if we already failed to download this one
        if (reading.reading_id, client_name) in failed_readings:
            continue

        # Try to download the image
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(reading.image_url)
                response.raise_for_status()

                image_data = response.content
                image = Image.open(BytesIO(image_data))

                # Resize image to fit canvas while maintaining aspect ratio
                image.thumbnail((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)

                st.session_state.current_reading = reading
                st.session_state.current_image = image
                st.session_state.current_client = client_name
                return

        except Exception:
            failed_readings.append((reading.reading_id, client_name))
            continue

    st.session_state.image_load_error = (
        f"Failed to load image after {max_attempts} attempts."
    )


def add_detection(class_label: int, canvas_objects: list | None = None):
    """Add a new detection with the given class."""
    if st.session_state.current_image is None:
        return

    # First, update existing detection rects from canvas if provided
    if canvas_objects:
        for i, obj in enumerate(canvas_objects):
            if i < len(st.session_state.detections) and obj.get("type") == "rect":
                st.session_state.detections[i]["rect"] = obj

    img_width, img_height = st.session_state.current_image.size

    # Use detection index for color (so each box has a unique color)
    detection_index = len(st.session_state.detections)
    colors = get_detection_color(detection_index)

    # Offset each new rectangle slightly so they don't stack exactly
    offset = detection_index * 20

    new_rect = {
        "type": "rect",
        "left": (img_width - DEFAULT_RECT_SIZE) / 2 + offset,
        "top": (img_height - DEFAULT_RECT_SIZE) / 2 + offset,
        "width": DEFAULT_RECT_SIZE,
        "height": DEFAULT_RECT_SIZE,
        "fill": colors["fill"],
        "stroke": colors["stroke"],
        "strokeWidth": 2,
        "angle": 0,
        "scaleX": 1,
        "scaleY": 1,
    }

    st.session_state.detections.append(
        {
            "class_label": class_label,
            "rect": new_rect,
            "annotator_reading": None,
        }
    )
    st.session_state.canvas_key += 1


def remove_detection(index: int, canvas_objects: list | None = None):
    """Remove a detection by index."""
    # First, update existing detection rects from canvas if provided
    if canvas_objects:
        for i, obj in enumerate(canvas_objects):
            if i < len(st.session_state.detections) and obj.get("type") == "rect":
                st.session_state.detections[i]["rect"] = obj

    if 0 <= index < len(st.session_state.detections):
        st.session_state.detections.pop(index)
        st.session_state.canvas_key += 1


# Load image button
if st.button("🔄 Load New Image", type="primary", use_container_width=True):
    load_new_image()

if st.session_state.image_load_error:
    st.error(st.session_state.image_load_error)

# Main annotation interface
if st.session_state.current_reading and st.session_state.current_image:
    reading: SourceReading = st.session_state.current_reading
    image: Image.Image = st.session_state.current_image

    # Get actual image dimensions on canvas
    img_width, img_height = image.size

    # Display reading info from source database
    client_name = st.session_state.current_client or "Unknown"
    st.info(
        f"📋 **According to our records:** (Source: {client_name})\n\n"
        f"- Meter type: **{reading.utility_type_display}**\n"
        f"- Previous reading: **{reading.reading_old_whole if reading.reading_old_whole is not None else 'N/A'}**\n"
        f"- Reading in this image: **{reading.reading_new_whole if reading.reading_new_whole is not None else 'N/A'}**"
    )

    # Build initial drawing from current detections
    initial_drawing = {
        "version": "5.3.0",
        "objects": [d["rect"] for d in st.session_state.detections],
    }

    # Canvas
    st.markdown("### Annotation Canvas")
    if st.session_state.detections:
        st.caption(
            "Move, resize, and rotate each box to fit the meter face. "
            "Use the rotation handle (circle above) to rotate."
        )
    else:
        st.caption(
            "Add a meter detection using the buttons below, or submit with no detections if no meter is visible."
        )

    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=2,
        stroke_color="#ffffff",
        background_image=image,
        initial_drawing=initial_drawing if st.session_state.detections else None,  # type: ignore
        update_streamlit=True,
        height=img_height,
        width=img_width,
        drawing_mode="transform",
        display_toolbar=True,
        key=f"annotation_canvas_{st.session_state.canvas_key}",
    )

    # Get current canvas objects for use in buttons
    canvas_objects = []
    if canvas_result.json_data and canvas_result.json_data.get("objects"):
        canvas_objects = canvas_result.json_data["objects"]

    # Add detection buttons (after canvas so we can access current positions)
    st.markdown("### Add Meter Detection")
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("+ Water", use_container_width=True):
            add_detection(0, canvas_objects)
            st.rerun()

    with col_btn2:
        if st.button("+ Electricity", use_container_width=True):
            add_detection(1, canvas_objects)
            st.rerun()

    st.divider()

    # Detection details and reading inputs
    if st.session_state.detections:
        st.markdown("### Detection Details")

        # Column headings
        col_h1, col_h2, col_h3 = st.columns([2, 2, 1])
        with col_h1:
            st.markdown("**Detection**")
        with col_h2:
            st.markdown("**Reading (Whole Number Only)**")

        for i, detection in enumerate(st.session_state.detections):
            class_label = detection["class_label"]
            class_name = CLASS_DISPLAY_NAMES[class_label]
            colors = get_detection_color(i)

            col_info, col_reading, col_remove = st.columns([2, 2, 1])

            with col_info:
                st.markdown(
                    f"<span style='color:{colors['stroke']}; font-size: 24px;'>■</span> "
                    f"**{i + 1}. {class_name}**",
                    unsafe_allow_html=True,
                )

            with col_reading:
                reading_value = st.number_input(
                    "Reading",
                    min_value=0,
                    step=1,
                    value=reading.reading_new_whole
                    if reading.reading_new_whole is not None
                    else 0,
                    key=f"reading_{i}",
                    label_visibility="collapsed",
                )
                st.session_state.detections[i]["annotator_reading"] = int(reading_value)

            with col_remove:
                if st.button("🗑️", key=f"remove_{i}", help="Remove this detection"):
                    remove_detection(i, canvas_objects)
                    st.rerun()

    st.divider()

    col_submit, col_skip = st.columns(2)

    submit_label = (
        "💾 Submit Annotation"
        if st.session_state.detections
        else "💾 Submit Annotation (No Meter)"
    )

    with col_submit:
        if st.button(
            submit_label,
            type="primary",
            use_container_width=True,
        ):
            # Build detections list - get current rects from canvas
            detection_objects = []
            canvas_objects = []
            if canvas_result.json_data and canvas_result.json_data.get("objects"):
                canvas_objects = canvas_result.json_data["objects"]

            # Validate all bounding boxes first
            validation_errors = []
            for i, detection in enumerate(st.session_state.detections):
                if i < len(canvas_objects) and canvas_objects[i].get("type") == "rect":
                    rect = canvas_objects[i]
                else:
                    rect = detection["rect"]

                is_valid, error_msg = validate_bounding_box(rect, img_width, img_height)
                if not is_valid:
                    class_name = CLASS_DISPLAY_NAMES[detection["class_label"]]
                    validation_errors.append(
                        f"Detection {i + 1} ({class_name}): {error_msg}"
                    )

            if validation_errors:
                for error in validation_errors:
                    st.error(error)
            else:
                for i, detection in enumerate(st.session_state.detections):
                    # Use canvas rect if available, otherwise use stored rect
                    if (
                        i < len(canvas_objects)
                        and canvas_objects[i].get("type") == "rect"
                    ):
                        rect = canvas_objects[i]
                    else:
                        rect = detection["rect"]
                    obb = calculate_obb_from_fabric_object(rect, img_width, img_height)
                    detection_objects.append(
                        Detection(
                            class_label=detection["class_label"],
                            obb=obb,
                            annotator_reading=detection.get("annotator_reading"),
                        )
                    )

                # Create and save annotation
                annotation = Annotation(
                    source_client=st.session_state.current_client,
                    source_reading_id=reading.reading_id,
                    image_url=reading.image_url,
                    detections=detection_objects,
                    annotated_by=state.username,
                )

                try:
                    save_annotation(annotation)
                    st.toast("Annotation saved!")
                    # Auto-load next image
                    load_new_image()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save annotation: {e}")

    with col_skip:
        if st.button("⏭️ Skip Image", use_container_width=True):
            load_new_image()
            st.rerun()

else:
    st.info("👆 Click **Load New Image** to start annotating")
