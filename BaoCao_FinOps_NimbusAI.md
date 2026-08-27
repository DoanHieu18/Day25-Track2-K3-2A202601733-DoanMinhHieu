# Báo cáo Phân tích FinOps & Tối ưu hóa Chi phí GPU
## Khách hàng: NimbusAI | Kỹ sư FinOps: Doan Minh Hieu (AICB - Track 2 - Day 25)

---

## 1. Tóm tắt Điều hành (Executive Summary)

Dự án kiểm toán và tối ưu hóa hạ tầng GPU cho startup **NimbusAI** đã hoàn thành xuất sắc việc nhận diện các điểm lãng phí tài nguyên và đề xuất giải pháp cắt giảm chi phí toàn diện.

### Các chỉ số then chốt:

| Chỉ số | Baseline (Trước tối ưu) | Optimized (Sau tối ưu) | Tiết kiệm | % Giảm |
|---|---|---|---|---|
| **Tổng chi phí hàng tháng** | **$27,133 / tháng** | **$14,626 / tháng** | **$12,507 / tháng** | **46.1%** |
| **Đơn giá Inference ($/1M-token)** | **$6.488 / 1M token** | **$1.126 / 1M token** | **$5.362 / 1M token** | **82.6%** |
| **Chi phí Inference theo ngày** | $48.87 / ngày | $8.48 / ngày | $40.39 / ngày | 82.6% |
| **Chi phí Workload Training & Dev** | $25,667 / tháng | $15,627 / tháng | $10,040 / tháng | 39.1% |
| **Lãng phí do GPU Idle** | $600 / tháng ($20/ngày) | $0 / tháng | $600 / tháng | 100.0% |
| **Lãng phí từ GPU-Util Lie** | $655 / tháng | $0 / tháng | $655 / tháng | 100.0% |

> **Bài học cốt lõi:** Thay vì đo lường đơn thuần bằng `$/GPU-giờ`, NimbusAI đã chuyển dịch sang thước đo kinh tế đơn vị chuẩn FinOps: **`$/1M-token`** và **MFU/MBU**, giúp phản ánh chính xác giá trị tính toán nhận được trên mỗi đồng vốn đầu tư.

---

## 2. Phân tích Chi tiết 4 Đòn bẩy Tối ưu (FinOps Levers) & Thứ tự Ưu tiên ROI

![Biểu đồ Tiết kiệm Chi phí theo Đòn bẩy](outputs/savings.png)

```
                       CƠ CẤU TIẾT KIỆM HÀNG THÁNG ($12,507)
  ┌────────────────────────────────────────────────────────────────────────┐
  │ Purchasing Strategy (Spot/Reserved) : $10,040 (80.3%)                  │
  │ Inference Levers (Cascade/Cache/Batch) : $1,212 (9.7%)                 │
  │ Right-size "GPU-Util Lie" : $655 (5.2%)                                │
  │ Kill Idle GPUs : $600 (4.8%)                                           │
  └────────────────────────────────────────────────────────────────────────┘
```

### 2.1. Đòn bẩy 1: Purchasing Strategy — Tiết kiệm $10,040/tháng (ROI cao nhất)
- **Cơ chế:** Phân loại 8 workloads theo duty cycle và tính chất có thể gián đoạn (`interruptible`):
  - **Reserved Instances (Cam kết 3 năm, discount 45%):** Áp dụng cho các job chạy 24/7 có duty cycle $\ge 55\%$ (điểm hòa vốn) như `job-infer-chat` (A10G), `job-infer-rag` (A100), `job-infer-search` (L4).
  - **Spot Instances (Chiết khấu 40–60% kèm checkpointing):** Áp dụng cho các job training/batch có `interruptible=1` như `job-train-llm` (H100), `job-train-embed` (A100), `job-finetune` (H100), `job-dev-sandbox` (A10G), `job-batch-eval` (H100). Dù tính thêm 3% checkpoint overhead và rủi ro rollback, Spot vẫn tiết kiệm từ 39% đến 58% chi phí.

### 2.2. Đòn bẩy 2: Inference Optimization Levers — Giảm 82.6% đơn giá phục vụ token
- **Bóc tách từng thành phần:**
  1. **Model Cascade (Đóng góp lớn nhất: 76.5% savings):** Định tuyến 80% request đơn giản sang Small model ($0.20/$0.40 per 1M-token) và chỉ dùng Large model ($3.00/$15.00) cho 20% prompt phức tạp.
  2. **Batch API (Đóng góp 16.9% savings):** Nhóm các workload không cần real-time (như `nightly-eval`) để hưởng chiết khấu 50%.
  3. **Prompt Caching (Đóng góp 9.4% savings):** Chiết khấu 90% chi phí input token cho các system prompt tĩnh lặp lại trong chat và RAG (cache hit rate đạt 31.9%).
- **Discount Stacking:** Khi kết hợp đồng thời Batch API + Prompt Cache (100% hit), chi phí chỉ còn $0.5 \times 0.1 = 0.05$ (giảm tới 95% so với naive).

### 2.3. Đòn bẩy 3: Right-sizing Over-provisioned GPUs — Tiết kiệm $655/tháng
- Hạ cấp các GPU bị nghẽn (như H100 chạy workload memory-bound) xuống GPU phù hợp hơn (A100 hoặc L4) mà không suy giảm throughput.

### 2.4. Đòn bẩy 4: Loại bỏ GPU Idle (Auto-shutdown) — Tiết kiệm $600/tháng
- Phát hiện `gpu-h100-5` bị bỏ trống 8 tiếng qua đêm sau khi train xong. Thiết lập automation shutdown giải phóng $20/ngày.

---

## 3. Bản chất Khoa học của "GPU-Util Lie"

### 3.1. Hiện tượng thực tế tại NimbusAI
Trong đợt kiểm toán M1, GPU `gpu-h100-4` ghi nhận **`gpu_util_pct = 98.2%`**, nhưng chỉ đạt **`MFU = 0.194` (19.4%)**. Tương tự, `gpu-a10g-1` đạt `96.9% util` nhưng `MFU = 0.268`.

### 3.2. Cơ chế kỹ thuật vì sao `nvidia-smi` "nói dối"
1. **Cách đo của `nvidia-smi`:** Chỉ số `GPU-Util %` là **thời gian xung nhịp hoạt động (time-active clock)**. Một GPU đang ở trạng thái `100% Util` đơn giản là trong chu kỳ lấy mẫu, có ít nhất một kernel đang active trên chip.
2. **Nghẽn băng thông bộ nhớ (Memory Bandwidth Stall):** Trong các tác vụ LLM Decode (bước sinh từng token một), cường độ số học (Arithmetic Intensity) cực thấp ($\sim 1\text{--}2\text{ FLOP/byte}$ so với điểm cân bằng Roofline của H100 là $295\text{ FLOP/byte}$). Tensor Cores phải nhàn rỗi chờ nạp trọng số từ HBM vào SRAM/Registers. GPU bận "đứng chờ bộ nhớ" nhưng `nvidia-smi` vẫn báo 98% Util.
3. **Kernel Launch Latency & Non-fused Ops:** Việc gọi nhiều kernel nhỏ không tối ưu (ví dụ thiếu Kernel Fusion như FlashAttention) gây overhead đồng bộ CPU-GPU, làm xung nhịp bận rộn mà không thực hiện được phép tính ma trận hữu ích nào.

### 3.3. Tác động tài chính
Doanh nghiệp trả đủ **100% tiền thuê GPU ($2.50/giờ cho H100)** nhưng thực tế chỉ nhận được **19.4% năng lực tính toán FLOPs**. Đây là nguyên nhân trực tiếp gây phình hóa đơn cloud mà các dashboard thông thường không thể phát hiện.

---

## 4. Kết quả Thực hiện 5 Phần Mở rộng "Your Turn"

### 🌟 Extension 1: Nâng cấp Chính sách Thuê GPU (`recommend_tier`)
- **Triển khai:** Bổ sung logic nhận diện thời gian chạy thực tế (`job_days`), loại GPU và tỷ lệ gián đoạn (`interrupt_rate`). So sánh linh hoạt giữa 1-year reserved ($2.00/h) và 3-year reserved ($1.40/h) trên H100.
- **Kết quả:** Ngăn chặn việc cam kết nhầm 3-year cho các job ngắn hạn (< 30 ngày), tối ưu điểm hòa vốn chính xác ở mức $55\%$ duty cycle.

### 🌟 Extension 2: VRAM Unit Economics & Right-sizing theo MBU
- **Bảng giá VRAM chuẩn hóa ($/GB-hr):**

| GPU Type | On-Demand ($/hr) | VRAM (GB) | Đơn giá $/GB-hr | Peak BW (TB/s) |
|---|---|---|---|---|
| **H100** | $2.50 | 80 GB | $0.0312 | 3.35 TB/s |
| **H200** | $3.95 | 141 GB | $0.0280 | 4.80 TB/s |
| **A100** | $1.79 | 80 GB | **$0.0224** | 2.00 TB/s |
| **A10G** | $1.00 | 24 GB | $0.0417 | 0.60 TB/s |
| **L4** | $0.80 | 24 GB | $0.0333 | 0.30 TB/s |
| **MI300X** | $1.95 | 192 GB | **$0.0102** | 5.30 TB/s |

- **Insight:** Đối với các tác vụ memory-bound có MBU thấp, việc chuyển từ H100 sang A100 hoặc MI300X giúp tiết kiệm tới **$2,580/tháng** mà vẫn đáp ứng hoàn hảo yêu cầu băng thông.

### 🌟 Extension 3: Kinh tế học Prompt Caching (`cache_is_worth_it`)
- **Công thức Break-even:** Caching chỉ có lãi khi $\text{Số lần đọc lại} \times \text{Tiết kiệm mỗi lần đọc} > \text{Chi phí ghi & lưu cache}$.
- **Tính toán:** Với mức giảm giá 90% (chỉ trả 10%), ngưỡng hòa vốn tối thiểu là **$> 1.11\times$ lần đọc lại**.
- **Đo lường dataset:** Tỷ lệ cache hit thực tế đạt **31.9%** tổng input token, trung bình mỗi prefix được tái sử dụng $4.0\times$ $\rightarrow$ Hàm `cache_is_worth_it()` trả về `True` cho cả Small và Large model tier.

### 🌟 Extension 4: Quản trị Ngân sách Reasoning (Reasoning Budget Governance)
- **Đo lường chi phí:**
  - **Reasoning requests:** Chỉ chiếm **8.4% tổng số request** (201/2,400) nhưng tiêu thụ tới **16.5% tổng token** (1.24 triệu token) và tiêu tốn **$1.40/ngày** chi phí inference.
  - **Tiêu thụ năng lượng:** Reasoning tiêu hao năng lượng gấp **$\sim 80\times$** so với prompt thông thường do quá trình chuỗi suy nghĩ dài (Chain-of-Thought).
- **Quy tắc Routing đề xuất:** Chỉ kích hoạt Reasoning khi bài toán yêu cầu logic/code phức tạp hoặc khi confidence score của Fast Small model $< 0.70$. Nếu khống chế reasoning ở mức hợp lý, NimbusAI có thể giảm thêm 10% chi phí inference và tiết kiệm đáng kể năng lượng.

### 🌟 Extension 5: Lập lịch Thông minh Hướng Carbon (Carbon-Aware Scheduling)
- **So sánh 5 khu vực cho 1,789.0 kWh điện toán gián đoạn:**

| Vùng (Region) | Cường độ Carbon (gCO2/kWh) | Tổng CO2 (kg) | Giá điện ($/kWh) | Chi phí Điện ($) |
|---|---|---|---|---|
| **us-east-1** (Mặc định) | 380 | 679.8 kg | $0.120 | $214.68 |
| **us-west-2** (Thủy điện Oregon) | 120 | 214.7 kg | $0.070 | $125.23 |
| **europe-north1** (Na Uy) | **30** | **53.7 kg** | $0.090 | $161.01 |
| **europe-central2** (Ba Lan - Than đá) | 660 | 1,180.7 kg | $0.180 | $322.02 |
| **us-east-wa** (Washington) | 90 | 161.0 kg | **$0.055** | **$98.39** |

- **Kết quả điều chuyển:** Chuyển các job training/batch có thể ngắt quãng từ `us-east-1` sang `europe-north1` giúp **giảm 92.1% lượng phát thải carbon** (tiết kiệm 626.1 kg CO2e) và giảm $53.67 tiền điện.

---

## 5. Phân bổ Chi phí & Chuẩn FOCUS (Maturity Roadmap)

- **Độ phủ gắn thẻ (Tag Coverage):** Đạt **92.0%** (vượt xa ngưỡng chuẩn FinOps 80%).
- **Cổng Chargeback:** Trạng thái **OPEN (Ready)**.
- **Phân bổ chi phí theo Team:**
  1. `assistant`: $2.59 / ngày (30.5%)
  2. `search`: $2.49 / ngày (29.4%)
  3. `eval`: $1.79 / ngày (21.1%)
  4. `rag`: $1.60 / ngày (18.9%)
- **Chuẩn xuất FOCUS (`outputs/focus_export.csv`):** Đã chuẩn hóa 50 dòng theo định dạng mở FinOps Open Cost & Usage Specification (FOCUS 1.x), sẵn sàng tích hợp đa nền tảng đám mây.

---

## 6. Top 3 Khuyến nghị Hành động cho FinOps Lead

1. **Hành động 1 (Triển khai ngay tuần 1): Tái cấu trúc Hợp đồng Mua GPU**
   - Ký kết Reserved 3-year cho 3 workload inference cốt lõi (`job-infer-chat`, `job-infer-rag`, `job-infer-search`).
   - Chuyển toàn bộ 5 job training/batch sang Spot Instance kèm thư viện tự động checkpointing (tiết kiệm ngay **$10,040/tháng**).
2. **Hành động 2 (Triển khai tuần 2): Tích hợp LLM Gateway Routing & Caching**
   - Triển khai LiteLLM Proxy làm gateway trung tâm, áp dụng quy tắc Model Cascade (80/20) và bật Prompt Caching cho tất cả request của team Chat & RAG (giảm **82.6% đơn giá per 1M-token**).
3. **Hành động 3 (Triển khai tuần 3-4): Tự động hóa Governance & Chargeback**
   - Cài đặt daemon tự động tắt GPU nhàn rỗi quá 30 phút.
   - Chính thức kích hoạt quy trình Chargeback theo chuẩn FOCUS dựa trên 92% tag coverage để phân định ngân sách rõ ràng cho từng phòng ban.
