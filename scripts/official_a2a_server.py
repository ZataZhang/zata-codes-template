"""官方 a2a-sdk 1.0.0 独立 HTTP+JSON 服务端，供 rv-7 出站互通验证。"""

from __future__ import annotations

import argparse

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandlerV2
from a2a.server.routes import create_agent_card_routes, create_rest_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import a2a_pb2
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google.protobuf.json_format import ParseDict


class OfficialEchoExecutor(AgentExecutor):
    """只产生固定文本，未知输入不伪装其他协议能力。"""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        initial_task = a2a_pb2.Task(
            id=context.task_id,
            context_id=context.context_id,
            status=a2a_pb2.TaskStatus(state=a2a_pb2.TASK_STATE_SUBMITTED),
        )
        await event_queue.enqueue_event(initial_task)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()
        await updater.start_work()
        await updater.add_artifact(
            [a2a_pb2.Part(text=f"official-remote: {user_text}")],
            name="response",
            last_chunk=True,
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def build_app(port: int) -> FastAPI:
    endpoint_url = f"http://127.0.0.1:{port}/a2a/agents/remote"
    card = ParseDict(
        {
            "name": "Official RV remote",
            "description": "Independent official SDK validation peer",
            "version": "1.0.0",
            "supportedInterfaces": [
                {
                    "url": endpoint_url,
                    "protocolBinding": "HTTP+JSON",
                    "protocolVersion": "1.0",
                }
            ],
            "capabilities": {"streaming": True, "pushNotifications": False},
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": [
                {
                    "id": "echo",
                    "name": "Echo",
                    "description": "Return a deterministic text artifact",
                    "tags": ["echo"],
                    "examples": ["hello"],
                }
            ],
            "securitySchemes": {
                "bearerAuth": {"httpAuthSecurityScheme": {"scheme": "bearer"}}
            },
            "securityRequirements": [{"schemes": {"bearerAuth": {"list": []}}}],
        },
        a2a_pb2.AgentCard(),
    )
    handler = DefaultRequestHandlerV2(
        OfficialEchoExecutor(),
        InMemoryTaskStore(),
        card,
    )
    app = FastAPI()

    @app.middleware("http")
    async def authorize_and_count(request: Request, call_next):
        print(f"OFFICIAL_REQUEST {request.method} {request.url.path}", flush=True)
        if request.headers.get("Authorization") != "Bearer rv58-peer-a-token":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    @app.get("/redirect-card")
    async def redirect_card():
        return RedirectResponse(url=endpoint_url, status_code=307)

    @app.get("/redirect-target")
    async def redirect_target():
        return JSONResponse({"unexpected": "redirect must not be followed"})

    for route in create_agent_card_routes(card, card_url="/a2a/agents/remote"):
        app.router.routes.append(route)
    for route in create_rest_routes(handler, path_prefix="/a2a/agents/remote"):
        app.router.routes.append(route)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    uvicorn.run(build_app(arguments.port), host="127.0.0.1", port=arguments.port, log_level="warning")


if __name__ == "__main__":
    main()
