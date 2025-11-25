"""
LangGraph orchestration workflow for timepoint generation.

This module defines the complete workflow from user input to final timepoint.
"""
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator
from datetime import datetime, timedelta
import asyncio
import logging

from app.agents.judge import judge_query
from app.agents.timeline import generate_timeline
from app.agents.scene_builder import build_scene
from app.agents.characters import generate_characters
from app.agents.moment import generate_moment
from app.agents.camera import generate_camera_directives
from app.agents.dialog import generate_dialog
from app.services.scene_graph import build_scene_graph, graph_to_image_prompt
from app.services.google_ai import generate_image, segment_image
from app.database import get_db_context
from app.models import ProcessingSession, Timepoint, ProcessingStatus
from app.utils.rate_limiter import update_rate_limit


class WorkflowState(TypedDict):
    """Shared state across all workflow nodes."""
    # Input
    session_id: str
    email: str
    user_query: str

    # Judge output
    is_valid: bool
    cleaned_query: str
    rejection_reason: str | None

    # Timeline output
    year: int
    season: str
    slug: str
    timepoint_id: str | None  # Created early for progressive loading
    timepoint_url: str | None  # URL to navigate to

    # Scene output
    setting: dict
    weather: dict
    location: dict

    # Characters
    characters: list[dict]

    # Moment (plot/interaction)
    moment: dict

    # Camera directives
    camera: dict

    # Graph
    scene_graph: dict

    # Images
    image_prompt: str
    image_url: str
    segmented_image_url: str
    color_map: dict

    # Dialog
    dialog: list[dict]

    # Metadata
    processing_steps: Annotated[Sequence[str], operator.add]
    errors: Annotated[Sequence[str], operator.add]


async def judge_node(state: WorkflowState) -> WorkflowState:
    """Validate and clean user input."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[JUDGE] Starting validation for query: {state['user_query'][:100]}")

    result = await judge_query(state["user_query"])

    logger.info(f"[JUDGE] Validation complete - Valid: {result.is_valid}, Cleaned: {result.cleaned_query[:100]}")

    return {
        **state,
        "is_valid": result.is_valid,
        "cleaned_query": result.cleaned_query,
        "rejection_reason": result.reason,
        "processing_steps": ["judge_completed"]
    }


async def should_continue(state: WorkflowState) -> str:
    """Conditional edge: continue if valid, end if invalid."""
    return "timeline" if state["is_valid"] else END


async def timeline_node(state: WorkflowState) -> WorkflowState:
    """Generate timeline metadata and slug."""
    import logging
    import uuid
    logger = logging.getLogger(__name__)
    logger.info(f"[TIMELINE] Generating timeline for: {state['cleaned_query'][:100]}")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_SCENE,
        {"stage": "timeline", "message": "Analyzing the time period..."}
    )

    timeline = await generate_timeline(state["cleaned_query"])

    logger.info(f"[TIMELINE] Complete - Year: {timeline.year}, Season: {timeline.season}, Location: {timeline.location}")

    # Create stub Timepoint record NOW so we can navigate to it immediately
    from app.models import Email
    timepoint_id = None
    timepoint_url = None

    try:
        with get_db_context() as db:
            # Get email record
            email_obj = db.query(Email).filter(Email.email == state["email"]).first()

            # Create unique slug
            base_slug = f"{timeline.year}-{timeline.season}-{timeline.slug}"
            existing = db.query(Timepoint).filter(Timepoint.slug == base_slug).first()
            if existing:
                unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
                logger.info(f"[TIMELINE] Slug exists, using unique slug: {unique_slug}")
            else:
                unique_slug = base_slug

            # Create stub timepoint with minimal data
            timepoint = Timepoint(
                email_id=email_obj.id,
                slug=unique_slug,
                year=timeline.year,
                season=timeline.season,
                input_query=state["user_query"],
                cleaned_query=state["cleaned_query"]
            )
            db.add(timepoint)
            db.commit()
            db.refresh(timepoint)
            timepoint_id = timepoint.id

            # Calculate URL for frontend
            url_slug = unique_slug.replace(f"{timeline.year}-{timeline.season}-", "", 1)
            timepoint_url = f"/{timeline.year}/{timeline.season}/{url_slug}"

            # Update session with timepoint_id and URL
            session = db.query(ProcessingSession).filter(
                ProcessingSession.session_id == state["session_id"]
            ).first()
            if session:
                session.timepoint_id = timepoint_id
                session.progress_data_json = {
                    "stage": "timeline",
                    "message": "Timeline created - building scene...",
                    "timepoint_url": timepoint_url
                }
                db.commit()

            logger.info(f"[TIMELINE] Stub timepoint created with ID: {timepoint_id}, URL: {timepoint_url}")

    except Exception as e:
        logger.error(f"[TIMELINE] Failed to create stub timepoint: {e}", exc_info=True)

    return {
        **state,
        "year": timeline.year,
        "season": timeline.season,
        "slug": timeline.slug,
        "location": {"name": timeline.location, "exact_date": timeline.exact_date},
        "timepoint_id": timepoint_id,
        "timepoint_url": timepoint_url,
        "processing_steps": ["timeline_completed"]
    }


async def scene_node(state: WorkflowState) -> WorkflowState:
    """Build scene setting and context."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[SCENE] Building scene for {state['year']} {state['season']}")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_SCENE,
        {"stage": "scene", "message": f"Building scene for {state['year']} in {state['location']['name']}..."}
    )

    timeline_data = {
        "year": state["year"],
        "season": state["season"],
        "location": state["location"]["name"]
    }

    scene_context = await build_scene(state["cleaned_query"], timeline_data)

    logger.info(f"[SCENE] Complete - Environment: {scene_context.setting.environment}")

    # Update timepoint with scene data
    setting = scene_context.setting.dict()
    weather = scene_context.weather.dict()
    props = [p.dict() for p in scene_context.props]

    await update_timepoint_progressive(
        state.get("timepoint_id"),
        metadata_json={
            "location": state["location"],
            "setting": setting,
            "weather": weather,
            "props": props
        }
    )

    return {
        **state,
        "setting": setting,
        "weather": weather,
        "props": props,
        "processing_steps": ["scene_completed"]
    }


async def characters_node(state: WorkflowState) -> WorkflowState:
    """Generate characters (parallel, up to 12)."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[CHARACTERS] Generating characters for scene")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_SCENE,
        {"stage": "characters", "message": "Generating historical characters for the scene..."}
    )

    timeline_data = {
        "year": state["year"],
        "season": state["season"],
        "location": state["location"]["name"]
    }

    scene_data = {
        "setting": state["setting"],
        "weather": state["weather"]
    }

    character_list = await generate_characters(
        state["cleaned_query"],
        timeline_data,
        scene_data
    )

    logger.info(f"[CHARACTERS] Complete - Generated {len(character_list.characters)} characters")

    # Update timepoint with character data
    characters = [c.dict() for c in character_list.characters]
    await update_timepoint_progressive(
        state.get("timepoint_id"),
        character_data_json=characters
    )

    return {
        **state,
        "characters": characters,
        "processing_steps": ["characters_completed"]
    }


async def moment_node(state: WorkflowState) -> WorkflowState:
    """Generate a specific dramatic moment/interaction for the scene."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[MOMENT] Generating plot moment for scene")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_SCENE,
        {"stage": "moment", "message": "Creating dramatic moment and interactions..."}
    )

    timeline_data = {
        "year": state["year"],
        "season": state["season"],
        "location": state["location"]["name"]
    }

    scene_data = {
        "setting": state["setting"],
        "weather": state["weather"]
    }

    moment = await generate_moment(
        state["cleaned_query"],
        timeline_data,
        scene_data,
        state["characters"]
    )

    logger.info(f"[MOMENT] Complete - Plot: {moment.plot_summary[:100]}...")
    logger.info(f"[MOMENT] Narrative beats: {len(moment.narrative_beats)}, Interactions: {len(moment.character_interactions)}")

    # Store moment data for dialog generation
    moment_dict = moment.dict()

    return {
        **state,
        "moment": moment_dict,
        "processing_steps": ["moment_completed"]
    }


async def camera_node(state: WorkflowState) -> WorkflowState:
    """Generate cinematic camera directives."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[CAMERA] Generating camera directives for cinematic composition")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_SCENE,
        {"stage": "camera", "message": "Setting up cinematic camera and lighting..."}
    )

    camera_directives = await generate_camera_directives(
        state["cleaned_query"],
        state["moment"],
        state["characters"],
        state["setting"],
        state["year"],
        state["location"]["name"]
    )

    logger.info(f"[CAMERA] Complete - Angle: {camera_directives.angle}, Lens: {camera_directives.lens}, Framing: {camera_directives.framing}")

    # Store camera data
    camera_dict = camera_directives.dict()

    return {
        **state,
        "camera": camera_dict,
        "processing_steps": ["camera_completed"]
    }


async def graph_builder_node(state: WorkflowState) -> WorkflowState:
    """Build NetworkX scene graph."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[GRAPH] Building scene graph")

    scene_graph = build_scene_graph(
        setting=state["setting"],
        weather=state["weather"],
        characters=state["characters"],
        props=state.get("props", [])
    )

    logger.info(f"[GRAPH] Complete - Graph nodes: {len(scene_graph.get('nodes', []))}")

    return {
        **state,
        "scene_graph": scene_graph,
        "processing_steps": ["graph_completed"]
    }


async def image_prompt_node(state: WorkflowState) -> WorkflowState:
    """Compile image generation prompt from ALL available context."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[IMAGE_PROMPT] Compiling comprehensive image prompt with moment, dialog, camera, and scene context")

    # Pass ALL context to image prompt generator
    image_prompt = graph_to_image_prompt(
        scene_graph=state["scene_graph"],
        cleaned_query=state["cleaned_query"],
        year=state["year"],
        location=state["location"]["name"],
        moment=state.get("moment"),  # Plot, action, emotional tone, interactions
        dialog=state.get("dialog"),  # Character dialogue
        characters=state["characters"],  # Full character bios
        setting=state["setting"],  # Scene details
        weather=state["weather"],  # Weather context
        camera=state.get("camera")  # Camera directives
    )

    logger.info(f"[IMAGE_PROMPT] Complete - Prompt length: {len(image_prompt)} chars")
    logger.info(f"[IMAGE_PROMPT] Included context: moment={bool(state.get('moment'))}, dialog={len(state.get('dialog', []))} lines, characters={len(state['characters'])}, camera={bool(state.get('camera'))}")

    return {
        **state,
        "image_prompt": image_prompt,
        "processing_steps": ["prompt_compiled"]
    }


async def generate_image_node(state: WorkflowState) -> WorkflowState:
    """Generate image using Gemini 2.5 Flash Image."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[IMAGE_GEN] Starting image generation")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_IMAGE,
        {"stage": "image", "message": "Generating historical scene image..."}
    )

    try:
        image_data = await generate_image(state["image_prompt"])
        logger.info(f"[IMAGE_GEN] Image generated successfully")

        # Update timepoint with main image IMMEDIATELY
        await update_timepoint_progressive(
            state.get("timepoint_id"),
            image_url=image_data
        )

        # Store image_prompt in metadata for reference
        await update_timepoint_progressive(
            state.get("timepoint_id"),
            metadata_json={
                **state.get("metadata_json", {}),
                "image_prompt": state["image_prompt"]
            }
        )

        return {
            **state,
            "image_url": image_data,
            "processing_steps": ["image_generated"]
        }

    except Exception as e:
        logger.error(f"[IMAGE_GEN] Failed: {str(e)}")
        # Continue workflow without image
        return {
            **state,
            "image_url": None,
            "errors": [f"Image generation failed: {str(e)}"],
            "processing_steps": ["image_failed"]
        }


async def dialog_node(state: WorkflowState) -> WorkflowState:
    """Generate character dialog."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DIALOG] Generating dialog")

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_SCENE,
        {"stage": "dialog", "message": "Generating period-accurate dialogue..."}
    )

    timeline_data = {
        "year": state["year"],
        "season": state["season"],
        "location": state["location"]["name"]
    }

    scene_data = {
        "setting": state["setting"],
        "weather": state["weather"]
    }

    dialog = await generate_dialog(
        state["cleaned_query"],
        timeline_data,
        state["characters"],
        scene_data,
        state["moment"]  # NEW: Pass moment context for narrative-driven dialog
    )

    logger.info(f"[DIALOG] Complete - Generated {len(dialog.lines)} lines")

    # Update timepoint with dialog data
    dialog_data = [line.dict() for line in dialog.lines]
    await update_timepoint_progressive(
        state.get("timepoint_id"),
        dialog_json=dialog_data
    )

    return {
        **state,
        "dialog": dialog_data,
        "processing_steps": ["dialog_completed"]
    }


async def segment_image_node(state: WorkflowState) -> WorkflowState:
    """Segment image to identify and label characters."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[IMAGE_SEG] Starting image segmentation")

    # Check if image exists
    if not state.get("image_url"):
        logger.warning(f"[IMAGE_SEG] No image URL available, skipping segmentation")
        return {
            **state,
            "segmented_image_url": None,
            "processing_steps": ["segmentation_skipped"]
        }

    # Update session status
    await update_session_status(
        state["session_id"],
        ProcessingStatus.GENERATING_IMAGE,
        {"stage": "segmentation", "message": "Identifying characters in scene..."}
    )

    try:
        # Get character names for segmentation
        character_names = [char['name'] for char in state.get("characters", [])]

        # Segment the image
        segmentation = await segment_image(state["image_url"], character_names)
        logger.info(f"[IMAGE_SEG] Segmentation complete")

        # Extract segmented image or text description
        seg_result = segmentation.get("segmentation_image") or segmentation.get("segmentation_data")
        color_map = segmentation.get("color_map", {})

        # Update timepoint with segmented image
        await update_timepoint_progressive(
            state.get("timepoint_id"),
            segmented_image_url=seg_result,
            metadata_json={
                **state.get("metadata_json", {}),
                "color_map": color_map
            }
        )

        return {
            **state,
            "segmented_image_url": seg_result,
            "color_map": color_map,
            "processing_steps": ["segmentation_completed"]
        }

    except Exception as e:
        logger.warning(f"[IMAGE_SEG] Segmentation failed: {str(e)}")
        # Continue without segmentation
        return {
            **state,
            "segmented_image_url": None,
            "processing_steps": ["segmentation_failed"]
        }


# Build workflow graph
def create_workflow() -> StateGraph:
    """Create the LangGraph workflow."""
    workflow = StateGraph(WorkflowState)

    # Add all nodes
    workflow.add_node("judge", judge_node)
    workflow.add_node("timeline", timeline_node)
    workflow.add_node("scene", scene_node)
    workflow.add_node("characters", characters_node)
    workflow.add_node("moment", moment_node)  # Plot/interaction moment
    workflow.add_node("camera", camera_node)  # Camera directives
    workflow.add_node("graph_builder", graph_builder_node)
    workflow.add_node("image_prompt", image_prompt_node)
    workflow.add_node("dialog", dialog_node)
    workflow.add_node("generate_image", generate_image_node)
    workflow.add_node("segment_image", segment_image_node)

    # Define workflow edges
    # Workflow: judge → timeline → scene → characters → MOMENT → DIALOG → CAMERA → graph → prompt → image → segmentation → END
    workflow.set_entry_point("judge")
    workflow.add_conditional_edges("judge", should_continue)
    workflow.add_edge("timeline", "scene")
    workflow.add_edge("scene", "characters")
    workflow.add_edge("characters", "moment")            # Moment after characters
    workflow.add_edge("moment", "dialog")                # Dialog after moment (uses moment context)
    workflow.add_edge("dialog", "camera")                # Camera after dialog (knows what's being said)
    workflow.add_edge("camera", "graph_builder")         # Graph builder after camera
    workflow.add_edge("graph_builder", "image_prompt")   # Image prompt has ALL context (moment, dialog, camera)
    workflow.add_edge("image_prompt", "generate_image")  # Generate image from complete prompt
    workflow.add_edge("generate_image", "segment_image") # Separate segmentation
    workflow.add_edge("segment_image", END)              # End after segmentation

    return workflow.compile()


async def update_session_status(session_id: str, status: ProcessingStatus, progress_data: dict = None):
    """Update processing session in database."""
    with get_db_context() as db:
        session = db.query(ProcessingSession).filter(
            ProcessingSession.session_id == session_id
        ).first()

        if session:
            session.status = status
            if progress_data:
                # MERGE progress_data with existing to preserve timepoint_url and other fields
                existing_data = session.progress_data_json or {}
                session.progress_data_json = {**existing_data, **progress_data}
            db.commit()


async def update_timepoint_progressive(timepoint_id: str, **updates):
    """Progressively update timepoint record as data becomes available."""
    logger = logging.getLogger(__name__)

    if not timepoint_id:
        return

    try:
        with get_db_context() as db:
            # CRITICAL FIX: Expire all cached objects before querying
            db.expire_all()

            timepoint = db.query(Timepoint).filter(Timepoint.id == timepoint_id).first()
            if timepoint:
                for key, value in updates.items():
                    if hasattr(timepoint, key):
                        setattr(timepoint, key, value)
                db.commit()

                # CRITICAL FIX: Expire objects after commit to ensure next read is fresh
                db.expire_all()

                # SYNC LOG: Backend just updated database
                import time
                update_timestamp = time.time()
                logger.info(f"[SYNC] ⬆️  Backend UPDATE at {update_timestamp:.3f} - fields: {list(updates.keys())}")
                logger.info(f"[SYNC] Frontend should see this on next poll (within 2s)")

                logger.info(f"[PROGRESSIVE] Updated timepoint {timepoint_id} with: {list(updates.keys())}")

                # Small delay to ensure PostgreSQL transaction is visible to concurrent reads
                await asyncio.sleep(0.05)
    except Exception as e:
        logger.error(f"[PROGRESSIVE] Failed to update timepoint: {e}", exc_info=True)


async def run_timepoint_workflow(session_id: str, email: str, query: str):
    """
    Execute the complete timepoint generation workflow.

    This function is called as a background task from the API.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Starting workflow for session {session_id}")

    start_time = datetime.utcnow()

    try:
        # Update status: validating
        logger.info(f"[WORKFLOW] Updating status to VALIDATING")
        await update_session_status(
            session_id,
            ProcessingStatus.VALIDATING,
            {"stage": "validating", "message": "Validating your time travel query..."}
        )

        logger.info(f"[WORKFLOW] Creating workflow graph")
        workflow = create_workflow()

        initial_state = {
            "session_id": session_id,
            "email": email,
            "user_query": query,
            "processing_steps": [],
            "errors": []
        }

        # Execute workflow
        logger.info(f"[WORKFLOW] Starting workflow execution")
        final_state = await workflow.ainvoke(initial_state)
        logger.info(f"[WORKFLOW] Workflow execution complete")

        # Check if validation failed
        if not final_state.get("is_valid"):
            logger.warning(f"[WORKFLOW] Query validation failed: {final_state.get('rejection_reason')}")
            await update_session_status(
                session_id,
                ProcessingStatus.FAILED,
                {"error": final_state.get("rejection_reason", "Invalid query")}
            )
            return

        # Calculate processing time
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.info(f"[WORKFLOW] Processing time: {processing_time}ms")

        # Update existing timepoint with final data (scene_graph and processing time)
        timepoint_id = final_state.get("timepoint_id")
        if timepoint_id:
            logger.info(f"[WORKFLOW] Updating timepoint {timepoint_id} with final data")
            await update_timepoint_progressive(
                timepoint_id,
                scene_graph_json=final_state.get("scene_graph"),
                processing_time_ms=processing_time
            )

        # Mark session as completed
        with get_db_context() as db:
            session = db.query(ProcessingSession).filter(
                ProcessingSession.session_id == session_id
            ).first()

            if session:
                session.status = ProcessingStatus.COMPLETED
                # timepoint_id was already set in timeline_node
                # timepoint_url was already set in timeline_node
                # Just update the completion message
                session.progress_data_json = {
                    **session.progress_data_json,
                    "stage": "completed",
                    "message": "Your timepoint is ready!"
                }
                db.commit()
                logger.info(f"[WORKFLOW] Status committed to COMPLETED, waiting for transaction visibility...")

                # Update rate limit
                update_rate_limit(db, email)

        # Small delay to ensure database transaction is fully visible to SSE polling
        # This helps avoid race conditions with READ COMMITTED isolation level
        await asyncio.sleep(0.3)
        logger.info(f"[WORKFLOW] Workflow completed successfully")

    except Exception as e:
        # Update session to failed
        logger.error(f"[WORKFLOW] Workflow failed with error: {str(e)}", exc_info=True)
        await update_session_status(
            session_id,
            ProcessingStatus.FAILED,
            {"error": str(e), "stage": "failed"}
        )
        raise  # Re-raise for logging
