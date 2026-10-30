#!/usr/bin/env python3
"""Read-only Qt dashboard for the verified standalone voice workflow."""
from pathlib import Path
import argparse
import json
import os
import sys
import time

from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, QLockFile, QStandardPaths
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QLinearGradient, QPen
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

from dashboard_model import load_view, CATEGORIES

ROOT = Path(__file__).resolve().parent
BG = '#080F1C'
PANEL = '#101C2D'
BORDER = '#23364C'
TEXT = '#EAF3FF'
MUTED = '#8DA4BF'
ACCENT = '#48E2BE'
FONT = 'Noto Sans CJK SC'


def color(value, alpha=None):
    result = QColor(value)
    if alpha is not None:
        result.setAlpha(alpha)
    return result


def font(size, bold=False):
    result = QFont(FONT)
    result.setPixelSize(size)
    result.setWeight(QFont.DemiBold if bold else QFont.Normal)
    return result


def text(p, rect, value, size=14, ink=TEXT, bold=False, align=Qt.AlignLeft | Qt.AlignVCenter,
         elide=False):
    p.setFont(font(size, bold))
    p.setPen(color(ink))
    if elide:
        value = p.fontMetrics().elidedText(str(value), Qt.ElideRight, int(rect.width()))
    p.drawText(rect, align, str(value))


def panel(p, rect, border=BORDER, fill=PANEL, radius=18):
    p.setPen(QPen(color(border), 1))
    p.setBrush(color(fill))
    p.drawRoundedRect(rect, radius, radius)


def pill(p, rect, value, ink=ACCENT):
    p.setPen(Qt.NoPen)
    p.setBrush(color(ink, 22))
    p.drawRoundedRect(rect, rect.height()/2, rect.height()/2)
    text(p, rect, value, 12, ink, True, Qt.AlignCenter)


class Dashboard(QWidget):
    def __init__(self, root=ROOT, activation_token=None):
        super().__init__()
        self.root = Path(root)
        self.records = self.root/'records'
        self.records.mkdir(parents=True, exist_ok=True)
        self.started_at = time.time()
        self.activation_ack = None
        self.last_error = None
        self.view = {}
        self.live_pixmap = QPixmap()
        self.last_image_key = None
        self.thumb_pixmap = QPixmap()
        self.thumb_key = None
        self.closed = False
        self.fullscreen_rect = QRectF()
        self.setWindowTitle('DOFBOT · 语音驱动智能垃圾分拣')
        self.setMinimumSize(1000, 680)
        self.resize(1240, 820)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(125)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.write_status)
        self.status_timer.start(1000)
        self.refresh()
        QTimer.singleShot(0, lambda: self.activate(activation_token))

    def activate(self, token=None):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if token:
            self.activation_ack = str(token)
        self.write_status()

    def refresh(self):
        try:
            view = load_view(self.root)
            if view['camera_live']:
                if view['image_key'] != self.last_image_key:
                    pixmap = QPixmap(view['image_path'])
                    if pixmap.isNull():
                        view['camera_live'] = False
                        view['camera_message'] = '正在等待完整相机画面'
                        self.live_pixmap = QPixmap()
                    else:
                        self.live_pixmap = pixmap
                        self.last_image_key = view['image_key']
            else:
                self.live_pixmap = QPixmap()
                self.last_image_key = None
            thumb = view['thumbnail']
            if thumb != self.thumb_key:
                self.thumb_pixmap = QPixmap(thumb) if thumb else QPixmap()
                self.thumb_key = thumb
            self.view = view
            self.last_error = view.get('error')
        except Exception as exc:
            self.last_error = str(exc)
            # Never retain a stale LIVE badge after a read/parse error.
            self.view.update(online=False, camera_live=False, state='offline', step=-1,
                             title='状态暂不可用', description='正在等待有效运行记录',
                             camera_message='状态暂不可用')
            self.live_pixmap = QPixmap()
        self.update()

    def write_status(self):
        record = dict(pid=os.getpid(), started_at=self.started_at, updated_at=time.time(),
                      visible=self.isVisible() and not self.closed, width=self.width(), height=self.height(),
                      runtime_pid=self.view.get('runtime_pid'), runtime_online=bool(self.view.get('online')),
                      camera_live=bool(self.view.get('camera_live')), last_error=self.last_error,
                      closed=self.closed, activation_ack=self.activation_ack)
        try:
            temp = self.records/'dashboard.tmp'
            temp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            temp.replace(self.records/'dashboard.json')
        except OSError as exc:
            self.last_error = '显示状态记录失败：'+str(exc)

    def screenshot(self, destination):
        self.refresh()
        QApplication.processEvents()
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if not self.grab().save(str(target), 'PNG'):
            raise RuntimeError('无法保存窗口截图：'+str(target))
        return str(target)

    def closeEvent(self, event):
        self.closed = True
        self.refresh_timer.stop()
        self.status_timer.stop()
        self.write_status()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def mouseMoveEvent(self, event):
        self.setCursor(Qt.PointingHandCursor if self.fullscreen_rect.contains(event.pos()) else Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.fullscreen_rect.contains(event.pos()):
            self.toggle_fullscreen()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), color(BG))
        w, h = self.width(), self.height()
        margin, gap = (24, 16) if w >= 1100 else (20, 14)
        header_h = 64 if h >= 740 else 58
        inner = w-2*margin
        self.paint_header(p, QRectF(margin, margin, inner, header_h))
        top_y = margin+header_h+gap
        body_h = h-top_y-margin
        top_h = int(body_h*.53)
        step_h = 90 if h >= 740 else 78
        bottom_y = top_y+top_h+step_h+gap*2
        bottom_h = h-margin-bottom_y
        video_w = int((inner-gap)*.66)
        self.paint_camera(p, QRectF(margin, top_y, video_w, top_h))
        self.paint_result(p, QRectF(margin+video_w+gap, top_y, inner-video_w-gap, top_h))
        self.paint_steps(p, QRectF(margin, top_y+top_h+gap, inner, step_h))
        timeline_w = int((inner-gap)*.59)
        self.paint_timeline(p, QRectF(margin, bottom_y, timeline_w, bottom_h))
        self.paint_categories(p, QRectF(margin+timeline_w+gap, bottom_y, inner-timeline_w-gap, bottom_h))
        p.end()

    def paint_header(self, p, r):
        # Small circuit-style arm mark, drawn locally; no external assets.
        x, y = r.x(), r.y()+8
        p.setPen(QPen(color(ACCENT), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(x+4, y+39), QPointF(x+38, y+39))
        p.drawLine(QPointF(x+20, y+36), QPointF(x+12, y+22))
        p.drawLine(QPointF(x+12, y+22), QPointF(x+29, y+7))
        p.drawLine(QPointF(x+29, y+7), QPointF(x+42, y+17))
        p.drawLine(QPointF(x+38, y+19), QPointF(x+44, y+23))
        p.drawLine(QPointF(x+42, y+14), QPointF(x+49, y+19))
        p.setBrush(color(BG))
        p.drawEllipse(QPointF(x+12, y+22), 4, 4)
        p.drawEllipse(QPointF(x+29, y+7), 4, 4)
        text(p, QRectF(x+65, r.y(), 170, 29), 'DOFBOT', 25, TEXT, True)
        text(p, QRectF(x+65, r.y()+31, 170, 22), 'VOICE  ×  VISION', 11, MUTED)
        text(p, QRectF(x+244, r.y()+1, r.width()-530, 30), '语音驱动 · 智能垃圾分拣', 23, TEXT, True, elide=True)
        online = self.view.get('online', False)
        text(p, QRectF(x+244, r.y()+34, r.width()-530, 21),
             '听见指令，识别物品，完成分类投放' if online else '显示窗口已打开 · 等待独立语音程序', 12, MUTED, elide=True)
        pill(p, QRectF(r.right()-240, r.y()+2, 106, 27), '●  运行已连接' if online else '○  程序离线', ACCENT if online else MUTED)
        text(p, QRectF(r.right()-246, r.y()+33, 118, 21), time.strftime('%H:%M:%S'), 15, MUTED, False, Qt.AlignCenter)
        self.fullscreen_rect = QRectF(r.right()-110, r.y()+6, 110, 40)
        panel(p, self.fullscreen_rect, BORDER, '#142237', 10)
        text(p, self.fullscreen_rect, '退出全屏' if self.isFullScreen() else '全屏  F11', 13, TEXT, False, Qt.AlignCenter)

    def paint_camera(self, p, r):
        panel(p, r)
        text(p, QRectF(r.x()+20, r.y()+10, 180, 28), '现场视野', 15, TEXT, True)
        is_live = self.view.get('camera_live', False) and not self.live_pixmap.isNull()
        pill(p, QRectF(r.right()-98, r.y()+13, 78, 24), '●  LIVE' if is_live else '未连接', ACCENT if is_live else MUTED)
        area = QRectF(r.x()+12, r.y()+48, r.width()-24, r.height()-93)
        path = QPainterPath()
        path.addRoundedRect(area, 10, 10)
        p.save()
        p.setClipPath(path)
        p.fillRect(area, color('#060D17'))
        if is_live:
            fitted = self.live_pixmap.size().scaled(int(area.width()), int(area.height()), Qt.KeepAspectRatio)
            target = QRectF(area.center().x()-fitted.width()/2, area.center().y()-fitted.height()/2,
                            fitted.width(), fitted.height())
            p.drawPixmap(target, self.live_pixmap, QRectF(self.live_pixmap.rect()))
        else:
            gradient = QLinearGradient(area.topLeft(), area.bottomRight())
            gradient.setColorAt(0, color('#0A1423'))
            gradient.setColorAt(1, color('#101E31'))
            p.fillRect(area, gradient)
            cx, cy = area.center().x(), area.center().y()-24
            p.setPen(QPen(color('#34516A'), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(cx-25, cy-18, 50, 36), 8, 8)
            p.drawEllipse(QPointF(cx, cy), 10, 10)
            text(p, QRectF(area.x()+10, cy+33, area.width()-20, 30), self.view.get('camera_message', '等待相机画面'), 16, MUTED, False, Qt.AlignCenter)
        p.restore()
        # Frame brackets are decorative; they do not denote detected objects.
        p.setPen(QPen(color(ACCENT if is_live else '#38516A', 170), 2))
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            xx = area.left()+10 if sx == 1 else area.right()-10
            yy = area.top()+10 if sy == 1 else area.bottom()-10
            p.drawLine(QPointF(xx, yy), QPointF(xx+sx*14, yy))
            p.drawLine(QPointF(xx, yy), QPointF(xx, yy+sy*14))
        footer = QRectF(r.x()+20, r.bottom()-37, r.width()-40, 25)
        text(p, QRectF(footer.x(), footer.y(), footer.width()*.55, footer.height()), self.view.get('title', '等待状态'), 14, ACCENT if self.view.get('online') else MUTED, True, elide=True)
        stamp = time.strftime('%H:%M:%S', time.localtime(self.view['frame_at'])) if is_live else '等待新画面'
        text(p, QRectF(footer.center().x(), footer.y(), footer.width()/2, footer.height()), '实时相机 · '+stamp if is_live else stamp, 11, MUTED, False, Qt.AlignRight | Qt.AlignVCenter)

    def paint_result(self, p, r):
        panel(p, r)
        x, width = r.x()+22, r.width()-44
        text(p, QRectF(x, r.y()+14, width, 23), '识别结果', 13, MUTED, True)
        label = self.view.get('label', '等待识别')
        text(p, QRectF(x, r.y()+43, width, 42), label, 29 if len(label) < 7 else 25, TEXT, True, elide=True)
        category = self.view.get('category')
        name, ink, _ = CATEGORIES.get(category, ('尚未确定类别', MUTED, ''))
        pill(p, QRectF(x, r.y()+96, min(width, 148), 29), name, ink)
        text(p, QRectF(x, r.y()+137, width, 20), '投放区域', 11, MUTED)
        text(p, QRectF(x, r.y()+158, width, 27), name if category else '识别后显示对应区域', 17, ink if category else MUTED, True, elide=True)
        p.setPen(QPen(color(BORDER), 1))
        p.drawLine(QPointF(x, r.y()+198), QPointF(x+width, r.y()+198))
        small = r.height() < 345
        state_y = r.y()+209
        text(p, QRectF(x, state_y, width, 24), self.view.get('title', '等待唤醒'), 16, ACCENT if self.view.get('state') != 'fault' else '#FF7A89', True, elide=True)
        text(p, QRectF(x, state_y+28, width, 37), self.view.get('description', ''), 11, MUTED, False, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
        if not small and not self.thumb_pixmap.isNull():
            thumbnail = QRectF(x, r.bottom()-88, 82, 61)
            p.save()
            clip = QPainterPath()
            clip.addRoundedRect(thumbnail, 7, 7)
            p.setClipPath(clip)
            fitted = self.thumb_pixmap.size().scaled(82, 61, Qt.KeepAspectRatio)
            p.fillRect(thumbnail, color('#080F1C'))
            p.drawPixmap(QRectF(thumbnail.x()+(82-fitted.width())/2, thumbnail.y()+(61-fitted.height())/2,
                               fitted.width(), fitted.height()), self.thumb_pixmap, QRectF(self.thumb_pixmap.rect()))
            p.restore()
            text(p, QRectF(x+94, thumbnail.y()+4, width-94, 24), '最近识别画面', 12, TEXT, True, elide=True)
            text(p, QRectF(x+94, thumbnail.y()+31, width-94, 20), '本轮留存 · 非实时', 10, MUTED, elide=True)

    def paint_steps(self, p, r):
        panel(p, r)
        text(p, QRectF(r.x()+20, r.y()+13, 108, 24), '任务流程', 13, TEXT, True)
        text(p, QRectF(r.x()+20, r.y()+42, 108, 20), '每轮重新唤醒', 10, MUTED)
        left = r.x()+161
        spacing = (r.width()-205)/4
        active = self.view.get('step', -1)
        labels = ['唤醒', '识别', '播报', '抓取投放', '完成']
        center_y = r.y()+27
        for index, label in enumerate(labels):
            cx = left+index*spacing
            if index < 4:
                p.setPen(QPen(color(ACCENT if active > index else BORDER, 160), 2))
                p.drawLine(QPointF(cx+20, center_y), QPointF(cx+spacing-20, center_y))
            passed, selected = 0 <= index < active, index == active
            p.setPen(QPen(color(ACCENT if passed or selected else '#37506A'), 1.5))
            p.setBrush(color(ACCENT if passed else '#183D3B' if selected else '#142337'))
            p.drawEllipse(QPointF(cx, center_y), 13, 13)
            text(p, QRectF(cx-13, center_y-13, 26, 26), '✓' if passed else str(index+1), 12,
                 BG if passed else ACCENT if selected else MUTED, True, Qt.AlignCenter)
            text(p, QRectF(cx-54, center_y+19, 108, 24), label, 12,
                 TEXT if passed or selected else MUTED, selected, Qt.AlignCenter)

    def paint_timeline(self, p, r):
        panel(p, r)
        text(p, QRectF(r.x()+20, r.y()+10, 240, 28), '语音与任务记录', 14, TEXT, True)
        count = self.view.get('executed', 0)
        pill(p, QRectF(r.right()-128, r.y()+13, 108, 25), '本次已执行  %s' % count, '#86B8FF')
        rows = self.view.get('timeline', [])
        available = max(1, int((r.height()-52)/31))
        rows = rows[-available:]
        if not rows:
            text(p, QRectF(r.x()+20, r.y()+53, r.width()-40, r.height()-70),
                 '语音识别与任务进程将在这里记录\n先唤醒，再说启动口令。', 13, MUTED,
                 False, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
            return
        for i, row in enumerate(rows):
            yy = r.y()+48+i*31
            ink = {'accent': ACCENT, 'error': '#FF7A89'}.get(row['tone'], MUTED)
            p.setBrush(color(ink))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(r.x()+23, yy+12), 3, 3)
            text(p, QRectF(r.x()+36, yy, r.width()-139, 24), row['text'], 12, TEXT if row['tone'] == 'accent' else MUTED, elide=True)
            stamp = time.strftime('%H:%M:%S', time.localtime(row['at']))
            text(p, QRectF(r.right()-88, yy, 68, 24), stamp, 11, '#7088A3', False, Qt.AlignRight | Qt.AlignVCenter)

    def paint_categories(self, p, r):
        gap = 10
        card_w, card_h = (r.width()-gap)/2, (r.height()-gap)/2
        selected = self.view.get('category')
        for i, (code, (name, ink, english)) in enumerate(CATEGORIES.items()):
            card = QRectF(r.x()+(i % 2)*(card_w+gap), r.y()+(i//2)*(card_h+gap), card_w, card_h)
            active = selected == code
            panel(p, card, ink if active else BORDER, '#152A3C' if active else PANEL, 14)
            icon_x, icon_y = card.x()+22, card.center().y()
            p.setPen(QPen(color(ink), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(color(ink, 20))
            p.drawRoundedRect(QRectF(icon_x-9, icon_y-8, 19, 23), 3, 3)
            p.drawLine(QPointF(icon_x-12, icon_y-11), QPointF(icon_x+13, icon_y-11))
            p.drawLine(QPointF(icon_x-4, icon_y-15), QPointF(icon_x+5, icon_y-15))
            p.drawLine(QPointF(icon_x-3, icon_y-3), QPointF(icon_x-3, icon_y+8))
            p.drawLine(QPointF(icon_x+4, icon_y-3), QPointF(icon_x+4, icon_y+8))
            text(p, QRectF(card.x()+49, icon_y-22, card.width()-59, 26), name, 14, TEXT, active, elide=True)
            text(p, QRectF(card.x()+49, icon_y+7, card.width()-59, 19), '当前投放类别' if active else english, 9, ink if active else MUTED, elide=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='DOFBOT只读展示窗口')
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--quit-after', type=float)
    parser.add_argument('--activation-token')
    args = parser.parse_args(argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName('DOFBOT Voice Dashboard')
    app.setFont(font(13))
    uid = os.getuid() if hasattr(os, 'getuid') else 1000
    name = 'dofbot-voice-dashboard-'+str(uid)
    request = dict(activate=True, snapshot=str(args.snapshot.resolve()) if args.snapshot else None,
                   activation_token=args.activation_token)

    def activate_existing(timeout=500):
        peer = QLocalSocket()
        peer.connectToServer(name)
        if not peer.waitForConnected(timeout):
            return False
        peer.write(json.dumps(request).encode()+b'\n')
        peer.flush()
        peer.waitForBytesWritten(1000)
        if peer.waitForReadyRead(5000):
            answer = bytes(peer.readAll()).decode(errors='replace')
            print(answer.strip(), flush=True)
        peer.disconnectFromServer()
        return True

    if activate_existing(200):
        return 0
    runtime = Path(QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation))
    runtime.mkdir(parents=True, exist_ok=True)
    single_lock = QLockFile(str(runtime/(name+'.lock')))
    single_lock.setStaleLockTime(0)
    if not single_lock.tryLock(0):
        if activate_existing(1500):
            return 0
        print('显示窗口正在启动，请稍后重试。', file=sys.stderr)
        return 1
    server = QLocalServer()
    QLocalServer.removeServer(name)
    if not server.listen(name):
        print('无法创建显示窗口通信端点。', file=sys.stderr)
        return 1
    window = Dashboard(activation_token=args.activation_token)
    connections = set()

    def accept():
        while server.hasPendingConnections():
            peer = server.nextPendingConnection()
            connections.add(peer)
            buffer = bytearray()
            def receive(peer=peer, buffer=buffer):
                buffer.extend(bytes(peer.readAll()))
                if b'\n' not in buffer:
                    return
                try:
                    message = json.loads(bytes(buffer).split(b'\n')[0])
                    window.activate(message.get('activation_token'))
                    destination = message.get('snapshot')
                    result = {'activated': True}
                    if destination:
                        result['snapshot'] = window.screenshot(destination)
                    peer.write(json.dumps(result).encode()+b'\n')
                    peer.flush()
                except Exception as exc:
                    peer.write(json.dumps({'error': str(exc)}).encode()+b'\n')
                    peer.flush()
                peer.disconnectFromServer()
            peer.readyRead.connect(receive)
            peer.disconnected.connect(lambda peer=peer: (connections.discard(peer), peer.deleteLater()))
            if peer.bytesAvailable():
                receive()
    server.newConnection.connect(accept)
    window.show()
    if args.snapshot:
        def capture():
            try:
                print(window.screenshot(args.snapshot), flush=True)
            except Exception as exc:
                window.last_error = str(exc)
                window.write_status()
                print(str(exc), file=sys.stderr)
        QTimer.singleShot(1500, capture)
    if args.quit_after is not None:
        QTimer.singleShot(max(1700 if args.snapshot else 0, int(args.quit_after*1000)), window.close)
    result = app.exec_()
    server.close()
    single_lock.unlock()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
