import time
import random
import pandas as pd
import gradio as gr


# =================================================
# Campus Shuttle Crowd Ranking app
# This file is organized into:
# 1. fixed route data,
# 2. input validation,
# 3. merge sort simulation logic,
# 4. HTML rendering helpers,
# 5. UI actions and layout.
# =================================================


# -------------------------------------------------
# Route data
# Keep these stop names in official route order so the
# simulation always works with a fixed West Campus -> Downtown path.
# -------------------------------------------------
FIXED_STOPS = [
    "Queen's West Campus",
    "Union / Pembroke",
    "Union / Willingdon",
    "Union / Victoria",
    "Union / Albert",
    "Union / Alfred",
    "Grant Hall",
    "Queen's / Kingston General Hospital",
    "Stuart / Arch",
    "Bagot / West",
    "Bagot / Earl",
    "Bagot / Johnson",
    "Downtown",
]

DEFAULT_COUNTS = [12, 19, 26, 34, 28, 41, 47, 39, 22, 31, 36, 44, 52]


def default_dataframe():
    # Used for the initial table load and the Reset button.
    # Build the starting table shown in the editable Gradio dataframe.
    return pd.DataFrame(
        {
            "Stop": FIXED_STOPS,
            "Crowd Count": DEFAULT_COUNTS,
        }
    )


# -------------------------------------------------
# Validation / parsing
# Everything here protects the fixed route structure before
# the data is passed into the sorting and animation logic.
# -------------------------------------------------
def parse_input_df(input_df):
    # Reject completely empty input before trying to normalize it.
    if input_df is None or len(input_df) == 0:
        raise ValueError("No stop data found.")

    # Convert Gradio's dataframe-style input into a pandas DataFrame we can validate.
    df = pd.DataFrame(input_df).copy()

    expected_columns = ["Stop", "Crowd Count"]
    if list(df.columns) != expected_columns:
        # Gradio may send slightly different column labels, so we force the internal names
        # we expect before validating the content.
        df.columns = expected_columns

    if len(df) != len(FIXED_STOPS):
        raise ValueError("The stop list was changed. Keep all fixed route stops.")

    stops = []
    for i, expected_stop in enumerate(FIXED_STOPS):
        # Each row must stay in the fixed route order; only the crowd count is editable.
        stop_name = str(df.iloc[i]["Stop"]).strip()
        crowd_raw = df.iloc[i]["Crowd Count"]

        if stop_name != expected_stop:
            raise ValueError(
                "Stop names must stay fixed in route order. Only edit crowd counts."
            )

        try:
            crowd_count = int(crowd_raw)
        except Exception:
            raise ValueError(f"Crowd count for '{expected_stop}' must be an integer.")

        if crowd_count < 0:
            raise ValueError(f"Crowd count for '{expected_stop}' cannot be negative.")

        # Store validated rows in a simple structure used everywhere else in the app.
        stops.append(
            {
                "stop_name": stop_name,
                "crowd_count": crowd_count,
            }
        )

    return stops


# -------------------------------------------------
# Merge Sort with visual states
# These helpers do two jobs at once:
# 1. sort the stops by crowd count,
# 2. capture snapshots so each step can be animated in the UI.
# -------------------------------------------------
def comes_before(left_stop, right_stop, ascending):
    # This comparison helper lets the same merge sort work for both ascending and descending
    # order without duplicating the merge logic.
    if ascending:
        return left_stop["crowd_count"] <= right_stop["crowd_count"]
    return left_stop["crowd_count"] >= right_stop["crowd_count"]


def clone_stops(stops):
    # Make a fresh copy so animation snapshots do not get overwritten by later updates.
    return [
        {"stop_name": stop["stop_name"], "crowd_count": stop["crowd_count"]}
        for stop in stops
    ]


def build_visual_states_for_merge_sort(stops, ascending=True):
    """
    Run merge sort while storing each important comparison/placement step.

    Returns:
    - final_sorted_stops
    - states: a list of snapshots for animation

    Each state contains:
    - current visible ranked list
    - highlighted compared stop names
    - highlighted placed stop names
    - action message
    """
    # 'working' is the live list that gradually changes as merge sort rebuilds each section.
    working = clone_stops(stops)
    states = []

    def record_state(message, compare_names=None, placed_names=None):
        # Every animation frame stores the current list plus which stops should be highlighted.
        states.append(
            {
                "list_state": clone_stops(working),
                "compare_names": compare_names[:] if compare_names else [],
                "placed_names": placed_names[:] if placed_names else [],
                "message": message,
            }
        )

    def merge_sort_range(start, end):
        # A range of size 0 or 1 is already sorted.
        if end - start <= 1:
            return working[start:end]

        mid = (start + end) // 2
        left = merge_sort_range(start, mid)
        right = merge_sort_range(mid, end)

        merged = []
        i = 0
        j = 0

        record_state(
            f"Split route section {start + 1}-{end} into two groups.",
            compare_names=[],
            placed_names=[],
        )

        # Merge the two already-sorted halves back together one choice at a time.
        while i < len(left) and j < len(right):
            left_stop = left[i]
            right_stop = right[j]

            record_state(
                f"Comparing {left_stop['stop_name']} ({left_stop['crowd_count']}) "
                f"with {right_stop['stop_name']} ({right_stop['crowd_count']}).",
                compare_names=[left_stop["stop_name"], right_stop["stop_name"]],
                placed_names=[],
            )

            if comes_before(left_stop, right_stop, ascending):
                merged.append(left_stop)
                record_state(
                    f"Placed {left_stop['stop_name']} into the ranked section.",
                    compare_names=[],
                    placed_names=[left_stop["stop_name"]],
                )
                i += 1
            else:
                merged.append(right_stop)
                record_state(
                    f"Placed {right_stop['stop_name']} into the ranked section.",
                    compare_names=[],
                    placed_names=[right_stop["stop_name"]],
                )
                j += 1

        # Once one side is exhausted, the remaining items from the other side are already in order.
        while i < len(left):
            merged.append(left[i])
            record_state(
                f"Appended remaining stop {left[i]['stop_name']}.",
                compare_names=[],
                placed_names=[left[i]["stop_name"]],
            )
            i += 1

        while j < len(right):
            merged.append(right[j])
            record_state(
                f"Appended remaining stop {right[j]['stop_name']}.",
                compare_names=[],
                placed_names=[right[j]["stop_name"]],
            )
            j += 1

        # Replace just this slice of the live working list so the UI shows the newest ranking progress.
        working[start:end] = merged

        record_state(
            f"Updated ranked section {start + 1}-{end}.",
            compare_names=[],
            placed_names=[stop["stop_name"] for stop in merged],
        )

        return merged

    record_state(
        "Ready to rank stops by crowd count.",
        compare_names=[],
        placed_names=[],
    )

    final_sorted = merge_sort_range(0, len(working))

    record_state(
        "Ranking complete.",
        compare_names=[],
        placed_names=[stop["stop_name"] for stop in final_sorted],
    )

    return final_sorted, states


# -------------------------------------------------
# Rendering
# This section turns Python data into the custom HTML blocks
# shown for the status area and the route ranking boards.
# -------------------------------------------------
def render_stop_board(stops, title, compare_names=None, placed_names=None, ranked=False):
    # These name lists decide which cards get visual emphasis during the animation.
    compare_names = compare_names or []
    placed_names = placed_names or []

    cards = []

    for idx, stop in enumerate(stops, start=1):
        # Choose a CSS class based on the stop's current role in the animation.
        extra_class = "normal-card"
        if stop["stop_name"] in compare_names:
            extra_class = "compare-card"
        elif stop["stop_name"] in placed_names:
            extra_class = "placed-card"
        elif ranked:
            extra_class = "ranked-card"

        cards.append(
            f"""
            <div class="stop-card {extra_class}">
                <div class="stop-rank">#{idx}</div>
                <div class="stop-info">
                    <div class="stop-name">{stop['stop_name']}</div>
                    <div class="stop-sub">Crowd estimate</div>
                </div>
                <div class="stop-count">{stop['crowd_count']}</div>
            </div>
            """
        )

    return f"""
    <div class="board">
        <div class="board-title">{title}</div>
        <div class="board-content">
            {''.join(cards)}
        </div>
    </div>
    """


def make_status_html(order, step_number, total_steps, message):
    # This summary panel gives the user quick context for the current simulation frame.
    mode = "Most Crowded First" if order == "Descending" else "Least Crowded First"
    return f"""
    <div class="status-grid">
        <div class="status-pill">
            <div class="status-label">Route</div>
            <div class="status-value">West Campus → Downtown</div>
        </div>
        <div class="status-pill">
            <div class="status-label">Ranking Mode</div>
            <div class="status-value">{mode}</div>
        </div>
        <div class="status-pill">
            <div class="status-label">Step</div>
            <div class="status-value">{step_number} / {total_steps}</div>
        </div>
        <div class="status-pill">
            <div class="status-label">Current Action</div>
            <div class="status-value">{message}</div>
        </div>
    </div>
    """


def make_dispatch_message(sorted_stops, ascending):
    # The final sorted list is translated into a plain-language recommendation here.
    # Turn the finished ranking into a plain-language recommendation for dispatch.
    if not sorted_stops:
        return "No recommendation available."

    counts = [s["crowd_count"] for s in sorted_stops]

    # Case 1: all equal
    if all(c == counts[0] for c in counts):
        return "All stops have equal crowd levels. Priority dispatch cannot be determined " \
        "based off crowd levels."

    if ascending:
        min_val = min(counts)
        tied = [s for s in sorted_stops if s["crowd_count"] == min_val]

        if len(tied) > 1:
            names = ", ".join([s["stop_name"] for s in tied])
            return f"Multiple least crowded stops: {names} ({min_val})"

        target = tied[0]
        return f"Least crowded stop: {target['stop_name']} ({target['crowd_count']})"

    else:
        max_val = max(counts)
        tied = [s for s in sorted_stops if s["crowd_count"] == max_val]

        if len(tied) > 1:
            names = ", ".join([s["stop_name"] for s in tied])
            return f"Multiple stops with the busiest crowds, send priority dispatches over to : {names} ({max_val})"

        target = tied[0]
        return (
            f"Send the extra shuttle to: {target['stop_name']} "
            f"({target['crowd_count']}) — busiest stop."
        )


def error_outputs(message):
    # I have now given birth to error_outputs, 
    # this will keep the output format consistent even when validation fails,
    # as well as the output shape consistent with the normal simulation outputs.
    error_html = f"""
    <div class="error-box">
        <b>Input Error:</b> {message}
    </div>
    """
    return error_html, "", "", "", ""


SPEED_MAP = {
    "Fast": 0.15,
    "Medium": 0.35,
    "Slow": 0.7
}

# -------------------------------------------------
# Main animation
# This generator is the main app workflow: validate input,
# build sorting states, stream them to Gradio, and log each step.
# -------------------------------------------------


def simulate_ranking(input_df, order, speed):
    # Convert the chosen speed label into a real pause duration.
    speed = SPEED_MAP[speed]
    try:
        stops = parse_input_df(input_df)
    except ValueError as e:
        yield error_outputs(str(e))
        return

    ascending = order == "Ascending"
    final_sorted, states = build_visual_states_for_merge_sort(stops, ascending=ascending)

    original_board = render_stop_board(
        stops,
        "Original Route Board",
        compare_names=[],
        placed_names=[],
        ranked=False,
    )

    log_lines = []

    for idx, state in enumerate(states, start=1):
        # Keep a running text log so the user can review the algorithm's decisions.
        log_lines.append(f"Step {idx}: {state['message']}")

        ranked_board = render_stop_board(
            state["list_state"],
            "Live Ranked Board",
            compare_names=state["compare_names"],
            placed_names=state["placed_names"],
            ranked=True,
        )

        dispatch_message = ""
        if idx == len(states):
            dispatch_message = make_dispatch_message(final_sorted, ascending)

        # Yielding after each recorded state allows Gradio to stream the animation live.
        yield (
            make_status_html(order, idx, len(states), state["message"]),
            original_board,
            ranked_board,
            dispatch_message,
            "\n".join(log_lines),
        )
        time.sleep(speed)

    yield (
        make_status_html(order, len(states), len(states), "Simulation complete."),
        original_board,
        render_stop_board(
            final_sorted,
            "Final Ranked Dispatch Board",
            compare_names=[],
            placed_names=[stop["stop_name"] for stop in final_sorted],
            ranked=True,
        ),
        make_dispatch_message(final_sorted, ascending),
        "\n".join(log_lines),
    )


# -------------------------------------------------
# Button helpers
# These are small utility functions that support the UI controls without
# affecting the actual sorting logic.
# -------------------------------------------------
def randomize_counts():
    # Generate sample crowd values so the user can quickly try different scenarios.
    counts = [random.randint(5, 60) for _ in FIXED_STOPS]
    return pd.DataFrame({"Stop": FIXED_STOPS, "Crowd Count": counts})


def reset_counts():
    # Restore the original dataset used when the app first loads.
    return default_dataframe()


def load_initial_ui():
    # Pre-render the two boards so the interface does not start empty.
    initial_stops = [
        {"stop_name": stop, "crowd_count": count}
        for stop, count in zip(FIXED_STOPS, DEFAULT_COUNTS)
    ]

    return (
        "",
        render_stop_board(initial_stops, "Original Route Board"),
        render_stop_board(initial_stops, "Live Ranked Board", ranked=True),
        "",
        "",
    )


# -------------------------------------------------
# Styling
# All custom CSS for the dashboard appearance lives in one place here
# This keeps things organised since the css can get lengthy imo
# now all layout/design changes can stay separate from the app logic.
# -------------------------------------------------
custom_css = """
.gradio-container {
    max-width: 1250px !important;
    margin: auto !important;
}

body {
    background: #f6f8fb;
}

#hero {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
    border-radius: 20px;
    padding: 28px;
    margin-bottom: 18px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.12);
}

.hero-title {
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 10px;
    color: #ffffff !important;
    line-height: 1.15;
}

.hero-sub {
    font-size: 1.02rem;
    color: #e2e8f0 !important;
    opacity: 1 !important;
    line-height: 1.55;
    max-width: 900px;
}

.panel {
    border: 1px solid #d8dee9 !important;
    border-radius: 18px !important;
    background: white !important;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06) !important;
    padding: 10px !important;
}

.panel h3 {
    font-size: 1.2rem !important;
    font-weight: 800 !important;
    color: #0f172a !important;
    margin-bottom: 8px !important;
}

.panel p,
.panel li,
.panel strong,
.panel div,
.panel span {
    color: #1e293b !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
}

.info-box {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    padding: 14px 16px;
    margin-top: 10px;
}

.info-title {
    font-size: 0.92rem;
    font-weight: 800;
    color: #334155;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
}

.info-text {
    font-size: 0.98rem;
    color: #0f172a;
    line-height: 1.55;
}

.status-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 14px;
}

.status-pill {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 16px;
    padding: 14px;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.status-label {
    font-size: 0.8rem;
    color: #64748b;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 700;
}

.status-value {
    font-size: 0.96rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.35;
}

.board {
    background: white;
    border: 1px solid #d8dee9;
    border-radius: 18px;
    padding: 16px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
    min-height: 100%;
}

.board-title {
    font-size: 0.95rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #475569;
    margin-bottom: 14px;
}

.board-content {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.stop-card {
    display: flex;
    align-items: center;
    gap: 14px;
    border-radius: 16px;
    padding: 12px 14px;
    border: 1px solid #e2e8f0;
    transition: all 0.2s ease-in-out;
}

.normal-card {
    background: #f8fbff;
}

.ranked-card {
    background: #fffaf0;
}

.compare-card {
    background: #fef3c7;
    border-color: #f59e0b;
    box-shadow: 0 0 0 2px rgba(245,158,11,0.16);
}

.placed-card {
    background: #dcfce7;
    border-color: #22c55e;
    box-shadow: 0 0 0 2px rgba(34,197,94,0.16);
}

.stop-rank {
    width: 42px;
    height: 42px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #e2e8f0;
    font-weight: 800;
    color: #0f172a;
    flex-shrink: 0;
}

.stop-info {
    flex: 1;
}

.stop-name {
    font-weight: 700;
    color: #0f172a;
    line-height: 1.25;
}

.stop-sub {
    font-size: 0.82rem;
    color: #64748b;
}

.stop-count {
    background: #0f172a !important;
    color: white !important;
    border-radius: 12px;
    padding: 8px 12px;
    font-weight: 800;
    min-width: 44px;
    text-align: center;
}

.dispatch-box textarea {
    font-weight: 700 !important;
    color: #0f172a !important;
}

.steps-box textarea {
    font-family: Consolas, monospace !important;
    line-height: 1.45 !important;
    color: #0f172a !important;
}

.error-box {
    background: #fff1f2;
    color: #9f1239;
    border: 1px solid #fecdd3;
    border-radius: 16px;
    padding: 14px;
    font-weight: 600;
}

button {
    border-radius: 14px !important;
    font-weight: 700 !important;
}

table th {
    white-space: normal !important;
    text-align: left !important;
    overflow-wrap: anywhere;
    padding-right: 16px !important;
    color: #0f172a !important;
    font-weight: 800 !important;
}

table td {
    color: #0f172a !important;
}

@media (max-width: 900px) {
    .status-grid {
        grid-template-columns: 1fr 1fr;
    }
}

@media (max-width: 650px) {
    .status-grid {
        grid-template-columns: 1fr;
    }
}
"""


# -------------------------------------------------
# UI
# This is the final Gradio layout:
# Here I am creating components, placing them on the page, and connecting buttons
# to the logic defined in the sections above.
# -------------------------------------------------
with gr.Blocks(css=custom_css, title="Campus Shuttle Crowd Ranking") as demo:
    # The rest of this block defines the full Gradio layout and wires UI components to functions.
    gr.HTML(
        """
        <div id="hero">
            <div class="hero-title">🚌 Campus Shuttle Crowd Ranking</div>
            <div class="hero-sub">
                Rank the real West Campus → Downtown stop sequence by crowd count using
                Merge Sort. Watch the ranked stop list reorder live as the algorithm
                compares and merges route sections.
            </div>
        </div>
        """
    )

    gr.Markdown("###  Kingston Transit Line 1 ")
    gr.Image(
        value="screenshotsngifs/Line1.png",
        show_label=False,
        interactive=True,
        container=True,
        height=360,
    )

    with gr.Row():
        with gr.Column(scale=6):
            with gr.Group(elem_classes="panel"):
                gr.Markdown("### Route Stop Crowd Input")
                gr.Markdown("Edit the crowd counts below for each stop on the fixed route.")

                input_df = gr.Dataframe(
                    # The stop names stay fixed, but users can edit the crowd counts in this table.
                    value=default_dataframe(),
                    headers=["Stop", "Crowd\nCount(#)"],
                    datatype=["str", "number"],
                    row_count=(len(FIXED_STOPS), "fixed"),
                    col_count=(2, "fixed"),
                    interactive=True,
                    wrap=True,
                    label="Live Stop Feed",
                )

                order = gr.Dropdown(
                    choices=["Descending", "Ascending"],
                    value="Descending",
                    label="Ranking Mode",
                )

                speed = gr.Dropdown(
                    choices = ["Medium", "Slow", "Fast"],
                    value = "Medium",
                    label="Simulation Speed"
                   
                )

                with gr.Row():
                    run_button = gr.Button("Run Live Simulation", variant="primary")
                    random_button = gr.Button("Randomize Counts")
                    reset_button = gr.Button("Reset Counts")

        with gr.Column(scale=4):
            with gr.Group(elem_classes="panel"):
                gr.Markdown("### Control Center")

                gr.HTML(
                    """
                    <div class="info-box">
                        <div class="info-title">What this app does</div>
                        <div class="info-text">
                            This app ranks shuttle stops by <b>crowd count</b> using
                            <b>Merge Sort</b>. It shows the original route order,
                            the live ranked order, and the final dispatch ranking.
                        </div>
                    </div>
                    """
                )

                gr.HTML(
                    """
                    <div class="info-box">
                        <div class="info-title">How to use it</div>
                        <div class="info-text">
                            1. Edit only the <b>Crowd Count</b> column.<br>
                            2. Choose <b>Descending</b> to find the busiest stop first,
                            or <b>Ascending</b> to find the least crowded stop first.<br>
                            3. Adjust <b>Animation Speed</b> if you want the simulation
                            to run faster or slower.<br>
                            4. Click <b>Run Live Simulation</b> to watch the ranked list
                            reorder in real time.
                        </div>
                    </div>
                    """
                )

                gr.HTML(
                    """
                    <div class="info-box">
                        <div class="info-title">Input rules</div>
                        <div class="info-text">
                            • Do <b>not</b> change stop names.<br>
                            • Crowd counts must be <b>whole numbers</b>.<br>
                            • Crowd counts cannot be <b>negative</b>.
                        </div>
                    </div>
                    """
                )

    status_output = gr.HTML()

    with gr.Row(equal_height=True):
        original_board_output = gr.HTML()
        ranked_board_output = gr.HTML()

    dispatch_output = gr.Textbox(
        label="Dispatch Recommendation",
        lines=2,
        elem_classes="dispatch-box",
    )

    steps_output = gr.Textbox(
        label="Simulation Log",
        lines=12,
        elem_classes="steps-box",
    )

    # Clicking Run starts the generator, which streams each merge-sort step to the UI.
    run_button.click(
        fn=simulate_ranking,
        inputs=[input_df, order, speed],
        outputs=[
            status_output,
            original_board_output,
            ranked_board_output,
            dispatch_output,
            steps_output,
        ],
    )

    # Helper buttons only update the editable input table.
    random_button.click(
        fn=randomize_counts,
        outputs=[input_df],
    )

    reset_button.click(
        fn=reset_counts,
        outputs=[input_df],
    )

    demo.load(
        fn=load_initial_ui,
        outputs=[
            status_output,
            original_board_output,
            ranked_board_output,
            dispatch_output,
            steps_output,
        ],
    )

if __name__ == "__main__":
    #With this I summon main. Letting allowed_paths to then let Gradio serve local assets
    #  like the route image from this project folder.
    demo.launch(allowed_paths=["."])
