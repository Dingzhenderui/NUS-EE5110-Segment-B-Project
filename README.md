# NUS-EE5110-Segment-B-Project

EE5110 事件相机模拟器。

项目读取一个高帧率视频，根据相邻帧的对数亮度变化生成事件列表，同时输出事件快照和事件叠加视频。

```text
高帧率视频 + 模拟参数
          ↓
      事件模拟器
          ↓
完整事件列表 + 事件快照 + 原视频事件叠加
```

## 项目目录

```text
NUS-EE5110-Segment-B-Project/
├─ pyproject.toml
├─ README.md
├─ docs/
│  └─ 性能问题分析与优化方案.md
├─ input/                         # 本地输入视频，全部由 Git 忽略
├─ output/                        # 运行生成，Git 忽略
└─ src/
   └─ event_camera_sim/
      ├─ __main__.py              # 命令入口
      ├─ config.py                # 用户参数
      ├─ events.py                # 事件生成算法
      ├─ video.py                 # 视频选择和读取
      ├─ storage.py               # HDF5 流式存储
      ├─ visualization.py         # 快照和叠加视频
      └─ pipeline.py              # 完整处理流程
```
