# 分拣候选门控接口 v1

`vg_sort_guard_axi` 是独立、同步时钟的 AXI4-Lite 从设备，32 位数据、12 位字节地址、低有效同步复位 `rst_n`。尚未分配板端物理地址；禁止用颜色 IP 的地址访问此模块。所有配置/帧字段经 PS 写入，`external_busy` 为同一时钟域的额外忙信号。输出 `permit_pulse` 仅持续一个时钟，并由寄存器记录事件；它不直接驱动机械臂。

现有颜色 PL 产生 `sequence`、`mask_count` 和全局 bbox。PS 负责校验相机/PL 帧号、请求号、会话、时间戳并设置 fresh/valid，然后提交给本模块。候选门控不能独立证明这些 PS 输入真实，也不识别垃圾类别或处理语音。

## 总线与寄存器

每次事务必须 32 位对齐；写入要求 `WSTRB=0xf`。部分/零 strobe、非法地址、只读寄存器写入、保留位非零及拒绝的命令返回 `SLVERR`，且不执行该写入。合法访问返回 `OKAY`。AW/W 可任意先后到达，B/R 支持背压，响应期间保持内容。最多各一笔未完成写/读；无中断、无 burst。

所有存储寄存器复位为 0，ID/VERSION 常量除外。STATUS bit2 是 effective busy 的组合读数：软件 BUSY 虽然被复位清零，`external_busy` 外部引脚不会被本模块复位；该引脚持续为 1 时，复位后的 STATUS 仍显示 busy，ARM 仍被拒绝。配置为 staging，运行时写配置不改变已 ARM 快照。16 位字段的高 16 位必须为 0。

| 偏移 | 名称 | 访问 | 含义 |
|---|---|---|---|
| `0x000` | ID | RO | `0x31444753`，SGD1 |
| `0x004` | VERSION | RO | `0x00010000` |
| `0x008` | COMMAND | WO / R=0 | 下表中的单个命令值，禁止位组合 |
| `0x00c` | BUSY | RW | bit0 软件 busy；与 `external_busy` 相或；其他位为 0 |
| `0x010` | STATUS | RO | bit0 active；bit1 ready；bit2 effective busy；bit3 consumed；bit4 timed_out；bit5 cancelled；bit6 bus_fault；其余 0 |
| `0x014` | ACTIVE_JOB | RO | 最近成功 ARM 的 job_id，任务结束仍保留 |
| `0x018` | LAST_SEQ | RO | ARM 时的 baseline，之后最近接受的严格更新帧序号 |
| `0x01c` | STABLE_COUNT | RO | 当前连续合格帧数，达到要求后饱和 |
| `0x020` | AGE_CYCLES | RO | 当前任务距 ARM / 最近有效新帧的时钟周期数；结束后保留 |
| `0x024` | PERMIT_COUNT | RO | 自复位累计许可次数，32 位自然回绕；ARM/CANCEL 不清零 |
| `0x028` | PERMIT_JOB | RO | 最近许可对应 job_id，ARM/CANCEL 不清零 |
| `0x02c` | LAST_REASON | RO | 0 idle/reset；1 armed；2 collecting；3 ready；4 bad_frame；5 jitter；6 timeout；7 cancelled；8 busy；9 consumed |
| `0x040` | CFG_JOB | RW | 非零 job_id；主机每轮使用新值，不复用已结束 job |
| `0x044` | CFG_BASELINE_SEQ | RW | ARM 前最后观察帧，只有序号严格更新的帧可计数 |
| `0x048` | CFG_ROI_XMIN | RW | 16 位，包含边界 |
| `0x04c` | CFG_ROI_YMIN | RW | 16 位，包含边界 |
| `0x050` | CFG_ROI_XMAX | RW | 16 位，包含边界 |
| `0x054` | CFG_ROI_YMAX | RW | 16 位，包含边界 |
| `0x058` | CFG_MIN_MASK | RW | 匹配像素数下界，必须 >0 |
| `0x05c` | CFG_MAX_MASK | RW | 匹配像素数上界，必须 >=MIN |
| `0x060` | CFG_REQUIRED | RW | 16 位，连续帧要求 1..65535 |
| `0x064` | CFG_JITTER | RW | 16 位，相对本段首帧四个 bbox 边界的最大绝对差，单位为 PL 像素 |
| `0x068` | CFG_TIMEOUT | RW | 非零，无有效新帧超时周期数；按实际接入时钟换算，不是毫秒 |
| `0x080` | FRAME_SEQ | RW | 32 位输入帧序号 |
| `0x084` | FRAME_MASK | RW | 32 位匹配像素数 |
| `0x088` | FRAME_XMIN | RW | 16 位 bbox 左边界 |
| `0x08c` | FRAME_YMIN | RW | 16 位 bbox 上边界 |
| `0x090` | FRAME_XMAX | RW | 16 位 bbox 右边界 |
| `0x094` | FRAME_YMAX | RW | 16 位 bbox 下边界 |
| `0x098` | FRAME_FLAGS | RW | bit0 valid、bit1 fresh，其他位必须 0；两位均为 1 才可能计数 |
| `0x09c` | FRAME_JOB | RW | 必须等于当前 ACTIVE_JOB |

| COMMAND 值 | 操作与接受条件 |
|---|---|
| `1` ARM | 仅 inactive、非 busy、配置有效时接受；锁存全部 CFG，active=1，ready/count/age=0，LAST_SEQ=baseline，清 consumed/timed_out/cancelled。活动任务内再次 ARM 返回 SLVERR，不改快照/计数/期限。 |
| `2` CANCEL | 总是接受；撤销当前任务、ready/count，置 cancelled；不产生许可。 |
| `4` CONSUME | 仅 active、ready、非 busy 且尚未到超时边界时接受；产生一次 permit_pulse，PERMIT_COUNT+1，PERMIT_JOB=ACTIVE_JOB，结束本轮并置 consumed。未 ready / 重复消费返回 SLVERR。 |
| `8` FRAME_COMMIT | 仅 active、非 busy、未到超时边界且 FRAME_JOB 匹配时接受；原子提交全部 FRAME staging。重复/倒序帧命令本身为 OKAY，但不影响计数/ready/新鲜度。 |
| `16` CLEAR_FAULT | 清总线 sticky bus_fault；不改变任务、许可、计数或期限。 |

配置有效条件：JOB 非零、ROI min<=max、MIN_MASK>0、MAX_MASK>=MIN_MASK、REQUIRED>0、TIMEOUT>0。其他字段可为 0。成功 ARM 不清 bus_fault；复位或 CLEAR_FAULT 才清除。

## 逐帧和单次任务语义

序号使用 32 位串行数比较：`delta = FRAME_SEQ - LAST_SEQ`，只有 `0 < delta < 2^31` 为更新，支持 `0xffffffff→0`。相差半空间或更大的跳变被忽略；主机不能跨会话复用序号而不重新 ARM。重复和倒序帧不刷新 AGE，不增加计数，也不替换锚点。

严格更新帧先更新 LAST_SEQ。fresh/valid 任一为 0 时清 ready/count/锚点，且不刷新 AGE；均为 1 时 AGE 清零。框颠倒、框不完全位于闭区间 ROI、MASK 不在闭区间 MIN..MAX 时同样清 ready/count/锚点。完全合格的首帧成为本段锚点并计为 1；后续帧四个边界相对这个固定锚点均不超过 JITTER 才递增计数。超过容差时清 ready/count/锚点；该帧不成为新段第一帧，下一合格帧才重新开始。这样缓慢漂移不会无限累计。

计数达到 REQUIRED 后 ready=1，计数饱和；继续输入好帧维持 ready，任何更新坏帧立即撤销 ready。它衡量所选颜色的全局框稳定性，不代表目标类别、实例分离、精度标定或抓取成功。

ARM 的周期 AGE=0；后续活动周期增加 AGE。若周期开始时 `AGE >= TIMEOUT-1`，本周期结束任务并置 timed_out，优先于新帧或 CONSUME；因此不能用恰好超时的帧延长任务。无新帧、重复/倒序帧、fresh/valid 失败最终都会超时。新的 fresh+valid 帧即使 ROI/面积不合格也证明新输入到达并刷新 AGE，但不能形成 ready。

优先级为复位 > busy > CANCEL > 超时 > ARM / FRAME_COMMIT / CONSUME。busy 取消活动任务并置 cancelled，busy 解除后仍需重新 ARM。busy 是操作约束，不是物理急停；本模块没有执行器输出。CANCEL/超时/busy 均不修改 PERMIT_COUNT/PERMIT_JOB。

主机应独占此模块，先核验 ID/VERSION，再写 CFG→ARM→读取 ACTIVE_JOB→逐帧写 FRAME→FRAME_COMMIT→读取 ready。最后 CONSUME 后必须核验 PERMIT_COUNT 恰增一次及 PERMIT_JOB 等于本轮；看到 ready 本身不构成许可。寄存器逐次读取不是原子快照，关键核验应重复检查 job/count。时钟/复位状态变化后必须重新初始化主机任务状态。

此版本仅提供 RTL、主机适配和离线证据；没有改动既有颜色 bit、部署地址、DOFBOT 运行程序或动作参数。
