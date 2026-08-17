# -*- coding: utf-8 -*-
"""自定义 Swagger UI：dashboard 同款主题 + 中英切换 + 默认折叠 Schema。

主题 token 与 dashboard/ui_theme.py 保持一致（冰晶蓝 / 极光紫 / 玻璃拟态），
通过 prefers-color-scheme 自动匹配深/浅模式。
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

# 与 dashboard/ui_theme.py DARK / LIGHT token 对齐
_DASHBOARD_CSS = """
:root {
  --bg: #0B0F17;
  --panel: #131B2A;
  --panel2: #1A2436;
  --text: #F8FAFC;
  --muted: #94A3B8;
  --accent: #38BDF8;
  --accent2: #C084FC;
  --border: rgba(255, 255, 255, 0.08);
  --grid: rgba(255, 255, 255, 0.05);
  --card-bg: rgba(19, 27, 42, 0.75);
  --shadow: 0 8px 32px rgba(0, 0, 0, 0.40);
  --glow: 0 0 20px rgba(56, 189, 248, 0.20);
  --get: #34D399;
  --post: #38BDF8;
  --put: #FB923C;
  --delete: #F87171;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #F8FAFC;
    --panel: #FFFFFF;
    --panel2: #F1F5F9;
    --text: #0F172A;
    --muted: #64748B;
    --accent: #0284C7;
    --accent2: #9333EA;
    --border: rgba(0, 0, 0, 0.06);
    --grid: rgba(0, 0, 0, 0.05);
    --card-bg: rgba(255, 255, 255, 0.90);
    --shadow: 0 4px 20px rgba(15, 23, 42, 0.06);
    --glow: 0 0 15px rgba(2, 132, 199, 0.15);
    --get: #16A34A;
    --post: #0284C7;
    --put: #EA580C;
    --delete: #DC2626;
  }
}

html, body { background: var(--bg) !important; }
body { margin: 0; }
.swagger-ui {
  color: var(--text);
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif !important;
}
.swagger-ui .topbar {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow);
  padding: 8px 0;
}
.swagger-ui .topbar .download-url-wrapper { display: none !important; }
.swagger-ui .info { margin: 26px 0 22px; }
.swagger-ui .info .title { color: var(--text); font-size: 24px; font-weight: 700; }
.swagger-ui .info .base-url { color: var(--muted); }
.swagger-ui .info .description .renderedMarkdown,
.swagger-ui .info .description .renderedMarkdown p { color: var(--muted); }

.swagger-ui .scheme-container {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.06) 0%, rgba(192, 132, 252, 0.03) 100%);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow);
  margin: 0 0 22px;
  padding: 14px 20px;
}
.swagger-ui .opblock-tag {
  color: var(--text);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
}
.swagger-ui .opblock-tag-section .opblock-tag small { color: var(--muted); }
.swagger-ui .opblock {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow);
  margin: 0 0 14px;
  overflow: hidden;
}
.swagger-ui .opblock .opblock-summary { border: none; padding: 10px 16px; }
.swagger-ui .opblock-summary-method {
  border-radius: 6px;
  font-size: 12px;
  min-width: 76px;
}
.swagger-ui .opblock.opblock-get .opblock-summary-method { background: var(--get); }
.swagger-ui .opblock.opblock-post .opblock-summary-method { background: var(--post); }
.swagger-ui .opblock.opblock-put .opblock-summary-method { background: var(--put); }
.swagger-ui .opblock.opblock-delete .opblock-summary-method { background: var(--delete); }
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
  border-radius: 8px;
}
.swagger-ui .btn {
  border-radius: 8px;
  box-shadow: none;
  font-weight: 600;
}
.swagger-ui .btn.authorize {
  background: transparent;
  border-color: var(--accent);
  color: var(--accent);
}
.swagger-ui .btn.authorize:hover { background: rgba(56, 189, 248, 0.10); }
.swagger-ui .btn.execute { background: var(--accent); color: #0B0F17; }
.swagger-ui .btn.execute:hover { filter: brightness(1.08); }
.swagger-ui .btn.cancel { color: var(--muted); }
.swagger-ui input[type="text"], .swagger-ui select {
  background: var(--panel);
  border-color: var(--border) !important;
  border-radius: 8px !important;
  color: var(--text) !important;
}
.swagger-ui section.models {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow);
}
.swagger-ui .model-box { background: var(--panel2); border-radius: 8px; }
.swagger-ui .model-title, .swagger-ui .prop-name { color: var(--accent); }
.swagger-ui .prop-type, .swagger-ui .prop-format { color: var(--accent2); }
.swagger-ui table.model tbody tr td { color: var(--text); }
.swagger-ui .dialog-ux .modal-ux {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow);
}
.swagger-ui .dialog-ux .modal-ux-header h3 { color: var(--text); }

.lang-toggle {
  position: fixed;
  top: 12px;
  right: 22px;
  z-index: 9999;
  background: var(--panel);
  border: 1px solid var(--accent);
  border-radius: 8px;
  box-shadow: var(--glow);
  color: var(--accent);
  cursor: pointer;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px;
  font-weight: 700;
  padding: 6px 14px;
}
.lang-toggle:hover { background: rgba(56, 189, 248, 0.12); }
"""

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

  function ensureToggle() {
    if (document.getElementById("lang-toggle")) return;
    var btn = document.createElement("button");
    btn.id = "lang-toggle";
    btn.type = "button";
    btn.className = "lang-toggle";
    btn.textContent = LANG === "zh" ? "EN" : "中文";
    btn.setAttribute("aria-label", LANG === "zh" ? "Switch to English" : "切换为中文");
    btn.addEventListener("click", function () {
      var url = new URL(window.location.href);
      url.searchParams.set("lang", OTHER);
      window.location.href = url.toString();
    });
    (document.body || document.documentElement).appendChild(btn);
  }

  function startObserver() {
    if (observer || !document.body) return;
    observer = new MutationObserver(function () {
      ensureToggle();
      applyPageMeta();
      translatePage();
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  function init() {
    document.documentElement.setAttribute("lang", LANG);
    ensureToggle();
    applyPageMeta();
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
  // Swagger UI 异步渲染兜底：即使错过 DOMContentLoaded 也会重试
  setTimeout(init, 800);
  setTimeout(init, 2200);
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
    html_content = html_content.replace("</head>", f"<style>{_DASHBOARD_CSS}</style></head>")
    js = (
        _TOGGLE_JS.replace("__LANG__", lang)
        .replace("__DICT__", json.dumps(_TRANSLATIONS, ensure_ascii=False))
        .replace("__PAGE_TITLES__", json.dumps(TITLES, ensure_ascii=False))
        .replace("__PAGE_DESCRIPTIONS__", json.dumps(DESCRIPTIONS, ensure_ascii=False))
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
