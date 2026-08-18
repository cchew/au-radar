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


def plot_guidance_to_reach_gap(chat_results, agent_results, output_path: str) -> None:
    chat_by_id = {r.service_id: r.mean_total for r in chat_results}
    agent_by_id = {r.task_id: r.mean_total for r in agent_results}
    common_ids = sorted(set(chat_by_id) & set(agent_by_id))

    fig, ax = plt.subplots(figsize=(8, max(3, len(common_ids) * 0.5)))
    for i, task_id in enumerate(common_ids):
        ax.plot([chat_by_id[task_id], agent_by_id[task_id]], [i, i], color="#999", zorder=1)
    ax.scatter([chat_by_id[i] for i in common_ids], range(len(common_ids)), color="#2a6f6f", label="Guidance", zorder=2)
    ax.scatter([agent_by_id[i] for i in common_ids], range(len(common_ids)), color="#c65911", label="Reach", zorder=2)
    ax.set_yticks(range(len(common_ids)))
    ax.set_yticklabels(common_ids)
    ax.set_xlim(0, 10)
    ax.set_xlabel("Score (0-10)")
    ax.set_title("AU guidance-to-reach gap")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
