"""Optional LLM backend for intent proposals. Runs through the normal session ledger: every call is a
NEW task => NEW session under a per-project intake work order, so no chat history is shared across
tasks or projects. Only the current project name and the user's text go into the prompt."""
from __future__ import annotations

PREFERRED = ("claude", "codex")  # owner preference: Claude first


def ready_provider(services) -> str | None:
    st = services.provider_statuses()
    return next((p for p in PREFERRED if st.get(p, ("", None))[0] == "ready"), None)


def make_asker(services, provider_id: str, timeout: int = 120):
    async def ask(prompt: str) -> str | None:
        project = services.registry.selected()
        if project is None or services.registry.path_missing(project):
            return None
        st = services.store
        wos = [w for w in st.list_work_orders(project.project_id) if w.kind == "general" and w.title == "Hội thoại"]
        wo = wos[0] if wos else st.create_work_order(project.project_id, "Hội thoại")
        task = st.create_task(wo.work_order_id, "Phân loại yêu cầu của khách")
        asg = st.create_assignment(task.task_id, "client_representative", provider_id)
        _, res = await services.sessions.execute(asg.assignment_id, prompt, project.root_path, timeout=timeout)
        return res.text if res.ok else None

    return ask
