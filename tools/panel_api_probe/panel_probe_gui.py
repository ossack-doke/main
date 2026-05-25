#!/usr/bin/env python3
"""Tk GUI: 按 3x-ui Wiki / 源码 REST 分组测试 Bearer API。"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext

try:
    from panel_api_probe import ProbeConfig, run_probe_lines
except ImportError:
    ProbeConfig = None  # type: ignore[misc, assignment]
    run_probe_lines = None  # type: ignore[misc, assignment]


CATEGORY_GROUPS: tuple[tuple[str, str], ...] = (
    ("inbounds", "入站"),
    ("clients", "客户端"),
    ("server", "服务端"),
    ("nodes", "节点"),
    ("geo", "自定义 Geo"),
    ("extra", "附加"),
    ("panel", "Panel 内置 API"),
    ("ui", "浏览器/UI 路由"),
)


def main() -> None:
    if ProbeConfig is None or run_probe_lines is None:
        messagebox.showerror(
            "错误",
            "无法导入 panel_api_probe。\n请将本脚本与 panel_api_probe.py、endpoints_manifest.json 置于同一目录，或检查 PyInstaller 打包配置。",
        )
        sys.exit(1)

    root = tk.Tk()
    root.title("3x-ui Panel API 自检（对齐 Wiki / 本仓库源码）")
    root.minsize(820, 640)

    outer = tk.Frame(root, padx=8, pady=8)
    outer.pack(fill=tk.BOTH, expand=True)

    conn = tk.LabelFrame(outer, text="连接", padx=6, pady=6)
    conn.pack(fill=tk.X, pady=(0, 6))

    r0 = tk.Frame(conn)
    r0.pack(fill=tk.X)
    tk.Label(r0, text="服务器 / IP").pack(side=tk.LEFT)
    host_e = tk.Entry(r0, width=34)
    host_e.pack(side=tk.LEFT, padx=(6, 12))
    host_e.insert(0, "127.0.0.1")

    tk.Label(r0, text="端口").pack(side=tk.LEFT)
    port_e = tk.Entry(r0, width=8)
    port_e.pack(side=tk.LEFT, padx=(6, 12))
    port_e.insert(0, "2053")

    use_https = tk.BooleanVar(value=False)
    tk.Checkbutton(r0, text="HTTPS", variable=use_https).pack(side=tk.LEFT)

    r1 = tk.Frame(conn)
    r1.pack(fill=tk.X, pady=4)
    tk.Label(r1, text="XUI_API_SECRET").pack(side=tk.LEFT)
    sec_e = tk.Entry(r1, width=64, show="*")
    sec_e.pack(side=tk.LEFT, padx=(6, 0))

    r2 = tk.Frame(conn)
    r2.pack(fill=tk.X, pady=4)
    tk.Label(r2, text="webBasePath").pack(side=tk.LEFT)
    wbp_e = tk.Entry(r2, width=62)
    wbp_e.pack(side=tk.LEFT, padx=(6, 0))
    # 必须与面板 DB 一致；本 fork 的安装脚本默认值见 install-online.sh / LOCAL_PANEL_GUIDE_zh.md
    wbp_e.insert(0, "/adV5YHG8JvMcm4rm5y/")

    tk.Label(
        conn,
        text="须与面板设置完全一致。若仍为默认 “/”，实际请求会变成 …/panel/api/…，而你的面板挂在随机段名下时会出现整页 404。",
        fg="#880000",
        anchor=tk.W,
        wraplength=800,
        justify=tk.LEFT,
    ).pack(fill=tk.X, anchor=tk.W, pady=(2, 0))

    adv = tk.LabelFrame(outer, text="高级（可选）", padx=6, pady=6)
    adv.pack(fill=tk.X, pady=(0, 6))

    def adv_row(parent: tk.Frame, la: str, default: str) -> tk.Entry:
        ro = tk.Frame(parent)
        ro.pack(fill=tk.X, pady=2)
        tk.Label(ro, text=la, width=16, anchor=tk.W).pack(side=tk.LEFT)
        e = tk.Entry(ro, width=54)
        e.insert(0, default)
        e.pack(side=tk.LEFT, padx=(4, 0))
        return e

    bucket_e = adv_row(adv, "统计 bucket", "60")
    metric_e = adv_row(adv, "metric", "cpu")
    tag_e = adv_row(adv, "观测 tag", "direct")
    logn_e = adv_row(adv, "日志行数", "50")
    to_e = adv_row(adv, "超时(秒)", "60")

    chk = tk.LabelFrame(outer, text="选项", padx=6, pady=6)
    chk.pack(fill=tk.X, pady=(0, 6))
    v_get_db = tk.BooleanVar(value=False)
    v_backup = tk.BooleanVar(value=False)
    v_danger = tk.BooleanVar(value=False)
    v_panel = tk.BooleanVar(value=False)
    v_ui = tk.BooleanVar(value=False)
    tk.Checkbutton(chk, text="含 GET 下载数据库 (getDb)", variable=v_get_db).grid(row=0, column=0, sticky=tk.W)
    tk.Checkbutton(chk, text="含 Telegram 备份 (backuptotgbot)", variable=v_backup).grid(row=0, column=1, sticky=tk.W)
    tk.Checkbutton(chk, text="⚠ 含破坏性 POST（删配置、重置流量、停 Xray…）", variable=v_danger).grid(
        row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 0)
    )
    tk.Checkbutton(
        chk, text="含 /panel/setting · /panel/xray（常为面板 Cookie 会话，不是纯 Bearer）", variable=v_panel
    ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
    tk.Checkbutton(chk, text="含 /login 等浏览器 UI 路由", variable=v_ui).grid(row=3, column=0, columnspan=2, sticky=tk.W)

    grp = tk.LabelFrame(outer, text="Wiki / 源码分组测试", padx=6, pady=6)
    grp.pack(fill=tk.X, pady=(0, 8))

    btn_frm = tk.Frame(grp)
    btn_frm.pack(fill=tk.X, pady=2)

    txt = scrolledtext.ScrolledText(outer, height=20, wrap=tk.WORD, font=("Consolas", 10))
    txt.pack(fill=tk.BOTH, expand=True, pady=4)

    log_q: queue.Queue[str | None] = queue.Queue()
    probe_buttons: list[tk.Button] = []

    def append_log(chunk: str) -> None:
        txt.insert(tk.END, chunk)
        txt.see(tk.END)

    def poll_queue() -> None:
        try:
            while True:
                msg = log_q.get_nowait()
                if msg is None:
                    for b in probe_buttons:
                        b.config(state=tk.NORMAL)
                    return
                append_log(msg)
        except queue.Empty:
            pass
        root.after(120, poll_queue)

    def build_base_url() -> str | None:
        h = host_e.get().strip()
        po = port_e.get().strip()
        if not h or not po:
            messagebox.showerror("缺少参数", "请填写服务器与端口。")
            return None
        sch = "https" if use_https.get() else "http"
        return f"{sch}://{h}:{po}"

    def make_cfg(base_url: str) -> ProbeConfig | None:
        try:
            timeout_s = float(to_e.get().strip() or "60")
        except ValueError:
            messagebox.showerror("", "超时必须是数字。")
            return None
        return ProbeConfig(
            base_url=base_url.strip(),
            secret=sec_e.get().strip(),
            web_base_path=wbp_e.get().strip() or "/",
            bucket=bucket_e.get().strip() or "60",
            metric=metric_e.get().strip() or "cpu",
            observatory_tag=tag_e.get().strip() or "direct",
            log_line_count=logn_e.get().strip() or "50",
            timeout=timeout_s,
            include_get_db=v_get_db.get(),
            include_backup_tgbot=v_backup.get(),
            also_panel_routes=v_panel.get(),
            also_ui_login_routes=v_ui.get(),
            include_post_destructive=v_danger.get(),
        )

    def worker(*, banner: str, categories: frozenset[str] | None) -> None:
        base = build_base_url()
        if base is None:
            log_q.put(None)
            return
        cfg = make_cfg(base)
        if cfg is None:
            log_q.put(None)
            return
        if not cfg.secret:
            log_q.put("错误: XUI_API_SECRET 不能为空。\n")
            log_q.put(None)
            return
        if cfg.include_post_destructive:
            log_q.put(">>> 已启用破坏性 POST — 仅建议在测试机上使用。\n")

        log_q.put(banner)

        def emit(line: str) -> None:
            log_q.put(line + "\n")

        try:
            exit_code, _lines = run_probe_lines(cfg, emit=emit, categories=categories)
            log_q.put(f"\n>>> 退出码 {exit_code}（0 表示未发现 FAIL）\n")
        except Exception as e:  # noqa: BLE001
            log_q.put(f"\n异常: {e!r}\n")
        finally:
            log_q.put(None)

    def start_run(*, banner: str, categories: frozenset[str] | None) -> None:
        if v_danger.get():
            if not messagebox.askyesno("破坏性 POST", "已勾选破坏性 POST。\n可能影响在线用户与服务，确认在当前服务器上执行？"):
                return

        txt.delete("1.0", tk.END)
        for b in probe_buttons:
            b.config(state=tk.DISABLED)
        threading.Thread(target=worker, kwargs={"banner": banner, "categories": categories}, daemon=True).start()
        root.after(100, poll_queue)

    def mk_btn(txt_lbl: str, cats: frozenset[str] | None, hdr: str) -> None:
        def _cmd() -> None:
            start_run(banner=hdr + "\n", categories=cats)

        b = tk.Button(btn_frm, text=txt_lbl, command=_cmd, width=14)
        b.pack(side=tk.LEFT, padx=(0, 6), pady=(0, 4))
        probe_buttons.append(b)

    mk_btn(
        "全部路由",
        None,
        "# 面板 API — 清单见 endpoints_manifest.json（由 generate_manifest.py 根据本仓库源码生成）\n"
        "# Wiki: https://github.com/MHSanaei/3x-ui/wiki/Configuration#api-documentation\n",
    )

    for key, zh in CATEGORY_GROUPS:
        mk_btn(
            zh,
            frozenset({key}),
            f"# --- 模块: {key} ({zh}) ---\n",
        )

    low = tk.Frame(grp)
    low.pack(fill=tk.X, pady=(6, 0))

    def clear_txt() -> None:
        txt.delete("1.0", tk.END)

    cl = tk.Button(low, text="清空输出", command=clear_txt)
    cl.pack(side=tk.LEFT, padx=(0, 8))

    def copy_out() -> None:
        root.clipboard_clear()
        root.clipboard_append(txt.get("1.0", tk.END))
        messagebox.showinfo("", "已复制到剪贴板")

    cb = tk.Button(low, text="复制结果", command=copy_out)
    cb.pack(side=tk.LEFT, padx=(0, 8))

    wiki = (
        "接口列表按本 fork 仓库 `web/controller` 注册路与 Wiki 对齐；Wiki 表中部分「入站」操作实际在 `/panel/api/clients`。\n"
        "OAuth: `Authorization: Bearer` + XUI_API_SECRET（本工具会自动加 Bearer）。路径必须包含 `/panel/api/...`。若 API-only "
        "下浏览器不带 Header 会看到 404，属预期。"
    )
    tk.Label(outer, text=wiki, justify=tk.LEFT, fg="#444", wraplength=860).pack(anchor=tk.W, pady=(4, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
