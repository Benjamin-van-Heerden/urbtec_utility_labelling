from io import BytesIO

import httpx
import streamlit as st
from PIL import Image

from components.streamlit_drawable_canvas import st_canvas
from env_settings import ENV_SETTINGS
from utils.database import (
    fetch_random_reading,
    get_annotated_reading_ids,
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
from utils.obb import calculate_obb_from_fabric_object
from utils.session_state import get_session_state

st.set_page_config(
    page_title="Meter Labelling",
    page_icon="🏷️",
    layout="wide",
)

state = get_session_state()

# Initialize local database
init_local_db()

# Constants
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
DEFAULT_RECT_SIZE = 150

st.title("🏷️ Label Meter Image")

# Instructions expander
with st.expander("📖 Instructions & Examples", expanded=False):
    st.markdown("""
    ### How to annotate meter images

    1. Click **"Load New Image"** to fetch a meter image from the database
    2. For each meter visible in the image, click the appropriate button to add a bounding box:
       - 🔵 **Add Cold Water Meter** (blue)
       - 🟠 **Add Hot Water Meter** (orange)
       - 🟢 **Add Electricity Meter** (green)
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
    - Rotate the box to align with the meter's orientation

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

# Display stats
distribution = get_class_distribution()
col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)

with col_stats1:
    st.metric("Total Images", distribution.total_images)
with col_stats2:
    st.metric("Cold Water", distribution.cold_water_count)
with col_stats3:
    st.metric("Hot Water", distribution.hot_water_count)
with col_stats4:
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
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False


def load_new_image():
    """Load a new image from the source database."""
    st.session_state.image_load_error = None
    st.session_state.current_image = None
    st.session_state.current_reading = None
    st.session_state.detections = []
    st.session_state.canvas_key += 1
    st.session_state.confirmed = False

    # Check class distribution to decide if we need more electricity
    dist = get_class_distribution()
    total = dist.cold_water_count + dist.hot_water_count + dist.electricity_count
    prefer_electricity = total > 0 and (dist.electricity_count / total) < 0.3

    # Get already annotated IDs
    excluded_ids = get_annotated_reading_ids(ENV_SETTINGS.source_client_name)

    # Try to fetch a reading (with retries for failed image downloads)
    max_attempts = 5
    for attempt in range(max_attempts):
        reading = fetch_random_reading(
            prefer_electricity=prefer_electricity,
            excluded_ids=excluded_ids,
        )

        if reading is None:
            st.session_state.image_load_error = "No more images available to annotate."
            return

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
                return

        except Exception:
            # Add this ID to excluded to avoid retrying
            excluded_ids.add(reading.reading_id)
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
    st.info(
        f"📋 **According to our records:**\n\n"
        f"- Meter type: **{reading.utility_type_display}**\n"
        f"- Previous reading: **{reading.reading_old_whole if reading.reading_old_whole is not None else 'N/A'}**\n"
        f"- Reading in this image: **{reading.reading_new_whole if reading.reading_new_whole is not None else 'N/A'}**"
    )

    # Build initial drawing from current detections
    initial_drawing = {
        "version": "5.3.0",
        "objects": [d["rect"] for d in st.session_state.detections],
    }

    # Show canvas first so we can get current positions
    st.markdown("### Annotation Canvas")
    if st.session_state.detections:
        st.caption(
            "Move, resize, and rotate each box to fit the meter face. "
            "Use the rotation handle (circle above) to rotate. "
            "Double-click a box to delete it."
        )
    else:
        st.caption(
            "Add meter detections using the buttons above, or submit with no detections if no meter is visible."
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
    st.markdown("### Add Meter Detections")
    col_btn1, col_btn2, col_btn3 = st.columns(3)

    with col_btn1:
        if st.button("+ Cold Water Meter", use_container_width=True):
            add_detection(0, canvas_objects)
            st.rerun()

    with col_btn2:
        if st.button("+ Hot Water Meter", use_container_width=True):
            add_detection(1, canvas_objects)
            st.rerun()

    with col_btn3:
        if st.button("+ Electricity Meter", use_container_width=True):
            add_detection(2, canvas_objects)
            st.rerun()

    st.divider()

    # Detection details and reading inputs
    if st.session_state.detections:
        st.markdown("### Detection Details")

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

    # Show YOLO format preview
    if st.session_state.detections:
        with st.expander("📐 YOLO OBB Format Preview", expanded=False):
            canvas_objs = []
            if canvas_result.json_data and canvas_result.json_data.get("objects"):
                canvas_objs = canvas_result.json_data["objects"]

            for i, detection in enumerate(st.session_state.detections):
                if i < len(canvas_objs) and canvas_objs[i].get("type") == "rect":
                    rect = canvas_objs[i]
                else:
                    rect = detection["rect"]
                obb = calculate_obb_from_fabric_object(rect, img_width, img_height)
                st.code(obb.to_yolo_format(detection["class_label"]))

    st.divider()

    # Confirmation and submit
    if not st.session_state.detections:
        confirm_text = "✅ I confirm that no utility meter face is present in the image"
    else:
        confirm_text = "✅ I have verified all annotations are correct"

    confirmed = st.checkbox(
        confirm_text, value=st.session_state.confirmed, key="confirm_checkbox"
    )
    st.session_state.confirmed = confirmed

    col_submit, col_skip = st.columns(2)

    with col_submit:
        if st.button(
            "💾 Submit Annotation",
            type="primary",
            disabled=not confirmed,
            use_container_width=True,
        ):
            # Build detections list - get current rects from canvas
            detection_objects = []
            canvas_objects = []
            if canvas_result.json_data and canvas_result.json_data.get("objects"):
                canvas_objects = canvas_result.json_data["objects"]

            for i, detection in enumerate(st.session_state.detections):
                # Use canvas rect if available, otherwise use stored rect
                if i < len(canvas_objects) and canvas_objects[i].get("type") == "rect":
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
                source_client=ENV_SETTINGS.source_client_name,
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
            st.session_state.current_reading = None
            st.session_state.current_image = None
            st.session_state.detections = []
            st.rerun()

else:
    st.info("👆 Click **Load New Image** to start annotating")
