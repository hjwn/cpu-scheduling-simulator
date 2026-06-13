from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, ttk


@dataclass(frozen=True)
class Process:
    name: str
    arrival: int
    burst: int
    priority: int


@dataclass(frozen=True)
class GanttSegment:
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class ProcessResult:
    name: str
    arrival: int
    burst: int
    priority: int
    completion: int
    turnaround: int
    waiting: int


@dataclass(frozen=True)
class AnimationSnapshot:
    time: int
    running: str
    ready_queue: list[str]
    remaining: dict[str, int]
    messages: list[str]


@dataclass(frozen=True)
class ScheduleResult:
    timeline: list[str]
    gantt_segments: list[GanttSegment]
    process_results: list[ProcessResult]
    average_waiting: float
    average_turnaround: float
    throughput: float
    event_logs: list[AnimationSnapshot]


def build_arrival_map(processes: list[Process]) -> dict[int, list[Process]]:
    order_map = {process.name: index for index, process in enumerate(processes)}
    arrival_map: dict[int, list[Process]] = defaultdict(list)
    for process in sorted(processes, key=lambda item: (item.arrival, order_map[item.name])):
        arrival_map[process.arrival].append(process)
    return arrival_map


def build_gantt_segments(timeline: list[str]) -> list[GanttSegment]:
    if not timeline:
        return []

    segments: list[GanttSegment] = []
    current_name = timeline[0]
    start_time = 0

    for current_time, name in enumerate(timeline[1:], start=1):
        if name != current_name:
            segments.append(GanttSegment(current_name, start_time, current_time))
            current_name = name
            start_time = current_time

    segments.append(GanttSegment(current_name, start_time, len(timeline)))
    return segments


def finalize_schedule(
    processes: list[Process],
    timeline: list[str],
    completion_times: dict[str, int],
    snapshots: list[AnimationSnapshot],
) -> ScheduleResult:
    if not processes:
        return ScheduleResult([], [], [], 0.0, 0.0, 0.0, [])

    process_results: list[ProcessResult] = []
    total_waiting = 0
    total_turnaround = 0

    for process in processes:
        completion = completion_times[process.name]
        turnaround = completion - process.arrival
        waiting = turnaround - process.burst
        total_waiting += waiting
        total_turnaround += turnaround
        process_results.append(
            ProcessResult(
                name=process.name,
                arrival=process.arrival,
                burst=process.burst,
                priority=process.priority,
                completion=completion,
                turnaround=turnaround,
                waiting=waiting,
            )
        )

    average_waiting = total_waiting / len(processes)
    average_turnaround = total_turnaround / len(processes)
    throughput = len(processes) / len(timeline) if timeline else 0.0

    return ScheduleResult(
        timeline=timeline,
        gantt_segments=build_gantt_segments(timeline),
        process_results=process_results,
        average_waiting=average_waiting,
        average_turnaround=average_turnaround,
        throughput=throughput,
        event_logs=snapshots,
    )


def make_snapshot(
    time: int,
    running: str,
    ready_queue: list[str],
    remaining: dict[str, int],
    messages: list[str],
    ordered_names: list[str],
) -> AnimationSnapshot:
    return AnimationSnapshot(
        time=time,
        running=running,
        ready_queue=list(ready_queue),
        remaining={name: remaining[name] for name in ordered_names},
        messages=messages,
    )


def append_dispatch_message(
    messages: list[str],
    time: int,
    next_name: str,
    previous_running: str,
    remaining: dict[str, int],
    process_map: dict[str, Process],
) -> None:
    if previous_running == next_name:
        return

    action = "실행 재개" if remaining[next_name] < process_map[next_name].burst else "실행 시작"
    messages.append(f"Time {time}: {next_name} {action}")


def schedule_fcfs(processes: list[Process], quantum: int | None = None) -> ScheduleResult:
    if not processes:
        return finalize_schedule([], [], {}, [])

    ordered_names = [process.name for process in processes]
    arrival_map = build_arrival_map(processes)
    process_map = {process.name: process for process in processes}
    remaining = {process.name: process.burst for process in processes}
    completion_times: dict[str, int] = {}
    ready_queue: deque[str] = deque()
    timeline: list[str] = []
    snapshots: list[AnimationSnapshot] = []
    current_name: str | None = None
    completed = 0
    time = 0
    previous_running = "IDLE"

    while completed < len(processes):
        messages: list[str] = []
        for process in arrival_map.get(time, []):
            ready_queue.append(process.name)
            messages.append(f"Time {time}: {process.name} 도착")

        if current_name is None and ready_queue:
            current_name = ready_queue.popleft()
            append_dispatch_message(
                messages, time, current_name, previous_running, remaining, process_map
            )

        running = current_name if current_name is not None else "IDLE"
        ready_snapshot = list(ready_queue)
        messages.append(
            f"Time {time}~{time + 1}: {'IDLE' if running == 'IDLE' else f'{running} 실행'}"
        )
        snapshots.append(
            make_snapshot(time, running, ready_snapshot, remaining, messages, ordered_names)
        )

        if current_name is None:
            timeline.append("IDLE")
            previous_running = "IDLE"
            time += 1
            continue

        timeline.append(current_name)
        remaining[current_name] -= 1

        if remaining[current_name] == 0:
            completion_times[current_name] = time + 1
            messages.append(f"Time {time + 1}: {current_name} 완료")
            current_name = None
            completed += 1

        previous_running = running
        time += 1

    return finalize_schedule(processes, timeline, completion_times, snapshots)


def schedule_sjf(processes: list[Process], quantum: int | None = None) -> ScheduleResult:
    if not processes:
        return finalize_schedule([], [], {}, [])

    order_map = {process.name: index for index, process in enumerate(processes)}
    ordered_names = [process.name for process in processes]
    arrival_map = build_arrival_map(processes)
    process_map = {process.name: process for process in processes}
    remaining = {process.name: process.burst for process in processes}
    completion_times: dict[str, int] = {}
    waiting_names: list[str] = []
    timeline: list[str] = []
    snapshots: list[AnimationSnapshot] = []
    current_name: str | None = None
    completed = 0
    time = 0
    previous_running = "IDLE"

    while completed < len(processes):
        messages: list[str] = []
        for process in arrival_map.get(time, []):
            waiting_names.append(process.name)
            messages.append(f"Time {time}: {process.name} 도착")

        if current_name is None and waiting_names:
            waiting_names.sort(
                key=lambda name: (
                    process_map[name].burst,
                    process_map[name].arrival,
                    order_map[name],
                )
            )
            current_name = waiting_names.pop(0)
            append_dispatch_message(
                messages, time, current_name, previous_running, remaining, process_map
            )

        if current_name is not None:
            waiting_names.sort(
                key=lambda name: (
                    process_map[name].burst,
                    process_map[name].arrival,
                    order_map[name],
                )
            )

        running = current_name if current_name is not None else "IDLE"
        ready_snapshot = list(waiting_names)
        messages.append(
            f"Time {time}~{time + 1}: {'IDLE' if running == 'IDLE' else f'{running} 실행'}"
        )
        snapshots.append(
            make_snapshot(time, running, ready_snapshot, remaining, messages, ordered_names)
        )

        if current_name is None:
            timeline.append("IDLE")
            previous_running = "IDLE"
            time += 1
            continue

        timeline.append(current_name)
        remaining[current_name] -= 1

        if remaining[current_name] == 0:
            completion_times[current_name] = time + 1
            messages.append(f"Time {time + 1}: {current_name} 완료")
            current_name = None
            completed += 1

        previous_running = running
        time += 1

    return finalize_schedule(processes, timeline, completion_times, snapshots)


def schedule_srt(processes: list[Process], quantum: int | None = None) -> ScheduleResult:
    if not processes:
        return finalize_schedule([], [], {}, [])

    order_map = {process.name: index for index, process in enumerate(processes)}
    ordered_names = [process.name for process in processes]
    arrival_map = build_arrival_map(processes)
    process_map = {process.name: process for process in processes}
    remaining = {process.name: process.burst for process in processes}
    completion_times: dict[str, int] = {}
    timeline: list[str] = []
    snapshots: list[AnimationSnapshot] = []
    completed = 0
    time = 0
    previous_running = "IDLE"

    while completed < len(processes):
        messages: list[str] = []
        for process in arrival_map.get(time, []):
            messages.append(f"Time {time}: {process.name} 도착")

        available = [
            process
            for process in processes
            if process.arrival <= time and remaining[process.name] > 0
        ]

        if not available:
            messages.append(f"Time {time}~{time + 1}: IDLE")
            snapshots.append(
                make_snapshot(time, "IDLE", [], remaining, messages, ordered_names)
            )
            timeline.append("IDLE")
            previous_running = "IDLE"
            time += 1
            continue

        min_remaining = min(remaining[process.name] for process in available)
        running_name: str

        if previous_running != "IDLE" and remaining.get(previous_running, 0) == min_remaining:
            running_name = previous_running
        else:
            selected = min(
                available,
                key=lambda process: (
                    remaining[process.name],
                    process.arrival,
                    order_map[process.name],
                ),
            )
            running_name = selected.name

        if previous_running not in ("IDLE", running_name) and remaining.get(previous_running, 0) > 0:
            messages.append(f"Time {time}: {previous_running} 선점됨, {running_name} 실행")
        elif previous_running != running_name:
            append_dispatch_message(
                messages, time, running_name, previous_running, remaining, process_map
            )

        ready_names = [
            process.name
            for process in sorted(
                available,
                key=lambda process: (
                    remaining[process.name],
                    process.arrival,
                    order_map[process.name],
                ),
            )
            if process.name != running_name
        ]

        messages.append(f"Time {time}~{time + 1}: {running_name} 실행")
        snapshots.append(
            make_snapshot(time, running_name, ready_names, remaining, messages, ordered_names)
        )

        timeline.append(running_name)
        remaining[running_name] -= 1

        if remaining[running_name] == 0:
            completion_times[running_name] = time + 1
            messages.append(f"Time {time + 1}: {running_name} 완료")
            completed += 1

        previous_running = running_name
        time += 1

    return finalize_schedule(processes, timeline, completion_times, snapshots)


def schedule_round_robin(processes: list[Process], quantum: int | None = None) -> ScheduleResult:
    if not processes:
        return finalize_schedule([], [], {}, [])
    if quantum is None or quantum <= 0:
        raise ValueError("Round Robin에는 양의 시간 할당량이 필요합니다.")

    ordered_names = [process.name for process in processes]
    arrival_map = build_arrival_map(processes)
    process_map = {process.name: process for process in processes}
    remaining = {process.name: process.burst for process in processes}
    completion_times: dict[str, int] = {}
    ready_queue: deque[str] = deque()
    timeline: list[str] = []
    snapshots: list[AnimationSnapshot] = []
    current_name: str | None = None
    quantum_used = 0
    completed = 0
    time = 0
    previous_running = "IDLE"

    while completed < len(processes):
        messages: list[str] = []
        for process in arrival_map.get(time, []):
            ready_queue.append(process.name)
            messages.append(f"Time {time}: {process.name} 도착")

        if current_name is None and ready_queue:
            current_name = ready_queue.popleft()
            quantum_used = 0
            append_dispatch_message(
                messages, time, current_name, previous_running, remaining, process_map
            )

        running = current_name if current_name is not None else "IDLE"
        ready_snapshot = list(ready_queue)
        messages.append(
            f"Time {time}~{time + 1}: {'IDLE' if running == 'IDLE' else f'{running} 실행'}"
        )
        snapshots.append(
            make_snapshot(time, running, ready_snapshot, remaining, messages, ordered_names)
        )

        if current_name is None:
            timeline.append("IDLE")
            previous_running = "IDLE"
            time += 1
            continue

        timeline.append(current_name)
        remaining[current_name] -= 1
        quantum_used += 1

        if remaining[current_name] == 0:
            completion_times[current_name] = time + 1
            messages.append(f"Time {time + 1}: {current_name} 완료")
            current_name = None
            quantum_used = 0
            completed += 1
        elif quantum_used == quantum:
            ready_queue.append(current_name)
            messages.append(f"Time {time + 1}: {current_name} 시간 할당량 종료, 대기열 뒤로 이동")
            current_name = None
            quantum_used = 0

        previous_running = running
        time += 1

    return finalize_schedule(processes, timeline, completion_times, snapshots)


def schedule_priority_round_robin(
    processes: list[Process], quantum: int | None = None
) -> ScheduleResult:
    if not processes:
        return finalize_schedule([], [], {}, [])
    if quantum is None or quantum <= 0:
        raise ValueError("Priority Round Robin에는 양의 시간 할당량이 필요합니다.")

    ordered_names = [process.name for process in processes]
    arrival_map = build_arrival_map(processes)
    process_map = {process.name: process for process in processes}
    remaining = {process.name: process.burst for process in processes}
    completion_times: dict[str, int] = {}
    ready_queues: dict[int, deque[str]] = defaultdict(deque)
    slice_progress = {process.name: 0 for process in processes}
    timeline: list[str] = []
    snapshots: list[AnimationSnapshot] = []
    current_name: str | None = None
    completed = 0
    time = 0
    previous_running = "IDLE"

    while completed < len(processes):
        messages: list[str] = []
        preempted = False
        for process in arrival_map.get(time, []):
            ready_queues[process.priority].append(process.name)
            messages.append(f"Time {time}: {process.name} 도착")

        if current_name is not None:
            current_priority = process_map[current_name].priority
            higher_priorities = [
                priority
                for priority, queue in ready_queues.items()
                if queue and priority < current_priority
            ]
            if higher_priorities:
                next_priority = min(higher_priorities)
                next_name = ready_queues[next_priority][0]
                ready_queues[current_priority].appendleft(current_name)
                messages.append(f"Time {time}: {current_name} 선점됨, {next_name} 실행")
                current_name = None
                preempted = True

        if current_name is None:
            available_priorities = [
                priority for priority, queue in ready_queues.items() if queue
            ]
            if available_priorities:
                selected_priority = min(available_priorities)
                current_name = ready_queues[selected_priority].popleft()
                if not preempted:
                    append_dispatch_message(
                        messages, time, current_name, previous_running, remaining, process_map
                    )

        running = current_name if current_name is not None else "IDLE"
        ready_snapshot: list[str] = []
        for priority in sorted(ready_queues):
            ready_snapshot.extend(list(ready_queues[priority]))

        messages.append(
            f"Time {time}~{time + 1}: {'IDLE' if running == 'IDLE' else f'{running} 실행'}"
        )
        snapshots.append(
            make_snapshot(time, running, ready_snapshot, remaining, messages, ordered_names)
        )

        if current_name is None:
            timeline.append("IDLE")
            previous_running = "IDLE"
            time += 1
            continue

        timeline.append(current_name)
        remaining[current_name] -= 1
        slice_progress[current_name] += 1

        if remaining[current_name] == 0:
            completion_times[current_name] = time + 1
            messages.append(f"Time {time + 1}: {current_name} 완료")
            slice_progress[current_name] = 0
            current_name = None
            completed += 1
        elif slice_progress[current_name] == quantum:
            current_priority = process_map[current_name].priority
            ready_queues[current_priority].append(current_name)
            messages.append(f"Time {time + 1}: {current_name} 시간 할당량 종료, 동일 우선순위 대기열 뒤로 이동")
            slice_progress[current_name] = 0
            current_name = None

        previous_running = running
        time += 1

    return finalize_schedule(processes, timeline, completion_times, snapshots)


SCHEDULERS = {
    "FCFS": schedule_fcfs,
    "SJF": schedule_sjf,
    "SRT": schedule_srt,
    "Round Robin": schedule_round_robin,
    "Priority Round Robin": schedule_priority_round_robin,
}


class CPUSchedulingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CPU Scheduling Simulator")
        self.geometry("1450x940")
        self.minsize(1280, 820)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        default_font = ("Malgun Gothic", 10)
        self.style.configure(".", font=default_font)
        self.style.configure("Treeview", rowheight=24)
        self.style.configure("Title.TLabel", font=("Malgun Gothic", 18, "bold"))
        self.style.configure("Section.TLabelframe.Label", font=("Malgun Gothic", 11, "bold"))

        self.processes: list[Process] = []
        self.current_result: ScheduleResult | None = None
        self.current_algorithm = ""
        self.process_color_map: dict[str, str] = {}
        self.animation_index = 0
        self.animation_job: str | None = None
        self.animation_running = False

        self.algorithm_var = tk.StringVar(value="FCFS")
        self.current_time_var = tk.StringVar(value="현재 시간: -")
        self.running_var = tk.StringVar(value="실행 중인 프로세스: -")
        self.ready_queue_var = tk.StringVar(value="준비 큐: -")
        self.awt_var = tk.StringVar(value="평균 대기 시간: -")
        self.att_var = tk.StringVar(value="평균 반환 시간: -")
        self.throughput_var = tk.StringVar(value="처리량: -")
        self.speed_label_var = tk.StringVar(value="재생 속도: 5")

        self._build_ui()
        self._update_quantum_state()
        self._reset_output_views()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        title_label = ttk.Label(
            self,
            text="CPU 스케줄링 시뮬레이터",
            style="Title.TLabel",
            anchor="center",
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        main_frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        main_frame.grid(row=1, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)

        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        right_panel.rowconfigure(2, weight=1)

        self._build_input_frame(left_panel)
        self._build_process_table(left_panel)
        self._build_algorithm_frame(left_panel)
        self._build_gantt_frame(right_panel)
        self._build_animation_frame(right_panel)
        self._build_result_frame(right_panel)

    def _build_input_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="프로세스 입력", style="Section.TLabelframe")
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        ttk.Label(frame, text="프로세스 이름").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Label(frame, text="도착 시간").grid(row=0, column=2, sticky="w", padx=8, pady=(8, 4))
        ttk.Label(frame, text="실행 시간").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(frame, text="우선순위").grid(row=1, column=2, sticky="w", padx=8, pady=4)

        self.name_entry = ttk.Entry(frame, width=18)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 4))

        self.arrival_entry = ttk.Entry(frame, width=18)
        self.arrival_entry.grid(row=0, column=3, sticky="ew", padx=8, pady=(8, 4))

        self.burst_entry = ttk.Entry(frame, width=18)
        self.burst_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        self.priority_entry = ttk.Entry(frame, width=18)
        self.priority_entry.grid(row=1, column=3, sticky="ew", padx=8, pady=4)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=8, pady=(8, 10))
        for column_index in range(4):
            button_frame.columnconfigure(column_index, weight=1)

        ttk.Button(button_frame, text="프로세스 추가", command=self.add_process).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(button_frame, text="선택 삭제", command=self.delete_selected_process).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(button_frame, text="샘플 불러오기", command=self.load_sample_data).grid(
            row=0, column=2, sticky="ew", padx=6
        )
        ttk.Button(button_frame, text="전체 초기화", command=self.clear_all_processes).grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )

    def _build_process_table(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="입력된 프로세스", style="Section.TLabelframe")
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = ("name", "arrival", "burst", "priority")
        self.process_tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        headings = {
            "name": "이름",
            "arrival": "도착",
            "burst": "실행",
            "priority": "우선순위",
        }
        widths = {"name": 100, "arrival": 70, "burst": 70, "priority": 80}

        for column in columns:
            self.process_tree.heading(column, text=headings[column])
            self.process_tree.column(column, width=widths[column], anchor="center", stretch=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=scrollbar.set)
        self.process_tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

    def _build_algorithm_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="알고리즘 설정", style="Section.TLabelframe")
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="알고리즘").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self.algorithm_box = ttk.Combobox(
            frame,
            textvariable=self.algorithm_var,
            state="readonly",
            values=list(SCHEDULERS.keys()),
        )
        self.algorithm_box.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 4))
        self.algorithm_box.bind("<<ComboboxSelected>>", self._on_algorithm_changed)

        ttk.Label(frame, text="시간 할당량").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.quantum_entry = ttk.Entry(frame)
        self.quantum_entry.insert(0, "2")
        self.quantum_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Button(frame, text="시뮬레이션 실행", command=self.run_simulation).grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 10)
        )

    def _build_gantt_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="최종 간트 차트", style="Section.TLabelframe")
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.gantt_canvas = tk.Canvas(frame, height=170, bg="white", highlightthickness=0)
        x_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.gantt_canvas.xview)
        self.gantt_canvas.configure(xscrollcommand=x_scrollbar.set)
        self.gantt_canvas.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        x_scrollbar.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

    def _build_animation_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="애니메이션", style="Section.TLabelframe")
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        controls = ttk.Frame(frame)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        controls.columnconfigure(4, weight=1)

        ttk.Button(controls, text="애니메이션 시작", command=self.start_animation).grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        ttk.Button(controls, text="일시정지", command=self.pause_animation).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Button(controls, text="리셋", command=self.reset_animation).grid(
            row=0, column=2, sticky="w", padx=6
        )
        ttk.Label(controls, text="속도").grid(row=0, column=3, sticky="w", padx=(18, 6))

        self.speed_scale = tk.Scale(
            controls,
            from_=1,
            to=10,
            orient="horizontal",
            showvalue=False,
            resolution=1,
            length=180,
            command=self._on_speed_changed,
        )
        self.speed_scale.set(5)
        self.speed_scale.grid(row=0, column=4, sticky="w")

        ttk.Label(controls, textvariable=self.speed_label_var).grid(
            row=0, column=5, sticky="e", padx=(12, 0)
        )

        live_gantt_frame = ttk.LabelFrame(frame, text="진행 중 간트 차트")
        live_gantt_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        live_gantt_frame.columnconfigure(0, weight=1)
        live_gantt_frame.rowconfigure(0, weight=1)

        self.live_gantt_canvas = tk.Canvas(
            live_gantt_frame,
            height=78,
            bg="white",
            highlightthickness=0,
        )
        live_x_scrollbar = ttk.Scrollbar(
            live_gantt_frame,
            orient="horizontal",
            command=self.live_gantt_canvas.xview,
        )
        self.live_gantt_canvas.configure(xscrollcommand=live_x_scrollbar.set)
        self.live_gantt_canvas.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        live_x_scrollbar.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        status_frame = ttk.Frame(frame)
        status_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))
        status_frame.columnconfigure(0, weight=0)
        status_frame.columnconfigure(1, weight=1)

        ttk.Label(status_frame, textvariable=self.current_time_var).grid(
            row=0, column=0, sticky="w", pady=2, padx=(0, 16)
        )
        ttk.Label(status_frame, textvariable=self.running_var).grid(
            row=0, column=1, sticky="w", pady=2
        )
        ttk.Label(status_frame, textvariable=self.ready_queue_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 2)
        )

        detail_frame = ttk.Frame(frame)
        detail_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.columnconfigure(1, weight=3)
        detail_frame.rowconfigure(0, weight=1)

        remaining_frame = ttk.LabelFrame(detail_frame, text="남은 실행 시간")
        remaining_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        remaining_frame.columnconfigure(0, weight=1)
        remaining_frame.rowconfigure(0, weight=1)

        self.remaining_tree = ttk.Treeview(
            remaining_frame,
            columns=("name", "remaining"),
            show="headings",
            height=12,
        )
        self.remaining_tree.heading("name", text="이름")
        self.remaining_tree.heading("remaining", text="남은 시간")
        self.remaining_tree.column("name", width=90, anchor="center", stretch=False)
        self.remaining_tree.column("remaining", width=100, anchor="center", stretch=False)
        self.remaining_tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)

        remaining_scrollbar = ttk.Scrollbar(
            remaining_frame, orient="vertical", command=self.remaining_tree.yview
        )
        self.remaining_tree.configure(yscrollcommand=remaining_scrollbar.set)
        remaining_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

        log_frame = ttk.LabelFrame(detail_frame, text="이벤트 로그")
        log_frame.grid(row=0, column=1, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.event_log_text = tk.Text(log_frame, wrap="word", height=15, state="disabled")
        self.event_log_text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.event_log_text.yview)
        self.event_log_text.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

    def _build_result_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="결과", style="Section.TLabelframe")
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        columns = ("name", "arrival", "burst", "priority", "completion", "turnaround", "waiting")
        self.result_tree = ttk.Treeview(frame, columns=columns, show="headings", height=8)
        headings = {
            "name": "이름",
            "arrival": "도착",
            "burst": "실행",
            "priority": "우선순위",
            "completion": "완료",
            "turnaround": "반환",
            "waiting": "대기",
        }
        widths = {
            "name": 90,
            "arrival": 65,
            "burst": 65,
            "priority": 80,
            "completion": 70,
            "turnaround": 70,
            "waiting": 70,
        }

        for column in columns:
            self.result_tree.heading(column, text=headings[column])
            self.result_tree.column(column, width=widths[column], anchor="center", stretch=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 6))
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=(8, 6))

        summary_frame = ttk.Frame(frame)
        summary_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 10))
        for column_index in range(3):
            summary_frame.columnconfigure(column_index, weight=1)

        ttk.Label(summary_frame, textvariable=self.awt_var).grid(row=0, column=0, sticky="w")
        ttk.Label(summary_frame, textvariable=self.att_var).grid(row=0, column=1, sticky="w")
        ttk.Label(summary_frame, textvariable=self.throughput_var).grid(row=0, column=2, sticky="w")

    def add_process(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("입력 오류", "프로세스 이름을 입력하세요.")
            return

        if any(process.name == name for process in self.processes):
            messagebox.showerror("입력 오류", "프로세스 이름은 중복될 수 없습니다.")
            return

        try:
            arrival = int(self.arrival_entry.get().strip())
            burst = int(self.burst_entry.get().strip())
            priority = int(self.priority_entry.get().strip())
        except ValueError:
            messagebox.showerror("입력 오류", "도착 시간, 실행 시간, 우선순위는 정수여야 합니다.")
            return

        if arrival < 0:
            messagebox.showerror("입력 오류", "도착 시간은 0 이상이어야 합니다.")
            return
        if burst <= 0:
            messagebox.showerror("입력 오류", "실행 시간은 0보다 커야 합니다.")
            return

        self.processes.append(Process(name=name, arrival=arrival, burst=burst, priority=priority))
        self._refresh_process_table()
        self._clear_process_inputs()
        self._reset_output_views()
        self.name_entry.focus_set()

    def delete_selected_process(self) -> None:
        selected_items = self.process_tree.selection()
        if not selected_items:
            messagebox.showerror("선택 오류", "삭제할 프로세스를 선택하세요.")
            return

        selected_names = set(selected_items)
        self.processes = [process for process in self.processes if process.name not in selected_names]
        self._refresh_process_table()
        self._reset_output_views()

    def load_sample_data(self) -> None:
        self.processes = [
            Process("P1", arrival=0, burst=8, priority=1),
            Process("P2", arrival=1, burst=4, priority=2),
            Process("P3", arrival=2, burst=9, priority=2),
            Process("P4", arrival=3, burst=5, priority=3),
            Process("P5", arrival=4, burst=2, priority=3),
        ]
        self._refresh_process_table()
        self._clear_process_inputs()
        self._reset_output_views()

    def clear_all_processes(self) -> None:
        self.processes.clear()
        self._refresh_process_table()
        self._clear_process_inputs()
        self._reset_output_views()

    def run_simulation(self) -> None:
        if not self.processes:
            messagebox.showerror("실행 오류", "최소 한 개 이상의 프로세스를 추가하세요.")
            return

        algorithm = self.algorithm_var.get()
        scheduler = SCHEDULERS.get(algorithm)
        if scheduler is None:
            messagebox.showerror("실행 오류", "알고리즘을 선택하세요.")
            return

        self._reset_output_views()

        quantum: int | None = None
        if algorithm in {"Round Robin", "Priority Round Robin"}:
            quantum_text = self.quantum_entry.get().strip()
            try:
                quantum = int(quantum_text)
            except ValueError:
                messagebox.showerror("입력 오류", "시간 할당량은 정수여야 합니다.")
                return
            if quantum <= 0:
                messagebox.showerror("입력 오류", "시간 할당량은 0보다 커야 합니다.")
                return

        try:
            result = scheduler(list(self.processes), quantum)
        except ValueError as error:
            messagebox.showerror("실행 오류", str(error))
            return

        self.current_result = result
        self.current_algorithm = algorithm
        self.process_color_map = self._generate_process_colors()
        self._draw_gantt_chart()
        self._populate_result_table()
        self._update_summary_labels()
        self.reset_animation()

    def start_animation(self) -> None:
        if self.current_result is None or not self.current_result.event_logs:
            messagebox.showerror("실행 오류", "먼저 시뮬레이션을 실행하세요.")
            return

        if self.animation_running:
            return

        if self.animation_index >= len(self.current_result.event_logs):
            self.reset_animation()

        self.animation_running = True
        self._play_animation_step()

    def _play_animation_step(self) -> None:
        if not self.animation_running or self.current_result is None:
            return

        if self.animation_index >= len(self.current_result.event_logs):
            self._finish_animation()
            return

        snapshot = self.current_result.event_logs[self.animation_index]
        self._render_snapshot(snapshot, append_logs=True)
        self.animation_index += 1

        delay = self._get_animation_delay()
        if self.animation_index < len(self.current_result.event_logs):
            self.animation_job = self.after(delay, self._play_animation_step)
        else:
            self.animation_job = self.after(delay, self._finish_animation)

    def pause_animation(self) -> None:
        self.animation_running = False
        if self.animation_job is not None:
            try:
                self.after_cancel(self.animation_job)
            except tk.TclError:
                pass
            self.animation_job = None

    def reset_animation(self) -> None:
        self.pause_animation()
        self.animation_index = 0
        self._clear_event_log()

        if self.current_result is None or not self.current_result.event_logs:
            self.current_time_var.set("현재 시간: -")
            self.running_var.set("실행 중인 프로세스: -")
            self.ready_queue_var.set("준비 큐: -")
            self._refresh_remaining_tree({}, 0)
            self._draw_live_gantt_chart(0, None)
            return

        first_snapshot = self.current_result.event_logs[0]
        self._render_snapshot(first_snapshot, append_logs=False)

    def _finish_animation(self) -> None:
        if self.current_result is None:
            return

        self.pause_animation()
        total_time = len(self.current_result.timeline)
        self.current_time_var.set(f"현재 시간: {total_time}")
        self.running_var.set("실행 중인 프로세스: 완료")
        self.ready_queue_var.set("준비 큐: 없음")
        self._refresh_remaining_tree({process.name: 0 for process in self.processes}, total_time, final=True)
        self._draw_live_gantt_chart(total_time, None)
        self._append_log_lines(["시뮬레이션 완료"])

    def _render_snapshot(self, snapshot: AnimationSnapshot, append_logs: bool) -> None:
        self.current_time_var.set(f"현재 시간: {snapshot.time}")
        self.running_var.set(f"실행 중인 프로세스: {snapshot.running}")
        queue_text = ", ".join(snapshot.ready_queue) if snapshot.ready_queue else "없음"
        self.ready_queue_var.set(f"준비 큐: {queue_text}")
        self._refresh_remaining_tree(snapshot.remaining, snapshot.time)
        self._draw_live_gantt_chart(snapshot.time + 1, snapshot.time)

        if append_logs:
            self._append_log_lines(snapshot.messages)

    def _refresh_remaining_tree(
        self,
        remaining: dict[str, int],
        time: int,
        final: bool = False,
    ) -> None:
        self.remaining_tree.delete(*self.remaining_tree.get_children())
        remaining_map = remaining if remaining else {process.name: process.burst for process in self.processes}

        for process in self.processes:
            if final:
                display_value = "완료"
            elif time < process.arrival:
                display_value = "미도착"
            else:
                value = remaining_map.get(process.name, process.burst)
                display_value = "완료" if value == 0 else str(value)

            self.remaining_tree.insert("", "end", iid=process.name, values=(process.name, display_value))

    def _append_log_lines(self, lines: list[str]) -> None:
        if not lines:
            return

        self.event_log_text.configure(state="normal")
        for line in lines:
            self.event_log_text.insert("end", f"{line}\n")
        self.event_log_text.see("end")
        self.event_log_text.configure(state="disabled")

    def _clear_event_log(self) -> None:
        self.event_log_text.configure(state="normal")
        self.event_log_text.delete("1.0", "end")
        self.event_log_text.configure(state="disabled")

    def _draw_live_gantt_chart(
        self,
        visible_units: int,
        highlight_index: int | None,
    ) -> None:
        self.live_gantt_canvas.delete("all")

        if self.current_result is None or not self.current_result.timeline or visible_units <= 0:
            self.live_gantt_canvas.create_text(
                20,
                16,
                anchor="nw",
                text="애니메이션을 시작하면 진행 중 간트 차트가 표시됩니다.",
                font=("Malgun Gothic", 10),
            )
            self.live_gantt_canvas.configure(scrollregion=(0, 0, 760, 78))
            self.live_gantt_canvas.xview_moveto(0)
            return

        timeline = self.current_result.timeline[:visible_units]
        unit_width = 38
        left_margin = 22
        top = 10
        block_height = 26
        label_y = top + block_height + 10

        for index, name in enumerate(timeline):
            x1 = left_margin + index * unit_width
            x2 = x1 + unit_width
            color = self.process_color_map.get(name, "#cfd8dc")
            is_current = index == highlight_index
            outline = "#d32f2f" if is_current else "#37474f"
            line_width = 3 if is_current else 1

            self.live_gantt_canvas.create_rectangle(
                x1,
                top,
                x2,
                top + block_height,
                fill=color,
                outline=outline,
                width=line_width,
            )
            self.live_gantt_canvas.create_text(
                (x1 + x2) / 2,
                top + block_height / 2,
                text=name,
                font=("Malgun Gothic", 8, "bold"),
            )
            self.live_gantt_canvas.create_text(
                x1,
                label_y,
                text=str(index),
                anchor="n",
                font=("Malgun Gothic", 8),
            )

        last_x = left_margin + len(timeline) * unit_width
        self.live_gantt_canvas.create_text(
            last_x,
            label_y,
            text=str(len(timeline)),
            anchor="n",
            font=("Malgun Gothic", 8),
        )

        total_width = left_margin * 2 + max(14 * unit_width, len(timeline) * unit_width)
        self.live_gantt_canvas.configure(scrollregion=(0, 0, total_width, 78))
        self._scroll_live_gantt_to_current(total_width, unit_width, left_margin, highlight_index)

    def _scroll_live_gantt_to_current(
        self,
        content_width: int,
        unit_width: int,
        left_margin: int,
        highlight_index: int | None,
    ) -> None:
        if highlight_index is None:
            self.live_gantt_canvas.xview_moveto(1.0)
            return

        self.live_gantt_canvas.update_idletasks()
        viewport_width = max(self.live_gantt_canvas.winfo_width(), 1)
        if content_width <= viewport_width:
            self.live_gantt_canvas.xview_moveto(0)
            return

        target_x = left_margin + (highlight_index + 1) * unit_width
        fraction = (target_x - viewport_width * 0.7) / (content_width - viewport_width)
        self.live_gantt_canvas.xview_moveto(max(0.0, min(1.0, fraction)))

    def _draw_gantt_chart(self) -> None:
        self.gantt_canvas.delete("all")

        if self.current_result is None or not self.current_result.gantt_segments:
            self.gantt_canvas.create_text(
                20,
                30,
                anchor="nw",
                text="시뮬레이션 결과를 실행하면 간트 차트가 표시됩니다.",
                font=("Malgun Gothic", 11),
            )
            self.gantt_canvas.configure(scrollregion=(0, 0, 900, 170))
            return

        unit_width = 42
        left_margin = 25
        top = 25
        height = 55

        for segment in self.current_result.gantt_segments:
            x1 = left_margin + segment.start * unit_width
            x2 = left_margin + segment.end * unit_width
            color = self.process_color_map.get(segment.name, "#cfd8dc")
            self.gantt_canvas.create_rectangle(x1, top, x2, top + height, fill=color, outline="#37474f")
            self.gantt_canvas.create_text(
                (x1 + x2) / 2,
                top + height / 2,
                text=segment.name,
                font=("Malgun Gothic", 10, "bold"),
            )
            self.gantt_canvas.create_text(
                x1,
                top + height + 18,
                text=str(segment.start),
                anchor="n",
                font=("Malgun Gothic", 9),
            )

        last_end = self.current_result.gantt_segments[-1].end
        last_x = left_margin + last_end * unit_width
        self.gantt_canvas.create_text(
            last_x,
            top + height + 18,
            text=str(last_end),
            anchor="n",
            font=("Malgun Gothic", 9),
        )
        self.gantt_canvas.create_text(
            25,
            8,
            anchor="nw",
            text=f"알고리즘: {self.current_algorithm}",
            font=("Malgun Gothic", 10, "bold"),
        )

        total_width = left_margin * 2 + max(18 * unit_width, last_end * unit_width)
        self.gantt_canvas.configure(scrollregion=(0, 0, total_width, 170))
        self.gantt_canvas.xview_moveto(0)

    def _populate_result_table(self) -> None:
        self.result_tree.delete(*self.result_tree.get_children())

        if self.current_result is None:
            return

        for result in self.current_result.process_results:
            self.result_tree.insert(
                "",
                "end",
                iid=result.name,
                values=(
                    result.name,
                    result.arrival,
                    result.burst,
                    result.priority,
                    result.completion,
                    result.turnaround,
                    result.waiting,
                ),
            )

    def _update_summary_labels(self) -> None:
        if self.current_result is None:
            self.awt_var.set("평균 대기 시간: -")
            self.att_var.set("평균 반환 시간: -")
            self.throughput_var.set("처리량: -")
            return

        self.awt_var.set(f"평균 대기 시간: {self.current_result.average_waiting:.2f}")
        self.att_var.set(f"평균 반환 시간: {self.current_result.average_turnaround:.2f}")
        self.throughput_var.set(f"처리량: {self.current_result.throughput:.4f}")

    def _refresh_process_table(self) -> None:
        self.process_tree.delete(*self.process_tree.get_children())
        for process in self.processes:
            self.process_tree.insert(
                "",
                "end",
                iid=process.name,
                values=(process.name, process.arrival, process.burst, process.priority),
            )

    def _clear_process_inputs(self) -> None:
        self.name_entry.delete(0, "end")
        self.arrival_entry.delete(0, "end")
        self.burst_entry.delete(0, "end")
        self.priority_entry.delete(0, "end")

    def _generate_process_colors(self) -> dict[str, str]:
        palette = [
            "#90caf9",
            "#a5d6a7",
            "#ffcc80",
            "#f48fb1",
            "#ce93d8",
            "#80cbc4",
            "#ffe082",
            "#bcaaa4",
            "#9fa8da",
            "#ef9a9a",
        ]
        color_map = {"IDLE": "#cfd8dc"}
        for index, process in enumerate(self.processes):
            color_map[process.name] = palette[index % len(palette)]
        return color_map

    def _reset_output_views(self) -> None:
        self.pause_animation()
        self.current_result = None
        self.current_algorithm = ""
        self.animation_index = 0
        self.process_color_map = {}
        self._clear_event_log()
        self._update_summary_labels()
        self.result_tree.delete(*self.result_tree.get_children())
        self.current_time_var.set("현재 시간: -")
        self.running_var.set("실행 중인 프로세스: -")
        self.ready_queue_var.set("준비 큐: -")
        self._refresh_remaining_tree({}, 0)
        self._draw_live_gantt_chart(0, None)
        self._draw_gantt_chart()

    def _on_algorithm_changed(self, event: tk.Event | None = None) -> None:
        self._update_quantum_state()

    def _update_quantum_state(self) -> None:
        if self.algorithm_var.get() in {"Round Robin", "Priority Round Robin"}:
            self.quantum_entry.configure(state="normal")
        else:
            self.quantum_entry.configure(state="disabled")

    def _on_speed_changed(self, value: str) -> None:
        speed = int(float(value))
        self.speed_label_var.set(f"재생 속도: {speed}")

    def _get_animation_delay(self) -> int:
        speed = int(float(self.speed_scale.get()))
        return max(120, 1150 - speed * 95)


if __name__ == "__main__":
    app = CPUSchedulingApp()
    app.mainloop()
