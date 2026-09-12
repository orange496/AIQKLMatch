"""
Swagger UI 汉化模块
===================

FastAPI 自带的接口文档（Swagger UI）界面文字全部是英文，
本模块负责把它整体变成中文，分两层处理：

1. **OpenAPI 结构层**：把 FastAPI 自动生成的英文内容改名 / 改描述，
   例如 "Successful Response" → "成功"、"Validation Error" → "参数校验失败"、
   组件 HTTPValidationError → 参数校验错误（含 $ref 引用同步替换）。

2. **页面渲染层**：用自定义的 /docs 路由替换默认路由，
   在页面里注入一小段脚本，用 MutationObserver 把 Swagger UI
   动态渲染出来的按钮、表头、提示语等英文实时换成中文。
   脚本会跳过 textarea / pre / code 等区域，避免改坏 JSON 示例数据。

用法（main.py）：

    from fastapi import FastAPI
    from docs_zh import setup_chinese_docs

    app = FastAPI(..., docs_url=None, redoc_url=None)   # 关掉英文默认文档
    setup_chinese_docs(app)                            # 挂上中文文档
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

__all__ = ["setup_chinese_docs"]

# --------------------------------------------------------------------------
# 一、静态资源（优先用本地 static/ 目录，答辩断网也能打开文档；没有则用 CDN）
# --------------------------------------------------------------------------
_SWAGGER_VERSION = "5"
_CDN_BASE = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{_SWAGGER_VERSION}"
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _asset(filename: str) -> str:
    """本地有同名文件就用本地，否则回落到 CDN。"""
    if os.path.exists(os.path.join(_STATIC_DIR, filename)):
        return f"/static/{filename}"
    return f"{_CDN_BASE}/{filename}"


# --------------------------------------------------------------------------
# 二、OpenAPI 结构汉化
# --------------------------------------------------------------------------
# 组件（Schemas）改名表：英文原名 -> 中文名
_SCHEMA_RENAME = {
    "HTTPValidationError": "参数校验错误",
    "ValidationError": "字段校验错误",
    "Body_train_ai_train_post": "训练AI请求体",
}

# 响应状态码描述汉化表
_RESPONSE_DESC = {
    "200": "成功",
    "201": "创建成功",
    "403": "没有权限",
    "404": "资源不存在",
    "422": "请求参数校验失败",
    "500": "服务器内部错误",
}


def _rename_refs(node, renames: dict[str, str]) -> None:
    """递归遍历 OpenAPI 结构，同步替换 $ref 里的组件名。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                prefix, _, name = value.rpartition("/")
                if name in renames:
                    node[key] = f"{prefix}/{renames[name]}"
            else:
                _rename_refs(value, renames)
    elif isinstance(node, list):
        for item in node:
            _rename_refs(item, renames)


def _localize_openapi(schema: dict) -> None:
    """就地汉化 OpenAPI 结构。"""
    # 1) 组件改名
    #    注意：Pydantic 会额外写入 "title" 字段，Swagger UI 优先显示 title，
    #    所以改名时必须把 title 一起改掉，否则界面上还是显示英文原名。
    schemas = schema.get("components", {}).get("schemas", {})
    for old, new in _SCHEMA_RENAME.items():
        if old in schemas:
            renamed = schemas.pop(old)
            if isinstance(renamed, dict) and renamed.get("title") == old:
                renamed["title"] = new
            schemas[new] = renamed
    _rename_refs(schema, _SCHEMA_RENAME)

    # 2) 状态码描述汉化
    http_methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in http_methods or not isinstance(operation, dict):
                continue
            for code, response in operation.get("responses", {}).items():
                if isinstance(response, dict) and code in _RESPONSE_DESC:
                    response["description"] = _RESPONSE_DESC[code]


def _build_openapi(app: FastAPI) -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    _localize_openapi(schema)
    app.openapi_schema = schema
    return schema


# --------------------------------------------------------------------------
# 三、页面文字汉化（样式 + 脚本，注入到 /docs 页面里）
# --------------------------------------------------------------------------
# Swagger UI 有些英文是用 CSS 伪元素 ::after 生成的（改 DOM 文字没用），
# 例如必填角标 "required"，只能用 CSS 覆盖。
_I18N_CSS = """
.parameter__name.required:after,
.opblock-title.required:after {
  content: "必填" !important;
}
"""

_I18N_JS = r"""
(function () {
  "use strict";

  // 英文 -> 中文 对照表
  var DICT = {
    // —— 顶部 / 通用 ——
    "Swagger UI": "接口文档",
    "Explore": "探索",
    "Authorize": "授权",
    "Close": "关闭",
    "Logout": "注销",
    "Loading...": "加载中…",
    "Select a definition": "选择定义",
    "Servers": "服务器",
    "No servers": "无服务器",
    "Server variables": "服务器变量",
    "Base URL": "基础地址",
    "Filter by tag": "按标签筛选",

    // —— 接口列表 ——
    "Operations": "接口列表",
    "Expand operation": "展开接口",
    "Collapse operation": "收起接口",
    "Expand all": "全部展开",
    "Collapse all": "全部收起",
    "Deprecated": "已废弃",
    "Undocumented": "无文档",

    // —— 参数 ——
    "Parameters": "请求参数",
    "No parameters": "无参数",
    "path": "路径参数",
    "query": "查询参数",
    "Request body": "请求体",
    "Media type": "媒体类型",
    "Controls Accept header.": "控制 Accept 请求头",
    "Name": "名称",
    "Description": "说明",
    "Required": "必填",
    "required": "必填",
    "Type": "类型",
    "Schema": "数据结构",
    "Example Value": "示例值",
    "Edit Value": "编辑值",
    "Schema value": "结构值",
    "Model": "模型",
    "Value": "值",
    "Default value": "默认值",
    "Default": "默认值",
    "Enum": "枚举值",
    "Pattern": "正则表达式",
    "Minimum": "最小值",
    "Maximum": "最大值",
    "Min Length": "最小长度",
    "Max Length": "最大长度",
    "Properties": "属性",
    "Additional properties": "其他属性",
    "Items": "元素",
    "Read only": "只读",
    "Write only": "只写",

    // —— 执行 / 响应 ——
    "Try it out": "试一试",
    "Cancel": "取消",
    "Clear": "清空",
    "Execute": "执行",
    "Reset": "重置",
    "Request URL": "请求地址",
    "Server response": "服务器响应",
    "Responses": "响应",
    "Response body": "响应体",
    "Response headers": "响应头",
    "Status Code": "状态码",
    "Code": "状态码",
    "Body": "响应体",
    "Headers": "响应头",
    "Links": "关联",
    "No links": "无关联",
    "Details": "详情",
    "Curl": "curl 命令",
    "Download": "下载",
    "Copy": "复制",
    "Copied!": "已复制！",
    "Copy to clipboard": "复制到剪贴板",
    "Copy path to clipboard": "复制接口路径",
    "Copy code to clipboard": "复制代码",
    "Copy cURL command to clipboard": "复制 curl 命令",
    "Request duration": "请求耗时",
    "Response size": "响应大小",
    "Successful Response": "成功",
    "Validation Error": "参数校验失败",
    "Failed to fetch": "请求失败",

    // —— 数据模型 ——
    "Schemas": "数据模型",
    "Models": "数据模型",

    // —— JSON 类型名 ——
    "string": "字符串",
    "integer": "整数",
    "number": "数字",
    "boolean": "布尔值",
    "array": "数组",
    "object": "对象",
    "null": "空",

    // —— 校验错误字段 ——
    "Location": "位置",
    "Message": "错误信息",
    "Error Type": "错误类型",
    "Input": "输入值",
    "Detail": "详细信息"
  };

  // 这些区域里的文字是"数据"，不能翻译（否则会改坏 JSON 示例/响应内容）
  var SKIP_TAGS = {
    TEXTAREA: 1, INPUT: 1, SELECT: 1, OPTION: 1,
    SCRIPT: 1, STYLE: 1, PRE: 1, CODE: 1, KBD: 1, SAMP: 1
  };
  // 只按 class 跳过"代码高亮"容器；数据本身还在 pre/code/textarea 里，已被上面的标签规则挡住
  var SKIP_CLASS = ["microlight"];

  function skipElement(el) {
    if (!el || el.nodeType !== 1) return false;
    if (SKIP_TAGS[el.tagName]) return true;
    var cls = el.className;
    if (typeof cls === "string") {
      for (var i = 0; i < SKIP_CLASS.length; i++) {
        if (cls.indexOf(SKIP_CLASS[i]) !== -1) return true;
      }
    }
    return false;
  }

  function inSkippedArea(node) {
    for (var el = node.parentNode; el && el.nodeType === 1; el = el.parentNode) {
      if (skipElement(el)) return true;
    }
    return false;
  }

  function lookup(text) {
    var key = text.trim();
    if (!key) return null;
    return Object.prototype.hasOwnProperty.call(DICT, key) ? DICT[key] : null;
  }

  function translateTextNode(node) {
    var zh = lookup(node.nodeValue);
    if (zh !== null) {
      node.nodeValue = node.nodeValue.replace(node.nodeValue.trim(), zh);
    }
  }

  // 有些句子被 <code> 之类的标签拆成了多段，
  // 例如 "Controls <code>Accept</code> header."，
  // 单看某一个文本节点匹配不上，这里按"整个元素的文字"再匹配一次。
  function translateElementText() {
    var walker = document.createTreeWalker(
      document.body, NodeFilter.SHOW_ELEMENT, null, false
    );
    var elements = [];
    var el;
    while ((el = walker.nextNode())) elements.push(el);
    for (var i = 0; i < elements.length; i++) {
      var node = elements[i];
      var count = node.children ? node.children.length : 0;
      if (count < 1 || count > 3) continue;          // 只处理小的行内片段
      if (skipElement(node) || inSkippedArea(node)) continue;
      var zh = lookup(node.textContent || "");
      if (zh !== null) node.textContent = zh;
    }
  }

  function translateAttributes(root) {
    if (!root.querySelectorAll) return;
    var attrs = ["placeholder", "title", "aria-label"];
    var els = root.querySelectorAll("[placeholder],[title],[aria-label]");
    for (var i = 0; i < els.length; i++) {
      for (var j = 0; j < attrs.length; j++) {
        var raw = els[i].getAttribute(attrs[j]);
        if (!raw) continue;
        var zh = lookup(raw);
        if (zh !== null) els[i].setAttribute(attrs[j], zh);
      }
    }
  }

  function translateAll() {
    if (!document.body) return;
    translateAttributes(document.body);
    var walker = document.createTreeWalker(
      document.body, NodeFilter.SHOW_TEXT, null, false
    );
    var node;
    while ((node = walker.nextNode())) {
      if (!inSkippedArea(node)) translateTextNode(node);
    }
    translateElementText();
  }

  var pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    setTimeout(function () { pending = false; translateAll(); }, 50);
  }

  function start() {
    translateAll();
    new MutationObserver(schedule).observe(document.body, {
      childList: true, subtree: true, characterData: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
"""


# --------------------------------------------------------------------------
# 四、对外入口
# --------------------------------------------------------------------------
def setup_chinese_docs(app: FastAPI, docs_path: str = "/docs") -> None:
    """把 app 的接口文档替换成中文版 Swagger UI。"""
    # 1) 汉化 OpenAPI 结构
    app.openapi = lambda: _build_openapi(app)  # type: ignore[method-assign]

    # 2) 本地 static/ 存在时挂载（用于离线加载 swagger-ui 资源）
    if os.path.isdir(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # 3) 自定义中文文档页面
    @app.get(docs_path, include_in_schema=False)
    async def chinese_docs() -> HTMLResponse:
        html = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} · 接口文档",
            swagger_js_url=_asset("swagger-ui-bundle.js"),
            swagger_css_url=_asset("swagger-ui.css"),
            swagger_ui_parameters={
                "deepLinking": True,
                "displayRequestDuration": True,
                "filter": True,
                "persistAuthorization": True,
                "defaultModelsExpandDepth": 1,
            },
        ).body.decode("utf-8")
        html = html.replace("</head>", f"<style>\n{_I18N_CSS}\n</style>\n</head>")
        html = html.replace(
            "</body>", f"<script>\n{_I18N_JS}\n</script>\n</body>"
        )
        return HTMLResponse(html)
