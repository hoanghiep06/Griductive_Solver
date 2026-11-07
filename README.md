griductive_project/
│
├── puzzles/                    # Dữ liệu các màn chơi (.json)
│   ├── puzzle_3x3_easy.json
│   ├── puzzle_4x4_medium.json
│   └── puzzle_5x5_stress.json
│
├── src/
│   ├── core/                   # [TV 1] Engine quản lý trạng thái trò chơi
│   │   ├── __init__.py
│   │   ├── character.py        # Đối tượng Nhân vật (Tên, Nghề nghiệp, Tọa độ)
│   │   ├── clue.py             # Cấu trúc manh mối công khai
│   │   ├── game_engine.py      # Nắm giữ hidden solution & unrevealed clues
│   │   └── public_kb.py        # Chỉ chứa thông tin công khai (Revealed clues + Proved verdicts)
│   │
│   ├── encoder/                # [TV 3 & TV 4] Chuyển đổi Logic sang CNF
│   │   ├── __init__.py
│   │   ├── variable_map.py     # Ánh xạ C_i và biến phụ (Auxiliary variables)
│   │   ├── cnf_encoder.py      # Encoder cho 6 Core Clues (FACT, SAME, DIFFERENT, EXACTLY,...)
│   │   ├── extended_clues.py   # Encoder cho 2 Extended Clues (PARITY, COUNT_COMPARE)
│   │   └── semantic_eval.py    # Direct Semantic Evaluators (không gọi CNF)
│   │
│   ├── solvers/                # [TV 2] DPLL SAT Solver thuần Python
│   │   ├── __init__.py
│   │   ├── dpll.py             # Thuật toán DPLL (Unit prop, Conflict, Backtrack, Metrics)
│   │   └── cnf_formula.py      # Lớp đại diện cho công thức CNF & Clause
│   │
│   ├── agent/                  # [TV 4 & TV 5] Logic Agent tự động suy luận
│   │   ├── __init__.py
│   │   ├── entailment.py       # Kiểm tra KB |- C_i via SAT query (KB AND NOT C_i is UNSAT)
│   │   ├── logic_agent.py      # Vòng lặp suy luận No-Guess & Hint generator
│   │   ├── uniqueness.py       # Kiểm tra nghiệm duy nhất của puzzle
│   │   └── deduction_trace.py  # Ghi log vết suy luận chi tiết
│   │
│   └── gui/                    # [TV 2 & TV 3] Giao diện người dùng
│       ├── __init__.py
│       ├── grid_view.py        # Vẽ lưới 3x3, 4x4, 5x5, lật thẻ, tô màu trạng thái
│       ├── clue_highlighter.py # Highlight các ô/vùng được manh mối tham chiếu
│       └── app_window.py       # Cửa sổ chính, nút Hint, Auto Solve, Modal thông báo
│
├── benchmark.py                # [TV 4] Script chạy tự động đo đạc 10-15 puzzles
├── main.py                     # Entry point chính chạy chương trình
├── requirements.txt            # Thư viện sử dụng
└── README.md                   # Hướng dẫn cài đặt và khởi chạy