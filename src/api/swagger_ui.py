# -*- coding: utf-8 -*-
"""自定义 Swagger UI：Streamlit 风格 + 中英切换 + 默认折叠 Schema。

设计说明：
- 使用 FastAPI 官方 get_swagger_ui_html() 生成页面，再注入 CSS/JS；
- 服务端按 ?lang=zh|en 渲染标题与描述，前端按钮切换 URL；
- 静态 UI 标签通过字典 + MutationObserver 动态翻译；
- 不修改 OpenAPI schema，不影响 API 契约。
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

_STREAMLIT_CSS = """
:root {
  --st-red: #FF4B4B;
  --st-bg: #FFFFFF;
  --st-page: #F8F9FB;
  --st-text: #262730;
  --st-muted: #555867;
  --st-border: #E6EAF2;
  --st-radius: 10px;
}
html, body { background: var(--st-page) !important; }
body { margin: 0; }
.swagger-ui {
  font-family: "Source Sans Pro", "Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif !important;
  color: var(--st-text);
}
.swagger-ui .topbar {
  background: var(--st-bg);
  border-bottom: 1px solid var(--st-border);
  box-shadow: 0 1px 2px rgba(38, 39, 48, 0.04);
  padding: 8px 0;
}
.swagger-ui .topbar .download-url-wrapper { display: none !important; }
.swagger-ui .info { margin: 26px 0 20px; }
.swagger-ui .info .title {
  color: var(--st-text);
  font-size: 24px;
  font-weight: 700;
}
.swagger-ui .info .base-url { color: var(--st-muted); }
.swagger-ui .info .description .renderedMarkdown { color: var(--st-muted); }
.swagger-ui .scheme-container {
  background: var(--st-bg);
  border: 1px solid var(--st-border);
  border-radius: var(--st-radius);
  box-shadow: 0 1px 3px rgba(38, 39, 48, 0.06);
  margin: 0 0 22px;
  padding: 14px 20px;
}
.swagger-ui .opblock-tag {
  color: var(--st-text);
  border-bottom: 1px solid var(--st-border);
  font-weight: 650;
}
.swagger-ui .opblock {
  background: var(--st-bg);
  border: 1px solid var(--st-border);
  border-radius: var(--st-radius);
  box-shadow: 0 1px 3px rgba(38, 39, 48, 0.06);
  margin: 0 0 14px;
  overflow: hidden;
}
.swagger-ui .opblock .opblock-summary {
  border: none;
  border-radius: 0;
  padding: 10px 16px;
}
.swagger-ui .opblock-summary-method {
  border-radius: 6px;
  font-size: 12px;
  min-width: 76px;
}
.swagger-ui .btn {
  border-radius: 8px;
  box-shadow: none;
  font-weight: 600;
}
.swagger-ui .btn.authorize {
  background: var(--st-bg);
  border-color: var(--st-red);
  color: var(--st-red);
}
.swagger-ui .btn.authorize:hover { background: #FFF1F1; }
.swagger-ui .btn.execute { background: var(--st-red); color: #fff; }
.swagger-ui .btn.execute:hover { background: #E94545; }
.swagger-ui .btn.cancel { color: var(--st-muted); }
.swagger-ui input[type="text"], .swagger-ui select {
  border-radius: 8px !important;
  border-color: var(--st-border) !important;
}
.swagger-ui section.models {
  background: var(--st-bg);
  border: 1px solid var(--st-border);
  border-radius: var(--st-radius);
}
.swagger-ui .model-box { background: var(--st-page); border-radius: 8px; }
.swagger-ui .model-title { color: var(--st-text); }
.swagger-ui .opblock-description-wrapper,
.swagger-ui .opblock-external-docs-wrapper,
.swagger-ui .opblock-title_normal { color: var(--st-muted); }
.lang-toggle {
  position: fixed;
  top: 13px;
  right: 24px;
  z-index: 1000;
  background: var(--st-bg);
  border: 1px solid var(--st-red);
  border-radius: 8px;
  color: var(--st-red);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 14px;
}
.lang-toggle:hover { background: #FFF1F1; }
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
  Object.keys(DICT).forEach(function (key) { EN_KEYS[key] = true; });

  function applyPageMeta() {
    var titleNode = document.querySelector(".swagger-ui .info .title");
    if (titleNode) { titleNode.textContent = PAGE_TITLES[LANG]; }
    var descNode = document.querySelector(".swagger-ui .info .description");
    if (descNode) {
      var html = PAGE_DESCRIPTIONS[LANG].split("\n\n").filter(Boolean)
        .map(function (part) { return "<p>" + part + "</p>"; }).join("");
      descNode.innerHTML = html;
    }
  }

  function walk(node) {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      var text = node.textContent.trim();
      if (LANG === "zh" && DICT[text]) { node.textContent = " " + DICT[text] + " "; }
      if (LANG === "en" && EN_KEYS[text] === undefined) {
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

  function translatePage() { walk(document.body); }

  function addToggle() {
    var btn = document.createElement("button");
    btn.className = "lang-toggle";
    btn.type = "button";
    btn.textContent = LANG === "zh" ? "EN" : "中文";
    btn.addEventListener("click", function () {
      var url = new URL(window.location.href);
      url.searchParams.set("lang", OTHER);
      window.location.href = url.toString();
    });
    document.body.appendChild(btn);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.documentElement.setAttribute("lang", LANG);
    addToggle();
    applyPageMeta();
    translatePage();
    var observer = new MutationObserver(function () {
      translatePage();
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  });
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
    html_content = html_content.replace("</head>", f"<style>{_STREAMLIT_CSS}</style></head>")
    js = (
        _TOGGLE_JS.replace("__LANG__", lang)
        .replace("__DICT__", json.dumps(_TRANSLATIONS, ensure_ascii=False))
        .replace("__PAGE_TITLES__", json.dumps(TITLES, ensure_ascii=False))
        .replace("__PAGE_DESCRIPTIONS__", json.dumps(DESCRIPTIONS, ensure_ascii=False))
    )
    html_content = html_content.replace("</body>", f"<script>{js}</script></body>")
    return HTMLResponse(content=html_content)


def register_docs_routes(app: FastAPI) -> None:
    """注册自定义 /docs 与 OAuth 重定向页。"""

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html(lang: str = Query("zh", pattern="^(zh|en)$")) -> HTMLResponse:
        return _render(lang, app)

    @app.get("/docs/oauth2-redirect", include_in_schema=False)
    async def swagger_oauth_redirect() -> HTMLResponse:
        return get_swagger_ui_oauth2_redirect_html()
