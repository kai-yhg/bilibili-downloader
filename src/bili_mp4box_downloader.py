import json
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import ImageTk
import qrcode

API = 'https://api.bilibili.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36'
QUALITY = {16: '360P', 32: '480P', 64: '720P', 80: '1080P', 112: '1080P 高码率', 116: '1080P 60帧', 120: '4K', 125: 'HDR', 126: '杜比视界'}
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SOURCE_DIR)
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else PROJECT_DIR
BUNDLE_DIR = getattr(sys, '_MEIPASS', PROJECT_DIR)
COOKIE_FILE = os.path.join(APP_DIR, 'bili_login_cookies.json')
ICON_ICO = os.path.join(BUNDLE_DIR, 'icon.ico')
COOKIES = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIES))


def load_cookies():
    if not os.path.exists(COOKIE_FILE): return
    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8') as handle: items = json.load(handle)
        for item in items:
            COOKIES.set_cookie(http.cookiejar.Cookie(0, item['name'], item['value'], None, False, item.get('domain', '.bilibili.com'), True, False, item.get('path', '/'), True, False, None, False, None, None, {}, False))
    except (OSError, ValueError, KeyError): pass


def save_cookies():
    items = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path} for c in COOKIES if 'bilibili.com' in c.domain]
    with open(COOKIE_FILE, 'w', encoding='utf-8') as handle: json.dump(items, handle, ensure_ascii=False)


load_cookies()


def request_json(path):
    req = urllib.request.Request(API + path, headers={'User-Agent': UA, 'Referer': 'https://www.bilibili.com/'})
    with OPENER.open(req, timeout=20) as response:
        data = json.loads(response.read().decode('utf-8'))
    if data.get('code') != 0:
        raise RuntimeError(data.get('message') or f'B站接口错误 {data.get("code")}')
    return data['data']


def passport_json(path):
    req = urllib.request.Request('https://passport.bilibili.com' + path, headers={'User-Agent': UA, 'Referer': 'https://www.bilibili.com/'})
    with OPENER.open(req, timeout=20) as response: data = json.loads(response.read().decode('utf-8'))
    if data.get('code') != 0: raise RuntimeError(data.get('message') or '登录接口错误')
    return data['data']


def parse_bvid(value):
    m = re.search(r'BV[a-zA-Z0-9]+', value.strip())
    if not m:
        raise ValueError('请输入有效的 B 站 BV 链接或 BV 号')
    return m.group(0)


def safe_name(value):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .') or 'bilibili_video'


class DownloadApp:
    def __init__(self, root):
        self.root = root
        self.root.title('B站 MP4Box 下载器')
        self.root.geometry('680x790')
        self.root.minsize(600, 720)
        if os.path.exists(ICON_ICO):
            try: self.root.iconbitmap(ICON_ICO)
            except tk.TclError: pass
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.login_cancel = threading.Event()
        self.pages = []
        self.qualities = []
        self.info = None
        self.page_index = 0
        self.quality_index = 0
        self.qr_image = None
        self.keep_m4s = tk.BooleanVar(value=False)
        self._build()
        self.root.bind_all('<MouseWheel>', self._on_wheel)
        self.root.after(100, self._poll)

    def _build(self):
        self.root.configure(bg='#f3f3f3')
        style = ttk.Style(); style.theme_use('clam')
        style.configure('TProgressbar', troughcolor='#ececec', background='#111111', borderwidth=0)
        shell = tk.Frame(self.root, bg='#ffffff', highlightthickness=1, highlightbackground='#dedede')
        shell.pack(fill='both', expand=True, padx=22, pady=18)
        header = tk.Frame(shell, bg='#ffffff', height=48); header.pack(fill='x', padx=16, pady=(10, 4))
        tk.Label(header, text='B站音画同步下载器', bg='#ffffff', fg='#111111', font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        tk.Label(header, text='本地 MP4Box 版', bg='#ffffff', fg='#777777', font=('Microsoft YaHei UI', 9)).pack(side='left', padx=8)
        self.login_btn = tk.Button(header, text='扫码登录' if not any(c.name == 'DedeUserID' for c in COOKIES) else '已登录', command=self.login, relief='flat', bg='#f2f2f2', fg='#333333', padx=10, pady=5, cursor='hand2')
        self.login_btn.pack(side='right')
        body = tk.Frame(shell, bg='#ffffff'); body.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(body, bg='#ffffff', highlightthickness=0, bd=0, yscrollincrement=20)
        self.scrollbar = tk.Scrollbar(body, orient='vertical', command=self.canvas.yview, width=12,
                                      borderwidth=0, elementborderwidth=0, relief='flat', highlightthickness=0,
                                      troughcolor='#ffffff', bg='#c4c4c4', activebackground='#9e9e9e')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        holder = tk.Frame(self.canvas, bg='#ffffff')
        self.canvas_window = self.canvas.create_window((0, 0), window=holder, anchor='nw')
        holder.bind('<Configure>', self._on_content_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        frm = tk.Frame(holder, bg='#ffffff'); frm.pack(fill='both', expand=True, padx=16, pady=(4, 16))
        tk.Label(frm, text='视频链接', bg='#ffffff', fg='#555555', font=('Microsoft YaHei UI', 9)).pack(anchor='w')
        row = tk.Frame(frm, bg='#ffffff'); row.pack(fill='x', pady=(5, 12))
        self.url = tk.Entry(row, relief='solid', bd=1, font=('Microsoft YaHei UI', 10)); self.url.pack(side='left', fill='x', expand=True, ipady=7)
        tk.Button(row, text='解析', command=self.resolve, relief='flat', bg='#111111', fg='#ffffff', padx=18, pady=7, cursor='hand2').pack(side='left', padx=(8, 0))
        self.video_card = tk.Label(frm, text='输入链接后读取视频与分 P 信息', anchor='w', justify='left', bg='#f5f5f5', fg='#666666', padx=12, pady=10, font=('Microsoft YaHei UI', 9))
        self.video_card.pack(fill='x', pady=(0, 12))
        tk.Label(frm, text='分 P', bg='#ffffff', fg='#333333', font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w')
        self.page_buttons = tk.Frame(frm, bg='#ffffff'); self.page_buttons.pack(fill='x', pady=(6, 12))
        tk.Label(frm, text='清晰度', bg='#ffffff', fg='#333333', font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w')
        self.quality_buttons = tk.Frame(frm, bg='#ffffff'); self.quality_buttons.pack(fill='x', pady=(6, 12))
        outrow = tk.Frame(frm, bg='#ffffff'); outrow.pack(fill='x', pady=(2, 10))
        self.output = tk.Entry(outrow, relief='solid', bd=1); self.output.pack(side='left', fill='x', expand=True, ipady=6)
        self.output.insert(0, os.path.join(os.path.expanduser('~'), 'Downloads'))
        tk.Button(outrow, text='选择目录', command=self.pick_output, relief='flat', bg='#eeeeee', padx=12, pady=6, cursor='hand2').pack(side='left', padx=(8, 0))
        filename_row = tk.Frame(frm, bg='#ffffff'); filename_row.pack(fill='x', pady=(0, 8))
        tk.Label(filename_row, text='文件名', bg='#ffffff', fg='#555555', width=7, anchor='w').pack(side='left')
        self.filename = tk.Entry(filename_row, relief='solid', bd=1); self.filename.pack(side='left', fill='x', expand=True, ipady=6)
        tk.Label(filename_row, text='.mp4', bg='#ffffff', fg='#777777', padx=7).pack(side='left')
        keep_row = tk.Frame(frm, bg='#ffffff'); keep_row.pack(fill='x', pady=(0, 8))
        tk.Checkbutton(keep_row, text='保留 M4S 文件', variable=self.keep_m4s, bg='#ffffff', fg='#333333', activebackground='#ffffff', selectcolor='#ffffff', font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.status = tk.Label(frm, text='请输入链接后解析', bg='#ffffff', fg='#666666', anchor='w')
        self.status.pack(anchor='w', pady=(6, 4))
        self.progress = ttk.Progressbar(frm, maximum=100); self.progress.pack(fill='x', pady=(0, 12))
        buttons = tk.Frame(frm, bg='#ffffff'); buttons.pack(fill='x')
        self.download_btn = tk.Button(buttons, text='开始下载', command=self.start, state='disabled', relief='flat', bg='#111111', fg='#ffffff', disabledforeground='#999999', padx=20, pady=9, cursor='hand2')
        self.download_btn.pack(side='left', fill='x', expand=True)
        tk.Button(buttons, text='取消', command=self.cancel.set, relief='flat', bg='#eeeeee', fg='#333333', padx=16, pady=9, cursor='hand2').pack(side='left', padx=(8, 0))
        self.log = tk.Text(frm, height=9, state='disabled', relief='flat', bg='#f5f5f5', fg='#555555', padx=8, pady=8, font=('Consolas', 9)); self.log.pack(fill='both', expand=True, pady=(12, 0))

    def _on_content_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_wheel(self, event):
        if self.root.winfo_containing(event.x_root, event.y_root) is self.log: return None
        self.canvas.yview_scroll(-3 if event.delta > 0 else 3, 'units')
        return 'break'

    def write_log(self, text):
        self.log.configure(state='normal'); self.log.insert('end', text + '\n'); self.log.see('end'); self.log.configure(state='disabled')

    def pick_output(self):
        value = filedialog.askdirectory(initialdir=self.output.get())
        if value: self.output.delete(0, 'end'); self.output.insert(0, value)

    def login(self):
        self.login_cancel.set()
        self.login_cancel = threading.Event()
        self.login_btn.configure(text='正在生成二维码...')
        threading.Thread(target=self._login_qr, daemon=True).start()

    def _login_qr(self):
        try:
            data = passport_json('/x/passport-login/web/qrcode/generate')
            image = qrcode.make(data['url']).resize((220, 220))
            self.events.put(('qr', image, data['qrcode_key']))
        except Exception as e: self.events.put(('error', '登录二维码生成失败：' + str(e)))

    def _poll_login(self, key):
        try:
            while not self.login_cancel.wait(2):
                data = passport_json('/x/passport-login/web/qrcode/poll?qrcode_key=' + urllib.parse.quote(key))
                code = data.get('code')
                if code == 0:
                    save_cookies(); self.events.put(('login_done',)); return
                if code == 86038: raise RuntimeError('二维码已失效，请重新扫码')
                self.events.put(('login_status', '已扫码，请在手机上确认' if code == 86090 else '等待手机扫码'))
        except Exception as e: self.events.put(('error', str(e)))

    def select_page(self, index):
        self.page_index = index
        self._render_page_buttons()
        self._set_default_filename()
        self.load_quality()

    def _set_default_filename(self):
        if not self.info or not self.pages: return
        page = self.pages[self.page_index]
        value = self.info['title'] + (f' - P{page["page"]} {page.get("part", "")}' if len(self.pages) > 1 else '')
        self.filename.delete(0, 'end')
        self.filename.insert(0, safe_name(value))

    def select_quality(self, index):
        self.quality_index = index
        self._render_quality_buttons()

    def _pill(self, parent, text, command, active, row, column):
        button = tk.Button(parent, text=text, command=command, relief='flat', bd=0,
                           bg='#111111' if active else '#f2f2f2', fg='#ffffff' if active else '#444444',
                           activebackground='#222222' if active else '#e8e8e8', activeforeground='#ffffff' if active else '#111111',
                           padx=10, pady=6, font=('Microsoft YaHei UI', 9), cursor='hand2')
        button.grid(row=row, column=column, sticky='ew', padx=(0, 6), pady=(0, 6))
        parent.grid_columnconfigure(column, weight=1)

    def _render_page_buttons(self):
        for child in self.page_buttons.winfo_children(): child.destroy()
        for i, item in enumerate(self.pages):
            text = f'P{item["page"]} {item.get("part", "")}'
            if len(text) > 18: text = text[:17] + '…'
            self._pill(self.page_buttons, text, lambda n=i: self.select_page(n), i == self.page_index, i // 3, i % 3)

    def _render_quality_buttons(self):
        for child in self.quality_buttons.winfo_children(): child.destroy()
        for i, item in enumerate(self.qualities):
            self._pill(self.quality_buttons, item['label'], lambda n=i: self.select_quality(n), i == self.quality_index, i // 4, i % 4)

    def resolve(self):
        try: bvid = parse_bvid(self.url.get())
        except Exception as e: messagebox.showerror('解析失败', str(e)); return
        self.download_btn.configure(state='disabled'); self.status.configure(text='正在读取视频信息...')
        threading.Thread(target=self._resolve, args=(bvid,), daemon=True).start()

    def _resolve(self, bvid):
        try:
            data = request_json('/x/web-interface/view?bvid=' + urllib.parse.quote(bvid))
            self.events.put(('resolved', data))
        except Exception as e: self.events.put(('error', str(e)))

    def load_quality(self):
        if not self.info: return
        cid = self.pages[self.page_index]['cid']
        self.status.configure(text='正在读取清晰度...'); self.download_btn.configure(state='disabled')
        threading.Thread(target=self._quality, args=(self.info['aid'], cid), daemon=True).start()

    def _quality(self, aid, cid):
        try:
            data = request_json(f'/x/player/playurl?avid={aid}&cid={cid}&qn=80&fnval=16&fourk=1&platform=pc')
            streams = data.get('dash', {}).get('video', [])
            self.events.put(('quality', streams))
        except Exception as e: self.events.put(('error', str(e)))

    def start(self):
        if not self.info or not self.qualities: return
        self.cancel.clear(); self.download_btn.configure(state='disabled'); self.progress['value'] = 0
        page = self.pages[self.page_index]; qn = self.qualities[self.quality_index]['id']
        raw_folder = self.output.get().strip()
        raw_filename = self.filename.get().strip()
        if raw_filename.lower().endswith('.mp4'): raw_filename = raw_filename[:-4].strip()
        if not raw_folder or not raw_filename:
            self.download_btn.configure(state='normal'); messagebox.showerror('无法下载', '请选择保存目录并填写文件名'); return
        folder = os.path.abspath(raw_folder)
        filename = safe_name(raw_filename)
        threading.Thread(target=self._download, args=(page, qn, folder, filename, self.keep_m4s.get()), daemon=True).start()

    def _download(self, page, qn, folder, base, keep_m4s):
        try:
            data = request_json(f'/x/player/playurl?avid={self.info["aid"]}&cid={page["cid"]}&qn={qn}&fnval=16&fourk=1&platform=pc')
            videos = [x for x in data.get('dash', {}).get('video', []) if x.get('id') == qn] or data.get('dash', {}).get('video', [])
            audio = data.get('dash', {}).get('audio', [])
            if not videos or not audio: raise RuntimeError('没有拿到 DASH 音频或视频地址，请确认已登录 B 站')
            video = max(videos, key=lambda x: int(x.get('bandwidth') or 0))
            audio = max(audio, key=lambda x: int(x.get('bandwidth') or 0))
            os.makedirs(folder, exist_ok=True)
            video_file, audio_file, output = [os.path.join(folder, base + ext) for ext in ('.video.m4s', '.audio.m4s', '.mp4')]
            self._save(self._stream_urls(video), video_file, '视频')
            self._save(self._stream_urls(audio), audio_file, '音频')
            mp4box = os.path.join(BUNDLE_DIR, 'MP4Box.exe') if getattr(sys, 'frozen', False) else os.path.join(PROJECT_DIR, 'vendor', 'MP4Box.exe')
            if not os.path.exists(mp4box): raise RuntimeError('找不到 MP4Box.exe，请把它放到程序目录或配置路径')
            self.events.put(('status', '正在用 MP4Box 无损合并...'))
            subprocess.run([mp4box, '-charset', 'utf8', '-add', video_file + '#video', '-add', audio_file + '#audio', '-new', output], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if not keep_m4s:
                for temp_file in (video_file, audio_file):
                    try: os.remove(temp_file)
                    except OSError as error: self.events.put(('status', f'临时文件未能删除：{os.path.basename(temp_file)}（{error}）'))
            self.events.put(('done', output))
        except Exception as e: self.events.put(('error', str(e)))

    @staticmethod
    def _stream_urls(stream):
        urls = [stream.get('baseUrl') or stream.get('base_url')]
        urls.extend(stream.get('backupUrl') or stream.get('backup_url') or [])
        return list(dict.fromkeys(url for url in urls if url))

    def _save(self, urls, path, label):
        if not urls: raise RuntimeError(label + '流没有可用的 CDN 地址')
        block = 8 * 1024 * 1024
        done = os.path.getsize(path) if os.path.exists(path) else 0
        total = 0
        stalled = 0
        with open(path, 'ab' if done else 'wb') as out:
            while True:
                if self.cancel.is_set(): raise RuntimeError('下载已取消')
                if total and done >= total: break
                progressed = False
                last_error = None
                for url in urls:
                    end = done + block - 1
                    headers = {'User-Agent': UA, 'Referer': 'https://www.bilibili.com/', 'Range': f'bytes={done}-{end}'}
                    try:
                        with OPENER.open(urllib.request.Request(url, headers=headers), timeout=45) as response:
                            content_range = response.headers.get('Content-Range', '')
                            match = re.search(r'/([0-9]+)$', content_range)
                            if match: total = int(match.group(1))
                            elif not total: total = int(response.headers.get('Content-Length') or 0)
                            if total and done >= total: last_error = None; break
                            if done and response.status != 206: raise RuntimeError('CDN 不支持断点续传')
                            while True:
                                data = response.read(1024 * 1024)
                                if not data: break
                                out.write(data); done += len(data); progressed = True
                                self.events.put(('progress', label, done, total))
                        last_error = None
                        break
                    except urllib.error.HTTPError as error:
                        if error.code == 416 and done: total = done; last_error = None; break
                        last_error = error
                    except Exception as error: last_error = error
                if last_error: raise RuntimeError(f'{label}下载失败：{last_error}')
                if total and done >= total: break
                if progressed: stalled = 0
                else:
                    stalled += 1
                    if stalled >= 3:
                        if not total: break
                        raise RuntimeError(f'{label}下载失败：连续 {stalled} 次未收到新数据，已停止重试')
        self.events.put(('progress', label, done, total or done))

    def _poll(self):
        try:
            while True:
                try: event = self.events.get_nowait()
                except queue.Empty: break
                try: self._handle_event(event)
                except Exception as error: self.write_log(f'界面事件处理出错：{error}')
        finally:
            self.root.after(100, self._poll)

    def _handle_event(self, event):
        kind = event[0]
        if kind == 'resolved':
            self.info = event[1]; self.pages = self.info.get('pages', [])
            self.page_index = 0; self._render_page_buttons()
            self.canvas.yview_moveto(0)
            self._set_default_filename()
            owner = self.info.get('owner', {}).get('name', '')
            self.video_card.configure(text=f'{self.info["title"]}\n{owner}  ·  {len(self.pages)} 个分 P')
            self.load_quality()
        elif kind == 'quality':
            unique = {}
            for item in event[1]:
                unique.setdefault(item['id'], {'id': item['id'], 'label': QUALITY.get(item['id'], item.get('new_description', str(item['id'])) )})
            self.qualities = sorted(unique.values(), key=lambda x: x['id'], reverse=True)
            self.quality_index = 0; self._render_quality_buttons(); self.download_btn.configure(state='normal'); self.status.configure(text=f'已找到 {len(self.qualities)} 种可用清晰度')
        elif kind == 'qr':
            popup = tk.Toplevel(self.root); popup.title('扫码登录 B 站'); popup.configure(bg='#ffffff'); popup.resizable(False, False)
            popup.protocol('WM_DELETE_WINDOW', lambda: (self.login_cancel.set(), popup.destroy(), self.login_btn.configure(text='扫码登录')))
            self.qr_image = ImageTk.PhotoImage(event[1]); tk.Label(popup, image=self.qr_image, bg='#ffffff').pack(padx=28, pady=(22, 8))
            self.qr_status = tk.Label(popup, text='请使用哔哩哔哩手机客户端扫码', bg='#ffffff', fg='#333333'); self.qr_status.pack(pady=(0, 22))
            threading.Thread(target=self._poll_login, args=(event[2],), daemon=True).start()
        elif kind == 'login_status':
            if hasattr(self, 'qr_status') and self.qr_status.winfo_exists(): self.qr_status.configure(text=event[1])
        elif kind == 'login_done':
            self.login_cancel.set()
            self.login_btn.configure(text='已登录')
            if hasattr(self, 'qr_status') and self.qr_status.winfo_exists(): self.qr_status.master.destroy()
            self.status.configure(text='登录成功，请重新解析视频')
            if self.url.get().strip(): self.resolve()
        elif kind == 'progress':
            _, label, done, total = event; self.status.configure(text=f'{label}下载中：{done / 1048576:.1f} MB'); self.progress['value'] = (done / total * 100) if total else 0
        elif kind == 'status': self.status.configure(text=event[1]); self.write_log(event[1])
        elif kind == 'done': self.progress['value'] = 100; self.status.configure(text='完成'); self.write_log('已生成：' + event[1]); self.download_btn.configure(state='normal'); messagebox.showinfo('下载完成', event[1])
        elif kind == 'error': self.status.configure(text='失败'); self.write_log('错误：' + event[1]); self.download_btn.configure(state='normal'); messagebox.showerror('下载失败', event[1])


if __name__ == '__main__':
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BiliMp4BoxDownloader.Local.1')
        except (AttributeError, OSError): pass
    root = tk.Tk(); DownloadApp(root); root.mainloop()
