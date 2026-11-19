"""官方 a2a-sdk 1.0.0 客户端：卡片、消息、重试、列表、订阅与取消。"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import a2a_pb2
from google.protobuf.json_format import ParseDict


def message_request(message_id: str, text: str, *, return_immediately: bool):
    return ParseDict(
        {
            "message": {
                "messageId": message_id,
                "role": "ROLE_USER",
                "parts": [{"text": text}],
            },
            "configuration": {"returnImmediately": return_immediately},
        },
        a2a_pb2.SendMessageRequest(),
    )


async def collect_send(client, request) -> list[object]:
    return [response async for response in client.send_message(request)]


def response_task(responses: list[object]):
    for response in responses:
        if response.HasField("task"):
            return response.task
    raise AssertionError("official client received no Task")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    headers = {"Authorization": f"Bearer {arguments.token}", "A2A-Version": "1.0"}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http_client:
        card_response = await http_client.get(arguments.agent_url)
        card_response.raise_for_status()
        card = ParseDict(card_response.json(), a2a_pb2.AgentCard())
        client = ClientFactory(
            ClientConfig(
                streaming=False,
                httpx_client=http_client,
                supported_protocol_bindings=["HTTP+JSON"],
            )
        ).create(card)
        first_responses = await collect_send(
            client, message_request("rv7-official-first", "hello from official SDK", return_immediately=False)
        )
        first_task = response_task(first_responses)
        retry_responses = await collect_send(
            client, message_request("rv7-official-first", "hello from official SDK", return_immediately=False)
        )
        retry_task = response_task(retry_responses)
        assert retry_task.id == first_task.id
        fetched_task = await client.get_task(a2a_pb2.GetTaskRequest(id=first_task.id))
        task_list = await client.list_tasks(a2a_pb2.ListTasksRequest())
        assert any(task.id == first_task.id for task in task_list.tasks)

        second_responses = await collect_send(
            client, message_request("rv7-official-cancel", "cancel this task", return_immediately=True)
        )
        second_task = response_task(second_responses)
        streaming_client = ClientFactory(
            ClientConfig(
                streaming=True,
                httpx_client=http_client,
                supported_protocol_bindings=["HTTP+JSON"],
            )
        ).create(card)
        subscription = streaming_client.subscribe(a2a_pb2.SubscribeToTaskRequest(id=second_task.id))
        initial_subscription = await anext(subscription)
        assert initial_subscription.HasField("task")
        cancelled_task = await client.cancel_task(a2a_pb2.CancelTaskRequest(id=second_task.id))
        remaining_events = [event async for event in subscription]
        fresh_cancelled_task = await client.get_task(a2a_pb2.GetTaskRequest(id=second_task.id))
        summary = {
            "sdk": "a2a-sdk==1.0.0",
            "card_interface": card.supported_interfaces[0].protocol_binding,
            "first_task_id": first_task.id,
            "first_state": a2a_pb2.TaskState.Name(first_task.status.state),
            "retry_same_id": retry_task.id == first_task.id,
            "fresh_state": a2a_pb2.TaskState.Name(fetched_task.status.state),
            "list_count": len(task_list.tasks),
            "subscription_variants": [event.WhichOneof("payload") for event in remaining_events],
            "cancel_task_id": cancelled_task.id,
            "cancel_state": a2a_pb2.TaskState.Name(cancelled_task.status.state),
            "fresh_cancel_state": a2a_pb2.TaskState.Name(fresh_cancelled_task.status.state),
        }
        assert summary["first_state"] == "TASK_STATE_COMPLETED"
        assert summary["cancel_state"] == summary["fresh_cancel_state"] == "TASK_STATE_CANCELED"
        with open(arguments.output, "w", encoding="utf-8") as output_file:
            json.dump(summary, output_file, indent=2)
            output_file.write("\n")
        print(json.dumps(summary, indent=2))
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
