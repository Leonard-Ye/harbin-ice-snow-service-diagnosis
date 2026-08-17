# -*- coding: utf-8 -*-
"""自定义 Swagger UI：dashboard 同源设计语言。

设计 token 对齐 dashboard/ui_theme.py 与 .streamlit/config.toml：
- 默认浅色（Streamlit Light 主题），支持手动切换深色；
- 冰晶蓝主色 + 极光紫辅色 + 玻璃拟态卡片；
- Inter 字体 + JetBrains Mono 代码字体（Google Fonts，离线自动回退系统字体）；
- 中英切换采用服务端 ?lang=zh|en + 前端静态标签字典翻译。
"""
from __future__ import annotations

import json

from fastapi import FastAPI, Query
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import HTMLResponse

TITLES = {
    "zh": "智能多源数据自动化与分析平台 · API 文档",
    "en": "Intelligent Multi-Source Data Platform · API Docs",
}

DESCRIPTIONS = {
    "zh": (
        "多源数据自动化与分析平台 API。\n\n"
        "提供锚点指标、数据质量审计、自动化 Pipeline 触发、通用表格体检与报表下载。\n\n"
        "所有指标均为 20 个核心锚点样本内 Z-score 相对值（0 = 样本均值）。"
    ),
    "en": (
        "API for the Intelligent Multi-Source Data Automation & Analysis Platform.\n\n"
        "Provides anchor metrics, data-quality auditing, automated pipeline runs, "
        "generic table profiling, and report downloads.\n\n"
        "All indices are relative Z-scores within the 20 core anchor sample (0 = sample mean)."
    ),
}

_FONT_LINKS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
"""

# Dashboard Light / Dark 双主题 token
_DASHBOARD_CSS = """
:root {
  --bg: #F8FAFC;
  --panel: #FFFFFF;
  --panel2: #F1F5F9;
  --text: #0F172A;
  --muted: #64748B;
  --accent: #0284C7;
  --accent-soft: rgba(2, 132, 199, 0.08);
  --accent2: #9333EA;
  --border: #E2E8F0;
  --grid: rgba(15, 23, 42, 0.05);
  --card-bg: rgba(255, 255, 255, 0.92);
  --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06);
  --get: #059669;
  --get-bg: #ECFDF5;
  --post: #0284C7;
  --post-bg: #EFF8FF;
  --put: #D97706;
  --put-bg: #FFF7ED;
  --delete: #DC2626;
  --delete-bg: #FEF2F2;
  --patch: #7C3AED;
  --patch-bg: #F5F3FF;
}
html[data-theme="dark"] {
  --bg: #090D16;
  --panel: #121722;
  --panel2: #182030;
  --text: #F1F5F9;
  --muted: #94A3B8;
  --accent: #38BDF8;
  --accent-soft: rgba(56, 189, 248, 0.10);
  --accent2: #C084FC;
  --border: #1E293B;
  --grid: rgba(255, 255, 255, 0.05);
  --card-bg: rgba(18, 23, 34, 0.88);
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.40);
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.35);
  --get: #4ADE80;
  --get-bg: rgba(74, 222, 128, 0.12);
  --post: #38BDF8;
  --post-bg: rgba(56, 189, 248, 0.12);
  --put: #FB923C;
  --put-bg: rgba(251, 146, 60, 0.12);
  --delete: #F87171;
  --delete-bg: rgba(248, 113, 113, 0.12);
  --patch: #C084FC;
  --patch-bg: rgba(192, 132, 252, 0.12);
}

html, body { background: var(--bg) !important; margin: 0; }
body {
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.swagger-ui {
  color: var(--text);
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif !important;
}
.swagger-ui .wrapper { max-width: 1320px; margin: 0 auto; padding: 0 24px; }

/* ---------- Topbar：玻璃拟态粘性栏 ---------- */
.swagger-ui .topbar {
  background: var(--card-bg) !important;
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  padding: 9px 0;
}
.swagger-ui .topbar .download-url-wrapper { display: none !important; }

/* ---------- Info：渐变 Hero 卡片 ---------- */
.swagger-ui .info {
  margin: 28px 0 22px;
  padding: 24px 28px;
  background: linear-gradient(135deg, var(--accent-soft) 0%, rgba(147, 51, 234, 0.03) 100%);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
}
.swagger-ui .info .title {
  color: var(--text);
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.4px;
  margin-bottom: 10px;
}
.swagger-ui .info .base-url { color: var(--muted); font-family: "JetBrains Mono", monospace; }
.swagger-ui .info .description .renderedMarkdown,
.swagger-ui .info .description .renderedMarkdown p {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}

/* ---------- Scheme 容器 ---------- */
.swagger-ui .scheme-container {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  margin: 0 0 22px;
  padding: 14px 20px;
}

/* ---------- 接口卡片：Bento Card ---------- */
.swagger-ui .opblock-tag {
  color: var(--text);
  border-bottom: 1px solid var(--border);
  font-size: 18px;
  font-weight: 700;
  padding-bottom: 10px;
}
.swagger-ui .opblock-tag small { color: var(--muted); font-weight: 500; }
.swagger-ui .opblock {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  margin: 0 0 14px;
  overflow: hidden;
  transition: box-shadow .18s ease, transform .18s ease;
}
.swagger-ui .opblock:hover {
  box-shadow: var(--shadow);
  transform: translateY(-1px);
}
.swagger-ui .opblock .opblock-summary { border: none; padding: 12px 18px; }
.swagger-ui .opblock-summary-method {
  border-radius: 8px;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  font-weight: 600;
  min-width: 78px;
  text-shadow: none;
}
.swagger-ui .opblock.opblock-get .opblock-summary-method { background: var(--get-bg); color: var(--get); }
.swagger-ui .opblock.opblock-post .opblock-summary-method { background: var(--post-bg); color: var(--post); }
.swagger-ui .opblock.opblock-put .opblock-summary-method { background: var(--put-bg); color: var(--put); }
.swagger-ui .opblock.opblock-delete .opblock-summary-method { background: var(--delete-bg); color: var(--delete); }
.swagger-ui .opblock.opblock-patch .opblock-summary-method { background: var(--patch-bg); color: var(--patch); }
.swagger-ui .opblock-summary-path {
  color: var(--text);
  font-family: "JetBrains Mono", monospace;
  font-weight: 500;
}
.swagger-ui .opblock-description-wrapper,
.swagger-ui .opblock-external-docs-wrapper,
.swagger-ui .opblock-title_normal,
.swagger-ui .opblock-section-header h4,
.swagger-ui .tab li button.tablinks,
.swagger-ui .response-col_status,
.swagger-ui table thead tr td { color: var(--text); }
.swagger-ui .opblock-section-header {
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 10px;
}

/* ---------- 按钮 ---------- */
.swagger-ui .btn {
  border-radius: 10px;
  box-shadow: none;
  font-weight: 600;
  transition: filter .15s ease, background .15s ease;
}
.swagger-ui .btn.authorize {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
}
.swagger-ui .btn.authorize:hover { background: var(--accent-soft); }
.swagger-ui .btn.execute { background: var(--accent); border-color: var(--accent); color: #fff; }
.swagger-ui .btn.execute:hover { filter: brightness(1.08); }
.swagger-ui .btn.cancel { color: var(--muted); }

/* ---------- 输入 / 表格 / 模型 ---------- */
.swagger-ui input[type="text"], .swagger-ui select {
  background: var(--panel);
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
}
.swagger-ui .body-textarea { border-radius: 10px; border-color: var(--border); }
.swagger-ui table { border-color: var(--border); }
.swagger-ui table tbody tr td { border-color: var(--border); color: var(--text); }
.swagger-ui section.models {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
}
.swagger-ui .model-box { background: var(--panel2); border-radius: 10px; }
.swagger-ui .model-title, .swagger-ui .prop-name { color: var(--accent); }
.swagger-ui .prop-type, .swagger-ui .prop-format { color: var(--accent2); }
.swagger-ui table.model tbody tr td { color: var(--text); }
.swagger-ui .dialog-ux .modal-ux {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
}
.swagger-ui .dialog-ux .modal-ux-header h3 { color: var(--text); }

/* ---------- 右上角控制组：语言 + 主题 ---------- */
.swagger-controls {
  position: fixed;
  top: 12px;
  right: 22px;
  z-index: 9999;
  display: flex;
  gap: 8px;
  align-items: center;
}
.ctrl-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
  color: var(--text);
  cursor: pointer;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px;
  font-weight: 600;
  padding: 7px 12px;
  transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
}
.ctrl-btn:hover { border-color: var(--accent); box-shadow: var(--shadow); background: var(--accent-soft); }
.ctrl-btn svg { width: 15px; height: 15px; stroke: currentColor; }
"""

_ICON_GLOBE = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M2 12h20"></path><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>'
_ICON_SUN = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"></path></svg>'
_ICON_MOON = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"></path></svg>'

_TRANSLATIONS = {
    "Authorize": "授权",
    "Authorizations": "授权管理",
    "Available authorizations": "可用授权",
    "Cancel": "取消",
    "Clear": "清除",
    "Close": "关闭",
    "Code": "代码",
    "Collapse all": "折叠全部",
    "Copied": "已复制",
    "Copy": "复制",
    "Default": "默认",
    "Description": "描述",
    "Details": "详情",
    "Download": "下载",
    "Example Value": "示例值",
    "Execute": "执行",
    "Expand all": "展开全部",
    "Logout": "退出登录",
    "Media type": "媒体类型",
    "Model": "模型",
    "Models": "模型",
    "No parameters": "无参数",
    "Parameters": "参数",
    "Request body": "请求体",
    "Request URL": "请求地址",
    "Response body": "响应体",
    "Responses": "响应",
    "Schema": "模型",
    "Schemas": "模型",
    "Send empty value": "发送空值",
    "Server response": "服务器响应",
    "Server variables": "服务器变量",
    "Servers": "服务器",
    "Try it out": "试一试",
}

_TOGGLE_JS = """
(function () {
  var LANG = "__LANG__";
  var OTHER = LANG === "zh" ? "en" : "zh";
  var DICT = __DICT__;
  var PAGE_TITLES = __PAGE_TITLES__;
  var PAGE_DESCRIPTIONS = __PAGE_DESCRIPTIONS__;
  var ICON_GLOBE = "__ICON_GLOBE__";
  var ICON_SUN = "__ICON_SUN__";
  var ICON_MOON = "__ICON_MOON__";
  var EN_KEYS = {};
  var observer = null;
  Object.keys(DICT).forEach(function (key) { EN_KEYS[key] = true; });

  function applyPageMeta() {
    var titleNode = document.querySelector(".swagger-ui .info .title");
    if (titleNode) { titleNode.textContent = PAGE_TITLES[LANG]; }
    var descNode = document.querySelector(".swagger-ui .info .description");
    if (descNode) {
      descNode.innerHTML = PAGE_DESCRIPTIONS[LANG].split("\\n\\n").filter(Boolean)
        .map(function (part) { return "<p>" + part + "</p>"; }).join("");
    }
  }

  function walk(node) {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      var text = node.textContent.trim();
      if (LANG === "zh" && DICT[text]) { node.textContent = " " + DICT[text] + " "; }
      if (LANG === "en" && !EN_KEYS[text]) {
        Object.keys(DICT).forEach(function (en) {
          if (DICT[en] === text) { node.textContent = " " + en + " "; }
        });
      }
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    var tag = node.tagName;
    if (tag !== "SCRIPT" && tag !== "STYLE" && tag !== "TEXTAREA" && tag !== "INPUT") {
      node.childNodes.forEach(walk);
    }
  }

  function translatePage() { walk(document.body || document.documentElement); }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("swagger-theme", theme); } catch (e) {}
    var themeBtn = document.getElementById("theme-toggle");
    if (themeBtn) {
      themeBtn.innerHTML = (theme === "light" ? ICON_MOON : ICON_SUN) +
        "<span>" + (theme === "light" ? "深色" : "浅色") + "</span>";
    }
  }

  function ensureControls() {
    if (document.getElementById("swagger-controls")) return;
    var controls = document.createElement("div");
    controls.id = "swagger-controls";
    controls.className = "swagger-controls";

    var langBtn = document.createElement("button");
    langBtn.id = "lang-toggle";
    langBtn.type = "button";
    langBtn.className = "ctrl-btn";
    langBtn.innerHTML = ICON_GLOBE + "<span>" + (LANG === "zh" ? "EN" : "中文") + "</span>";
    langBtn.addEventListener("click", function () {
      var url = new URL(window.location.href);
      url.searchParams.set("lang", OTHER);
      window.location.href = url.toString();
    });

    var themeBtn = document.createElement("button");
    themeBtn.id = "theme-toggle";
    themeBtn.type = "button";
    themeBtn.className = "ctrl-btn";
    themeBtn.addEventListener("click", function () {
      applyTheme(currentTheme() === "light" ? "dark" : "light");
    });

    controls.appendChild(langBtn);
    controls.appendChild(themeBtn);
    (document.body || document.documentElement).appendChild(controls);
    applyTheme(currentTheme());
  }

  function startObserver() {
    if (observer || !document.body) return;
    observer = new MutationObserver(function () {
      ensureControls();
      translatePage();
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  function init() {
    document.documentElement.setAttribute("lang", LANG);
    applyPageMeta();
    ensureControls();
    translatePage();
    startObserver();
  }

  function boot() {
    if (document.body) { init(); }
    else { setTimeout(boot, 20); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
  setTimeout(init, 700);
  setTimeout(init, 1800);
})();
"""


def _render(lang: str, app: FastAPI) -> HTMLResponse:
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=TITLES[lang],
        swagger_favicon_url="/static/swagger-favicon.svg",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 0,
            "docExpansion": "list",
            "displayRequestDuration": True,
            "filter": True,
            "showExtensions": True,
        },
    )
    html_content = html.body.decode("utf-8") if isinstance(html.body, bytes) else str(html.body)
    html_content = html_content.replace("</head>", f"{_FONT_LINKS}<style>{_DASHBOARD_CSS}</style></head>")
    js = (
        _TOGGLE_JS.replace("__LANG__", lang)
        .replace("__DICT__", json.dumps(_TRANSLATIONS, ensure_ascii=False))
        .replace("__PAGE_TITLES__", json.dumps(TITLES, ensure_ascii=False))
        .replace("__PAGE_DESCRIPTIONS__", json.dumps(DESCRIPTIONS, ensure_ascii=False))
        .replace("__ICON_GLOBE__", _ICON_GLOBE)
        .replace("__ICON_SUN__", _ICON_SUN)
        .replace("__ICON_MOON__", _ICON_MOON)
    )
    html_content = html_content.replace("</body>", f"<script>{js}</script></body>")
    return HTMLResponse(content=html_content, headers={"Cache-Control": "no-store"})


def register_docs_routes(app: FastAPI) -> None:
    """注册自定义 /docs 与 OAuth 重定向页。"""

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html(lang: str = Query("zh", pattern="^(zh|en)$")) -> HTMLResponse:
        return _render(lang, app)

    @app.get("/docs/oauth2-redirect", include_in_schema=False)
    async def swagger_oauth_redirect() -> HTMLResponse:
        return get_swagger_ui_oauth2_redirect_html()
