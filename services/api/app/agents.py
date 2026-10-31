from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    purpose: str
    keywords: tuple[str, ...]
    workflow: tuple[str, ...]
    permission: str = "analysis_and_drafts"


AGENTS = (
    Agent(
        "orchestrator",
        "Personal AI Employee",
        "Understand requests, select a specialist, plan work, track progress, and review outcomes.",
        ("coordinate", "orchestrate", "help me", "general"),
        ("Clarify the requested outcome", "Select the right specialist", "Plan bounded steps", "Review the result"),
    ),
    Agent(
        "engineering",
        "Engineering",
        "Electrical and electronics engineering, embedded systems, sensors, PCB design, and calculations.",
        ("circuit", "electronics", "electrical", "pcb", "sensor", "voltage", "current", "embedded"),
        ("Identify specifications and constraints", "Check calculations and safety assumptions", "Prepare a design or diagnostic plan", "List verification steps"),
    ),
    Agent(
        "software_development",
        "Software Development",
        "Repository analysis, coding, testing, debugging, documentation, and deployment assistance.",
        ("code", "software", "repository", "bug", "debug", "api", "web app", "typescript", "python", "git"),
        ("Inspect the relevant code and requirements", "Break the change into small edits", "Implement and verify the change", "Summarize files and remaining risks"),
    ),
    Agent(
        "robotics",
        "Robotics and Physical AI",
        "Robotics, ROS, simulation, computer vision, autonomous systems, and edge AI.",
        ("robot", "robotics", "ros", "computer vision", "edge ai", "actuator", "physical ai"),
        ("Identify the platform and safety envelope", "Prefer simulation or read-only diagnostics first", "Plan the integration", "Require human approval for physical control"),
    ),
    Agent(
        "agriculture",
        "Agriculture",
        "Greenhouse monitoring, agricultural research, IoT, sensors, irrigation, and automation.",
        ("agriculture", "farm", "crop", "greenhouse", "irrigation", "soil", "livestock", "agro"),
        ("Identify crop, site, and measurement context", "Separate observed data from assumptions", "Prepare a monitoring or intervention plan", "Flag environmental and equipment risks"),
    ),
    Agent(
        "business_operations",
        "Business Operations",
        "Business planning, CRM, customer communication, proposals, quotations, sales, and follow-ups.",
        ("business", "customer", "crm", "quotation", "proposal", "sales", "invoice", "follow-up", "follow up"),
        ("Identify the business outcome and audience", "Gather approved project and customer facts", "Draft the requested workflow or communication", "Leave sending and financial actions for approval"),
    ),
    Agent(
        "marketing",
        "Marketing",
        "Social media, campaigns, market research, content planning, and marketing analytics.",
        ("marketing", "social media", "campaign", "content calendar", "brand", "advertisement", "analytics"),
        ("Identify audience and objective", "Draft channel-specific content", "Check claims and brand constraints", "Leave publishing for approval"),
    ),
    Agent(
        "research",
        "Research",
        "Compare sources, technical documents, scientific literature, and prepare structured reports.",
        ("research", "paper", "literature", "compare sources", "study", "evidence", "findings"),
        ("Define the research question", "Gather and compare sources", "Separate evidence from interpretation", "Report citations and uncertainty"),
    ),
    Agent(
        "project_manager",
        "Project Manager",
        "Projects, milestones, task scheduling, progress reports, deadlines, and reminders.",
        ("project", "milestone", "task", "deadline", "schedule", "roadmap", "progress", "plan"),
        ("Define scope and acceptance criteria", "Break work into trackable steps", "Identify dependencies and blockers", "Set a review point"),
    ),
    Agent(
        "system_administration",
        "System Administration",
        "Windows, Linux, VPS, containers, monitoring, deployment diagnostics, backups, and infrastructure.",
        ("windows", "linux", "server", "vps", "docker", "deploy", "backup", "firewall", "system"),
        ("Inspect the target and current state", "Prefer read-only diagnostics", "Prepare a reversible change plan", "Require approval for system or production changes"),
    ),
)

BY_ID = {agent.id: agent for agent in AGENTS}


def list_agents() -> list[dict]:
    return [
        {
            **asdict(agent),
            "keywords": list(agent.keywords),
            "workflow": list(agent.workflow),
            "tools": [],
        }
        for agent in AGENTS
    ]


def route_intent(request: str) -> dict:
    text = " " + " ".join(request.lower().split()) + " "
    scores = {
        agent.id: sum(1 for word in agent.keywords if " " + word + " " in text)
        for agent in AGENTS
        if agent.id != "orchestrator"
    }
    agent_id = max(scores, key=scores.get) if scores and max(scores.values()) else "orchestrator"
    score = scores.get(agent_id, 0)
    return {
        "agent": BY_ID[agent_id].id,
        "name": BY_ID[agent_id].name,
        "confidence": round(min(0.95, 0.45 + score * 0.12), 2) if score else 0.35,
        "method": "local_keyword_router",
    }


def make_plan(agent_id: str, request: str) -> list[dict]:
    agent = BY_ID.get(agent_id, BY_ID["orchestrator"])
    return [
        {
            "id": str(index + 1),
            "title": title,
            "status": "pending",
            "requires_approval": False,
        }
        for index, title in enumerate(agent.workflow)
    ]