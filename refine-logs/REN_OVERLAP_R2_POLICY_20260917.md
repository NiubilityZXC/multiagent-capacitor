# R2 全量重叠审计政策

仅落实用户在R2具体批准请求后回复“继续”的范围。保留v1失败目录、50份回执、全部旧seals和29项冻结文件；新建overlap_fleet_20260917_r2。不得使用v1半成品索引、改名v1目录或重写旧BLOCKED，不自动反复重试。

全量数据边界完全沿用旧full-fleet preflight与pipeline：113组/233文件/1633表/104190778行；8行seed、25窗口、32行精确投影候选保证；1000000候选预算、40GiB启动空间门槛，超限fail closed。无模型/API/GPU/数值target/RUL/P2；所有旧禁止标志false。

R2 release先核验35项POLICY、原始批准及本次批准记录，再检查v1失败回执和启动器独立复审。launch不读原始XLS，使用已审durable_local_job启动固定R2 execute命令；child重新核验release并执行旧全量preflight后才读取XLS。无shell拼接、tee或会话stdout管道。supervisor、job目录和数据/公共结果目录只能新建。

job目录在ignored data/raw/ren_scs/overlap_fleet_20260917_r2_job；REQUEST、STARTED、RETURNED、runtime.log均本地保存。PID/STARTED不是成功，必须同时具备RETURNED.child_returncode=0、全量SUMMARY/COMPLETE及独立结果对账。supervisor强杀或宿主重启仍可导致无RETURNED，此时保留未知/失败，不自动补成成功。

任何新入口改动必须整体集成复审后生成独立release；本政策本身不构成pre-run PASS。全量完成仍只是overlap observations，不能自动授予Data Gate、设备身份或目标资格。
