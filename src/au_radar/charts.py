import matplotlib
matplotlib.use("Agg")  # no display backend needed for batch chart generation
import matplotlib.pyplot as plt


def plot_service_scores(chat_results, output_path: str) -> None:
    ids = [r.service_id for r in chat_results]
    scores = [r.mean_total for r in chat_results]

    fig, ax = plt.subplots(figsize=(10, max(4, len(ids) * 0.4)))
    ax.barh(ids, scores, color="#2a6f6f")
    ax.set_xlim(0, 10)
    ax.set_xlabel("Chat legibility score (0-10)")
    ax.set_title("AU chat/informational legibility by service")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_guidance_to_reach_gap(
    chat_results, agent_results, output_path: str, task_to_chat_id: dict[str, str],
) -> int:
    """Join chat (guidance) and agent (reach) results via task_to_chat_id, a
    map of AgentTask.id -> AgentTask.chat_service_id. Chat/agent IDs use
    different naming conventions (e.g. "passport" vs "passport_agent") so a
    direct set intersection on the raw IDs is always empty; this map is the
    join key. Returns the number of matched pairs plotted, so callers/tests
    can assert the chart isn't silently empty.
    """
    chat_by_id = {r.service_id: r.mean_total for r in chat_results}
    agent_by_id = {r.task_id: r.mean_total for r in agent_results}

    matched_task_ids = sorted(
        task_id for task_id in agent_by_id
        if task_to_chat_id.get(task_id) in chat_by_id
    )

    fig, ax = plt.subplots(figsize=(8, max(3, len(matched_task_ids) * 0.5)))
    for i, task_id in enumerate(matched_task_ids):
        chat_score = chat_by_id[task_to_chat_id[task_id]]
        agent_score = agent_by_id[task_id]
        ax.plot([chat_score, agent_score], [i, i], color="#999", zorder=1)
    ax.scatter(
        [chat_by_id[task_to_chat_id[t]] for t in matched_task_ids],
        range(len(matched_task_ids)), color="#2a6f6f", label="Guidance", zorder=2,
    )
    ax.scatter(
        [agent_by_id[t] for t in matched_task_ids],
        range(len(matched_task_ids)), color="#c65911", label="Reach", zorder=2,
    )
    ax.set_yticks(range(len(matched_task_ids)))
    ax.set_yticklabels(matched_task_ids)
    ax.set_xlim(0, 10)
    ax.set_xlabel("Score (0-10)")
    ax.set_title("AU guidance-to-reach gap")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return len(matched_task_ids)
