import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QComboBox, QFrame, QSizePolicy,
    QScrollArea, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontDatabase,
    QRadialGradient, QCursor
)

C_BG        = QColor('#0a0a0a')
C_RED       = QColor('#cc1a1a')
C_RED_HOT   = QColor('#ff2222')
C_RED_DIM   = QColor('#3a0000')
C_GRID      = QColor('#191919')
C_GRID_FINE = QColor('#131313')
C_TEXT      = QColor('#dddddd')
C_TEXT_DIM  = QColor('#4a4a4a')
C_TRAJ_1    = QColor('#ff3333')
C_TRAJ_2    = QColor('#ff8c00')
C_WALL      = QColor('#252525')
C_WALL_EDGE = QColor('#404040')
C_HIT       = QColor('#ff6600')
C_RICOCHET  = QColor('#ffaa00')
C_LAUNCH    = QColor('#33ff88')
C_TARGET    = QColor('#ff3333')

HANDLE_R    = 10


# ── Physics constants ─────────────────────────────────────────────────────────
G       = 9.81
RHO_AIR = 1.225
DT      = 0.002
MAX_T   = 10.0

OBJECTS = {
    'Playing Card': {
        # Card thrown edge-on (spinning): Cd ~0.05 (thin disc edge-on)
        # Cd=1.4 is face-on tumbling — unrealistic for a skilled throw
        'mass': 0.00178, 'cd': 0.05,  'area': 0.00581,   'cl': 0.60,
        'restitution': 0.20, 'color': C_TRAJ_1, 'icon': 'CARD',
        'v0_max': 28.0
    },
    'Coin (nickel)': {
        # Coin spinning flat: Cd ~0.47 (disc face-on — coins tumble)
        'mass': 0.0050,  'cd': 0.47, 'area': 0.000314,  'cl': 0.45,
        'restitution': 0.60, 'color': QColor('#ffd700'), 'icon': 'COIN',
        'v0_max': 18.0
    },
    'Bottle Cap': {
        'mass': 0.0018,  'cd': 0.60, 'area': 0.000855,  'cl': 0.55,
        'restitution': 0.35, 'color': QColor('#aaaaff'), 'icon': 'CAP',
        'v0_max': 22.0
    },
    'Throwing Knife': {
        # Knife flies tip-first: Cd ~0.10 (streamlined body)
        'mass': 0.200,   'cd': 0.10, 'area': 0.00040,   'cl': 0.25,
        'restitution': 0.65, 'color': QColor('#cccccc'), 'icon': 'KNIFE',
        'v0_max': 22.0
    },
    'Shuriken': {
        'mass': 0.050,   'cd': 0.45, 'area': 0.00126,   'cl': 0.50,
        'restitution': 0.55, 'color': QColor('#aaddff'), 'icon': 'SHURK',
        'v0_max': 25.0
    },
    '9mm Round': {
        'mass': 0.00800, 'cd': 0.30, 'area': 0.0000636, 'cl': 0.15,
        'restitution': 0.40, 'color': QColor('#ffee88'), 'icon': '9MM',
        'v0_max': 400.0
    }
}


# ── Physics engine ────────────────────────────────────────────────────────────
def simulate(obj, v0, angle_deg, spin_rpm, launch_x, launch_y,
             walls, world_w, world_h, max_bounces):
    m, cd, area, cl = obj['mass'], obj['cd'], obj['area'], obj['cl']
    rest = obj['restitution']
    angle = math.radians(angle_deg)
    vx, vy = v0 * math.cos(angle), v0 * math.sin(angle)
    x, y = float(launch_x), float(launch_y)
    t, bounces = 0.0, 0
    omega = spin_rpm * (2.0 * math.pi / 60.0)
    points = [(x, y, t, None)]
    max_steps = int(MAX_T / DT) + 1000
    step = 0

    while t < MAX_T and bounces <= max_bounces and step < max_steps:
        step += 1
        speed = math.sqrt(vx * vx + vy * vy)

        if speed < 0.005:
            break

        fd  = 0.5 * RHO_AIR * cd * area * speed * speed
        axd = -(fd / m) * (vx / speed)
        ayd = -(fd / m) * (vy / speed)
        ow  = abs(omega) * math.exp(-0.04 * t)
        sg  = 1 if omega >= 0 else -1
        fm  = 0.5 * RHO_AIR * cl * area * ow * speed
        axm = sg * fm / m * (-vy / speed)
        aym = sg * fm / m * (vx / speed)
        ax, ay = axd + axm, -G + ayd + aym

        nx  = x  + vx * DT + 0.5 * ax * DT * DT
        ny  = y  + vy * DT + 0.5 * ay * DT * DT
        nvx = vx + ax * DT
        nvy = vy + ay * DT

        if ny <= 0.0:
            if bounces < max_bounces:
                ny = 0.0
                nvy = -nvy * rest
                nvx = nvx * rest
                omega *= 0.7
                bounces += 1

                points.append((nx, ny, t + DT, 'bounce'))

                x, y, vx, vy = nx, ny, nvx, nvy

                t += DT

                continue

            else:
                points.append((nx, 0.0, t + DT, 'stop'))

                break

        if ny >= world_h:
            ny = world_h
            nvy = -nvy * rest
            nvx = nvx * rest
            bounces += 1

            points.append((nx, ny, t + DT, 'bounce'))

            x, y, vx, vy = nx, ny, nvx, nvy

            t += DT

            continue

        if nx >= world_w:
            nx = world_w
            nvx = -nvx * rest
            nvy = nvy * rest
            bounces += 1

            points.append((nx, ny, t + DT, 'bounce'))

            x, y, vx, vy = nx, ny, nvx, nvy

            t += DT

            continue

        hit_wall = False

        for wall in walls:
            wx, wy, ww, wh = wall
            dx, dy = nx - x, ny - y
            te, tx_ = 0.0, 1.0

            skip = False

            for (d, qmin, qcur) in [
                ( dx,  wx,        x), (-dx, -(wx+ww), -x),
                ( dy,  wy,        y), (-dy, -(wy+wh), -y)
            ]:
                if abs(d) < 1e-12:
                    if qcur < qmin:
                        skip = True

                    break

                else:
                    th = (qmin - qcur) / d

                    if d > 0:
                        te = max(te, th)

                    else:
                        tx_ = min(tx_, th)

            if skip or te > tx_ or te > 1.0 or tx_ < 0.0:
                continue

            hx, hy = x + dx * te, y + dy * te
            dl, dr = abs(hx - wx), abs(hx - (wx + ww))
            db, dt_ = abs(hy - wy), abs(hy - (wy + wh))

            if min(dl, dr) <= min(db, dt_):
                nvx = -nvx * rest
                nvy = nvy * rest
                nx = (wx - 0.01) if hx < wx + ww * 0.5 else (wx + ww + 0.01)
                ny = hy

            else:
                nvy = -nvy * rest
                nvx = nvx * rest
                nx = hx
                ny = (wy - 0.01) if hy < wy + wh * 0.5 else (wy + wh + 0.01)

            bounces += 1
            hit_wall = True

            points.append((nx, ny, t + DT, 'hit_wall'))

            break

        if not hit_wall:
            points.append((nx, ny, t + DT, None))

        x, y, vx, vy = nx, ny, nvx, nvy

        t += DT

    return points


# ── Force ↔ velocity conversion ──────────────────────────────────────────────
# When you throw something, you apply a force F over a contact time Δt.
# The resulting impulse J = F·Δt gives the projectile its momentum: m·v₀ = J
# so  v₀ = F·Δt / m.
#
# Contact time depends on throwing style:
#   - snap throw (card, cap):  Δt ≈ 0.05 s
#   - full arm swing (knife):  Δt ≈ 0.12 s
#   - coin flick:              Δt ≈ 0.04 s
# We store Δt per object; for UI we expose force in Newtons (1–200 N range).

CONTACT_TIME = {
    'Playing Card': 0.00050,
    'Coin (nickel)': 0.00090,
    'Bottle Cap': 0.00040,
    'Throwing Knife': 0.04400,
    'Shuriken': 0.01250,
    '9mm Round': 0.03200
}

def force_to_v0(force_n, obj_name, mass):
    dt = CONTACT_TIME.get(obj_name, 0.07)

    return (force_n * dt) / mass          # v₀ = F·Δt / m

def v0_to_force(v0, obj_name, mass):
    dt = CONTACT_TIME.get(obj_name, 0.07)

    return (v0 * mass) / dt               # F = m·v₀ / Δt


# ── Auto-aim solver ───────────────────────────────────────────────────────────
# Strategy: for a fixed launch force (= fixed v₀ for the chosen object),
# sweep angle 0..89° and find the angle that brings the trajectory closest
# to the target.  If the miss is still large, also sweep force levels and
# pick the (force, angle) pair with minimum miss distance.
#
# Two-pass approach:
#   Pass 1 – coarse grid: 18 force levels × 90 angles → pick best
#   Pass 2 – fine search: ±20% around best force, ±10° around best angle
#
# Returns dict {v0, angle, force, miss, pts} or None if unsolvable.

def _miss(pts, tx, ty):
    '''Minimum distance from any point on trajectory to target (tx,ty).'''
    best = float('inf')

    for (x, y, t, ev) in pts:
        d = math.sqrt((x - tx)**2 + (y - ty)**2)

        if d < best:
            best = d

    return best

def auto_aim(obj, obj_name, tx, ty, lx, ly, spin,
             walls, world_w, world_h, max_bounces):
    '''
    Two-pass grid search to find (force_N, angle_deg) that minimises the
    closest-approach distance to target (tx, ty).

    Pass 1 — coarse: 20 force levels × 30 angles
    Pass 2 — fine:   40 force sub-levels × 80 angle sub-levels around best
    Returns dict {v0, angle, force, miss, pts}  or  None if miss > 20m.
    '''
    mass = obj['mass']
    dx   = tx - lx
    dy   = ty - ly
    dist = math.sqrt(dx*dx + dy*dy)

    # geometric angle hint (ignore drag — just direction to target)
    hint_ang = math.degrees(math.atan2(max(dy, 0.0), max(abs(dx), 0.001)))
    hint_ang = max(0.0, min(80.0, hint_ang))

    # Force range: spread across 5 decades — from a gentle tap to a hard throw.
    # Use logarithmic spacing so low forces are well-sampled (short distances).
    def _log_range(lo, hi, n):
        return [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]

    force_levels = _log_range(0.3, 100.0, 20)

    # Angle range: always include angles near the geometric hint and near 45°
    a_extras = sorted(set([
        max(0, hint_ang - 20), max(0, hint_ang - 10), hint_ang,
        hint_ang + 10, hint_ang + 20, 30, 45, 10, 5, 2,
    ]))
    angle_coarse = sorted(set(list(range(0, 85, 5)) + [int(a) for a in a_extras]))

    best_miss = float('inf')
    best_f    = force_levels[len(force_levels)//2]
    best_ang  = hint_ang
    best_pts  = []

    # ── Pass 1: coarse ────────────────────────────────────────────────────
    for f in force_levels:
        v0 = force_to_v0(f, obj_name, mass)

        if v0 < 0.05 or v0 > 1000:
            continue

        for ang in angle_coarse:
            pts = simulate(obj, v0, ang, spin, lx, ly,
                           walls, world_w, world_h, max_bounces)
            m = _miss(pts, tx, ty)

            if m < best_miss:
                best_miss = m
                best_f = f
                best_ang = ang
                best_pts = pts

    if best_miss > dist * 3 + 10:
        return   # completely off — no plausible trajectory exists

    # ── Pass 2: fine grid around best ─────────────────────────────────────
    f_lo  = max(0.1,  best_f   * 0.6)
    f_hi  = min(100,  best_f   * 1.7)
    a_lo  = max(0.0,  best_ang - 15.0)
    a_hi  = min(87.0, best_ang + 15.0)

    for fi in range(41):
        f  = f_lo + (f_hi - f_lo) * fi / 40
        v0 = force_to_v0(f, obj_name, mass)

        if v0 < 0.05 or v0 > 1000:
            continue

        for ai in range(81):
            ang = a_lo + (a_hi - a_lo) * ai / 80
            pts = simulate(obj, v0, ang, spin, lx, ly,
                           walls, world_w, world_h, max_bounces)
            m = _miss(pts, tx, ty)

            if m < best_miss:
                best_miss = m
                best_f = f
                best_ang = ang
                best_pts = pts

    # ── Pass 3: ultra-fine zoom (only if still off by > 5 cm) ─────────────
    if best_miss > 0.05:
        f_lo2  = max(0.05, best_f   * 0.85)
        f_hi2  = min(100,  best_f   * 1.15)
        a_lo2  = max(0.0,  best_ang - 5.0)
        a_hi2  = min(87.0, best_ang + 5.0)

        for fi in range(51):
            f  = f_lo2 + (f_hi2 - f_lo2) * fi / 50
            v0 = force_to_v0(f, obj_name, mass)

            if v0 < 0.05 or v0 > 1000:
                continue

            for ai in range(101):
                ang = a_lo2 + (a_hi2 - a_lo2) * ai / 100
                pts = simulate(obj, v0, ang, spin, lx, ly,
                               walls, world_w, world_h, max_bounces)
                m = _miss(pts, tx, ty)

                if m < best_miss:
                    best_miss = m
                    best_f = f
                    best_ang = ang
                    best_pts = pts

    return {
        'v0': force_to_v0(best_f, obj_name, mass),
        'angle': best_ang,
        'force': best_f,
        'miss': best_miss,
        'pts': best_pts
    }


# ── Viewport — supports pan + zoom ───────────────────────────────────────────
class Viewport:
    '''
    World extent is always 0..world_w × 0..world_h (meters).
    The *view* is a sub-window [vx0, vy0]..[vx0+vw, vy0+vh] inside that world,
    mapped to the full canvas rectangle (with a fixed pixel margin).
    '''
    MARGIN = 44

    def __init__(self, world_w, world_h, cw, ch):
        self.world_w = world_w
        self.world_h = world_h
        # visible range (world coords)
        self.vx0 = 0.0
        self.vy0 = 0.0
        self.vw  = float(world_w)   # visible width in metres
        self.vh  = float(world_h)
        self._cw = cw
        self._ch = ch
        self._update()

    def _update(self):
        m = self.MARGIN
        self.sx = (self._cw - 2 * m) / self.vw
        self.sy = (self._ch - 2 * m) / self.vh

    def resize(self, cw, ch):
        self._cw, self._ch = cw, ch
        self._update()

    # ── coordinate transforms ──────────────────────────────────────────────
    def to_canvas(self, wx, wy):
        m = self.MARGIN
        cx = m + (wx - self.vx0) * self.sx
        cy = self._ch - m - (wy - self.vy0) * self.sy

        return cx, cy

    def to_world(self, cx, cy):
        m = self.MARGIN
        wx = self.vx0 + (cx - m) / self.sx
        wy = self.vy0 + (self._ch - m - cy) / self.sy

        return wx, wy

    # ── zoom ──────────────────────────────────────────────────────────────
    def zoom_at(self, cx, cy, factor):
        '''Zoom by factor, keeping canvas point (cx,cy) fixed in world space.'''
        wx, wy = self.to_world(cx, cy)
        self.vw = max(1.0, min(self.world_w * 4, self.vw * factor))
        self.vh = max(0.5, min(self.world_h * 4, self.vh * factor))
        self._update()
        # reposition so (wx,wy) stays under cursor
        m = self.MARGIN
        self.vx0 = wx - (cx - m) / self.sx
        self.vy0 = wy - (self._ch - m - cy) / self.sy
        self._clamp()

    def reset_zoom(self):
        self.vx0 = 0.0
        self.vy0 = 0.0
        self.vw  = float(self.world_w)
        self.vh  = float(self.world_h)
        self._update()

    # ── pan ───────────────────────────────────────────────────────────────
    def pan(self, dcx, dcy):
        '''Shift view by (dcx, dcy) canvas pixels.'''
        self.vx0 -= dcx / self.sx
        self.vy0 += dcy / self.sy
        self._clamp()

    def _clamp(self):
        # allow a bit of over-scroll (half a view-width) for comfort
        pad_x = self.vw * 0.5
        pad_y = self.vh * 0.5

        self.vx0 = max(-pad_x, min(self.world_w + pad_x - self.vw, self.vx0))
        self.vy0 = max(-pad_y, min(self.world_h + pad_y - self.vh, self.vy0))

    # ── helpers ───────────────────────────────────────────────────────────
    def visible_rect(self):
        return self.vx0, self.vy0, self.vx0 + self.vw, self.vy0 + self.vh

    def zoom_level(self):
        # 1.0 = default; larger = more zoomed in
        return self.world_w / self.vw


# ── Canvas ────────────────────────────────────────────────────────────────────
class BallisticsCanvas(QWidget):
    wall_placed     = pyqtSignal()
    launch_moved    = pyqtSignal(float, float)   # wx, wy
    target_moved    = pyqtSignal(float, float)

    FRAME_MS = 16

    # drag target ids
    _NONE   = 0
    _LAUNCH = 1
    _TARGET = 2
    _WALL   = 3
    _PAN    = 4

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.world_w = 50.0
        self.world_h = 20.0
        self.vp = Viewport(self.world_w, self.world_h, 800, 500)

        self.walls        = []
        self.placing_wall = False
        self._wall_start  = None
        self._mouse_pos   = None

        self.trajectories   = []
        self.playback_speed = 1.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # draggable points
        self.launch_x = 2.0
        self.launch_y = 1.0
        self.target_x = 45.0
        self.target_y = 1.5

        # interaction state
        self._drag_what  = self._NONE
        self._pan_origin = None   # canvas pixel origin for pan gesture

    # ── playback ──────────────────────────────────────────────────────────
    def set_playback_speed(self, spd):
        self.playback_speed = max(0.05, float(spd))

    def _steps_per_frame(self):
        return max(1, int((self.FRAME_MS / 1000.0) / DT * self.playback_speed))

    def _tick(self):
        n = self._steps_per_frame()

        any_active = False

        for tr in self.trajectories:
            if tr['visible'] < len(tr['points']):
                tr['visible'] = min(tr['visible'] + n, len(tr['points']))

                any_active = True

        self.update()

        if not any_active:
            self._timer.stop()

    # ── public API ────────────────────────────────────────────────────────
    def set_placing_wall(self, on):
        self.placing_wall = on
        self.setCursor(Qt.CursorShape.CrossCursor if on
                       else Qt.CursorShape.ArrowCursor)

    def clear_walls(self):
        self.walls = []
        self.update()

    def clear_trajectories(self):
        self.trajectories = []
        self._timer.stop()
        self.update()

    def launch(self, data):
        if len(self.trajectories) >= 2:
            self.trajectories = []

        self.trajectories.append({
            'points': data['points'],
            'color': data['color'],
            'label': data['label'],
            'visible': 0
        })

        self._timer.start(self.FRAME_MS)

    def set_launch_pos(self, wx, wy):
        self.launch_x = max(0.0, min(self.world_w, wx))
        self.launch_y = max(0.0, min(self.world_h, wy))
        self.update()

    def set_target_pos(self, wx, wy):
        self.target_x = max(0.0, min(self.world_w, wx))
        self.target_y = max(0.0, min(self.world_h, wy))
        self.update()

    # ── hit-test a draggable handle ───────────────────────────────────────
    def _hit(self, cx, cy, wx, wy):
        hx, hy = self.vp.to_canvas(wx, wy)

        return math.sqrt((cx - hx) ** 2 + (cy - hy) ** 2) <= HANDLE_R + 4

    # ── mouse ─────────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        cx, cy = ev.position().x(), ev.position().y()
        btn = ev.button()

        if btn == Qt.MouseButton.MiddleButton:
            self._drag_what  = self._PAN
            self._pan_origin = (cx, cy)
            self.setCursor(Qt.CursorShape.SizeAllCursor)

            return

        if self.placing_wall and btn == Qt.MouseButton.RightButton:
            self.set_placing_wall(False)

            return

        if self.placing_wall and btn == Qt.MouseButton.LeftButton:
            self._drag_what = self._WALL
            self._wall_start = self.vp.to_world(cx, cy)

            return

        if btn == Qt.MouseButton.LeftButton:
            if self._hit(cx, cy, self.launch_x, self.launch_y):
                self._drag_what = self._LAUNCH
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

                return

            if self._hit(cx, cy, self.target_x, self.target_y):
                self._drag_what = self._TARGET
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

                return

    def mouseReleaseEvent(self, ev):
        cx, cy = ev.position().x(), ev.position().y()
        btn = ev.button()

        if btn == Qt.MouseButton.MiddleButton and self._drag_what == self._PAN:
            self._drag_what = self._NONE
            self._pan_origin = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

            return

        if self._drag_what == self._WALL and btn == Qt.MouseButton.LeftButton:
            if self._wall_start:
                wx2, wy2 = self.vp.to_world(cx, cy)
                wx1, wy1 = self._wall_start

                x, y = min(wx1, wx2), min(wy1, wy2)
                w, h = abs(wx2 - wx1), abs(wy2 - wy1)

                if w > 0.05 and h > 0.05:
                    self.walls.append((x, y, w, h))
                    self.wall_placed.emit()

                self._wall_start = None
                self.update()

            self._drag_what = self._NONE

            return

        if btn == Qt.MouseButton.LeftButton:
            if self._drag_what in (self._LAUNCH, self._TARGET):
                self._drag_what = self._NONE
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, ev):
        cx, cy = ev.position().x(), ev.position().y()

        self._mouse_pos = (cx, cy)

        if self._drag_what == self._PAN and self._pan_origin:
            ox, oy = self._pan_origin

            self.vp.pan(cx - ox, cy - oy)
            self._pan_origin = (cx, cy)
            self.update()

            return

        if self._drag_what == self._LAUNCH:
            wx, wy = self.vp.to_world(cx, cy)

            self.launch_x = max(0.0, min(self.world_w, wx))
            self.launch_y = max(0.0, min(self.world_h, wy))
            self.launch_moved.emit(self.launch_x, self.launch_y)
            self.update()

            return

        if self._drag_what == self._TARGET:
            wx, wy = self.vp.to_world(cx, cy)

            self.target_x = max(0.0, min(self.world_w, wx))
            self.target_y = max(0.0, min(self.world_h, wy))
            self.target_moved.emit(self.target_x, self.target_y)
            self.update()

            return

        # update cursor to hint draggable handles
        if not self.placing_wall and self._drag_what == self._NONE:
            if (self._hit(cx, cy, self.launch_x, self.launch_y) or
                    self._hit(cx, cy, self.target_x, self.target_y)):
                self.setCursor(Qt.CursorShape.OpenHandCursor)

            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.placing_wall:
            self.update()

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        factor = 0.85 if delta > 0 else (1.0 / 0.85)

        cx = ev.position().x()
        cy = ev.position().y()

        self.vp.zoom_at(cx, cy, factor)
        self.update()

    def reset_zoom(self):
        self.vp.reset_zoom()
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────
    def resizeEvent(self, _ev):
        self.vp.resize(self.width(), self.height())

        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._bg(p)
        self._grid(p)
        self._floor(p)
        self._walls_draw(p)
        self._trajs(p)
        self._launch_handle(p)
        self._target_handle(p)
        self._legend(p)
        self._wall_preview(p)
        self._ruler(p)
        self._zoom_badge(p)

        p.end()

    def _bg(self, p):
        p.fillRect(self.rect(), C_BG)
        gr = QRadialGradient(self.width() / 2, self.height() / 2,
                             max(self.width(), self.height()) * 0.7)
        gr.setColorAt(0, QColor(0, 0, 0, 0))
        gr.setColorAt(1, QColor(0, 0, 0, 100))
        p.fillRect(self.rect(), QBrush(gr))

    def _grid(self, p):
        vx0, vy0, vx1, vy1 = self.vp.visible_rect()
        # choose grid step based on zoom
        zoom = self.vp.zoom_level()

        if zoom >= 8:
            step = 0.5

        elif zoom >= 3:
            step = 1.0

        elif zoom >= 1.5:
            step = 2.0

        else:
            step = 5.0

        p.setPen(QPen(C_GRID_FINE if step <= 1.0 else C_GRID, 1))
        x = math.floor(vx0 / step) * step

        while x <= vx1 + step:
            cx1, cy1 = self.vp.to_canvas(x, vy0)
            cx2, cy2 = self.vp.to_canvas(x, vy1)

            p.drawLine(int(cx1), int(cy1), int(cx2), int(cy2))

            x += step

        y = math.floor(vy0 / step) * step

        while y <= vy1 + step:
            cx1, cy1 = self.vp.to_canvas(vx0, y)
            cx2, cy2 = self.vp.to_canvas(vx1, y)

            p.drawLine(int(cx1), int(cy1), int(cx2), int(cy2))

            y += step

    def _floor(self, p):
        vx0, _, vx1, _ = self.vp.visible_rect()
        cx1, cy1 = self.vp.to_canvas(vx0, 0)
        cx2, cy2 = self.vp.to_canvas(vx1, 0)
        p.setPen(QPen(C_RED_DIM, 2))
        p.drawLine(int(cx1), int(cy1), int(cx2), int(cy2))
        p.setPen(QPen(QColor('#1e0000'), 1))
        x = math.floor(vx0)

        while x <= vx1 + 2:
            fx, fy = self.vp.to_canvas(x, 0)
            p.drawLine(int(fx), int(fy), int(fx + 6), int(fy + 6))
            x += 2

    def _walls_draw(self, p):
        for (wx, wy, ww, wh) in self.walls:
            cx, cy = self.vp.to_canvas(wx, wy + wh)
            cw = ww * self.vp.sx
            ch = wh * self.vp.sy

            if cw < 1 or ch < 1:
                continue

            p.fillRect(int(cx), int(cy), int(cw), int(ch), QBrush(C_WALL))
            p.setPen(QPen(C_WALL_EDGE, 1))
            p.drawRect(int(cx), int(cy), int(cw), int(ch))
            p.setPen(QPen(QColor('#2e2e2e'), 1))

            for di in range(0, int(cw + ch), 10):
                x0 = int(cx + di)
                y0 = int(cy)
                x1 = int(cx)
                y1 = int(cy + di)
                p.drawLine(max(int(cx), x0), y0, x1, max(int(cy), y1))

    def _launch_handle(self, p):
        cx, cy = self.vp.to_canvas(self.launch_x, self.launch_y)

        col = C_LAUNCH

        # outer ring
        p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 80), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), HANDLE_R + 5, HANDLE_R + 5)
        # filled circle
        p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 40)))
        p.setPen(QPen(col, 2))
        p.drawEllipse(QPointF(cx, cy), HANDLE_R, HANDLE_R)
        # crosshair
        p.setPen(QPen(col, 1))
        p.drawLine(int(cx - HANDLE_R - 4), int(cy), int(cx + HANDLE_R + 4), int(cy))
        p.drawLine(int(cx), int(cy - HANDLE_R - 4), int(cx), int(cy + HANDLE_R + 4))
        # label
        p.setFont(QFont('Courier New', 7))
        p.setPen(QPen(col, 1))
        p.drawText(int(cx) + HANDLE_R + 4, int(cy) - 4,
                   f'LAUNCH  {self.launch_x:.1f},{self.launch_y:.1f}m')

    def _target_handle(self, p):
        tx, ty = self.vp.to_canvas(self.target_x, self.target_y)

        for r, col in [
            (28, QColor(70, 0, 0, 50)),
            (20, QColor(130, 0, 0, 70)),
            (12, QColor(190, 10, 10, 90)),
            (6,  C_RED_HOT)
        ]:
            p.setPen(QPen(col, 1))
            p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 25)))
            p.drawEllipse(QPointF(tx, ty), r, r)

        p.setPen(QPen(C_RED, 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(int(tx - 36), int(ty), int(tx + 36), int(ty))
        p.drawLine(int(tx), int(ty - 36), int(tx), int(ty + 36))
        # drag handle ring
        p.setPen(QPen(QColor('#cc1a1a88'), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(tx, ty), HANDLE_R, HANDLE_R)
        # label
        p.setFont(QFont('Courier New', 7))
        p.setPen(QPen(C_RED, 1))
        p.drawText(int(tx) + HANDLE_R + 4, int(ty) - 4,
                   f'TARGET  {self.target_x:.1f},{self.target_y:.1f}m')

    def _trajs(self, p):
        for traj in self.trajectories:
            pts = traj['points']
            col = traj['color']
            vis = traj['visible']

            if vis < 2:
                continue

            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 30), 6))

            px_, py_ = None, None

            for i in range(vis):
                cx, cy = self.vp.to_canvas(pts[i][0], pts[i][1])

                if px_ is not None:
                    p.drawLine(int(px_), int(py_), int(cx), int(cy))

                px_, py_ = cx, cy

            p.setPen(QPen(col, 2))

            px_, py_ = None, None

            for i in range(vis):
                cx, cy = self.vp.to_canvas(pts[i][0], pts[i][1])

                if px_ is not None:
                    p.drawLine(int(px_), int(py_), int(cx), int(cy))

                px_, py_ = cx, cy

            for i in range(vis):
                ev = pts[i][3]

                if ev in ('bounce', 'hit_wall'):
                    cx, cy = self.vp.to_canvas(pts[i][0], pts[i][1])

                    rc = C_RICOCHET if ev == 'bounce' else C_HIT

                    p.setPen(QPen(rc, 2))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPointF(cx, cy), 5, 5)
                    p.setPen(QPen(rc, 1))
                    p.drawEllipse(QPointF(cx, cy), 9, 9)

            if vis > 0:
                cx, cy = self.vp.to_canvas(pts[vis-1][0], pts[vis-1][1])

                p.setBrush(QBrush(col))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), 4, 4)

    def _legend(self, p):
        p.setFont(QFont('Courier New', 8))

        fy = 14

        for traj in self.trajectories:
            if traj['visible'] < 2:
                continue

            col = traj['color']

            p.setPen(QPen(col, 2))
            p.drawLine(12, fy + 5, 36, fy + 5)
            p.setPen(QPen(C_TEXT, 1))
            p.drawText(42, fy + 9, traj['label'])
            fy += 18

    def _wall_preview(self, p):
        if not (self.placing_wall and self._wall_start and self._mouse_pos):
            return

        cx1, cy1 = self.vp.to_canvas(*self._wall_start)
        cx2, cy2 = self._mouse_pos

        p.setPen(QPen(QColor('#ffffff44'), 1, Qt.PenStyle.DashLine))
        p.setBrush(QBrush(QColor('#ffffff0d')))

        x = min(int(cx1), int(cx2))
        y = min(int(cy1), int(cy2))

        p.drawRect(x, y, abs(int(cx2) - int(cx1)), abs(int(cy2) - int(cy1)))

    def _ruler(self, p):
        zoom = self.vp.zoom_level()

        if zoom >= 8:
            step = 0.5

        elif zoom >= 3:
            step = 1.0

        elif zoom >= 1.5:
            step = 2.0

        else:
            step = 5.0

        vx0, vy0, vx1, vy1 = self.vp.visible_rect()

        p.setFont(QFont('Courier New', 7))
        p.setPen(QPen(C_TEXT_DIM, 1))
        x = math.ceil(vx0 / step) * step

        while x <= vx1:
            cx, cy = self.vp.to_canvas(x, 0)
            label = f'{x:.0f}m' if step >= 1 else f'{x:.1f}m'
            p.drawText(int(cx) - 8, int(cy) + 14, label)

            x += step

        y = math.ceil(vy0 / step) * step

        while y <= vy1:
            cx, cy = self.vp.to_canvas(0, y)
            label = f'{y:.0f}m' if step >= 1 else f'{y:.1f}m'
            p.drawText(4, int(cy) + 4, label)

            y += step

    def _zoom_badge(self, p):
        zoom = self.vp.zoom_level()

        txt = f'x{zoom:.1f}  {self.vp.vw:.1f}m wide'

        p.setFont(QFont('Courier New', 8))
        p.setPen(QPen(QColor('#333333'), 1))
        p.drawText(self.width() - 120, self.height() - 8, txt)


# ── UI helpers ────────────────────────────────────────────────────────────────
def _lbl(text, size=9, color='#888888', bold=False, letter_spacing=0):
    w = QLabel(text)
    w.setStyleSheet(
        f'color:{color};font-family:"Courier New";font-size:{size}px;'
        f'font-weight:{"bold" if bold else "normal"};'
        f'letter-spacing:{letter_spacing}px;'
    )

    return w

def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet('background:#250000;border:none;')

    return f

def _section(text):
    w = QLabel(text)
    w.setFixedHeight(22)
    w.setStyleSheet(
        'color:#773333;font-family:"Courier New";font-size:8px;'
        'font-weight:bold;letter-spacing:2px;padding-top:6px;'
    )

    return w

def _slider(lo, hi, val, cb):
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    s.setFixedHeight(18)
    s.setStyleSheet('''
        QSlider::groove:horizontal{height:3px;background:#200000;border-radius:1px;}
        QSlider::handle:horizontal{background:#cc1a1a;border:1px solid #993333;
            width:13px;height:13px;margin:-5px 0;border-radius:6px;}
        QSlider::sub-page:horizontal{background:#6a0000;border-radius:1px;}
    ''')
    s.valueChanged.connect(cb)

    return s

def _val(text, width=52):
    w = QLabel(text)
    w.setFixedWidth(width)
    w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    w.setStyleSheet(
        'color:#dd2222;font-family:"Courier New";font-size:10px;font-weight:bold;'
    )

    return w

def _row(slider, val_lbl):
    r = QHBoxLayout()
    r.setSpacing(6)
    r.setContentsMargins(0, 0, 0, 0)
    r.addWidget(slider)
    r.addWidget(val_lbl)

    return r

def _spinbox(lo, hi, val, decimals=1, step=0.1):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setFixedHeight(22)
    s.setStyleSheet('''
        QDoubleSpinBox{
            background:#131313;color:#dd2222;border:1px solid #280000;
            border-radius:2px;font-family:"Courier New";font-size:9px;
            padding:0 3px;}
        QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{
            width:14px;background:#1a0000;border:none;}
    ''')

    return s


class RedButton(QPushButton):
    def __init__(self, text, h=38):
        super().__init__(text)

        self.setFixedHeight(h)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet('''
            QPushButton{background:#aa1111;color:#ffffff;border:1px solid #660000;
                border-radius:2px;font-family:"Courier New";font-size:11px;
                font-weight:bold;letter-spacing:2px;}
            QPushButton:hover{background:#cc2222;border-color:#993333;}
            QPushButton:pressed{background:#881111;}
        ''')


class GhostButton(QPushButton):
    def __init__(self, text, h=26):
        super().__init__(text)

        self.setFixedHeight(h)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet('''
            QPushButton{background:transparent;color:#666666;border:1px solid #282828;
                border-radius:2px;font-family:"Courier New";font-size:9px;
                letter-spacing:1px;padding:0 6px;}
            QPushButton:hover{background:#180808;color:#aaaaaa;border-color:#442222;}
            QPushButton:checked{background:#1a0808;color:#cc4444;border-color:#551111;}
        ''')


class StyledCombo(QComboBox):
    def __init__(self):
        super().__init__()

        self.setFixedHeight(26)
        self.setStyleSheet('''
            QComboBox{background:#131313;color:#cccccc;border:1px solid #280000;
                border-radius:2px;font-family:"Courier New";font-size:9px;padding:0 6px;}
            QComboBox::drop-down{border:none;width:18px;}
            QComboBox QAbstractItemView{background:#131313;color:#cccccc;
                border:1px solid #280000;selection-background-color:#330000;
                font-family:"Courier New";font-size:9px;}
        ''')


# ── Control panel ─────────────────────────────────────────────────────────────
class ControlPanel(QWidget):
    launch_requested   = pyqtSignal(dict)
    compare_requested  = pyqtSignal(dict)
    clear_requested    = pyqtSignal()
    wall_mode_toggled  = pyqtSignal(bool)
    clear_walls_req    = pyqtSignal()
    speed_changed      = pyqtSignal(float)
    zoom_reset_req     = pyqtSignal()
    launch_pos_changed = pyqtSignal(float, float)
    target_pos_changed = pyqtSignal(float, float)
    aim_requested      = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        self.setFixedWidth(252)
        self.setStyleSheet('background:#0f0f0f;')

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('''
            QScrollArea{border:none;background:#0f0f0f;}
            QScrollBar:vertical{background:#0f0f0f;width:4px;border:none;}
            QScrollBar::handle:vertical{background:#2e0000;border-radius:2px;min-height:18px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        ''')
        inner = QWidget()
        inner.setStyleSheet('background:#0f0f0f;')
        L = QVBoxLayout(inner)
        L.setContentsMargins(10, 10, 10, 14)
        L.setSpacing(3)

        self._build(L)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _coord_row(self, label_x, label_y, spin_x, spin_y):
        r = QHBoxLayout()
        r.setSpacing(4)
        r.setContentsMargins(0, 0, 0, 0)
        lx = QLabel(label_x)
        lx.setFixedWidth(12)
        lx.setStyleSheet('color:#555555;font-family:"Courier New";font-size:8px;')
        ly = QLabel(label_y)
        ly.setFixedWidth(12)
        ly.setStyleSheet('color:#555555;font-family:"Courier New";font-size:8px;')
        r.addWidget(lx)
        r.addWidget(spin_x)
        r.addSpacing(6)
        r.addWidget(ly)
        r.addWidget(spin_y)

        return r

    def _build(self, L):
        logo = QLabel('BULLSEYE')
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(30)
        logo.setStyleSheet(
            'color:#bb1111;font-family:"Courier New";font-size:17px;'
            'font-weight:bold;letter-spacing:5px;'
        )
        L.addWidget(logo)
        sub = _lbl('BALLISTIC SIMULATOR  v3.0', 7, '#2e2e2e', letter_spacing=1)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        L.addWidget(sub)
        L.addSpacing(4)
        L.addWidget(_sep())

        # projectile
        L.addWidget(_section('PROJECTILE'))

        self.combo = StyledCombo()

        for name in OBJECTS:
            self.combo.addItem(f'[{OBJECTS[name]["icon"]}] {name}')

        self.combo.currentIndexChanged.connect(self._on_obj)

        L.addWidget(self.combo)

        self.lbl_info = _lbl('', 8, '#3e3e3e')
        self.lbl_info.setWordWrap(True)

        L.addWidget(self.lbl_info)

        # velocity / force (linked)
        L.addWidget(_section('THROW FORCE'))

        self.val_f = _val('15 N', 60)

        # force range 1..200 N
        self.sld_f = _slider(1, 200, 15, self._on_force)

        L.addLayout(_row(self.sld_f, self.val_f))

        # computed v₀ display — read-only, updates with force+object
        row_vd = QHBoxLayout()
        row_vd.setContentsMargins(0, 0, 0, 0)
        row_vd.setSpacing(4)
        row_vd.addWidget(_lbl('v\u2080 =', 8, '#444444'))

        self.lbl_v0 = _lbl('---', 9, '#993333')

        row_vd.addWidget(self.lbl_v0)
        row_vd.addStretch()
        L.addLayout(row_vd)
        L.addWidget(_lbl('F\u00b7\u0394t/m   \u2014 changes with object mass', 7, '#333333'))

        # angle
        L.addWidget(_section('LAUNCH ANGLE'))

        self.val_a = _val('35\u00b0')
        self.sld_a = _slider(0, 90, 35, lambda v: self.val_a.setText(f'{v}\u00b0'))

        L.addLayout(_row(self.sld_a, self.val_a))

        # spin
        L.addWidget(_section('SPIN  (rpm)'))

        self.val_s = _val('0')
        self.sld_s = _slider(-3000, 3000, 0, lambda v: self.val_s.setText(f'{v:+d}'))

        L.addLayout(_row(self.sld_s, self.val_s))
        L.addWidget(_lbl('- left \u00b7 0 none \u00b7 + right/lift', 7, '#333333'))

        # bounces
        L.addWidget(_section('MAX BOUNCES'))

        self.val_b = _val('3')
        self.sld_b = _slider(0, 10, 3, lambda v: self.val_b.setText(str(v)))

        L.addLayout(_row(self.sld_b, self.val_b))

        L.addSpacing(4)
        L.addWidget(_sep())

        # launch position
        L.addWidget(_section('LAUNCH POINT'))

        self.spn_lx = _spinbox(0, 50, 2.0)
        self.spn_ly = _spinbox(0, 20, 1.0)
        self.spn_lx.valueChanged.connect(self._on_launch_coord)
        self.spn_ly.valueChanged.connect(self._on_launch_coord)

        L.addLayout(self._coord_row('X', 'Y', self.spn_lx, self.spn_ly))
        L.addWidget(_lbl('drag \u25cb green handle on canvas', 7, '#333333'))

        # target position
        L.addWidget(_section('TARGET POINT'))

        self.spn_tx = _spinbox(0, 50, 45.0)
        self.spn_ty = _spinbox(0, 20, 1.5)
        self.spn_tx.valueChanged.connect(self._on_target_coord)
        self.spn_ty.valueChanged.connect(self._on_target_coord)

        L.addLayout(self._coord_row('X', 'Y', self.spn_tx, self.spn_ty))
        L.addWidget(_lbl('drag \u25cb red target on canvas', 7, '#333333'))

        L.addSpacing(4)
        L.addWidget(_sep())

        # playback speed
        L.addWidget(_section('PLAYBACK SPEED'))

        self.val_spd = _val('1.00x')
        self.sld_spd = _slider(5, 500, 100, self._on_speed)

        L.addLayout(_row(self.sld_spd, self.val_spd))
        L.addWidget(_lbl('<1.0 slow-mo  |  1.0 real  |  >1.0 fast', 7, '#333333'))

        L.addSpacing(4)
        L.addWidget(_sep())

        # zoom controls
        L.addWidget(_section('VIEW'))
        row_z = QHBoxLayout()
        row_z.setSpacing(4)
        row_z.setContentsMargins(0, 0, 0, 0)

        self.btn_zoom_reset = GhostButton('\u2715 RESET ZOOM')
        self.btn_zoom_reset.clicked.connect(self.zoom_reset_req)

        row_z.addWidget(self.btn_zoom_reset)

        L.addLayout(row_z)
        L.addWidget(_lbl('scroll wheel = zoom  |  MMB drag = pan', 7, '#333333'))

        L.addSpacing(4)
        L.addWidget(_sep())
        L.addSpacing(2)

        # action buttons
        self.btn_throw = RedButton('\u25b6  THROW', 38)
        self.btn_throw.clicked.connect(lambda: self.launch_requested.emit(self._params()))

        L.addWidget(self.btn_throw)
        L.addSpacing(2)

        # auto-aim — gold accent button
        self.btn_aim = QPushButton('\u25ce  AUTO-AIM')
        self.btn_aim.setFixedHeight(34)
        self.btn_aim.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_aim.setStyleSheet('''
            QPushButton{
                background:#2a1e00;color:#e8a020;border:1px solid #6a4800;
                border-radius:2px;font-family:"Courier New";font-size:10px;
                font-weight:bold;letter-spacing:2px;}
            QPushButton:hover{background:#3a2a00;border-color:#aa7000;color:#ffcc44;}
            QPushButton:pressed{background:#1a1200;}
        ''')
        self.btn_aim.clicked.connect(lambda: self.aim_requested.emit(self._params()))

        L.addWidget(self.btn_aim)

        # auto-aim result label
        self.lbl_aim = QLabel('')
        self.lbl_aim.setWordWrap(True)
        self.lbl_aim.setStyleSheet(
            'color:#7a6000;font-family:"Courier New";font-size:8px;'
            'padding:2px 0;line-height:140%;'
        )

        L.addWidget(self.lbl_aim)

        L.addSpacing(2)

        self.btn_compare = GhostButton('+ ADD COMPARISON')
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self._params()))

        L.addWidget(self.btn_compare)

        self.btn_clear = GhostButton('\u2715 CLEAR TRAJECTORIES')
        self.btn_clear.clicked.connect(self.clear_requested)

        L.addWidget(self.btn_clear)

        L.addSpacing(3)
        L.addWidget(_sep())

        # walls
        L.addWidget(_section('OBSTACLES'))

        self.btn_wall = GhostButton('\u25a0 PLACE WALL')
        self.btn_wall.setCheckable(True)
        self.btn_wall.clicked.connect(
            lambda checked: self.wall_mode_toggled.emit(checked))

        L.addWidget(self.btn_wall)

        self.btn_clrwall = GhostButton('\u2715 REMOVE ALL WALLS')
        self.btn_clrwall.clicked.connect(self.clear_walls_req)

        L.addWidget(self.btn_clrwall)

        L.addSpacing(3)
        L.addWidget(_sep())

        # stats
        L.addWidget(_section('LAST THROW'))

        self.lbl_stats = QLabel('Range: \u2014\nPeak:  \u2014\nTime:  \u2014')
        self.lbl_stats.setStyleSheet(
            'color:#6e2222;font-family:"Courier New";font-size:9px;'
            'line-height:150%;padding:2px 0;'
        )

        L.addWidget(self.lbl_stats)

        L.addSpacing(6)
        L.addStretch()

        self._on_obj(0)

    # ── internal slots ─────────────────────────────────────────────────────
    def _on_obj(self, idx):
        obj  = list(OBJECTS.values())[idx]
        name = list(OBJECTS.keys())[idx]

        self.lbl_info.setText(
            f'mass {obj["mass"]*1000:.1f}g  Cd {obj["cd"]}  e {obj["restitution"]}'
        )
        self._update_v0_display(name, obj['mass'])

    def _on_force(self, raw_n):
        idx  = self.combo.currentIndex()
        name = list(OBJECTS.keys())[idx]
        obj  = list(OBJECTS.values())[idx]

        self.val_f.setText(f'{raw_n} N')
        self._update_v0_display(name, obj['mass'])

    def _update_v0_display(self, obj_name, mass):
        f  = self.sld_f.value()

        v0 = force_to_v0(f, obj_name, mass)

        self.lbl_v0.setText(f'{v0:.1f} m/s')

    def _on_speed(self, raw):
        spd = raw / 100.0

        self.val_spd.setText(f'{spd:.2f}x')
        self.speed_changed.emit(spd)

    def _on_launch_coord(self):
        self.launch_pos_changed.emit(self.spn_lx.value(), self.spn_ly.value())

    def _on_target_coord(self):
        self.target_pos_changed.emit(self.spn_tx.value(), self.spn_ty.value())

    def _params(self):
        idx  = self.combo.currentIndex()
        name = list(OBJECTS.keys())[idx]
        obj  = OBJECTS[name]
        force = self.sld_f.value()
        v0    = force_to_v0(force, name, obj['mass'])

        return {
            'name': name, 'obj': obj,
            'v0': v0,   'force': force,
            'angle': self.sld_a.value(),
            'spin': self.sld_s.value(),
            'bounces': self.sld_b.value(),
            'launch_x': self.spn_lx.value(),
            'launch_y': self.spn_ly.value(),
            'target_x': self.spn_tx.value(),
            'target_y': self.spn_ty.value()
        }

    # ── called from canvas when user drags handles ─────────────────────────
    def sync_launch(self, wx, wy):
        self.spn_lx.blockSignals(True)
        self.spn_ly.blockSignals(True)
        self.spn_lx.setValue(round(wx, 2))
        self.spn_ly.setValue(round(wy, 2))
        self.spn_lx.blockSignals(False)
        self.spn_ly.blockSignals(False)

    def sync_target(self, wx, wy):
        self.spn_tx.blockSignals(True)
        self.spn_ty.blockSignals(True)
        self.spn_tx.setValue(round(wx, 2))
        self.spn_ty.setValue(round(wy, 2))
        self.spn_tx.blockSignals(False)
        self.spn_ty.blockSignals(False)

    def apply_aim_result(self, result):
        '''Called by BullseyeApp after auto_aim() returns a solution.'''
        if result is None:
            self.lbl_aim.setText('\u274c No solution found.\nTry moving points closer.')
            self.lbl_aim.setStyleSheet(
                'color:#882222;font-family:"Courier New";font-size:8px;'
                'padding:2px 0;line-height:140%;'
            )
            return

        # push found angle into slider
        ang = int(round(result['angle']))

        self.sld_a.setValue(max(0, min(90, ang)))

        # push found force into slider
        frc = int(round(result['force']))

        self.sld_f.setValue(max(1, min(200, frc)))
        # update v0 display
        idx  = self.combo.currentIndex()
        name = list(OBJECTS.keys())[idx]
        obj  = list(OBJECTS.values())[idx]

        self._update_v0_display(name, obj['mass'])

        miss = result['miss']
        ok   = miss < 0.15
        col  = '#448844' if ok else '#886600'
        sym  = '\u2713' if ok else '\u25b3'

        self.lbl_aim.setText(
            f'{sym} angle {result["angle"]:.1f}\u00b0  '
            f'force {result["force"]:.0f}N\n'
            f'   v\u2080 {result["v0"]:.1f} m/s  '
            f'miss {miss*100:.0f} cm'
        )
        self.lbl_aim.setStyleSheet(
            f'color:{col};font-family:"Courier New";font-size:8px;'
            'padding:2px 0;line-height:140%;'
        )

    def update_stats(self, pts, name):
        if not pts:
            return

        mx = max(p[0] for p in pts)
        my = max(p[1] for p in pts)

        tt = pts[-1][2]

        self.lbl_stats.setText(
            f'Object: {name}\nRange:  {mx:.1f} m\n'
            f'Peak:   {my:.1f} m\nTime:   {tt:.2f} s'
        )


# ── Title bar ──────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, win):
        super().__init__(win)

        self._win = win
        self._drag = None
        self.setFixedHeight(36)
        self.setStyleSheet('background:#090909;border-bottom:1px solid #250000;')

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 4, 0)
        lay.setSpacing(0)
        dot = QLabel('\u25ce')
        dot.setFixedWidth(20)
        dot.setStyleSheet('color:#771111;font-size:11px;padding-right:6px;')
        lay.addWidget(dot)
        title = QLabel('BULLSEYE  \u00b7  TACTICAL BALLISTICS')
        title.setStyleSheet(
            'color:#771111;font-family:"Courier New";font-size:10px;'
            'font-weight:bold;letter-spacing:3px;'
        )
        lay.addWidget(title)
        lay.addStretch()

        for sym, slot in [('\u2014', win.showMinimized),
                          ('\u25a1', self._toggle_max),
                          ('\u2715', win.close)]:
            b = QPushButton(sym)
            b.setFixedSize(28, 28)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setStyleSheet('''
                QPushButton{background:transparent;color:#3e3e3e;
                    border:none;font-size:11px;font-family:"Courier New";}
                QPushButton:hover{background:#220000;color:#dd2222;}
            ''')
            b.clicked.connect(slot)
            lay.addWidget(b)

    def _toggle_max(self):
        w = self._win

        w.showNormal() if w.isMaximized() else w.showMaximized()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, ev):
        if self._drag and ev.buttons() == Qt.MouseButton.LeftButton:
            self._win.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _ev):
        self._drag = None


# ── Main window ────────────────────────────────────────────────────────────────
class BullseyeApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Bullseye')
        self.setMinimumSize(920, 560)
        self.resize(1200, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setStyleSheet('QWidget{background:#0a0a0a;color:#cccccc;}')
        self._build()

    def _build(self):
        root = QWidget()

        self.setCentralWidget(root)

        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)
        vlay.addWidget(TitleBar(self))

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.panel = ControlPanel()
        self.panel.launch_requested.connect(self._launch)
        self.panel.compare_requested.connect(self._compare)
        self.panel.clear_requested.connect(self._clear)
        self.panel.wall_mode_toggled.connect(self._wall_mode)
        self.panel.clear_walls_req.connect(self._clear_walls)
        self.panel.speed_changed.connect(self._set_speed)
        self.panel.zoom_reset_req.connect(self._zoom_reset)
        self.panel.launch_pos_changed.connect(self._panel_launch_moved)
        self.panel.target_pos_changed.connect(self._panel_target_moved)
        self.panel.aim_requested.connect(self._auto_aim)

        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet('background:#280000;')

        self.canvas = BallisticsCanvas()
        self.canvas.wall_placed.connect(lambda: self.panel.btn_wall.setChecked(False))
        self.canvas.launch_moved.connect(self.panel.sync_launch)
        self.canvas.target_moved.connect(self.panel.sync_target)

        body.addWidget(self.panel)
        body.addWidget(div)
        body.addWidget(self.canvas)
        vlay.addLayout(body, 1)

        status = QLabel(
            '  scroll = zoom  |  MMB drag = pan  |  '
            'LMB drag handles = move points  |  '
            'PLACE WALL mode: LMB drag = draw, RMB = cancel'
        )
        status.setFixedHeight(18)
        status.setStyleSheet(
            'background:#080808;color:#272727;font-family:"Courier New";'
            'font-size:7px;border-top:1px solid #1a0000;padding-left:6px;'
        )
        vlay.addWidget(status)

    def _label_for(self, p, suffix=''):
        sp = f' spin{p["spin"]:+d}' if abs(p['spin']) > 50 else ''

        return (f'{p["name"]}  {p["force"]:.0f}N'
                f'  ({p["v0"]:.1f}m/s) {p["angle"]}deg{sp}{suffix}')

    def _run(self, p):
        return simulate(
            p['obj'], p['v0'], p['angle'], p['spin'],
            p['launch_x'], p['launch_y'],
            self.canvas.walls,
            self.canvas.world_w, self.canvas.world_h,
            p['bounces']
        )

    def _launch(self, p):
        self.canvas.clear_trajectories()

        pts = self._run(p)

        self.canvas.launch({'points': pts, 'color': p['obj']['color'],
                            'label': self._label_for(p)})
        self.panel.update_stats(pts, p['name'])

    def _compare(self, p):
        pts = self._run(p)

        self.canvas.launch({'points': pts, 'color': C_TRAJ_2,
                            'label': self._label_for(p, ' [B]')})

    def _auto_aim(self, p):
        self.panel.btn_aim.setText('\u25ce  COMPUTING...')
        self.panel.btn_aim.setEnabled(False)

        QApplication.processEvents()

        result = auto_aim(
            p['obj'], p['name'],
            p['target_x'], p['target_y'],
            p['launch_x'], p['launch_y'],
            p['spin'],
            self.canvas.walls,
            self.canvas.world_w, self.canvas.world_h,
            p['bounces']
        )

        self.panel.btn_aim.setText('\u25ce  AUTO-AIM')
        self.panel.btn_aim.setEnabled(True)
        self.panel.apply_aim_result(result)

        if result:
            # immediately draw the found trajectory
            self.canvas.clear_trajectories()
            self.canvas.launch({
                'points': result['pts'],
                'color': QColor('#ffcc44'),
                'label': (f'AUTO  {p["name"]}  '
                        f'{result["force"]:.0f}N '
                        f'{result["angle"]:.1f}deg'),
            })
            self.panel.update_stats(result['pts'], p['name'])

    def _clear(self):
        self.canvas.clear_trajectories()
        self.panel.lbl_stats.setText('Range: \u2014\nPeak:  \u2014\nTime:  \u2014')

    def _wall_mode(self, on):
        self.canvas.set_placing_wall(on)

    def _clear_walls(self):
        self.canvas.clear_walls()
        self.panel.btn_wall.setChecked(False)
        self.canvas.set_placing_wall(False)

    def _set_speed(self, spd):
        self.canvas.set_playback_speed(spd)

    def _zoom_reset(self):
        self.canvas.reset_zoom()

    def _panel_launch_moved(self, wx, wy):
        self.canvas.set_launch_pos(wx, wy)

    def _panel_target_moved(self, wx, wy):
        self.canvas.set_target_pos(wx, wy)


def main():
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName('Bullseye')
        QFontDatabase.addApplicationFont(
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
        win = BullseyeApp()
        win.show()
        sys.exit(app.exec())
    except Exception as exc:
        print(f'[BULLSEYE] startup error: {exc}', file=sys.stderr)
        print('Ensure PyQt6 is installed:  pip install PyQt6', file=sys.stderr)

        sys.exit(1)


if __name__ == '__main__':
    main()
