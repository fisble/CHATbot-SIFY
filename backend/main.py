"""
FastAPI main application for the ThinkerLLM multi-agent AI system.
Provides REST API, WebSocket, and SSE endpoints for agent orchestration.
"""

import asyncio
import json
from typing import Dict, Set, Optional, AsyncGenerator, List, Any
from decimal import Decimal
from contextlib import asynccontextmanager
from datetime import datetime
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from models.schemas import (
    AgentRequest, AgentEvent, AgentEventType, AgentName,
    Storyboard, SessionInfo, MasterPlan
)
from agents import PreActAgent, ReActAgent, ReFlectAgent, AgentContext
from storage.mongodb import get_mongodb_service
from rag.retriever import get_rag_service
from prompts.dynamic_prompt_builder import get_prompt_builder
import httpx


# Custom JSON encoder for datetime and other types
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'model_dump'):  # Pydantic model
            return obj.model_dump()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def serialize_for_json(obj):
    """Recursively serialize an object for JSON, handling datetime and other special types."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, 'model_dump'):  # Pydantic model
        return serialize_for_json(obj.model_dump())
    elif hasattr(obj, 'isoformat'):  # date, time, etc
        return obj.isoformat()
    return obj

#image
from fastapi import UploadFile, File

import base64
import os
# Custom JSON encoder for datetime and other types
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, 'model_dump'):  # Pydantic model
            return obj.model_dump()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def serialize_for_json(obj):
    """Recursively serialize an object for JSON, handling datetime and other special types."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, 'model_dump'):  # Pydantic model
        return serialize_for_json(obj.model_dump())
    elif hasattr(obj, 'isoformat'):  # date, time, etc
        return obj.isoformat()
    return obj

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}
# Store SSE connections
sse_connections: Dict[str, asyncio.Queue] = {}
# Store running tasks
running_tasks: Dict[str, asyncio.Task] = {}
# Store pending plans awaiting approval (in-memory cache)
pending_plans: Dict[str, Dict] = {}


async def save_pending_plan(session_id: str, plan_data: Dict):
    """Save pending plan to MongoDB for persistence across restarts."""
    mongodb = await get_mongodb_service()
    # Store in memory
    pending_plans[session_id] = plan_data
    # Also persist to MongoDB
    try:
        await mongodb.db.pending_plans.update_one(
            {"session_id": session_id},
            {"$set": {"session_id": session_id, "plan_data": plan_data}},
            upsert=True
        )
    except Exception as e:
        print(f"[WARN] Could not persist pending plan: {e}")


async def get_pending_plan(session_id: str) -> Optional[Dict]:
    """Get pending plan from memory or MongoDB."""
    # Check memory first
    if session_id in pending_plans:
        return pending_plans[session_id]
    # Try MongoDB
    try:
        mongodb = await get_mongodb_service()
        doc = await mongodb.db.pending_plans.find_one({"session_id": session_id})
        if doc:
            plan_data = doc.get("plan_data", {})
            # Cache in memory
            pending_plans[session_id] = plan_data
            return plan_data
    except Exception as e:
        print(f"[WARN] Could not load pending plan from MongoDB: {e}")
    return None


async def delete_pending_plan(session_id: str):
    """Delete pending plan from memory and MongoDB."""
    if session_id in pending_plans:
        del pending_plans[session_id]
    try:
        mongodb = await get_mongodb_service()
        await mongodb.db.pending_plans.delete_one({"session_id": session_id})
    except Exception as e:
        print(f"[WARN] Could not delete pending plan: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Initialize RAG with domain content
    rag_service = get_rag_service()
    await rag_service.initialize_domain_content()
    print("RAG service initialized with domain content")
    
    # Connect to MongoDB
    mongodb = await get_mongodb_service()
    print("MongoDB connection established")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    for task in running_tasks.values():
        task.cancel()
    if mongodb:
        await mongodb.disconnect()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="ThinkerLLM - Multi-agent AI assistant with PreAct planning, ReAct execution, and ReFlect validation",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Request/Response Models ====================

class RunAgentRequest(BaseModel):
    query: str
    domain: Optional[str] = None  # Optional - will auto-detect if not provided


class PreActPlanRequest(BaseModel):
    query: str
    domain: Optional[str] = None  # Optional - will auto-detect if not provided


class ExecutePlanRequest(BaseModel):
    session_id: str
    approved: bool = True
    enable_web_search: bool = False  # Web search only when user explicitly enables it


class RunAgentResponse(BaseModel):
    session_id: str
    status: str
    message: str
    detected_domain: Optional[str] = None


class PlanResponse(BaseModel):
    session_id: str
    plan: dict
    mermaid_diagram: str
    status: str
    detected_domain: Optional[str] = None


class DomainListResponse(BaseModel):
    domains: list

# ==================== Vision API (VISION MODE ONLY) ====================
# NOTE: This endpoint is only used when user is in VISION mode in the frontend.
# Vision functionality has been isolated to the Vision mode to keep other modes clean.
#image
class VisionRequest(BaseModel):
    image_data_url: str
# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "preact_plan": "POST /api/preact-plan",
            "execute": "POST /api/execute",
            "events_sse": "GET /api/events/{session_id}",
            "websocket": "WS /ws/{session_id}",
            "domains": "GET /api/domains",
            "memory": "GET /api/memory/{session_id}",
            "rag_search": "POST /api/rag-search"
        }
    }


@app.get("/api/domains", response_model=DomainListResponse)
async def get_domains():
    """Get list of available domains."""
    prompt_builder = get_prompt_builder()
    domains = prompt_builder.get_available_domains()
    return DomainListResponse(domains=domains)

# Vision system prompt (VISION MODE ONLY)
#image
SYSTEM_PROMPT="""You are a vision analysis agent.

Describe only what is directly visible in the image.

Use the following sections exactly once, in this order:
Overall Scene & Environment
Background & Setting Details
Objects and Spatial Positions
Textures, Materials, and Surfaces
Lighting, Shadows, and Color Tones
Subject Analysis (if present)
Scene Context and Possible Setting

Rules:
- Each sentence must describe a unique, concrete visual detail.
- Do not repeat information across sentences or sections.
- Do not describe emotions, symbolism, atmosphere, intent, or meaning.
- Do not use abstract language.
- Do not summarize or conclude.
- Stop generating text immediately when no new visual details remain.
"""
# Vision endpoint (VISION MODE ONLY - used by frontend Vision mode)
@app.post("/vision")
async def vision_endpoint(payload: VisionRequest):
    import os
    
    try:
        url = "https://ai.sifylivelearn.com/llama/v1/chat/completions"

        body = {
            "model": "meta-llama/Llama-3.2-11B-Vision-Instruct",
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": payload.image_data_url
                            }
                        }
                    ]
                }
            ],

            "max_tokens": 500,
            "temperature": 0.0,
            "frequency_penalty": 1.0,
            "presence_penalty": 0.0,
            "stop": [
            "Scene Context and Possible Setting"
            ]
        }

        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('VISION_API_KEY')}"
        }

        # Use httpx.AsyncClient for truly async (non-blocking) HTTP requests
        # This prevents thread pool exhaustion and blocking other operations
        timeout = httpx.Timeout(25.0, connect=5.0)  # 25s total, 5s connect
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=body, headers=headers)
            
            if response.status_code != 200:
                return {
                    "error": f"Vision API returned status {response.status_code}: {response.text[:200]}"
                }
            
            result = response.json()
            
            if "choices" not in result or len(result["choices"]) == 0:
                return {
                    "error": "Vision API returned invalid response format"
                }
            
            return {
                "reply": result["choices"][0]["message"]["content"]
            }
        except httpx.TimeoutException:
            return {
                "error": "Vision API request timed out after 25 seconds. Please try again."
            }
        except httpx.RequestError as e:
            return {
                "error": f"Vision API request failed: {str(e)}"
            }

    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}"
        }

# ==================== PreAct Plan Generation ====================

@app.post("/api/preact-plan")
async def generate_preact_plan(request: PreActPlanRequest):
    """
    Generate a PreAct plan WITHOUT execution.
    User must approve the plan before execution begins.
    
    Domain is optional - will auto-detect from query if not provided.
    """
    import asyncio
    import traceback
    from services.direct_chat import get_direct_chat_service
    
    try:
        print(f"[PREACT_PLAN] Received request: query='{request.query[:50]}...', domain={request.domain}")
        
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Auto-detect domain if not provided
        effective_domain = request.domain
        if not effective_domain or effective_domain == "auto":
            direct_service = get_direct_chat_service()
            effective_domain = direct_service.detect_domain(request.query)
        
        print(f"[PREACT_PLAN] Effective domain: {effective_domain}")
        
        # Create session
        mongodb = await get_mongodb_service()
        session = await mongodb.create_session(
            domain=effective_domain,
            query=request.query
        )
        
        print(f"[PREACT_PLAN] Session created: {session.session_id}")
        
        # Create agent context
        context = AgentContext(
            session_id=session.session_id,
            domain=effective_domain,
            query=request.query
        )
        
        # Run PreAct agent to generate plan with timeout protection
        preact_agent = PreActAgent()
        events = []
        
        print(f"[PREACT_PLAN] Starting PreAct agent run...")
        try:
            # Add timeout protection for PreAct planning (90 seconds max)
            async def run_preact_with_timeout():
                events_list = []
                async for event in preact_agent.run(context):
                    events_list.append({
                        "agent": event.agent.value if hasattr(event.agent, 'value') else str(event.agent),
                        "event": event.event.value if hasattr(event.event, 'value') else str(event.event),
                        "content": event.content,
                        "metadata": event.metadata,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    print(f"[PREACT_PLAN] Event received: {event.event} ({len(events_list)} events so far)")
                return events_list
            
            events = await asyncio.wait_for(run_preact_with_timeout(), timeout=90.0)
        except asyncio.TimeoutError:
            print(f"[PREACT_PLAN] Planning timed out after 90 seconds")
            raise HTTPException(
                status_code=504,
                detail="Planning took too long. The LLM service may be slow. Please try again."
            )
        except Exception as agent_error:
            print(f"[PREACT_PLAN] Error in PreAct agent run: {str(agent_error)}")
            print(f"[PREACT_PLAN] Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating plan: {str(agent_error)}"
            )
        
        print(f"[PREACT_PLAN] Agent run completed. Total events: {len(events)}")
    
        # Get reasoning plan from metadata first
        reasoning_plan = context.metadata.get("reasoning_plan", {})
        
        if not reasoning_plan:
            print(f"[PREACT_PLAN] WARNING: No reasoning plan found in context metadata")
            reasoning_plan = {}
        
        # Use detected domain from reasoning plan if available
        detected_domain = reasoning_plan.get("detected_domain", effective_domain) if reasoning_plan else effective_domain
        
        print(f"[PREACT_PLAN] Generating Mermaid diagram...")
        # Generate Mermaid diagram
        mermaid_diagram = generate_mermaid_diagram(context.master_plan, effective_domain)
        
        print(f"[PREACT_PLAN] Storing pending plan...")
        # Store pending plan with all metadata (persisted to MongoDB)
        plan_storage = {
            "master_plan": context.master_plan.model_dump() if context.master_plan else None,
            "reasoning_plan": reasoning_plan,
            "metadata": context.metadata,
            "events": events,
            "mermaid": mermaid_diagram,
            "domain": effective_domain,
            "detected_domain": detected_domain,
            "query": request.query,
            "created_at": datetime.utcnow().isoformat()
        }
        await save_pending_plan(session.session_id, plan_storage)
        
        # Build response with reasoning plan
        response_plan = {
            **(context.master_plan.model_dump() if context.master_plan else {}),
            "reasoning_plan": reasoning_plan,
            "steps": reasoning_plan.get("steps", []),
            "task_understanding": reasoning_plan.get("task_understanding", ""),
            "approach": reasoning_plan.get("approach", ""),
            "constraints": reasoning_plan.get("constraints", []),
            "success_criteria": reasoning_plan.get("success_criteria", []),
            "estimated_complexity": reasoning_plan.get("estimated_complexity", "moderate"),
            "detected_domain": reasoning_plan.get("detected_domain", effective_domain),
            "domain_skills": reasoning_plan.get("domain_skills", []),
            "domain_capabilities": reasoning_plan.get("domain_capabilities", [])
        }
        
        print(f"[PREACT_PLAN] Returning response with {len(events)} events and {len(reasoning_plan.get('steps', []))} steps")
        
        return {
            "session_id": session.session_id,
            "status": "plan_ready",
            "plan": response_plan,
            "reasoning_plan": reasoning_plan,
            "mermaid_diagram": mermaid_diagram,
            "events": events,
            "step_count": len(reasoning_plan.get("steps", [])),
            "detected_domain": detected_domain,
            "clarification_questions": reasoning_plan.get("clarification_questions", []),
            "message": "Plan generated. Review and approve to start execution."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PREACT_PLAN] Fatal error: {str(e)}")
        print(f"[PREACT_PLAN] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate plan: {str(e)}"
        )


# ==================== Plan Refinement ====================

class PlanRefineRequest(BaseModel):
    """Request model for plan refinement."""
    session_id: str
    user_responses: Dict[str, Any] = {}  # Responses to clarification questions
    chat_message: str = ""  # Additional user instructions
    chat_history: List[Dict] = []  # Previous chat messages


@app.post("/api/preact-plan/refine")
async def refine_preact_plan(request: PlanRefineRequest):
    """
    Refine an existing PreAct plan based on user feedback.
    
    This endpoint allows users to:
    1. Answer clarification questions
    2. Provide additional instructions
    3. Chat with the AI to optimize the plan
    """
    # Get the pending plan (from memory or MongoDB)
    pending = await get_pending_plan(request.session_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending plan found for this session")
    
    original_plan = pending.get("reasoning_plan", {})
    
    # Reconstruct context from stored data
    from models.agent_models import AgentContext
    context = AgentContext(
        session_id=request.session_id,
        domain=pending.get("domain", "general"),
        query=pending.get("query", "")
    )
    # Restore metadata
    if pending.get("metadata"):
        context.metadata.update(pending["metadata"])
    
    if not context:
        raise HTTPException(status_code=400, detail="Invalid plan context")
    
    # Run PreAct refinement
    preact_agent = PreActAgent()
    events = []
    refined_plan = None
    mermaid_diagram = None
    
    async for event in preact_agent.refine_plan(
        context=context,
        original_plan=original_plan,
        user_responses=request.user_responses,
        chat_message=request.chat_message,
        chat_history=request.chat_history
    ):
        events.append({
            "agent": event.agent.value if hasattr(event.agent, 'value') else str(event.agent),
            "event": event.event.value if hasattr(event.event, 'value') else str(event.event),
            "content": event.content,
            "metadata": event.metadata,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Capture refined plan from PLAN event
        if event.event == AgentEventType.PLAN and event.metadata:
            refined_plan = event.metadata.get("reasoning_plan", {})
            mermaid_diagram = event.metadata.get("mermaid_diagram")
    
    # Get the refined plan from context if not captured from event
    if not refined_plan:
        refined_plan = context.metadata.get("reasoning_plan", original_plan)
    
    # Update chat history in the plan
    chat_history = request.chat_history.copy()
    if request.chat_message:
        chat_history.append({"role": "user", "content": request.chat_message})
        chat_history.append({
            "role": "assistant", 
            "content": f"I've updated the plan based on your feedback. The plan now has {len(refined_plan.get('steps', []))} steps."
        })
    
    refined_plan["chat_history"] = chat_history
    
    # Update pending plan (persisted to MongoDB)
    new_refinement_count = pending.get("refinement_count", 0) + 1
    updated_plan = {
        **pending,
        "reasoning_plan": refined_plan,
        "mermaid": mermaid_diagram or pending.get("mermaid"),
        "events": events,
        "is_refined": True,
        "refinement_count": new_refinement_count
    }
    await save_pending_plan(request.session_id, updated_plan)
    
    # Build response plan
    response_plan = {
        "reasoning_plan": refined_plan,
        "steps": refined_plan.get("steps", []),
        "task_understanding": refined_plan.get("task_understanding", ""),
        "approach": refined_plan.get("approach", ""),
        "constraints": refined_plan.get("constraints", []),
        "success_criteria": refined_plan.get("success_criteria", []),
        "estimated_complexity": refined_plan.get("estimated_complexity", "moderate"),
        "detected_domain": refined_plan.get("detected_domain"),
        "clarification_questions": refined_plan.get("clarification_questions", []),
        "chat_history": chat_history
    }
    
    return {
        "session_id": request.session_id,
        "status": "plan_refined",
        "plan": response_plan,
        "reasoning_plan": refined_plan,
        "mermaid_diagram": mermaid_diagram or pending.get("mermaid"),
        "events": events,
        "step_count": len(refined_plan.get("steps", [])),
        "chat_history": chat_history,
        "is_refined": True,
        "refinement_count": new_refinement_count,
        "message": "Plan refined based on your feedback. Review and approve to start execution."
    }


def generate_mermaid_diagram(master_plan: Optional[MasterPlan], domain: str) -> str:
    """Generate a Mermaid flowchart from the master plan."""
    if not master_plan:
        return """
graph TD
    A[Domain Selection] --> B[Prompt Generation]
    B --> C[RAG Retrieval]
    C --> D[PreAct Planning]
    D --> E[User Approval]
    E --> F[ReAct Generation]
    F --> G[ReFlect Validation]
    G --> H[TME Memory Update]
    H --> I[Final Output]
"""
    
    diagram = f"""
graph TD
    subgraph PreAct["🎯 PreAct Planning"]
        A[📋 Domain: {domain}] --> B[🔍 RAG Knowledge Retrieval]
        B --> C[📝 Plan Generation]
        C --> D[📊 Requirements Analysis]
        D --> E[🎨 Strategy Setup]
    end
    
    subgraph Steps["📝 Execution Steps"]
"""
    
    # Add step nodes
    for i, step in enumerate(master_plan.scene_outline[:6]):
        step_short = step[:30] + "..." if len(step) > 30 else step
        diagram += f'        S{i+1}["Step {i+1}: {step_short}"]\n'
    
    # Connect steps
    step_count = min(len(master_plan.scene_outline), 6)
    if step_count > 0:
        diagram += f'        E --> S1\n'
        for i in range(1, step_count):
            diagram += f'        S{i} --> S{i+1}\n'
        diagram += f'        S{step_count} --> F\n'
    else:
        diagram += f'        E --> F\n'
    
    diagram += """    end
    
    subgraph ReAct["⚡ ReAct Execution"]
        F[🧠 Reasoning Loop]
        F --> G[📖 Content Generation]
        G --> H[💾 TME Memory Update]
    end
    
    subgraph ReFlect["🔄 ReFlect Validation"]
        H --> I[✅ Quality Check]
        I --> J[📊 Quality Score]
        J --> K[✨ Final Output]
    end
    
    style PreAct fill:#e3f2fd
    style Steps fill:#f3e5f5
    style ReAct fill:#e8f5e9
    style ReFlect fill:#fff3e0
"""
    
    return diagram


# ==================== Execute Approved Plan ====================

@app.post("/api/execute")
async def execute_plan(request: ExecutePlanRequest):
    """
    Execute an approved PreAct plan.
    Starts the ReAct and ReFlect phases.
    """
    session_id = request.session_id
    
    # Get plan from memory or MongoDB (survives server restarts)
    plan_data = await get_pending_plan(session_id)
    
    if not plan_data:
        raise HTTPException(
            status_code=404,
            detail="No pending plan found for this session. Generate a plan first."
        )
    
    if not request.approved:
        # Remove the pending plan
        await delete_pending_plan(session_id)
        return {"status": "cancelled", "message": "Plan execution cancelled."}
    
    # Create SSE queue for this session BEFORE starting the task
    print(f"[EXECUTE] Creating SSE queue for session {session_id}")
    sse_connections[session_id] = asyncio.Queue()
    
    # Store web search flag in plan_data for pipeline
    plan_data["enable_web_search"] = request.enable_web_search
    
    # Store the plan data and mark as ready for execution
    # The actual execution will start with a small delay to allow SSE connection
    async def delayed_execution():
        # Wait for SSE connection to be established
        await asyncio.sleep(0.5)  # Small delay to allow frontend to connect
        print(f"[EXECUTE] Starting delayed execution for session {session_id}, web_search={request.enable_web_search}")
        await execute_agent_pipeline(session_id=session_id, plan_data=plan_data)
    
    task = asyncio.create_task(delayed_execution())
    running_tasks[session_id] = task
    
    return {
        "status": "executing",
        "session_id": session_id,
        "message": f"Execution started. Connect to /api/events/{session_id} for live updates."
    }


async def execute_agent_pipeline(session_id: str, plan_data: Dict):
    """Execute the ReAct and ReFlect phases after plan approval."""
    import traceback
    
    mongodb = await get_mongodb_service()
    queue = sse_connections.get(session_id)
    
    print(f"[PIPELINE] Starting execution for session {session_id}")
    
    # Recreate context from stored plan
    context = AgentContext(
        session_id=session_id,
        domain=plan_data["domain"],
        query=plan_data["query"]
    )
    
    # Restore master plan
    if plan_data["master_plan"]:
        context.master_plan = MasterPlan(**plan_data["master_plan"])
    
    # Restore reasoning plan and metadata
    if plan_data.get("reasoning_plan"):
        context.metadata["reasoning_plan"] = plan_data["reasoning_plan"]
        print(f"[PIPELINE] Loaded reasoning plan with {len(plan_data['reasoning_plan'].get('steps', []))} steps")
    if plan_data.get("metadata"):
        context.metadata.update(plan_data["metadata"])
    
    # Store web search flag in context (from request, default False)
    context.metadata["enable_web_search"] = plan_data.get("enable_web_search", False)
    
    react_agent = ReActAgent()
    reflect_agent = ReFlectAgent()
    
    try:
        await mongodb.update_session(session_id, {"status": "running"})
        
        # Emit execution start
        await emit_event(queue, session_id, AgentEvent(
            agent=AgentName.SYSTEM,
            event=AgentEventType.STATUS,
            content="Starting execution of approved plan..."
        ))
        
        # Phase 2: ReAct Content Generation
        print(f"[PIPELINE] Starting ReAct phase...")
        await emit_event(queue, session_id, AgentEvent(
            agent=AgentName.REACT,
            event=AgentEventType.STATUS,
            content="Starting ReAct reasoning phase..."
        ))
        
        react_event_count = 0
        try:
            async for event in react_agent.run(context):
                react_event_count += 1
                print(f"[REACT] Event {react_event_count}: {event.event.value if hasattr(event.event, 'value') else event.event}")
                await emit_event(queue, session_id, event)
        except Exception as react_error:
            print(f"[REACT ERROR] {str(react_error)}")
            print(traceback.format_exc())
            await emit_event(queue, session_id, AgentEvent(
                agent=AgentName.REACT,
                event=AgentEventType.ERROR,
                content=f"ReAct error: {str(react_error)}"
            ))
        
        print(f"[PIPELINE] ReAct completed with {react_event_count} events")
        print(f"[PIPELINE] ReAct output length: {len(context.metadata.get('react_output', ''))}")
        
        # Phase 3: ReFlect Validation
        print(f"[PIPELINE] Starting ReFlect phase...")
        await emit_event(queue, session_id, AgentEvent(
            agent=AgentName.REFLECT,
            event=AgentEventType.STATUS,
            content="Starting ReFlect validation phase..."
        ))
        
        reflect_event_count = 0
        try:
            async for event in reflect_agent.run(context):
                reflect_event_count += 1
                print(f"[REFLECT] Event {reflect_event_count}: {event.event.value if hasattr(event.event, 'value') else event.event}")
                await emit_event(queue, session_id, event)
        except Exception as reflect_error:
            print(f"[REFLECT ERROR] {str(reflect_error)}")
            print(traceback.format_exc())
            await emit_event(queue, session_id, AgentEvent(
                agent=AgentName.REFLECT,
                event=AgentEventType.ERROR,
                content=f"ReFlect error: {str(reflect_error)}"
            ))
        
        print(f"[PIPELINE] ReFlect completed with {reflect_event_count} events")
        
        # Get final output
        final_output = context.metadata.get("reflect_output") or context.metadata.get("react_output", "")
        final_scores = context.metadata.get("reflect_scores", {})
        
        print(f"[PIPELINE] Final output length: {len(final_output)}")
        print(f"[PIPELINE] Final scores: {final_scores}")
        
        # Send final output event
        await emit_event(queue, session_id, AgentEvent(
            agent=AgentName.SYSTEM,
            event=AgentEventType.SCENE,
            content=f"📄 Final Output:\n\n{final_output[:2000]}{'...' if len(final_output) > 2000 else ''}",
            metadata={
                "final_output": final_output,
                "quality_score": final_scores.get("overall", 0),
                "event_type": "final_output"
            }
        ))
        
        # Save final storyboard (only if one was created)
        if context.storyboard:
            await mongodb.save_storyboard(context.storyboard)
        
        # Send complete event
        await emit_event(queue, session_id, AgentEvent(
            agent=AgentName.SYSTEM,
            event=AgentEventType.COMPLETE,
            content=f"✅ Generation complete!\n\n📊 Quality Score: {final_scores.get('overall', 'N/A')}/10\n📝 Output Length: {len(final_output)} characters",
            metadata={
                "storyboard": context.storyboard.model_dump() if context.storyboard else None,
                "final_output": final_output,
                "quality_score": final_scores.get("overall"),
                "react_iterations": context.metadata.get("react_iterations", 0)
            }
        ))
        
        await mongodb.update_session(session_id, {"status": "complete"})
        
    except Exception as e:
        await emit_event(queue, session_id, AgentEvent(
            agent=AgentName.SYSTEM,
            event=AgentEventType.ERROR,
            content=f"Error during execution: {str(e)}"
        ))
        await mongodb.update_session(session_id, {"status": "error"})
    finally:
        # Cleanup (remove from memory and MongoDB)
        await delete_pending_plan(session_id)
        if session_id in running_tasks:
            del running_tasks[session_id]


async def emit_event(queue: Optional[asyncio.Queue], session_id: str, event: AgentEvent):
    """Emit event to SSE queue and store in MongoDB."""
    # Serialize metadata to handle datetime objects
    serialized_metadata = serialize_for_json(event.metadata) if event.metadata else {}
    
    event_data = {
        "agent": event.agent.value if hasattr(event.agent, 'value') else str(event.agent),
        "event": event.event.value if hasattr(event.event, 'value') else str(event.event),
        "content": event.content[:200] + "..." if event.content and len(event.content) > 200 else event.content,
        "metadata": serialized_metadata,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Store full content for transmission
    full_event_data = {
        "agent": event.agent.value if hasattr(event.agent, 'value') else str(event.agent),
        "event": event.event.value if hasattr(event.event, 'value') else str(event.event),
        "content": event.content,
        "metadata": serialized_metadata,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add to SSE queue (use full event data)
    if queue:
        await queue.put(full_event_data)
    else:
        print(f"[EMIT] Warning: No queue for session {session_id}")
    
    # Also broadcast to WebSocket if connected
    if session_id in active_connections:
        ws = active_connections[session_id]
        try:
            await ws.send_json(full_event_data)
        except:
            pass
    
    # Store event in MongoDB
    mongodb = await get_mongodb_service()
    try:
        await mongodb.add_agent_event(
            session_id=session_id,
            event=event
        )
    except Exception as e:
        print(f"MongoDB storage error: {e}")


# ==================== SSE Events Endpoint ====================

@app.get("/api/events/{session_id}")
async def events_stream(session_id: str, request: Request):
    """
    Server-Sent Events endpoint for real-time agent streaming.
    Alternative to WebSocket for better compatibility.
    """
    
    async def event_generator():
        # IMPORTANT: Use existing queue if available (created by /api/execute)
        # Only create new queue if not exists
        if session_id not in sse_connections:
            print(f"[SSE] Creating new queue for session {session_id}")
            sse_connections[session_id] = asyncio.Queue()
        else:
            print(f"[SSE] Using existing queue for session {session_id}")
        
        queue = sse_connections[session_id]
        
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'session_id': session_id})}\n\n"
        print(f"[SSE] Connected for session {session_id}")
        
        events_sent = 0
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    print(f"[SSE] Client disconnected for session {session_id}")
                    break
                
                try:
                    # Wait for events with timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=10.0)
                    
                    event_type = event.get("event", "message")
                    events_sent += 1
                    print(f"[SSE] Sending event {events_sent}: {event_type} for session {session_id}")
                    
                    # Serialize event data to handle datetime and other special types
                    serialized_event = serialize_for_json(event)
                    yield f"event: {event_type}\ndata: {json.dumps(serialized_event)}\n\n"
                    
                    # Only end stream on SYSTEM complete/error (not individual agent complete events)
                    # This allows ReAct to complete and ReFlect to still run
                    agent = event.get("agent", "")
                    if event_type == "error":
                        print(f"[SSE] Stream ending (error) for session {session_id}")
                        break
                    if event_type == "complete" and agent == "system":
                        print(f"[SSE] Stream ending (system complete) for session {session_id}")
                        break
                        
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"
                    
        finally:
            # Cleanup
            print(f"[SSE] Cleaning up session {session_id}, sent {events_sent} events")
            if session_id in sse_connections:
                del sse_connections[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==================== Memory Endpoint ====================

@app.get("/api/memory/{session_id}")
async def get_memory(session_id: str):
    """Get TME memory entries for a session."""
    from memory.tme import get_tme_service
    tme = get_tme_service()
    
    memories = await tme.get_all_memories(session_id)
    
    return {
        "session_id": session_id,
        "memories": [
            {
                "type": m.memory_type,
                "content": m.content,
                "tags": m.tags,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None
            }
            for m in memories
        ]
    }


# ==================== RAG Search Endpoint ====================

class RAGSearchRequest(BaseModel):
    query: str
    domain: str
    n_results: int = 5


@app.post("/api/rag-search")
async def rag_search(request: RAGSearchRequest):
    """Search RAG knowledge base."""
    rag = get_rag_service()
    results = await rag.search(
        query=request.query,
        domain=request.domain,
        n_results=request.n_results
    )
    
    return {
        "query": request.query,
        "domain": request.domain,
        "results": [
            {
                "content": r.content,
                "source": r.source,
                "relevance": r.relevance_score
            }
            for r in results
        ]
    }


# ==================== Direct Chat (Normal Mode) ====================

class DirectChatRequest(BaseModel):
    query: str
    domain: Optional[str] = None  # Optional - will auto-detect if not provided


@app.post("/api/chat/direct")
async def direct_chat(request: DirectChatRequest):
    """
    Direct chat endpoint for normal chatbot conversations.
    
    Features:
    - Auto-detects domain from query if not provided
    - Works as a normal chatbot for general questions
    - Generates structured content only when explicitly requested
    """
    from services.direct_chat import get_direct_chat_service
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    direct_service = get_direct_chat_service()
    result = await direct_service.generate_full(
        query=request.query,
        domain=request.domain  # Can be None for auto-detection
    )
    
    return {
        "mode": "direct",
        "domain": result["detected_domain"],
        "query": request.query,
        "response": result["response"],
        "is_storyboard": result["is_storyboard"],
        "timestamp": datetime.utcnow().isoformat()
    }


@app.websocket("/ws/direct/{session_id}")
async def websocket_direct_chat(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming direct chat responses.
    Supports auto-detection of domain from query.
    """
    from services.direct_chat import get_direct_chat_service
    
    await websocket.accept()
    print(f"[DIRECT_WS] Connection accepted for session {session_id}")
    
    try:
        data = await websocket.receive_json()
        domain = data.get("domain")  # Optional - None for auto-detection
        query = data.get("query", "")
        force_web_search = data.get("force_web_search", False)  # Manual web search trigger
        
        print(f"[DIRECT_WS] Received query: '{query[:50]}...' domain: {domain}, force_web_search: {force_web_search}")
        
        if not query:
            await websocket.send_json({"type": "error", "content": "Query is required"})
            await websocket.close()
            return
        
        direct_service = get_direct_chat_service()
        
        # Auto-detect domain for start message
        detected_domain = direct_service.detect_domain(query) if not domain else domain
        is_storyboard = direct_service.is_storyboard_request(query)
        
        print(f"[DIRECT_WS] Detected domain: {detected_domain}, is_storyboard: {is_storyboard}")
        
        # Check if web search should be used (either auto-detected or manually triggered)
        sources = []
        web_context = ""
        should_search = not is_storyboard and (force_web_search or direct_service.should_use_web_search(query))
        
        # If web search will be used, send status immediately for instant feedback
        if should_search:
            print(f"[DIRECT_WS] Web search triggered for query")
            await websocket.send_json({
                "type": "status",
                "status": "searching",
                "content": "🔍 Searching the web for current information...",
                "has_sources": False
            })
        
        # Send initial start message
        await websocket.send_json({
            "type": "start",
            "mode": "direct",
            "domain": detected_domain,
            "is_storyboard": is_storyboard,
            "has_sources": should_search,
            "content": f"Processing your {'storyboard request' if is_storyboard else 'question'}..."
        })
        
        if should_search:
            try:
                from services.web_search_service import web_search
                sources = web_search(query, top_k=5)
                if sources and len(sources) > 0:
                    web_context = "\n".join(
                        f"- {s.get('title', 'No title')}: {s.get('snippet', 'No snippet')}" 
                        for s in sources if s
                    )
                    print(f"[DIRECT_WS] Found {len(sources)} web search results")
                    # Notify frontend that search completed
                    await websocket.send_json({
                        "type": "status",
                        "status": "search_complete",
                        "content": f"✅ Found {len(sources)} relevant sources. Generating answer with citations...",
                        "has_sources": True,
                        "source_count": len(sources)
                    })
                else:
                    sources = []  # Ensure sources is an empty list, not None
                    web_context = ""
                    await websocket.send_json({
                        "type": "status",
                        "status": "search_complete",
                        "content": "No additional sources found. Generating answer...",
                        "has_sources": False
                    })
            except Exception as e:
                error_msg = str(e)
                print(f"[DIRECT_WS] Web search error: {error_msg}")
                
                # Check if it's an authentication error
                if "403" in error_msg or "Unauthorized" in error_msg:
                    error_message = "Web search API key is invalid or missing. Please configure SERPER_API_KEY."
                else:
                    error_message = "Web search unavailable. Generating answer from knowledge base..."
                
                sources = []
                web_context = ""
                should_search = False  # Disable enhanced prompt since search failed
                
                await websocket.send_json({
                    "type": "status",
                    "status": "search_error",
                    "content": error_message,
                    "has_sources": False
                })
        
        full_response = ""
        chunk_count = 0
        
        try:
            # Only use enhanced prompt with citations if we actually have sources
            # If web search failed or returned no results, use normal prompt
            if should_search and sources and len(sources) > 0 and web_context:
                # Build prompt with web context for streaming
                detected_domain = domain if domain and domain != "auto" else direct_service.detect_domain(query)
                mode = "storyboard" if is_storyboard else "chat"
                system_prompt = direct_service.STORYBOARD_SYSTEM_PROMPT if mode == "storyboard" else direct_service.SYSTEM_PROMPT
                
                base_prompt = direct_service.build_prompt(query, detected_domain, mode)
                
                # Format sources with numbers for citation
                sources_list = "\n".join(
                    f"[{i+1}] {s.get('title', 'No title')}: {s.get('snippet', 'No snippet')}"
                    for i, s in enumerate(sources) if s
                )
                
                enhanced_prompt = f"""Use the following web search results to answer the user's question. You MUST cite sources inline using [1], [2], [3], etc. to reference the numbered sources below.

WEB SEARCH RESULTS:
{sources_list}

CRITICAL INSTRUCTIONS:
- You MUST cite sources inline by placing citation numbers like [1] or [2] immediately after sentences or facts that come from the sources
- Cite multiple sources like [1][2] if information comes from multiple sources
- If you use information from the web search results, you MUST cite them - do not omit citations
- Write naturally and conversationally, but always include citations when using information from sources
- Citations should appear right after the relevant information, like this: "Coffee was invented in Ethiopia [1]."
- ONLY use citation numbers [1] through [{len(sources)}] - these are the only valid citations
- Do NOT write "[Error: list index out of range]" or any error messages
- Do NOT use citation numbers that don't exist (e.g., if there are 3 sources, do not use [4] or higher)
- If you're not using information from the sources, do not add citations

---
User question:
{base_prompt}
"""
                
                # Stream with enhanced prompt
                error_detected = False
                async for chunk in direct_service.llm.generate_stream(
                    prompt=enhanced_prompt,
                    system_prompt=system_prompt,
                    temperature=0.7
                ):
                    # Detect error chunks from LLM
                    if chunk.strip().startswith("[Error:") or chunk.strip().startswith("Error:"):
                        error_detected = True
                        error_message = chunk.strip().replace("[Error:", "").replace("]", "").strip()
                        # Send error message and break
                        await websocket.send_json({
                            "type": "error",
                            "content": error_message or "Request failed. Please try again."
                        })
                        break
                    
                    full_response += chunk
                    chunk_count += 1
                    await websocket.send_json({"type": "chunk", "content": chunk})
                
                # If error was detected, don't send complete message
                if error_detected:
                    return
            else:
                # Normal streaming without web search
                error_detected = False
                async for chunk in direct_service.generate(query=query, domain=domain, stream=True):
                    # Detect error chunks from LLM (e.g., "[Error: Request timed out...]")
                    if chunk.strip().startswith("[Error:") or chunk.strip().startswith("Error:"):
                        error_detected = True
                        error_message = chunk.strip().replace("[Error:", "").replace("]", "").strip()
                        # Send error message and break
                        await websocket.send_json({
                            "type": "error",
                            "content": error_message or "Request failed. Please try again."
                        })
                        break
                    
                    full_response += chunk
                    chunk_count += 1
                    await websocket.send_json({"type": "chunk", "content": chunk})
                
                # If error was detected, don't send complete message
                if error_detected:
                    return
        except WebSocketDisconnect:
            # Client disconnected during streaming - graceful exit (normal scenario)
            # This happens when user closes tab, navigates away, or connection drops
            print(f"[DIRECT_WS] Client disconnected gracefully during streaming: {session_id}")
            return
        except Exception as send_error:
            # Check for other disconnection-related exceptions
            error_name = type(send_error).__name__
            error_str = str(send_error)
            if ("ClientDisconnected" in error_name or 
                "ConnectionClosed" in error_name or 
                "ConnectionClosed" in error_str or
                "disconnected" in error_str.lower()):
                # This is a normal disconnection (user closed tab/navigated away) - not an error
                print(f"[DIRECT_WS] Client disconnected gracefully during streaming: {session_id}")
                return
            # Send error to client before re-raising
            try:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Server error: {str(send_error)[:200]}"
                })
            except:
                pass
            # Re-raise if it's a different error
            raise send_error
        
        print(f"[DIRECT_WS] Generated {chunk_count} chunks, total length: {len(full_response)}")
        print(f"[DIRECT_WS] Sending sources: {len(sources) if sources else 0} sources")
        
        # Always send sources if web search was attempted (even if empty or error)
        # This allows frontend to show sources panel even when manual search was triggered
        final_sources = sources if sources else []
        
        await websocket.send_json({
            "type": "complete", 
            "content": full_response,
            "domain": detected_domain,
            "is_storyboard": is_storyboard,
            "sources": final_sources,
            "web_search_used": should_search
        })
        
    except WebSocketDisconnect:
        print(f"[DIRECT_WS] Disconnected: {session_id}")
    except Exception as e:
        print(f"[DIRECT_WS] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


# ==================== Multi-Agent WebSocket ====================

@app.post("/api/agent/run", response_model=RunAgentResponse)
async def run_agent(request: RunAgentRequest):
    """
    Start the agent pipeline for multi-agent generation.
    Domain is optional - will auto-detect from query if not provided.
    """
    from services.direct_chat import get_direct_chat_service
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Auto-detect domain if not provided
    effective_domain = request.domain
    if not effective_domain or effective_domain == "auto":
        direct_service = get_direct_chat_service()
        effective_domain = direct_service.detect_domain(request.query)
    
    mongodb = await get_mongodb_service()
    session = await mongodb.create_session(
        domain=effective_domain,
        query=request.query
    )
    
    return RunAgentResponse(
        session_id=session.session_id,
        status="created",
        message=f"Session created. Connect to WebSocket at /ws/{session.session_id}",
        detected_domain=effective_domain
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time agent streaming."""
    await websocket.accept()
    
    mongodb = await get_mongodb_service()
    session = await mongodb.get_session(session_id)
    
    if not session:
        await websocket.send_json({
            "agent": "system",
            "event": "error",
            "content": "Session not found",
            "timestamp": datetime.utcnow().isoformat()
        })
        await websocket.close()
        return
    
    active_connections[session_id] = websocket
    
    try:
        await websocket.send_json({
            "agent": "system",
            "event": "connected",
            "content": f"Connected to session {session_id}",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=settings.ws_heartbeat_interval
                )
                
                if data.get("command") == "start":
                    task = asyncio.create_task(
                        run_agent_pipeline_ws(
                            session_id=session_id,
                            domain=session.domain,
                            query=session.query,
                            websocket=websocket
                        )
                    )
                    running_tasks[session_id] = task
                    await task
                    break
                    
                elif data.get("command") == "ping":
                    await websocket.send_json({
                        "agent": "system",
                        "event": "pong",
                        "content": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "agent": "system",
                    "event": "heartbeat",
                    "content": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "agent": "system",
                "event": "error",
                "content": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
    finally:
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in running_tasks:
            running_tasks[session_id].cancel()
            del running_tasks[session_id]


async def run_agent_pipeline_ws(
    session_id: str,
    domain: str,
    query: str,
    websocket: WebSocket
) -> None:
    """Run the complete agent pipeline via WebSocket."""
    mongodb = await get_mongodb_service()
    
    context = AgentContext(
        session_id=session_id,
        domain=domain,
        query=query
    )
    
    preact_agent = PreActAgent()
    react_agent = ReActAgent()
    reflect_agent = ReFlectAgent()
    
    try:
        await mongodb.update_session(session_id, {"status": "running"})
        
        # Phase 1: PreAct Planning
        await send_ws_event(websocket, mongodb, session_id, AgentEvent(
            agent=AgentName.PREACT,
            event=AgentEventType.STATUS,
            content="🎯 Starting PreAct planning phase..."
        ))
        
        async for event in preact_agent.run(context):
            await send_ws_event(websocket, mongodb, session_id, event)
        
        # Phase 2: ReAct Generation
        await send_ws_event(websocket, mongodb, session_id, AgentEvent(
            agent=AgentName.REACT,
            event=AgentEventType.STATUS,
            content="⚡ Starting ReAct content generation..."
        ))
        
        async for event in react_agent.run(context):
            await send_ws_event(websocket, mongodb, session_id, event)
        
        # Phase 3: ReFlect Validation
        await send_ws_event(websocket, mongodb, session_id, AgentEvent(
            agent=AgentName.REFLECT,
            event=AgentEventType.STATUS,
            content="🔄 Starting ReFlect validation..."
        ))
        
        async for event in reflect_agent.run(context):
            await send_ws_event(websocket, mongodb, session_id, event)
        
        # Save and complete (only if storyboard was created)
        if context.storyboard:
            await mongodb.save_storyboard(context.storyboard)
        
        await send_ws_event(websocket, mongodb, session_id, AgentEvent(
            agent=AgentName.SYSTEM,
            event=AgentEventType.COMPLETE,
            content="✅ Generation complete!",
            metadata={
                "storyboard": context.storyboard.model_dump() if context.storyboard else None,
                "final_output": context.metadata.get("reflect_output") or context.metadata.get("react_output", "")
            }
        ))
        
        await mongodb.update_session(session_id, {"status": "complete"})
        
    except Exception as e:
        await send_ws_event(websocket, mongodb, session_id, AgentEvent(
            agent=AgentName.SYSTEM,
            event=AgentEventType.ERROR,
            content=f"❌ Error: {str(e)}"
        ))
        await mongodb.update_session(session_id, {"status": "error"})


async def send_ws_event(
    websocket: WebSocket,
    mongodb,
    session_id: str,
    event: AgentEvent
) -> None:
    """Send event via WebSocket and store in MongoDB."""
    event_data = {
        "agent": event.agent.value if hasattr(event.agent, 'value') else str(event.agent),
        "event": event.event.value if hasattr(event.event, 'value') else str(event.event),
        "content": event.content,
        "metadata": event.metadata,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        await websocket.send_json(event_data)
    except Exception as e:
        print(f"WebSocket send error: {e}")
    
    # Store in MongoDB
    try:
        await mongodb.add_agent_event(
            session_id=session_id,
            event=event
        )
    except Exception as e:
        print(f"MongoDB storage error: {e}")


# ==================== Session Endpoints ====================

@app.get("/api/sessions")
async def list_sessions(limit: int = 20, skip: int = 0):
    """List recent sessions."""
    mongodb = await get_mongodb_service()
    sessions = await mongodb.list_sessions(limit=limit, skip=skip)
    return {"sessions": [s.model_dump() for s in sessions]}


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    mongodb = await get_mongodb_service()
    session = await mongodb.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@app.get("/api/storyboard/{session_id}")
async def get_storyboard(session_id: str):
    """Get the storyboard for a session."""
    mongodb = await get_mongodb_service()
    storyboard = await mongodb.get_session_storyboard(session_id)
    if not storyboard:
        raise HTTPException(status_code=404, detail="Storyboard not found")
    return storyboard.model_dump()


@app.get("/api/history/{session_id}")
async def get_chat_history(session_id: str, limit: Optional[int] = None):
    """Get chat history for a session."""
    mongodb = await get_mongodb_service()
    history = await mongodb.get_chat_history(session_id, limit=limit)
    return {"history": [h.model_dump() for h in history]}
