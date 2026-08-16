# -*- coding: utf-8 -*-
"""Pipeline 配置：从 TOML 文件加载，路径统一相对仓库根解析。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class PipelineConfigError(ValueError):
    """Pipeline 配置非法。"""


class RawDataUnavailableError(FileNotFoundError):
    """全量原始数据不存在（公开 clone 环境常见）。"""


@dataclass
class PipelineConfig:
    """多源数据自动化 Pipeline 配置。"""

    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    xhs_path: Path = field(default_factory=lambda: Path("analysis/V25_Full_Mapping/xhs_to_amap_full_mapped.csv"))
    dp_path: Path = field(default_factory=lambda: Path("analysis/V25_Full_Mapping/dianping_to_amap_full_mapped.csv"))
    amap_path: Path = field(default_factory=lambda: Path("analysis/V27_Amap_Expansion/amap_poi_master_unlimited.csv"))
    ctrip_path: Path = field(default_factory=lambda: Path("00_原始基座数据/携程经纬度.csv"))
    out_dir: Path = field(default_factory=lambda: Path("analysis/V30_Multi_Source_Fusion_R2"))
    db_path: Path = field(default_factory=lambda: Path("data/platform.db"))
    scales: List[int] = field(default_factory=lambda: [1, 3, 5])
    main_scale: int = 3
    method: str = "equal"
    parity_mode: bool = True

    @classmethod
    def from_toml(cls, path: str | Path) -> "PipelineConfig":
        """从 TOML 读取配置。所有相对路径基于仓库根解析。"""
        path = Path(path)
        if not path.exists():
            raise PipelineConfigError(f"配置文件不存在: {path}")
        with path.open("rb") as fh:
            raw: Dict[str, Any] = tomllib.load(fh)

        base_dir = path.resolve().parent.parent
        io = raw.get("io", {})
        pipeline = raw.get("pipeline", {})

        def resolve(p: Any) -> Path:
            p = Path(str(p))
            return p if p.is_absolute() else (base_dir / p).resolve()

        cfg = cls(
            project_root=base_dir,
            xhs_path=resolve(io["xhs"]),
            dp_path=resolve(io["dp"]),
            amap_path=resolve(io["amap"]),
            ctrip_path=resolve(io["ctrip"]),
            out_dir=resolve(io.get("out_dir", "analysis/V30_Multi_Source_Fusion_R2")),
            db_path=resolve(io.get("db_path", "data/platform.db")),
            scales=[int(x) for x in pipeline.get("scales", [1, 3, 5])],
            main_scale=int(pipeline.get("main_scale", 3)),
            method=str(pipeline.get("method", "equal")),
            parity_mode=bool(pipeline.get("parity_mode", True)),
        )

        if cfg.main_scale not in cfg.scales:
            raise PipelineConfigError(f"main_scale={cfg.main_scale} 不在 scales={cfg.scales} 中")
        if cfg.method not in ("equal", "entropy"):
            raise PipelineConfigError("method 仅支持 equal 或 entropy")
        return cfg

    def missing_inputs(self) -> List[Path]:
        return [p for p in (self.xhs_path, self.dp_path, self.amap_path, self.ctrip_path) if not p.exists()]
